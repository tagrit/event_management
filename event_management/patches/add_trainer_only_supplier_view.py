import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    """Hide the accounting/procurement-only parts of the Supplier form when
    "Is Trainer" is checked, so adding a trainer only shows trainer-relevant
    fields (name, area of expertise, rate, CV/documents). Regular suppliers
    (is_trainer unchecked) are completely unaffected - this only adds a
    depends_on condition to existing core fields via Property Setter, it
    doesn't touch the Supplier doctype itself.
    """
    if not frappe.db.exists("DocType", "Supplier"):
        return

    hide_when_trainer = [
        "tax_tab",
        "contact_and_address_tab",
        "accounting_tab",
        "settings_tab",
        "portal_users_tab",
        "defaults_section",
        "internal_supplier_section",
        "column_break2",  # "More Information" section
        "supplier_type",
        "is_transporter",
    ]

    for fieldname in hide_when_trainer:
        make_property_setter(
            "Supplier",
            fieldname,
            "depends_on",
            "eval:!doc.is_trainer",
            "Code",
            validate_fields_for_doctype=False,
        )

    frappe.db.commit()
