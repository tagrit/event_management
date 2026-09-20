import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Add the event_registration link to Sales Invoice, mirroring the same
    field already added to Purchase Invoice/Payment Entry for trainer costs.
    This lets accounts tag a client invoice to the event it's billing for,
    so income can be aggregated per event alongside the existing expense
    tracking (Purchase Invoice/Payment Entry.event_registration)."""

    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "event_registration",
                "label": "Event Registration",
                "fieldtype": "Link",
                "options": "Event Registration",
                "insert_after": "customer",
                "description": "Link this invoice to a training event",
            }
        ]
    }

    create_custom_fields(custom_fields, update=True)

    frappe.db.commit()
