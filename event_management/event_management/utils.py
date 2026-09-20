import frappe

FINANCE_ROLES = ["Accounts User", "Accounts Manager", "Auditor"]


def is_finance_user(user=None):
    """Whether the given (or current) user should see money figures -
    reused by the workspace KPI cards, the Event Registration Finance
    buttons, and every report that includes financial columns."""
    return bool(set(frappe.get_roles(user)) & set(FINANCE_ROLES))
