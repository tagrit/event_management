import frappe
from frappe.utils import flt

FINANCE_ROLES = ["Accounts User", "Accounts Manager", "Auditor"]


def is_finance_user(user=None):
    """Whether the given (or current) user should see money figures -
    reused by the workspace KPI cards, the Event Registration Finance
    buttons, and every report that includes financial columns."""
    return bool(set(frappe.get_roles(user)) & set(FINANCE_ROLES))


def expense_entry_installed():
    """Whether journal_plus's Expense Entry doctype exists on this site.
    Expense Entry is a second expense-booking path alongside Purchase
    Invoice, only present where journal_plus happens to be installed -
    every expense aggregation query that includes it must be guarded by
    this, or it breaks sites that don't have journal_plus."""
    return bool(frappe.db.exists("DocType", "Expense Entry"))


def get_event_expense_entry_total(event_registration_name):
    """Submitted Expense Entry total tagged to one event. An Expense Entry
    has no separate invoiced/paid distinction like Purchase Invoice does -
    submitting it means the money was paid out via its mode of payment, so
    its full total counts as both billed and paid."""
    if not expense_entry_installed():
        return 0
    return flt(frappe.db.sql("""
        SELECT COALESCE(SUM(total), 0)
        FROM `tabExpense Entry`
        WHERE docstatus = 1 AND event_registration = %s
    """, event_registration_name)[0][0])


def get_module_expense_entry_total():
    """Submitted Expense Entry total across all events, module-wide."""
    if not expense_entry_installed():
        return 0
    return flt(frappe.db.sql("""
        SELECT COALESCE(SUM(total), 0)
        FROM `tabExpense Entry`
        WHERE docstatus = 1 AND event_registration IS NOT NULL AND event_registration != ''
    """)[0][0])


def get_expense_entry_totals_by_event(event_names):
    """Submitted Expense Entry totals for a batch of events, keyed by event
    name - for reports that list many events and need to avoid an N+1 query
    per row (e.g. Event Profitability Report)."""
    if not expense_entry_installed() or not event_names:
        return {}
    rows = frappe.db.sql("""
        SELECT event_registration, SUM(total) as total
        FROM `tabExpense Entry`
        WHERE docstatus = 1 AND event_registration IN %(names)s
        GROUP BY event_registration
    """, {"names": event_names}, as_dict=1)
    return {r.event_registration: flt(r.total) for r in rows}


def get_event_expense_entry_breakdown(event_registration_name):
    """Expense Entry line items for one event, grouped by expense account -
    merges with the Purchase Invoice breakdown in get_event_financial_summary
    so the account-level view covers both expense-booking paths."""
    if not expense_entry_installed():
        return []
    return frappe.db.sql("""
        SELECT
            COALESCE(eed.expense_account, 'Unspecified Account') as category,
            SUM(eed.amount) as amount
        FROM `tabExpense Entry Detail` eed
        INNER JOIN `tabExpense Entry` ee ON eed.parent = ee.name
        WHERE ee.docstatus = 1 AND ee.event_registration = %s
        GROUP BY category
    """, event_registration_name, as_dict=1)


def get_expense_entry_totals_by_division(division_where_clause, values):
    """Submitted Expense Entry totals grouped by the owning event's
    division - for Division Performance Report. division_where_clause/values
    must match the same filter conditions (date range etc.) used for the
    other expense sources in that report, joined through Event Registration
    since Expense Entry itself has no division field."""
    if not expense_entry_installed():
        return {}
    rows = frappe.db.sql(f"""
        SELECT er.division, SUM(ee.total) as total
        FROM `tabExpense Entry` ee
        INNER JOIN `tabEvent Registration` er ON er.name = ee.event_registration
        WHERE ee.docstatus = 1 AND {division_where_clause}
        GROUP BY er.division
    """, values, as_dict=1)
    return {r.division: flt(r.total) for r in rows}
