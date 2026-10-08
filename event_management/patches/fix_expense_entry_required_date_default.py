import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    """journal_plus's Expense Entry.required_date ships with default="now",
    which isn't a valid Frappe date-default expression (should be "Today") -
    MariaDB rejects it outright ("Incorrect date value: 'now'") the moment a
    new Expense Entry is saved, since the field's own broken default gets
    applied to every new document, including ones opened via our own "Add
    Expense Via Expense Entry" button. Overriding it with a Property Setter
    rather than editing the third-party app's own file, since that edit
    would be lost on any journal_plus update. Only runs where the doctype
    actually exists (journal_plus installed)."""
    if not frappe.db.exists("DocType", "Expense Entry"):
        return

    make_property_setter("Expense Entry", "required_date", "default", "Today", "Text")

    frappe.db.commit()
