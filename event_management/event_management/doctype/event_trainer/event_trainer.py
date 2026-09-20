import frappe
from frappe.model.document import Document
from frappe.utils import getdate, formatdate, get_url, now, flt
from frappe.utils.pdf import get_pdf
import base64
import os


def _get_file_as_base64(file_url):
    """
    Resolve any Frappe file URL to base64.
    Uses Frappe's File doctype — works on both local and production.
    Falls back to direct filesystem path if File doctype lookup fails.
    """
    if not file_url:
        return ""
    try:
        file_doc = frappe.get_doc("File", {"file_url": file_url})
        content = file_doc.get_content()
        if isinstance(content, str):
            content = content.encode("utf-8")
        return base64.b64encode(content).decode("utf-8")
    except Exception:
        clean = file_url.lstrip("/")
        path = frappe.get_site_path(clean) if clean.startswith("private/") else frappe.get_site_path("public", clean)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        frappe.log_error(f"File not found: {file_url}", "PDF Asset Missing")
        return ""


MAX_TRAINERS_PER_EVENT = 3


class EventTrainer(Document):
    def validate(self):
        """Validation before saving"""
        if not self.trainer:
            frappe.throw("Please select a trainer")

        if self.training_start_date and self.training_end_date:
            if getdate(self.training_end_date) < getdate(self.training_start_date):
                frappe.throw("Training end date cannot be before start date")

        self.validate_trainer_count()

        self.calculate_total_amount()

    def validate_trainer_count(self):
        if not self.event_registration:
            return

        existing_count = frappe.db.count(
            "Event Trainer",
            {"event_registration": self.event_registration, "name": ["!=", self.name or ""]}
        )
        if existing_count >= MAX_TRAINERS_PER_EVENT:
            frappe.throw(
                f"This event already has {existing_count} trainer(s) assigned. "
                f"An event can have at most {MAX_TRAINERS_PER_EVENT} trainers."
            )
        
    def calculate_total_amount(self):
        """Calculate total payment based on rate type and duration"""
        if not self.trainer or not self.rate_type:
            return
            
        trainer = frappe.get_doc("Supplier", self.trainer)
        
        if self.rate_type == "Fixed Rate":
            self.total_amount = flt(self.agreed_rate or trainer.trainer_rate)
            
        elif self.rate_type == "Hourly Rate":
            hours = flt(self.number_of_hours or 8)
            self.total_amount = flt(self.agreed_rate or trainer.trainer_rate) * hours
            
        elif self.rate_type == "Daily Rate":
            days = flt(self.number_of_days or 1)
            self.total_amount = flt(self.agreed_rate or trainer.trainer_rate) * days
    
    def update_payment_status(self):
        """Check if trainer has been paid - FIXED DOUBLE COUNTING"""
        if not self.name:
            return
        
        paid_from_direct_payments = frappe.db.sql("""
            SELECT COALESCE(SUM(pe.paid_amount), 0)
            FROM `tabPayment Entry` pe
            WHERE pe.docstatus = 1
            AND pe.party_type = 'Supplier'
            AND pe.party = %s
            AND pe.event_trainer = %s
            AND NOT EXISTS (
                SELECT 1 FROM `tabPayment Entry Reference` per
                WHERE per.parent = pe.name
            )
        """, (self.trainer, self.name))[0][0] or 0
        
        paid_from_invoice_allocations = frappe.db.sql("""
            SELECT COALESCE(SUM(per.allocated_amount), 0)
            FROM `tabPayment Entry Reference` per
            INNER JOIN `tabPayment Entry` pe ON per.parent = pe.name
            INNER JOIN `tabPurchase Invoice` pi ON per.reference_name = pi.name
            WHERE pe.docstatus = 1
            AND pe.party_type = 'Supplier'
            AND pe.party = %s
            AND pi.event_trainer = %s
        """, (self.trainer, self.name))[0][0] or 0
        
        paid_amount = paid_from_direct_payments + paid_from_invoice_allocations
        
        self.db_set('paid_amount', paid_amount, update_modified=False)
        
        if paid_amount == 0:
            status = "Unpaid"
        elif paid_amount >= self.total_amount:
            status = "Paid"
        else:
            status = "Partially Paid"
            
        self.db_set('payment_status', status, update_modified=False)


def build_contract_template_args(trainer_doc, signature_base64=None):
    """Shared template context for the contract PDF, used both when emailing
    it and when rendering/regenerating it from the public signing page."""
    event = frappe.get_doc("Event Registration", trainer_doc.event_registration)
    trainer = frappe.get_doc("Supplier", trainer_doc.trainer)

    return {
        "trainer": trainer,
        "event": event,
        "trainer_assignment": trainer_doc,
        "event_date": f"{formatdate(event.start_date, 'dd MMM yyyy')} to {formatdate(event.end_date, 'dd MMM yyyy')}",
        "location": f"{event.event_venue}, {event.event_location}",
        "contract_date": formatdate(now(), 'dd MMM yyyy'),
        "total_amount": trainer_doc.total_amount,
        "rate_details": f"{trainer_doc.rate_type}: {frappe.format_value(trainer_doc.agreed_rate, 'Currency')}",
        "signature_base64": signature_base64,
        "signed_date": formatdate(trainer_doc.contract_signed_date, 'dd MMM yyyy') if trainer_doc.contract_signed_date else None
    }


@frappe.whitelist()
def send_trainer_contract(event_trainer_name):
    """Send contract to trainer via email, with a public link they can use
    to sign it digitally without needing a login."""
    if not event_trainer_name:
        frappe.throw("Event Trainer record not found")

    try:
        trainer_doc = frappe.get_doc("Event Trainer", event_trainer_name)

        trainer_email = trainer_doc.email
        if not trainer_email:
            frappe.throw(f"No email address found for trainer {trainer_doc.trainer_name}. Please update the Event Trainer record.")

        if not trainer_doc.signature_token:
            trainer_doc.db_set('signature_token', frappe.generate_hash(length=32), update_modified=False)
            trainer_doc.reload()

        template_args = build_contract_template_args(trainer_doc)
        signing_link = f"{get_url()}/trainer-sign?token={trainer_doc.signature_token}"
        template_args["signing_link"] = signing_link

        contract_pdf = _generate_trainer_contract_pdf(template_args)

        sender_email = None
        try:
            settings = frappe.get_doc("Event Management Setting")
            sender_email = settings.sender_email if hasattr(settings, 'sender_email') else None
        except Exception:
            pass

        email_args = {
            "recipients": [trainer_email],
            "subject": f"Training Contract - {template_args['event'].event_name}",
            "message": _get_contract_email_body(template_args),
            "attachments": [{
                "fname": f"Contract_{trainer_doc.trainer_name.replace(' ', '_')}_{event_trainer_name}.pdf",
                "fcontent": contract_pdf
            }],
            "now": True
        }

        if sender_email:
            email_args["sender"] = sender_email

        frappe.sendmail(**email_args)

        trainer_doc.db_set('contract_sent', 1, update_modified=True)
        trainer_doc.db_set('contract_sent_date', now(), update_modified=True)

        frappe.msgprint(f"✅ Contract sent successfully to {template_args['trainer'].supplier_name} ({trainer_email})")

        return {
            "success": True,
            "message": f"Contract sent to {trainer_email}",
            "trainer_name": template_args['trainer'].supplier_name,
            "email": trainer_email
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Trainer Contract Send Failed")
        frappe.throw(f"Failed to send contract: {str(e)}")


def _generate_trainer_contract_pdf(template_args):
    """Generate PDF contract for trainer - WITH DETAILED ERROR CATCHING"""
    error_details = []
    
    try:
        template_args.update({"is_pdf": True})
        error_details.append("✓ Set is_pdf flag")

        try:
            settings = frappe.get_doc("Event Management Setting")
            error_details.append("✓ Loaded Event Management Setting")
        except Exception as e:
            error_details.append(f"✗ Failed to load Event Management Setting: {str(e)}")
            raise

        # Production-safe: use File doctype instead of raw filesystem paths
        logo_base64 = _get_file_as_base64(settings.company_logo if hasattr(settings, 'company_logo') else None)
        error_details.append("✓ Loaded logo" if logo_base64 else "⚠ Logo not found or empty")

        signature_base64 = _get_file_as_base64(settings.company_signature if hasattr(settings, 'company_signature') else None)
        error_details.append("✓ Loaded signature" if signature_base64 else "⚠ Signature not found or empty")

        template_args.update({
            "logo_base64": logo_base64,
            "signature_base64": signature_base64
        })
        error_details.append("✓ Updated template_args with logo and signature")

        template_path = "event_management/templates/attachments/trainer_contract.html"
        error_details.append(f"→ Attempting to render template: {template_path}")

        try:
            full_template_path = frappe.get_app_path("event_management", "templates", "attachments", "trainer_contract.html")
            if os.path.exists(full_template_path):
                error_details.append(f"✓ Template file exists at: {full_template_path}")
            else:
                error_details.append(f"✗ Template file NOT FOUND at: {full_template_path}")
                raise FileNotFoundError(f"Template not found: {full_template_path}")
        except Exception as e:
            error_details.append(f"✗ Template path check failed: {str(e)}")
            raise

        try:
            contract_html = frappe.render_template(template_path, template_args)
            error_details.append("✓ Template rendered successfully")
        except Exception as e:
            error_details.append(f"✗ Template rendering failed: {str(e)}")
            raise

        try:
            pdf_content = get_pdf(contract_html)
            error_details.append("✓ PDF generated successfully")
            return pdf_content
        except Exception as e:
            error_details.append(f"✗ PDF generation failed: {str(e)}")
            raise

    except Exception as e:
        error_msg = "\n".join(error_details)
        error_msg += f"\n\n=== FINAL ERROR ===\n{str(e)}\n\n=== FULL TRACEBACK ===\n{frappe.get_traceback()}"
        frappe.log_error(error_msg, "Trainer Contract PDF Generation Failed - DETAILED")

        frappe.msgprint(
            f"<b>PDF Generation Error Details:</b><br><br>" + "<br>".join(error_details) + f"<br><br><b>Error:</b> {str(e)}",
            title="Template Rendering Failed",
            indicator="red"
        )

        # Fallback: plain HTML contract
        simple_html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; padding: 40px; color: #333; }}
                h1 {{ color: #1e3a8a; border-bottom: 3px solid #3b82f6; padding-bottom: 10px; }}
                .details {{ background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .detail-row {{ margin: 10px 0; padding: 8px 0; border-bottom: 1px solid #e2e8f0; }}
                .label {{ font-weight: bold; color: #1e3a8a; display: inline-block; width: 150px; }}
                .error-box {{ margin-top: 30px; padding: 15px; background: #fef2f2; border-left: 4px solid #dc2626; font-size: 9pt; }}
                .error-details {{ font-family: monospace; background: white; padding: 10px; margin-top: 10px; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <h1>Training Service Contract</h1>
            <div class="details">
                <div class="detail-row">
                    <span class="label">Trainer:</span> {template_args.get('trainer').supplier_name if hasattr(template_args.get('trainer', {}), 'supplier_name') else 'N/A'}
                </div>
                <div class="detail-row">
                    <span class="label">Event:</span> {template_args.get('event').event_name if hasattr(template_args.get('event', {}), 'event_name') else 'N/A'}
                </div>
                <div class="detail-row">
                    <span class="label">Date:</span> {template_args.get('event_date', 'N/A')}
                </div>
                <div class="detail-row">
                    <span class="label">Location:</span> {template_args.get('location', 'N/A')}
                </div>
                <div class="detail-row">
                    <span class="label">Payment Type:</span> {template_args.get('rate_details', 'N/A')}
                </div>
                <div class="detail-row">
                    <span class="label">Total Amount:</span> <strong>{frappe.format_value(template_args.get('total_amount', 0), 'Currency')}</strong>
                </div>
            </div>
            <div class="error-box">
                <strong>⚠️ Template Rendering Error</strong>
                <p>This is a fallback contract. The main template failed to render.</p>
                <div class="error-details">
                    {'<br>'.join(error_details)}
                    <br><br><strong>Error:</strong> {str(e)}
                </div>
            </div>
        </body>
        </html>
        """
        return get_pdf(simple_html)


def _get_contract_email_body(template_args):
    """Generate email body for contract"""
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #20639B;">Training Contract</h2>
        <p>Dear {template_args['trainer'].supplier_name},</p>
        <p>Please find attached your training contract for the following event:</p>
        <div style="background-color: #f5f5f5; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 5px 0;"><strong>Event:</strong> {template_args['event'].event_name}</p>
            <p style="margin: 5px 0;"><strong>Date:</strong> {template_args['event_date']}</p>
            <p style="margin: 5px 0;"><strong>Location:</strong> {template_args['location']}</p>
            <p style="margin: 5px 0;"><strong>Payment:</strong> {template_args['rate_details']}</p>
            <p style="margin: 5px 0;"><strong>Total Amount:</strong> {frappe.format_value(template_args['total_amount'], 'Currency')}</p>
        </div>
        <p>Please review the attached contract, then sign it digitally using the button below - no printing, scanning, or account needed.</p>
        <div style="text-align: center; margin: 25px 0;">
            <a href="{template_args.get('signing_link', '#')}" style="background-color: #20639B; color: white; padding: 12px 28px; border-radius: 5px; text-decoration: none; font-weight: bold; display: inline-block;">
                Sign Contract Online
            </a>
        </div>
        <p style="font-size: 12px; color: #888;">If the button doesn't work, copy and paste this link into your browser:<br>{template_args.get('signing_link', '')}</p>
        <p>Once signed, you can send your invoice to our accounts department.</p>
        <p>If you have any questions, please don't hesitate to contact us.</p>
        <p>Best regards,<br>Event Management Team</p>
    </div>
    """


@frappe.whitelist(allow_guest=True)
def get_contract_for_signing(token):
    """Public (no login) lookup used by the /trainer-sign page to show the
    trainer their contract details before they sign."""
    if not token:
        return {"success": False, "message": "Invalid signing link"}

    trainer_doc = frappe.db.get_value("Event Trainer", {"signature_token": token}, "name")
    if not trainer_doc:
        return {"success": False, "message": "Invalid or expired signing link"}

    trainer_doc = frappe.get_doc("Event Trainer", trainer_doc)

    if trainer_doc.contract_signed:
        return {
            "success": True,
            "already_signed": True,
            "message": f"This contract was already signed on {formatdate(trainer_doc.contract_signed_date, 'dd MMM yyyy')}.",
            "trainer_name": trainer_doc.trainer_name,
            "event_name": trainer_doc.event_name
        }

    args = build_contract_template_args(trainer_doc)

    return {
        "success": True,
        "already_signed": False,
        "trainer_name": args["trainer"].supplier_name,
        "event_name": args["event"].event_name,
        "event_date": args["event_date"],
        "location": args["location"],
        "rate_details": args["rate_details"],
        "total_amount": frappe.format_value(args["total_amount"], "Currency")
    }


@frappe.whitelist(allow_guest=True)
def submit_signed_contract(token, signature_data):
    """Public (no login) endpoint the /trainer-sign page posts the drawn
    signature to. Regenerates the contract PDF with the signature embedded,
    stores it against the Event Trainer record, and marks it signed."""
    if not token or not signature_data:
        return {"success": False, "message": "Missing signature"}

    trainer_name = frappe.db.get_value("Event Trainer", {"signature_token": token}, "name")
    if not trainer_name:
        return {"success": False, "message": "Invalid or expired signing link"}

    trainer_doc = frappe.get_doc("Event Trainer", trainer_name)

    if trainer_doc.contract_signed:
        return {"success": False, "message": "This contract has already been signed."}

    try:
        signature_base64 = signature_data.split(",")[-1]  # strip the data:image/png;base64, prefix

        trainer_doc.db_set("contract_signed", 1, update_modified=False)
        trainer_doc.db_set("contract_signed_date", now(), update_modified=False)
        trainer_doc.reload()

        template_args = build_contract_template_args(trainer_doc, signature_base64=signature_base64)
        signed_pdf = _generate_trainer_contract_pdf(template_args)

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": f"Signed_Contract_{trainer_doc.name}.pdf",
            "attached_to_doctype": "Event Trainer",
            "attached_to_name": trainer_doc.name,
            "attached_to_field": "signed_contract",
            "content": signed_pdf,
            "is_private": 1
        })
        file_doc.insert(ignore_permissions=True)
        trainer_doc.db_set("signed_contract", file_doc.file_url, update_modified=False)

        frappe.db.commit()

        admin_email = frappe.db.get_single_value("Event Management Setting", "admin_email") or "info@tagrit.com"
        frappe.sendmail(
            recipients=[admin_email, trainer_doc.email],
            subject=f"Contract Signed - {trainer_doc.trainer_name} - {trainer_doc.event_name}",
            message=f"""
            <div style="font-family: Arial, sans-serif;">
                <h2 style="color: #4CAF50;">✓ Contract Signed</h2>
                <p><strong>{trainer_doc.trainer_name}</strong> has digitally signed the training contract for
                <strong>{trainer_doc.event_name}</strong> on {formatdate(now(), 'dd MMM yyyy')}.</p>
                <p>The signed contract is attached to the Event Trainer record ({trainer_doc.name}) in the system.</p>
            </div>
            """,
            attachments=[{"fname": f"Signed_Contract_{trainer_doc.name}.pdf", "fcontent": signed_pdf}],
            now=True
        )

        return {"success": True, "message": "Thank you! Your signed contract has been received."}

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Trainer Contract Signing Failed")
        return {"success": False, "message": "Something went wrong saving your signature. Please try again or contact us."}


@frappe.whitelist()
def get_trainer_payment_summary(event_trainer_name):
    """Get payment summary for a specific trainer assignment - FIXED DOUBLE COUNTING"""
    trainer_doc = frappe.get_doc("Event Trainer", event_trainer_name)
    
    payments = frappe.get_all(
        "Payment Entry",
        filters={
            "docstatus": 1,
            "party_type": "Supplier",
            "party": trainer_doc.trainer,
            "event_trainer": event_trainer_name
        },
        fields=["name", "posting_date", "paid_amount", "reference_no", "remarks"],
        order_by="posting_date desc"
    )
    
    invoices = frappe.get_all(
        "Purchase Invoice",
        filters={
            "docstatus": 1,
            "supplier": trainer_doc.trainer,
            "event_trainer": event_trainer_name
        },
        fields=["name", "posting_date", "grand_total", "outstanding_amount", "status"],
        order_by="posting_date desc"
    )
    
    direct_payments = frappe.db.sql("""
        SELECT COALESCE(SUM(pe.paid_amount), 0)
        FROM `tabPayment Entry` pe
        WHERE pe.docstatus = 1
        AND pe.party_type = 'Supplier'
        AND pe.party = %s
        AND pe.event_trainer = %s
        AND NOT EXISTS (
            SELECT 1 FROM `tabPayment Entry Reference` per
            WHERE per.parent = pe.name
        )
    """, (trainer_doc.trainer, event_trainer_name))[0][0] or 0
    
    allocated_from_invoices = frappe.db.sql("""
        SELECT COALESCE(SUM(per.allocated_amount), 0)
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe ON per.parent = pe.name
        INNER JOIN `tabPurchase Invoice` pi ON per.reference_name = pi.name
        WHERE pe.docstatus = 1
        AND pe.party_type = 'Supplier'
        AND pe.party = %s
        AND pi.event_trainer = %s
    """, (trainer_doc.trainer, event_trainer_name))[0][0] or 0
    
    total_paid = direct_payments + allocated_from_invoices
    total_invoiced = sum([i.grand_total for i in invoices])
    total_outstanding = sum([i.outstanding_amount for i in invoices])
    
    return {
        "trainer_name": trainer_doc.trainer_name,
        "event_name": trainer_doc.event_name,
        "total_amount": trainer_doc.total_amount,
        "total_paid": total_paid,
        "total_invoiced": total_invoiced,
        "total_outstanding": total_outstanding,
        "balance": trainer_doc.total_amount - total_paid,
        "payment_status": trainer_doc.payment_status,
        "payments": payments,
        "invoices": invoices
    }


@frappe.whitelist()
def get_available_trainers(area_of_expertise=None):
    """Get list of available trainers (suppliers marked as trainers)"""
    filters = {"is_trainer": 1}
    
    if area_of_expertise:
        filters["area_of_expertise"] = ["like", f"%{area_of_expertise}%"]
    
    trainers = frappe.get_all(
        "Supplier",
        filters=filters,
        fields=["name", "supplier_name", "area_of_expertise", "trainer_rate_type", "trainer_rate", "email_id"]
    )
    
    return trainers


@frappe.whitelist()
def create_trainer_payment_entry(event_trainer_name, amount, reference_no=None, remarks=None, link_to_invoice=None, auto_submit=False):
    """Helper to create payment entry for trainer"""
    trainer_doc = frappe.get_doc("Event Trainer", event_trainer_name)
    
    company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
    company_currency = frappe.get_cached_value("Company", company, "default_currency")
    mode_of_payment = frappe.db.get_value("Mode of Payment", {"enabled": 1}, "name") or "Cash"
    mode_of_payment_doc = frappe.get_doc("Mode of Payment", mode_of_payment)
    payment_account = None
    
    for account in mode_of_payment_doc.accounts:
        if account.company == company:
            payment_account = account.default_account
            break
    
    if not payment_account:
        payment_account = frappe.get_cached_value("Company", company, "default_cash_account")
    
    if not payment_account:
        frappe.throw("Please set up a default payment account in Mode of Payment or Company settings")
    
    payable_account = frappe.get_cached_value("Company", company, "default_payable_account")
    
    payment = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Pay",
        "party_type": "Supplier",
        "party": trainer_doc.trainer,
        "company": company,
        "posting_date": now(),
        "paid_from": payment_account,
        "paid_to": payable_account,
        "paid_amount": flt(amount),
        "received_amount": flt(amount),
        "source_exchange_rate": 1,
        "target_exchange_rate": 1,
        "reference_no": reference_no or trainer_doc.name,
        "reference_date": now(),
        "remarks": remarks or f"Payment for {trainer_doc.event_name}",
        "mode_of_payment": mode_of_payment,
        "event_registration": trainer_doc.event_registration,
        "event_trainer": event_trainer_name
    })
    
    if link_to_invoice:
        invoice = frappe.get_doc("Purchase Invoice", link_to_invoice)
        payment.append("references", {
            "reference_doctype": "Purchase Invoice",
            "reference_name": link_to_invoice,
            "total_amount": invoice.grand_total,
            "outstanding_amount": invoice.outstanding_amount,
            "allocated_amount": min(flt(amount), invoice.outstanding_amount)
        })
    
    payment.insert()
    
    if auto_submit:
        payment.submit()
    
    return payment.name


@frappe.whitelist()
def make_payment_entry_from_invoice(purchase_invoice_name):
    """Create payment entry from purchase invoice with proper linking"""
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    
    payment_entry = get_payment_entry("Purchase Invoice", purchase_invoice_name)
    
    invoice = frappe.get_doc("Purchase Invoice", purchase_invoice_name)
    if hasattr(invoice, 'event_trainer') and invoice.event_trainer:
        payment_entry.event_trainer = invoice.event_trainer
    
    return payment_entry




@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None):
    """Create Purchase Invoice from Event Trainer"""
    from frappe.model.mapper import get_mapped_doc
    
    def set_missing_values(source, target):
        target.event_registration = source.event_registration
        target.event_trainer = source.name
        
        item_code = "Training Service"
        ensure_training_service_item_exists(item_code)
        
        target.append("items", {
            "item_code": item_code,
            "item_name": item_code,
            "description": f"Training services for {source.event_name}",
            "qty": 1,
            "rate": source.total_amount,
            "amount": source.total_amount,
            "uom": "Nos"
        })
    
    doclist = get_mapped_doc(
        "Event Trainer",
        source_name,
        {
            "Event Trainer": {
                "doctype": "Purchase Invoice",
                "field_map": {
                    "trainer": "supplier",
                    "trainer_name": "supplier_name"
                }
            }
        },
        target_doc,
        set_missing_values
    )
    
    return doclist


def ensure_training_service_item_exists(item_code):
    """Ensure Training Service item exists, create if it doesn't"""
    if frappe.db.exists("Item", item_code):
        return
    
    try:
        item_group = None
        
        if frappe.db.exists("Item Group", "Services"):
            item_group = "Services"
        elif frappe.db.exists("Item Group", "Service"):
            item_group = "Service"
        else:
            item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
        
        if not item_group:
            frappe.throw("No valid Item Group found. Please create an Item Group first.")
        
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_code,
            "item_group": item_group,
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "is_purchase_item": 1,
            "is_sales_item": 0,
            "description": "Training service for event management",
            "maintain_stock": 0
        })
        
        item.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.msgprint(f"Item '{item_code}' created automatically", alert=True, indicator="green")
        
    except Exception as e:
        frappe.log_error(f"Error creating Training Service item: {str(e)}", "Training Service Item Creation")
        frappe.throw(f"Could not create '{item_code}' item. Error: {str(e)}")


def update_trainer_payment_on_payment_submit(doc, method):
    """Update Event Trainer payment status when payment is submitted"""
    if doc.party_type == "Supplier" and hasattr(doc, 'event_trainer') and doc.event_trainer:
        try:
            frappe.enqueue(
                method='event_management.event_management.doctype.event_trainer.event_trainer._update_trainer_payment_status',
                queue='short',
                timeout=300,
                event_trainer=doc.event_trainer,
                enqueue_after_commit=True
            )
        except Exception as e:
            frappe.log_error(f"Error enqueuing trainer payment update: {str(e)}", "Payment Status Update")


def update_trainer_payment_on_payment_cancel(doc, method):
    """Update Event Trainer payment status when payment is cancelled"""
    if doc.party_type == "Supplier" and hasattr(doc, 'event_trainer') and doc.event_trainer:
        try:
            frappe.enqueue(
                method='event_management.event_management.doctype.event_trainer.event_trainer._update_trainer_payment_status',
                queue='short',
                timeout=300,
                event_trainer=doc.event_trainer,
                enqueue_after_commit=True
            )
        except Exception as e:
            frappe.log_error(f"Error enqueuing trainer payment update: {str(e)}", "Payment Status Update")


def update_trainer_payment_on_invoice_submit(doc, method):
    """Update Event Trainer when invoice is submitted"""
    if hasattr(doc, 'event_trainer') and doc.event_trainer:
        try:
            frappe.enqueue(
                method='event_management.event_management.doctype.event_trainer.event_trainer._update_trainer_payment_status',
                queue='short',
                timeout=300,
                event_trainer=doc.event_trainer,
                enqueue_after_commit=True
            )
        except Exception as e:
            frappe.log_error(f"Error enqueuing trainer on invoice submit: {str(e)}", "Invoice Submit Hook")


def update_trainer_payment_on_invoice_cancel(doc, method):
    """Update Event Trainer when invoice is cancelled"""
    if hasattr(doc, 'event_trainer') and doc.event_trainer:
        try:
            frappe.enqueue(
                method='event_management.event_management.doctype.event_trainer.event_trainer._update_trainer_payment_status',
                queue='short',
                timeout=300,
                event_trainer=doc.event_trainer,
                enqueue_after_commit=True
            )
        except Exception as e:
            frappe.log_error(f"Error enqueuing trainer on invoice cancel: {str(e)}", "Invoice Cancel Hook")


def _update_trainer_payment_status(event_trainer):
    """Background task to update payment status"""
    try:
        if frappe.session.user == 'Guest':
            frappe.set_user("Administrator")
        
        trainer_doc = frappe.get_doc("Event Trainer", event_trainer)
        trainer_doc.update_payment_status()
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(
            f"Error updating trainer payment status in background: {str(e)}\n{frappe.get_traceback()}",
            "Background Payment Status Update"
        )


@frappe.whitelist()
def get_trainers_with_fresh_status(event_registration):
    """Get trainers with freshly calculated payment status"""
    trainers = frappe.get_all(
        "Event Trainer",
        filters={"event_registration": event_registration},
        fields=["name", "trainer", "trainer_name", "email", "mobile_no", "rate_type",
                "total_amount", "contract_sent"]
    )
    
    for trainer in trainers:
        trainer_doc = frappe.get_doc("Event Trainer", trainer.name)
        trainer_doc.update_payment_status()
        trainer_doc.reload()
        trainer["paid_amount"] = trainer_doc.paid_amount or 0
        trainer["payment_status"] = trainer_doc.payment_status
    
    return trainers


@frappe.whitelist()
def force_update_payment_status(event_trainer_name):
    """Force update payment status for a specific trainer"""
    trainer_doc = frappe.get_doc("Event Trainer", event_trainer_name)
    trainer_doc.update_payment_status()
    trainer_doc.reload()

    return {
        "paid_amount": trainer_doc.paid_amount or 0,
        "payment_status": trainer_doc.payment_status,
        "total_amount": trainer_doc.total_amount
    }


@frappe.whitelist()
def get_trainer_profile(trainer):
    """Aggregate everything the Trainer Profile page needs: contact/CV info,
    KPIs, every event they've trained, and a running payment statement
    (invoices owed + payments made, in date order) across all events -
    the trainer's aging/statement view."""
    if not frappe.db.exists("Supplier", trainer):
        frappe.throw("Trainer not found")

    supplier = frappe.get_doc("Supplier", trainer)

    assignments = frappe.get_all(
        "Event Trainer",
        filters={"trainer": trainer},
        fields=[
            "name", "event_registration", "event_name", "event_start_date", "event_end_date",
            "event_venue", "event_location", "rate_type", "agreed_rate", "total_amount",
            "paid_amount", "payment_status", "contract_sent", "contract_signed", "contract_signed_date"
        ],
        order_by="event_start_date desc"
    )

    for assignment in assignments:
        # Keep stored payment status fresh (same as get_trainers_with_fresh_status)
        assignment_doc = frappe.get_doc("Event Trainer", assignment["name"])
        assignment_doc.update_payment_status()
        assignment_doc.reload()
        assignment["paid_amount"] = assignment_doc.paid_amount or 0
        assignment["payment_status"] = assignment_doc.payment_status

    total_events = len(assignments)
    total_earned = sum(flt(a["total_amount"]) for a in assignments)
    total_paid = sum(flt(a["paid_amount"]) for a in assignments)
    total_outstanding = total_earned - total_paid

    invoices = frappe.get_all(
        "Purchase Invoice",
        filters={"supplier": trainer, "docstatus": 1},
        fields=["name", "posting_date", "grand_total", "event_trainer"],
        order_by="posting_date asc"
    )

    payments = frappe.get_all(
        "Payment Entry",
        filters={"party_type": "Supplier", "party": trainer, "docstatus": 1},
        fields=["name", "posting_date", "paid_amount", "event_trainer", "remarks"],
        order_by="posting_date asc"
    )

    assignment_event_names = {a["name"]: a["event_name"] for a in assignments}

    ledger = []
    for inv in invoices:
        ledger.append({
            "date": inv.posting_date,
            "type": "Invoice",
            "reference": inv.name,
            "description": assignment_event_names.get(inv.event_trainer, "Training Invoice"),
            "amount": flt(inv.grand_total)
        })
    for pay in payments:
        ledger.append({
            "date": pay.posting_date,
            "type": "Payment",
            "reference": pay.name,
            "description": assignment_event_names.get(pay.event_trainer) or pay.remarks or "Payment",
            "amount": -flt(pay.paid_amount)
        })

    ledger.sort(key=lambda row: row["date"])

    running_balance = 0
    for row in ledger:
        running_balance += row["amount"]
        row["balance"] = running_balance
        row["date"] = formatdate(row["date"])

    documents = [
        {"document_name": row.document_name, "file": row.file, "description": row.description}
        for row in (supplier.get("trainer_documents") or [])
    ]

    return {
        "trainer": {
            "name": supplier.name,
            "supplier_name": supplier.supplier_name,
            "email": getattr(supplier, "email_id", None),
            "mobile_no": getattr(supplier, "mobile_no", None),
            "area_of_expertise": getattr(supplier, "area_of_expertise", None),
            "rate_type": getattr(supplier, "trainer_rate_type", None),
            "rate": getattr(supplier, "trainer_rate", None),
            "cv_attachment": getattr(supplier, "cv_attachment", None)
        },
        "kpis": {
            "total_events": total_events,
            "total_earned": total_earned,
            "total_paid": total_paid,
            "total_outstanding": total_outstanding
        },
        "assignments": assignments,
        "ledger": ledger,
        "documents": documents
    }