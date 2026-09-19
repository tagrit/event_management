import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Add a multi-document table to Supplier for trainers, alongside the
    existing single cv_attachment field (ID copies, certifications, signed
    contracts, etc. - anything beyond the one CV file). Also marks the
    existing is_trainer field as a standard filter so the Supplier list can
    be quickly filtered down to just trainers (update=True re-applies this
    onto the field created by the earlier add_trainer_management_fields
    patch, which already ran on existing sites)."""

    custom_fields = {
        "Supplier": [
            {
                "fieldname": "trainer_documents",
                "label": "Additional Documents",
                "fieldtype": "Table",
                "options": "Event Attachment",
                "insert_after": "cv_attachment",
                "depends_on": "eval:doc.is_trainer==1",
                "description": "Certifications, ID copies, signed contracts, or any other supporting documents for this trainer."
            },
            {
                "fieldname": "is_trainer",
                "label": "Is Trainer",
                "fieldtype": "Check",
                "insert_after": "supplier_type",
                "description": "Check this if supplier is also a trainer",
                "in_standard_filter": 1
            }
        ]
    }

    create_custom_fields(custom_fields, update=True)
    frappe.db.commit()
