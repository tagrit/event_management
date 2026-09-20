import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days, now, get_datetime, nowdate, formatdate, get_url, validate_email_address, get_time, flt
from frappe.utils.pdf import get_pdf
import hashlib
import json
import base64
from frappe import _
import os
import re
from event_management.event_management.schedule_utils import schedule_is_due


def get_cc_email_list(settings):
    """Combine the single 'CC Email' field with the multi-address 'CC Emails (Others)'
    field on Event Management Setting into one deduped list of valid addresses."""
    raw_addresses = []
    if settings.cc_email:
        raw_addresses.append(settings.cc_email)
    if settings.cc_emails:
        raw_addresses.extend(re.split(r"[,;\n]+", settings.cc_emails))

    seen = set()
    cc_list = []
    for address in raw_addresses:
        address = address.strip()
        if not address or address.lower() in seen:
            continue
        try:
            validate_email_address(address, throw=True)
        except Exception:
            frappe.log_error(f"Skipping invalid CC address: {address}", "Event Management CC Email")
            continue
        seen.add(address.lower())
        cc_list.append(address)

    return cc_list


class EventRegistration(Document):
    def validate(self):
        """This runs before saving the document"""
        if len(self.delegates) != self.number_of_delegates:
            frappe.throw(f"You said {self.number_of_delegates} delegates but added {len(self.delegates)} to the list.")

        if self.start_date and self.end_date:
            if get_datetime(self.end_date) < get_datetime(self.start_date):
                frappe.throw("End date cannot be before start date!")

        self.revenue = self.number_of_delegates * self.charges_per_delegate

        self.generate_event_identifier()

        self.sync_delegate_confirmations()

    def before_update_after_submit(self):
        """Frappe skips validate() when resaving an already-submitted document
        (it runs this hook instead), so the delegate-confirmation sync has to be
        repeated here too - otherwise confirming a delegate on a submitted event
        (the normal case) silently never sets confirmed_by/all_confirmed."""
        self.sync_delegate_confirmations()

    def sync_delegate_confirmations(self):
        for delegate in self.delegates:
            if not delegate.confirmation_token:
                delegate.confirmation_token = self.generate_confirmation_token(delegate.email)

            # Track who actually confirmed each delegate: the logged-in user for a
            # manual desk confirmation, or "Guest" when the delegate self-confirmed
            # via the emailed link (that endpoint runs with allow_guest=True).
            if delegate.confirmed and not delegate.confirmed_by:
                delegate.confirmed_by = frappe.session.user
            if delegate.confirmed and not delegate.confirmation_date:
                delegate.confirmation_date = now()
            elif not delegate.confirmed:
                delegate.confirmed_by = None

        self.update_all_confirmed_status()

    def before_insert(self):
        self.set_default_attachments()

    def set_default_attachments(self):
        default_docs = [
            {"name": "Program Outline", "desc": "Detailed schedule of the training sessions."},
            {"name": "Seminar Details", "desc": "Overview of topics, speakers, and objectives."},
            {"name": "Accommodations & Amenities", "desc": "Information regarding stay and local facilities."}
        ]

        if not self.get("welcome_attachments"):
            for doc in default_docs:
                self.append("welcome_attachments", {
                    "document_name": doc["name"],
                    "description": doc["desc"]
                })
        
    def update_all_confirmed_status(self):
        if not self.delegates:
            self.all_confirmed = 0
            return
        all_confirmed = all(d.confirmed for d in self.delegates)
        self.all_confirmed = 1 if all_confirmed else 0
        
    def on_update(self):
        old_status = self.all_confirmed
        all_confirmed = all(d.confirmed for d in self.delegates) if self.delegates else False
        new_status = 1 if all_confirmed else 0
        
        if old_status != new_status:
            frappe.db.set_value("Event Registration", self.name, "all_confirmed", new_status, update_modified=False)

    def autoname(self):
        def get_code(text):
            if not text: return "NA"
            return re.sub(r'[^a-zA-Z0-9]', '', text)[:3].upper()

        org = get_code(self.organization_name)
        loc = get_code(self.event_location)
        dt = getdate(self.start_date).strftime('%y%m%d') if self.start_date else "000000"
        base_id = f"{org}-{loc}-{dt}"

        existing_count = frappe.db.count("Event Registration", {
            "name": ["like", f"{base_id}-%"]
        })
        suffix = str(existing_count + 1).zfill(2)
        self.name = f"{base_id}-{suffix}"
        
    def generate_event_identifier(self):
        if all([self.organization_name, self.event_location, self.start_date]):
            def get_code(text):
                return re.sub(r'[^a-zA-Z0-9]', '', text)[:3].upper()

            org = get_code(self.organization_name)
            loc = get_code(self.event_location)
            dt = getdate(self.start_date).strftime('%y%m%d')
            base_id = f"{org}-{loc}-{dt}"

            if not self.event_identifier or not self.event_identifier.startswith(base_id):
                existing_count = frappe.db.count("Event Registration", {
                    "event_identifier": ["like", f"{base_id}%"],
                    "name": ["!=", self.name]
                })
                suffix = str(existing_count + 1).zfill(2)
                self.event_identifier = f"{base_id}-{suffix}"
                
    def generate_confirmation_token(self, email):
        token_string = f"{self.name}-{email}-{now()}"
        return hashlib.sha256(token_string.encode()).hexdigest()[:32]

    def update_all_confirmed_status(self):
        if not self.delegates:
            self.all_confirmed = 0
            return
        all_confirmed = all(d.confirmed for d in self.delegates)
        self.all_confirmed = 1 if all_confirmed else 0

    def on_submit(self):
        if not self.amended_from:
            self.send_invitations_to_all_delegates()
        else:
            frappe.msgprint(_("This is an amended record. Invitations were not re-sent automatically."))

    def _get_attendance_email_template(self):
        template_name = "Event Registration Confirmation"
        if frappe.db.exists("Email Template", template_name):
            return {"type": "ui", "name": template_name}
        return {
            "type": "file",
            "path": "event_management/templates/emails/registration_confirmation.html"
        }


    def send_invitations_to_all_delegates(self):
        if not self.delegates:
            frappe.msgprint("No delegates found!")
            return

        template_info = self._get_attendance_email_template()
        first_delegate = self.delegates[0]  # ← Get only the first delegate

        try:
            self._send_single_invitation(first_delegate, template_info)
            self.db_set("invitation_sent", 1)
            frappe.msgprint(f"✅ Invitation sent to {first_delegate.first_name} {first_delegate.last_name}!")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Invitation failed for {first_delegate.email}")

    def _send_single_invitation(self, delegate, template_info):
        base_url = get_url()
        confirmation_link = (
            f"{base_url}/api/method/event_management.event_management.doctype."
            f"event_registration.event_registration.confirm_delegate?token={delegate.confirmation_token}"
        )

        settings = frappe.get_doc("Event Management Setting")
        cc = get_cc_email_list(settings)

        template_args = {
            "event": self,
            "delegate": {
                "full_name": f"{delegate.first_name} {delegate.last_name}",
                "first_name": f"{delegate.first_name}",
                "last_name" : f"{delegate.last_name}",
                "email": delegate.email,
            },
            "event_date": f"{formatdate(self.start_date, 'dd MMM yyyy')} to {formatdate(self.end_date, 'dd MMM yyyy')}",
            "location": f"{self.event_venue}, {self.event_location}",
            "confirmation_link": confirmation_link,
            "cpd_calendar_link": settings.calendar_link or "https://tagrit.com/calendars",
        }

        attachments = self._generate_pdf_attachments(template_args)

        if template_info["type"] == "ui":
            email_template = frappe.get_doc("Email Template", template_info["name"])
            subject = frappe.render_template(email_template.subject, template_args)
            message = frappe.render_template(email_template.response, template_args)
            frappe.sendmail(
                recipients=[delegate.email],
                cc=cc,
                expose_recipients="header",  # ← forces CC to show in email header
                subject=subject,
                message=message,
                attachments=attachments
            )
        else:
            message = frappe.render_template(
                template_info["path"],
                template_args
            )
            frappe.sendmail(
                recipients=[delegate.email],
                cc=cc,
                expose_recipients="header",  # ← forces CC to show in email header
                subject=f"{self.event_name} Registration Confirmation",
                message=message,
                attachments=attachments
            )
            

         
    def _generate_pdf_attachments(self, template_args):
        attachments = []
        try:
            template_args.update({"is_pdf": True})
            settings = frappe.get_doc("Event Management Setting")
 
            def get_file_as_base64(file_url):
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
                    if clean.startswith("private/"):
                        path = frappe.get_site_path(clean)
                    else:
                        path = frappe.get_site_path("public", clean)
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            return base64.b64encode(f.read()).decode("utf-8")
                    frappe.log_error(f"File not found: {file_url}", "PDF Asset Missing")
                    return ""
 
            template_args.update({
                "logo_base64":      get_file_as_base64(settings.company_logo),
                "signature_base64": get_file_as_base64(settings.company_signature),
                # ── NEW: stamp loaded from Event Management Setting ──────────
                "stamp_base64":     get_file_as_base64(getattr(settings, "company_stamp", None)),
            })
 
            invitation_html = frappe.render_template(
                "event_management/templates/attachments/training_invitation_letter.html",
                template_args
            )
            attachments.append({
                "fname": f"Invitation_{self.name}.pdf",
                "fcontent": get_pdf(invitation_html)
            })
 
            invoice_html = frappe.render_template(
                "event_management/templates/attachments/proforma_invoice.html",
                template_args
            )
            attachments.append({
                "fname": f"Proforma_{self.name}.pdf",
                "fcontent": get_pdf(invoice_html)
            })
 
        except Exception:
            frappe.log_error(frappe.get_traceback(), "PDF Attachment Generation Failed")
 
        return attachments
            
@frappe.whitelist(allow_guest=True)
def confirm_delegate(token):
    if not token:
        return {"success": False, "message": "Invalid confirmation link"}

    delegates = frappe.get_all(
        "Event Delegate",
        filters={"confirmation_token": token},
        fields=["name", "parent", "first_name", "last_name", "email", "confirmed"],
    )

    if not delegates:
        return {"success": False, "message": "Invalid or expired confirmation link"}

    delegate = delegates[0]

    if delegate.confirmed:
        return {
            "success": True,
            "already_confirmed": True,
            "message": f"Thank you {delegate.first_name}! Your attendance was already confirmed.",
        }

    try:
        frappe.db.set_value(
            "Event Delegate",
            delegate.name,
            {"confirmed": 1, "confirmation_date": now()},
        )

        event = frappe.get_doc("Event Registration", delegate.parent)
        event.update_all_confirmed_status()
        event.save()

        frappe.sendmail(
            recipients=[delegate.email],
            subject=f"Confirmation Received - {event.event_name}",
            message=f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #4CAF50;">✓ Attendance Confirmed!</h2>
                <p>Dear {delegate.first_name} {delegate.last_name},</p>
                <p>Thank you for confirming your attendance at <strong>{event.event_name}</strong>.</p>
                <div style="background-color: #e8f5e9; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Your attendance is confirmed for:</strong></p>
                    <p style="margin: 10px 0 0 0;">{event.start_date} to {event.end_date}</p>
                    <p style="margin: 5px 0 0 0;">{event.event_venue}, {event.event_location}</p>
                </div>
                <p>You will receive additional information about the event closer to the date.</p>
                <p>Best regards,<br>Event Management Team</p>
            </div>
            """,
        )

        frappe.db.commit()

        return {
            "success": True,
            "message": f"Thank you {delegate.first_name}! Your attendance has been confirmed.",
            "event_name": event.event_name,
            "event_date": f"{event.start_date} to {event.end_date}",
        }

    except Exception as e:
        frappe.log_error(f"Confirmation error: {str(e)}")
        return {
            "success": False,
            "message": "An error occurred. Please contact the event organizer.",
        }


@frappe.whitelist()
def get_confirmation_summary(event_name):
    event = frappe.get_doc("Event Registration", event_name)

    total = len(event.delegates)
    confirmed = sum(1 for d in event.delegates if d.confirmed)
    pending = total - confirmed

    delegates_list = []
    for d in event.delegates:
        delegates_list.append(
            {
                "name": f"{d.first_name} {d.last_name}",
                "email": d.email,
                "confirmed": d.confirmed,
                "confirmation_date": d.confirmation_date,
            }
        )

    return {
        "total": total,
        "confirmed": confirmed,
        "pending": pending,
        "percentage": round((confirmed / total * 100) if total > 0 else 0, 1),
        "delegates": delegates_list,
    }


def _get_attendance_email_template():
    if frappe.db.exists("Email Template", "Event Attendance Confirmation"):
        return {"type": "ui", "name": "Event Attendance Confirmation"}
    return {
        "type": "file",
        "path": "event_management/templates/emails/attendance_confirmation.html"
    }


@frappe.whitelist()
def resend_invitation(event_name, delegate_email):
    if not event_name or not delegate_email:
        frappe.throw("Missing event or delegate email")

    validate_email_address(delegate_email, throw=True)

    event = frappe.get_doc("Event Registration", event_name)
    delegate = next((d for d in event.delegates if d.email == delegate_email), None)

    if not delegate:
        frappe.throw("Delegate not found for this event")

    if delegate.confirmed:
        frappe.msgprint(
            f"{delegate.first_name} {delegate.last_name} has already confirmed attendance."
        )
        return

    confirmation_link = (
        get_url()
        + "/api/method/event_management.event_management.doctype.event_registration."
        "event_registration.confirm_delegate" + f"?token={delegate.confirmation_token}"
    )

    template_args = {
        "division": event.division or "Training",
        "event_date": formatdate(event.start_date, "dd MMM yyyy"),
        "location": f"{event.event_venue}, {event.event_location}",
        "delegate": {"full_name": f"{delegate.first_name} {delegate.last_name}",
                     "first_name": delegate.first_name,   # ← ADD THIS
                     "last_name": delegate.last_name
                     },
        "first_name": f"{delegate.first_name}",
        "last_name" : f"{delegate.last_name}",
        "event": event,
        "confirmation_link": confirmation_link,
        "client_list": [f"{d.first_name} {d.last_name}" for d in event.delegates],
        "company_name": frappe.defaults.get_global_default("company"),
    }

    template_info = _get_attendance_email_template()

    try:
        if template_info["type"] == "ui":
            email_template = frappe.get_doc("Email Template", template_info["name"])
            subject = frappe.render_template(email_template.subject, template_args)
            message = frappe.render_template(email_template.response, template_args)
            frappe.sendmail(
                recipients=[delegate.email],
                subject=subject,
                message=message,
            )
        else:
            # ✅ FIX: Same fix applied here — pre-render with frappe.render_template()
            # to correctly resolve the app path, pass as message= not template=
            message = frappe.render_template(
                template_info["path"],
                template_args
            )
            frappe.sendmail(
                recipients=[delegate.email],
                subject=f"{event.event_name} - Invitation",
                message=message,
            )

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Resend Attendance Invitation Failed")
        frappe.throw(
            "Failed to send invitation email. Please check Email Settings or logs."
        )


@frappe.whitelist()
def send_confirmation_list_email(recipient=None):
    today = getdate(nowdate())
    
    events = frappe.get_all(
        "Event Registration",
        filters={
            "docstatus": 1,
            "start_date": [">=", today]
        },
        fields=["name", "event_name", "organization_name", "start_date", "end_date", "all_confirmed"],
        order_by="start_date asc"
    )

    if not events:
        frappe.msgprint("No upcoming events found for reporting.")
        return

    html_report = _generate_event_report_html(events, report_type="upcoming_all")

    if not recipient:
        recipient = frappe.db.get_single_value("Event Management Setting", "admin_email") or "info@tagrit.com"

    try:
        frappe.sendmail(
            recipients=[recipient],
            subject=f"Upcoming Events Confirmation Status - {formatdate(nowdate())}",
            message=html_report,
            now=True
        )
        frappe.msgprint(f"✅ Report successfully sent to {recipient}!")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Event Report Failed")
        frappe.msgprint("Failed to send report. Check Error Logs.")


def _generate_event_report_html(events, report_type="all"):
    if report_type == "upcoming_all":
        title = "Upcoming Events - Confirmation Status Report"
        subtitle = f"Showing all {len(events)} upcoming events with delegate confirmation details"
    else:
        title = "Event Confirmation Status Report"
        subtitle = f"Total Events: {len(events)}"
    
    html = f"""<div style="font-family: Arial, sans-serif; color: #333;">
                <h2>{title}</h2>
                <p>Generated on: {formatdate(nowdate())}</p>
                <p style="color: #666;">{subtitle}</p>
                <hr>"""

    # Group events by division so each department (e.g. ABA, DSAIC) gets its
    # own clearly labeled section in the same email, instead of one
    # undifferentiated list. Order within each group follows the original
    # (chronological) order of `events`.
    events_by_division = {}
    division_order = []
    for event_summary in events:
        full_event = frappe.get_doc("Event Registration", event_summary.name)
        division = full_event.division or "Unassigned"
        if division not in events_by_division:
            events_by_division[division] = []
            division_order.append(division)
        events_by_division[division].append(full_event)

    for division in division_order:
        division_events = events_by_division[division]
        html += f"""
        <h2 style="margin-top: 30px; padding-bottom: 6px; border-bottom: 2px solid #20639B; color: #20639B;">
            {division} Report
        </h2>
        <p style="color: #666; margin: 4px 0 10px;">{len(division_events)} event(s)</p>"""

        for event in division_events:
            total = len(event.delegates)
            confirmed = sum(1 for d in event.delegates if d.confirmed)
            pending = total - confirmed
            percentage = round((confirmed / total * 100) if total > 0 else 0, 1)
            status_color = "#20639B" if event.all_confirmed else "#ff9800"

            days_until = (getdate(event.start_date) - getdate(nowdate())).days
            days_text = f"{days_until} days away" if days_until > 0 else "Today" if days_until == 0 else f"{abs(days_until)} days ago"

            html += f"""
            <div style="margin: 20px 0; border: 1px solid #eee; padding: 15px; border-radius: 8px;">
                <h3 style="color: {status_color};">{event.event_name}</h3>
                <p>
                    <strong>Organization:</strong> {event.organization_name} |
                    <strong>Date:</strong> {formatdate(event.start_date)} to {formatdate(event.end_date)}
                    <span style="color: #666;">({days_text})</span>
                </p>
                <p><strong>Venue:</strong> {event.event_venue}, {event.event_location}</p>
                <p style="background: #f8f9fa; padding: 10px; border-radius: 4px; margin: 10px 0;">
                    <strong>Confirmation Status:</strong>
                    <span style="color: #20639B; font-weight: bold;">{confirmed} Confirmed</span> |
                    <span style="color: #ff9800; font-weight: bold;">{pending} Pending</span> |
                    <span style="color: #666; font-weight: bold;">{percentage}% Complete</span>
                </p>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                    <tr style="background: #f8f9fa; border-bottom: 2px solid #eee;">
                        <th style="padding: 8px; text-align: left;">Delegate</th>
                        <th style="padding: 8px; text-align: left;">Email</th>
                        <th style="padding: 8px; text-align: center;">Status</th>
                        <th style="padding: 8px; text-align: center;">Confirmed On</th>
                    </tr>"""

            for d in event.delegates:
                status = "✅ Confirmed" if d.confirmed else "⏳ Pending"
                row_bg = "#f0fff4" if d.confirmed else "#fffaf0"
                conf_date = formatdate(d.confirmation_date) if d.confirmation_date else "N/A"
                html += f"""<tr style="background: {row_bg}; border-bottom: 1px solid #eee;">
                            <td style="padding: 8px;">{d.first_name} {d.last_name}</td>
                            <td style="padding: 8px;">{d.email}</td>
                            <td style="padding: 8px; text-align: center;">{status}</td>
                            <td style="padding: 8px; text-align: center;">{conf_date}</td>
                        </tr>"""
            html += "</table></div>"

    html += "</div>"
    return html

@frappe.whitelist()
def send_welcome_email_to_confirmed(event_name):
    if not event_name:
        frappe.throw("Missing event name")

    event = frappe.get_doc("Event Registration", event_name)

    confirmed_delegates = [d for d in event.delegates if d.confirmed]
    if not confirmed_delegates:
        frappe.msgprint("No confirmed delegates yet!")
        return

    settings = frappe.get_doc("Event Management Setting")
    cc = get_cc_email_list(settings)

    custom_attachments = []
    for row in event.get("welcome_attachments"):
        if row.file:
            file_doc = frappe.get_doc("File", {"file_url": row.file})
            # ✅ FIX: Get raw content, encode as base64 to survive email queue
            # serialization on production. Raw bytes break in JSON serialization.
            file_content = file_doc.get_content()
            if isinstance(file_content, str):
                file_content = file_content.encode("utf-8")
            custom_attachments.append({
                "fname": file_doc.file_name or row.file.split("/")[-1],
                "fcontent": base64.b64encode(file_content).decode("utf-8"),
                "is_private": file_doc.is_private
            })

    template_info = _get_event_welcome_template()
    success_count = 0

    for delegate in confirmed_delegates:
        try:
            template_args = {
                "event": event,
                "delegate": {
                    "full_name": f"{delegate.first_name} {delegate.last_name}",
                    "first_name": f"{delegate.first_name}",
                    "last_name" : f"{delegate.last_name}",
                    "email": delegate.email,
                },
                "event_date": f"{formatdate(event.start_date, 'dd MMM yyyy')} to {formatdate(event.end_date, 'dd MMM yyyy')}",
                "location": f"{event.event_venue}, {event.event_location}",
            }

            if template_info["type"] == "ui":
                email_template = frappe.get_doc("Email Template", template_info["name"])
                subject = frappe.render_template(email_template.subject, template_args)
                message = frappe.render_template(email_template.response, template_args)
                frappe.sendmail(
                    recipients=[delegate.email],
                    cc=cc,
                    expose_recipients="header",
                    subject=subject,
                    message=message,
                    attachments=custom_attachments,
                    now=True
                )
            else:
                # ✅ FIX: Same fix — pre-render with frappe.render_template()
                # to correctly resolve app path, pass as message= not template=
                message = frappe.render_template(
                    template_info["path"],
                    template_args
                )
                frappe.sendmail(
                    recipients=[delegate.email],
                    cc=cc,
                    expose_recipients="header",
                    subject=f"Welcome to {event.event_name}",
                    message=message,
                    attachments=custom_attachments
                )
            success_count += 1

        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Welcome Email Failed for {delegate.email}")

    if success_count > 0:
        event.db_set("welcome_email_sent", 1)
        frappe.msgprint(f"✅ Welcome email with {len(custom_attachments)} attachments sent to {success_count} delegates!")

def _get_event_welcome_template():
    template_name = "Event Welcome"
    if frappe.db.exists("Email Template", template_name):
        return {"type": "ui", "name": template_name}
    return {
        "type": "file",
        "path": "event_management/templates/emails/event_welcome.html"
    }
    
@frappe.whitelist()
def get_venues_by_location(location):
    venues = frappe.get_all(
        "Event Venue",
        filters={"location": location},
        fields=["name", "venue_name", "capacity"],
    )
    return venues


@frappe.whitelist()
def send_automated_reminders():
    today = getdate(nowdate())
    start_range = add_days(today, 7)
    end_range = add_days(today, 13)
    
    events = frappe.get_all(
        "Event Registration",
        filters={
            "docstatus": 1,
            "start_date": ["between", [start_range, end_range]],
            "all_confirmed": 0
        },
        fields=["name"]
    )

    for e in events:
        doc = frappe.get_doc("Event Registration", e.name)
        for d in doc.delegates:
            if not d.confirmed:
                resend_invitation(doc.name, d.email)
        

@frappe.whitelist()
def trigger_automated_wednesday_report():
    today = getdate(nowdate())
    reporting_window = add_days(today, 10)

    events_to_process = frappe.get_all(
        "Event Registration",
        filters={
            "docstatus": 1,
            "start_date": ["between", [today, reporting_window]],
            "final_report_sent": 0
        },
        fields=["name", "event_name", "organization_name", "start_date", "end_date", "all_confirmed"],
        order_by="start_date asc"
    )

    if not events_to_process:
        frappe.log_error("No upcoming events found for Wednesday report", "Wednesday Report - No Events")
        return

    html_report = _generate_event_report_html(events_to_process, report_type="upcoming_all")

    recipient = frappe.db.get_single_value("Event Management Setting", "admin_email") or "info@tagrit.com"
    
    frappe.sendmail(
        recipients=[recipient],
        subject=f"Upcoming Events Status - Weekly Report - {formatdate(nowdate())}",
        message=html_report,
        now=True
    )

    for e in events_to_process:
        frappe.db.set_value("Event Registration", e.name, "final_report_sent", 1, update_modified=False)
    
    frappe.db.commit()
    
    frappe.log_error(
        f"Wednesday report sent successfully for {len(events_to_process)} events to {recipient}",
        "Wednesday Report Success"
    )


def _run_if_schedule_due(settings, enabled_field, day_field, time_field, last_run_field, default_day, action):
    """Shared wiring between a Setting doc's schedule fields and the pure
    schedule_is_due() check: checks whether the named schedule is due right
    now, runs `action()` if so, and records the run so it doesn't fire again
    today."""
    if not settings.get(enabled_field):
        return

    time_value = settings.get(time_field)
    if not time_value:
        return

    now_dt = get_datetime(now())
    scheduled_day = settings.get(day_field) or default_day
    scheduled_time = get_time(time_value)
    last_run_value = settings.get(last_run_field)

    if not schedule_is_due(now_dt, scheduled_day, scheduled_time, last_run_value):
        return

    action()

    frappe.db.set_value("Event Management Setting", None, last_run_field, str(getdate(now_dt)))
    frappe.db.commit()


@frappe.whitelist()
def check_and_run_scheduled_welcome_emails():
    """Runs frequently (see hooks.py cron). Only actually dispatches once, on the
    day/time configured on Event Management Setting, so the schedule can be
    changed from the Setting page without touching code or restarting anything."""
    settings = frappe.get_doc("Event Management Setting")
    _run_if_schedule_due(
        settings,
        enabled_field="welcome_email_schedule_enabled",
        day_field="welcome_email_day",
        time_field="welcome_email_time",
        last_run_field="welcome_email_last_run",
        default_day="Thursday",
        action=_run_confirmed_welcome_email_batch
    )


@frappe.whitelist()
def check_and_run_scheduled_reminders():
    """Runs frequently (see hooks.py cron). Only actually dispatches once, on the
    day/time configured on Event Management Setting, so the schedule can be
    changed from the Setting page without touching code or restarting anything."""
    settings = frappe.get_doc("Event Management Setting")
    _run_if_schedule_due(
        settings,
        enabled_field="reminder_email_schedule_enabled",
        day_field="reminder_email_day",
        time_field="reminder_email_time",
        last_run_field="reminder_email_last_run",
        default_day="Monday",
        action=send_automated_reminders
    )


def _run_confirmed_welcome_email_batch():
    """Send the confirmed-delegate welcome email for every submitted,
    fully-confirmed event that hasn't had it sent yet."""
    events_to_process = frappe.get_all(
        "Event Registration",
        filters={
            "docstatus": 1,
            "all_confirmed": 1,
            "welcome_email_sent": 0
        },
        fields=["name"]
    )

    if not events_to_process:
        frappe.log_error("No confirmed events pending a welcome email", "Scheduled Welcome Email - No Events")
        return

    for e in events_to_process:
        try:
            send_welcome_email_to_confirmed(e.name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Scheduled Welcome Email Failed for {e.name}")

    frappe.log_error(
        f"Scheduled welcome email run processed {len(events_to_process)} event(s)",
        "Scheduled Welcome Email Success"
    )


@frappe.whitelist()
def get_dashboard_data():
    draft_count = frappe.db.count("Event Registration", {"docstatus": 0})
    confirmed_count = frappe.db.count("Event Registration", {"docstatus": 1, "all_confirmed": 1})
    pending_count = frappe.db.count("Event Registration", {"docstatus": 1, "all_confirmed": 0})
    
    total_revenue = frappe.db.sql("""
        SELECT SUM(revenue) as total
        FROM `tabEvent Registration`
        WHERE docstatus = 1
    """, as_dict=1)[0].total or 0
    
    total_delegates = frappe.db.sql("""
        SELECT COUNT(*) as total
        FROM `tabEvent Delegate`
        WHERE parent IN (
            SELECT name FROM `tabEvent Registration` WHERE docstatus = 1
        )
    """, as_dict=1)[0].total or 0
    
    confirmed_delegates = frappe.db.sql("""
        SELECT COUNT(*) as total
        FROM `tabEvent Delegate`
        WHERE confirmed = 1
        AND parent IN (
            SELECT name FROM `tabEvent Registration` WHERE docstatus = 1
        )
    """, as_dict=1)[0].total or 0
    
    pending_delegates = total_delegates - confirmed_delegates
    
    upcoming_events = frappe.db.sql("""
        SELECT COUNT(*) as total
        FROM `tabEvent Registration`
        WHERE docstatus = 1
        AND start_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
    """, as_dict=1)[0].total or 0
    
    events_by_month = frappe.db.sql("""
        SELECT 
            DATE_FORMAT(start_date, '%b %Y') as month,
            COUNT(*) as count
        FROM `tabEvent Registration`
        WHERE docstatus = 1
        AND start_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(start_date, '%Y-%m')
        ORDER BY start_date
    """, as_dict=1)
    
    revenue_by_month = frappe.db.sql("""
        SELECT 
            DATE_FORMAT(start_date, '%b %Y') as month,
            SUM(revenue) as revenue
        FROM `tabEvent Registration`
        WHERE docstatus = 1
        AND start_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(start_date, '%Y-%m')
        ORDER BY start_date
    """, as_dict=1)
    
    top_organizations = frappe.db.sql("""
        SELECT 
            organization_name,
            COUNT(*) as event_count,
            SUM(revenue) as total_revenue
        FROM `tabEvent Registration`
        WHERE docstatus = 1
        GROUP BY organization_name
        ORDER BY event_count DESC
        LIMIT 5
    """, as_dict=1)
    
    confirmation_rate = round((confirmed_delegates / total_delegates * 100) if total_delegates > 0 else 0, 1)
    
    return {
        "summary": {
            "draft_events": draft_count,
            "confirmed_events": confirmed_count,
            "pending_events": pending_count,
            "total_revenue": total_revenue,
            "total_delegates": total_delegates,
            "confirmed_delegates": confirmed_delegates,
            "pending_delegates": pending_delegates,
            "confirmation_rate": confirmation_rate,
            "upcoming_events": upcoming_events
        },
        "charts": {
            "events_by_month": events_by_month,
            "revenue_by_month": revenue_by_month
        },
        "top_organizations": top_organizations
    }


def _get_event_customer(event):
    """The Customer billed for this event's client organization, or None if
    the Event Organization record hasn't been linked to one yet."""
    if not event.organization_name:
        return None
    return frappe.db.get_value("Event Organization", event.organization_name, "customer")


def ensure_training_fee_item_exists(item_code="Training Fee"):
    """Ensure a sales-side Training Fee item exists, mirroring
    event_trainer.ensure_training_service_item_exists on the purchase side."""
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
            "is_purchase_item": 0,
            "is_sales_item": 1,
            "description": "Training fee billed to client organizations for event management",
            "maintain_stock": 0
        })
        item.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.msgprint(f"Item '{item_code}' created automatically", alert=True, indicator="green")

    except Exception as e:
        frappe.log_error(f"Error creating Training Fee item: {str(e)}", "Training Fee Item Creation")
        frappe.throw(f"Could not create '{item_code}' item. Error: {str(e)}")


@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None):
    """Create a Sales Invoice from Event Registration, billing the Customer
    linked to the event's client Event Organization."""
    from frappe.model.mapper import get_mapped_doc

    event = frappe.get_doc("Event Registration", source_name)
    customer = _get_event_customer(event)
    if not customer:
        frappe.throw(
            f"'{event.organization_name}' has no Customer linked yet. "
            f"Open the Event Organization record and set its Customer field first."
        )

    def set_missing_values(source, target):
        target.customer = customer
        target.event_registration = source.name

        item_code = "Training Fee"
        ensure_training_fee_item_exists(item_code)

        target.append("items", {
            "item_code": item_code,
            "item_name": item_code,
            "description": f"Training fee for {source.event_name} ({formatdate(source.start_date)} to {formatdate(source.end_date)})",
            "qty": source.number_of_delegates,
            "rate": source.charges_per_delegate,
            "amount": source.revenue,
            "uom": "Nos"
        })

    doclist = get_mapped_doc(
        "Event Registration",
        source_name,
        {
            "Event Registration": {
                "doctype": "Sales Invoice",
            }
        },
        target_doc,
        set_missing_values
    )

    return doclist


@frappe.whitelist()
def create_event_payment_entry(event_registration_name, amount, reference_no=None, remarks=None, link_to_invoice=None, auto_submit=False):
    """Record a payment received from the client organization for this event."""
    event = frappe.get_doc("Event Registration", event_registration_name)
    customer = _get_event_customer(event)
    if not customer:
        frappe.throw(
            f"'{event.organization_name}' has no Customer linked yet. "
            f"Open the Event Organization record and set its Customer field first."
        )

    company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
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

    receivable_account = frappe.get_cached_value("Company", company, "default_receivable_account")

    payment = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": customer,
        "company": company,
        "posting_date": now(),
        "paid_from": receivable_account,
        "paid_to": payment_account,
        "paid_amount": flt(amount),
        "received_amount": flt(amount),
        "source_exchange_rate": 1,
        "target_exchange_rate": 1,
        "reference_no": reference_no or event_registration_name,
        "reference_date": now(),
        "remarks": remarks or f"Payment received for {event.event_name}",
        "mode_of_payment": mode_of_payment,
        "event_registration": event_registration_name
    })

    if link_to_invoice:
        invoice = frappe.get_doc("Sales Invoice", link_to_invoice)
        payment.append("references", {
            "reference_doctype": "Sales Invoice",
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
def get_event_financial_summary(event_registration_name):
    """Full income/expense breakdown for one event: what was invoiced and
    collected from the client, what trainers were paid, what other expenses
    (hotel, delegate materials, etc.) were booked against it via Purchase
    Invoice, and the resulting net profit - for the CFO/management report."""
    event = frappe.get_doc("Event Registration", event_registration_name)

    invoiced_row = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0), COALESCE(SUM(outstanding_amount), 0)
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND event_registration = %s
    """, event_registration_name)[0]
    total_invoiced = flt(invoiced_row[0])
    total_invoice_outstanding = flt(invoiced_row[1])
    collected_via_invoice = total_invoiced - total_invoice_outstanding

    collected_direct = flt(frappe.db.sql("""
        SELECT COALESCE(SUM(pe.paid_amount), 0)
        FROM `tabPayment Entry` pe
        WHERE pe.docstatus = 1
        AND pe.payment_type = 'Receive'
        AND pe.event_registration = %s
        AND NOT EXISTS (
            SELECT 1 FROM `tabPayment Entry Reference` per WHERE per.parent = pe.name
        )
    """, event_registration_name)[0][0] or 0)

    total_collected = collected_via_invoice + collected_direct

    trainers = frappe.get_all(
        "Event Trainer",
        filters={"event_registration": event_registration_name},
        fields=["name", "trainer_name", "total_amount", "paid_amount", "payment_status"]
    )
    trainer_contracted = sum(flt(t.total_amount) for t in trainers)
    trainer_paid = sum(flt(t.paid_amount) for t in trainers)

    other_invoices = frappe.db.sql("""
        SELECT name, supplier_name, grand_total, outstanding_amount
        FROM `tabPurchase Invoice`
        WHERE docstatus = 1
        AND event_registration = %s
        AND (event_trainer IS NULL OR event_trainer = '')
    """, event_registration_name, as_dict=1)

    other_total_billed = sum(flt(inv.grand_total) for inv in other_invoices)
    other_total_paid = sum(flt(inv.grand_total) - flt(inv.outstanding_amount) for inv in other_invoices)

    other_breakdown = frappe.db.sql("""
        SELECT
            COALESCE(pii.expense_account, 'Unspecified Account') as category,
            SUM(pii.amount) as amount
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
        WHERE pi.docstatus = 1
        AND pi.event_registration = %s
        AND (pi.event_trainer IS NULL OR pi.event_trainer = '')
        GROUP BY category
        ORDER BY amount DESC
    """, event_registration_name, as_dict=1)

    total_expenses_paid = trainer_paid + other_total_paid
    total_expenses_billed = trainer_contracted + other_total_billed
    net_profit = total_collected - total_expenses_paid
    profit_margin = round((net_profit / total_collected * 100), 1) if total_collected else 0

    return {
        "event": {
            "name": event.name,
            "event_name": event.event_name,
            "organization_name": event.organization_name,
            "start_date": event.start_date,
            "end_date": event.end_date,
            "division": event.division,
            "number_of_delegates": event.number_of_delegates,
            "budgeted_revenue": flt(event.revenue),
        },
        "income": {
            "total_invoiced": total_invoiced,
            "invoice_outstanding": total_invoice_outstanding,
            "collected_via_invoice": collected_via_invoice,
            "collected_direct": collected_direct,
            "total_collected": total_collected,
        },
        "expenses": {
            "trainers": {
                "contracted": trainer_contracted,
                "paid": trainer_paid,
                "detail": trainers,
            },
            "other": {
                "billed": other_total_billed,
                "paid": other_total_paid,
                "breakdown": other_breakdown,
                "invoices": other_invoices,
            },
            "total_billed": total_expenses_billed,
            "total_paid": total_expenses_paid,
        },
        "net_profit": net_profit,
        "profit_margin": profit_margin,
    }