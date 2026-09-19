import frappe


def execute():
    """One-time cleanup of the Division master data on existing sites.

    Historically 'ABA' and 'BTS' both existed as separate divisions for the
    same department (BTS is the newer name), and 'DSAC'/'DSAIC' both existed
    for what should be a single department (DSAIC is the correct name).
    A third group of courses (event names starting with 'GPS'/'FESGI',
    'FESGI' being the old course-line name) had never been split into their
    own division and were left sitting under DSAC.

    This merges ABA into BTS, merges DSAC into DSAIC, and carves the
    GPS/FESGI-named events out into a new GPS division. frappe.rename_doc
    with merge=True updates every Event Registration.division reference
    automatically, so no other doctype needs touching.
    """
    if not frappe.db.exists("DocType", "Division"):
        return

    if frappe.db.exists("Division", "ABA") and frappe.db.exists("Division", "BTS"):
        frappe.rename_doc("Division", "ABA", "BTS", merge=True, force=True)

    if frappe.db.exists("Division", "DSAC") and frappe.db.exists("Division", "DSAIC"):
        frappe.rename_doc("Division", "DSAC", "DSAIC", merge=True, force=True)

    if not frappe.db.exists("Division", "GPS"):
        frappe.get_doc({
            "doctype": "Division",
            "division": "GPS",
            "description": "Split out from DSAIC: courses previously branded FESGI, now GPS."
        }).insert(ignore_permissions=True)

    if frappe.db.exists("DocType", "Event Registration"):
        frappe.db.sql("""
            UPDATE `tabEvent Registration`
            SET division = 'GPS'
            WHERE division = 'DSAIC'
              AND (event_name LIKE 'GPS %' OR event_name LIKE 'FESGI %')
        """)

    frappe.db.commit()
