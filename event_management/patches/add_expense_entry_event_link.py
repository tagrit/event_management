import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Add an Event Registration link to journal_plus's Expense Entry, so an
    expense (hotel, delegate materials, etc.) booked via Expense Entry can be
    tagged to the event it's for, same as the existing event_registration
    field on Purchase Invoice/Sales Invoice/Payment Entry. Only runs where
    both apps are installed (Expense Entry won't exist otherwise)."""
    if not frappe.db.exists("DocType", "Expense Entry"):
        return

    custom_fields = {
        "Expense Entry": [
            {
                "fieldname": "event_registration",
                "label": "Event Registration",
                "fieldtype": "Link",
                "options": "Event Registration",
                "insert_after": "payment_to",
                "description": "Link this expense to a training event",
            }
        ]
    }

    create_custom_fields(custom_fields, update=True)

    frappe.db.commit()
