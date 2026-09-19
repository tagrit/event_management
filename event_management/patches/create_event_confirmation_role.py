import frappe


def execute():
    """Create the 'Event Confirmation Officer' role.

    Delegate confirmation used to be writable by anyone holding System
    Manager (which every staff user on this site has), so there was no way
    to restrict who confirms delegates or trace who did it. The Confirmed /
    Confirmation Date / Confirmed By fields on Event Delegate are now
    permlevel-restricted to this role (System Manager keeps read-only
    visibility). Assign this role, from the User doctype, to the one person
    who should be confirming delegates.
    """
    if frappe.db.exists("Role", "Event Confirmation Officer"):
        return

    frappe.get_doc({
        "doctype": "Role",
        "role_name": "Event Confirmation Officer",
        "desk_access": 1
    }).insert(ignore_permissions=True)

    frappe.db.commit()
