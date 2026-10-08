import frappe

METHOD_PATH = "event_management.event_management.doctype.event_registration.event_registration"

CARD = {
    "name": "Event CB - Expenses Not Paid",
    "label": "Expenses Not Paid",
    "method": f"{METHOD_PATH}.card_expenses_owed",
    "color": "#dc2626",
    "document_type": "GL Entry",
}


def execute():
    """Add the "Expenses Not Paid" KPI card introduced alongside the
    supplier-owed-amount reporting fix. A new entry added to the existing
    CARDS list in create_event_workspace_number_cards.py would never run on
    an already-installed site - patches.txt only runs each patch once - so
    this is its own one-off patch, same pattern as
    fix_expense_entry_required_date_default.py."""
    previous_flag = frappe.flags.in_import
    frappe.flags.in_import = True
    try:
        if not frappe.db.exists("Number Card", CARD["name"]):
            doc = frappe.new_doc("Number Card")
            doc.name = CARD["name"]
            doc.label = CARD["label"]
            doc.type = "Custom"
            doc.method = CARD["method"]
            doc.document_type = CARD["document_type"]
            doc.is_public = 1
            doc.show_percentage_stats = 0
            doc.color = CARD["color"]
            doc.insert(ignore_permissions=True)
    finally:
        frappe.flags.in_import = previous_flag

    frappe.db.commit()
