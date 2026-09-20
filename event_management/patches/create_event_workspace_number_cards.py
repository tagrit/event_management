import frappe

METHOD_PATH = "event_management.event_management.doctype.event_registration.event_registration"

CARDS = [
    {
        "name": "Event CB - Revenue Collected",
        "label": "Revenue Collected",
        "method": f"{METHOD_PATH}.card_revenue_collected",
        "color": "#16a34a",
    },
    {
        "name": "Event CB - Expenses Paid",
        "label": "Expenses Paid",
        "method": f"{METHOD_PATH}.card_expenses_paid",
        "color": "#d97706",
    },
    {
        "name": "Event CB - Net Profit",
        "label": "Net Profit",
        "method": f"{METHOD_PATH}.card_net_profit",
        "color": "#1e3a8a",
    },
    {
        "name": "Event CB - Confirmation Rate",
        "label": "Confirmation Rate",
        "method": f"{METHOD_PATH}.card_confirmation_rate",
        "color": "#3b82f6",
    },
    {
        "name": "Event CB - Confirmed Events",
        "label": "Confirmed Events",
        "method": f"{METHOD_PATH}.card_confirmed_events",
        "color": "#16a34a",
    },
    {
        "name": "Event CB - Pending Events",
        "label": "Pending Events",
        "method": f"{METHOD_PATH}.card_pending_events",
        "color": "#d97706",
    },
    {
        "name": "Event CB - Upcoming Events",
        "label": "Upcoming Events (30 days)",
        "method": f"{METHOD_PATH}.card_upcoming_events",
        "color": "#8b5cf6",
    },
]


def execute():
    """Create the Number Cards used by the Event CB workspace's top KPI
    section. Idempotent - safe to re-run (e.g. on a fresh install)."""
    for card in CARDS:
        if frappe.db.exists("Number Card", card["name"]):
            continue

        frappe.get_doc({
            "doctype": "Number Card",
            "name": card["name"],
            "label": card["label"],
            "type": "Custom",
            "method": card["method"],
            "document_type": "Event Registration",
            "is_public": 1,
            "show_percentage_stats": 0,
            "color": card["color"],
        }).insert(ignore_permissions=True)

    frappe.db.commit()
