import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Fix field ordering: the trainer custom fields (is_trainer onward) were
    anchored with insert_after="supplier_type", but Supplier Name should
    always be the first field a user sees/fills in. Re-anchoring the first
    field in that chain (is_trainer) to insert_after="supplier_name" moves
    the whole chain - is_trainer, trainer_details_section, area_of_expertise,
    trainer_rate_type, trainer_rate, cv_attachment - right after the name
    field instead of ahead of it. trainer_documents follows cv_attachment
    already, so it doesn't need to move separately.
    """
    if not frappe.db.exists("DocType", "Supplier"):
        return

    create_custom_fields(
        {
            "Supplier": [
                {
                    "fieldname": "is_trainer",
                    "label": "Is Trainer",
                    "fieldtype": "Check",
                    "insert_after": "supplier_name",
                    "description": "Check this if supplier is also a trainer"
                }
            ]
        },
        update=True
    )

    frappe.db.commit()
