import frappe

from event_management.event_management.doctype.event_organization.event_organization import (
    get_or_create_customer,
)


def execute():
    """One-time backfill: link (or create) a Customer for every Event
    Organization that predates the customer field, so Finance can invoice
    any of them without first re-creating the organization as a Customer."""
    orgs = frappe.get_all("Event Organization", fields=["name", "customer", "organization"])

    for org in orgs:
        if org.customer:
            continue
        try:
            customer = get_or_create_customer(org.organization)
            frappe.db.set_value("Event Organization", org.name, "customer", customer, update_modified=False)
        except Exception:
            frappe.log_error(title=f"Backfill Event Organization Customer failed: {org.name}")

    frappe.db.commit()
