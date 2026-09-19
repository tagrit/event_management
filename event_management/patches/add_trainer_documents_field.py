import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Add a multi-document table to Supplier for trainers, alongside the
    existing single cv_attachment field (ID copies, certifications, signed
    contracts, etc. - anything beyond the one CV file)."""

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
            }
        ]
    }

    create_custom_fields(custom_fields, update=True)
    frappe.db.commit()
