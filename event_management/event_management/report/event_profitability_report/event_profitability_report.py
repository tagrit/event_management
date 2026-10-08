import frappe
from frappe.utils import flt

from event_management.event_management.utils import get_expense_entry_totals_by_event


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Event", "fieldname": "name", "fieldtype": "Link", "options": "Event Registration", "width": 150},
        {"label": "Event Name", "fieldname": "event_name", "fieldtype": "Data", "width": 200},
        {"label": "Organization", "fieldname": "organization_name", "fieldtype": "Link", "options": "Event Organization", "width": 150},
        {"label": "Division", "fieldname": "division", "fieldtype": "Link", "options": "Division", "width": 100},
        {"label": "Start Date", "fieldname": "start_date", "fieldtype": "Date", "width": 100},
        {"label": "Budgeted Revenue", "fieldname": "revenue", "fieldtype": "Currency", "width": 130},
        {"label": "Total Invoiced", "fieldname": "total_invoiced", "fieldtype": "Currency", "width": 130},
        {"label": "Income Collected", "fieldname": "income_collected", "fieldtype": "Currency", "width": 130},
        {"label": "Amount Due", "fieldname": "amount_due", "fieldtype": "Currency", "width": 140},
        {"label": "Trainer Costs Contracted", "fieldname": "trainer_billed", "fieldtype": "Currency", "width": 150},
        {"label": "Trainer Costs Paid", "fieldname": "trainer_paid", "fieldtype": "Currency", "width": 130},
        {"label": "Other Expenses Billed", "fieldname": "other_billed", "fieldtype": "Currency", "width": 140},
        {"label": "Other Expenses Paid", "fieldname": "other_paid", "fieldtype": "Currency", "width": 140},
        {"label": "Total Expenses Billed", "fieldname": "total_expenses_billed", "fieldtype": "Currency", "width": 150},
        {"label": "Total Expenses Paid", "fieldname": "total_expenses", "fieldtype": "Currency", "width": 140},
        {"label": "Expenses Not Paid", "fieldname": "amount_owed", "fieldtype": "Currency", "width": 140},
        {"label": "Net Profit", "fieldname": "net_profit", "fieldtype": "Currency", "width": 120},
        {"label": "Margin %", "fieldname": "margin", "fieldtype": "Percent", "width": 90},
    ]


def get_data(filters):
    conditions = ["er.docstatus = 1"]
    values = {}

    if filters.get("from_date"):
        conditions.append("er.start_date >= %(from_date)s")
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        conditions.append("er.start_date <= %(to_date)s")
        values["to_date"] = filters.to_date

    if filters.get("division"):
        conditions.append("er.division = %(division)s")
        values["division"] = filters.division

    if filters.get("organization_name"):
        conditions.append("er.organization_name = %(organization_name)s")
        values["organization_name"] = filters.organization_name

    where_clause = " AND ".join(conditions)

    events = frappe.db.sql(f"""
        SELECT er.name, er.event_name, er.organization_name, er.division, er.start_date, er.revenue
        FROM `tabEvent Registration` er
        WHERE {where_clause}
        ORDER BY er.start_date DESC
    """, values, as_dict=1)

    if not events:
        return []

    event_names = [e.name for e in events]

    invoice_rows = frappe.db.sql("""
        SELECT event_registration,
            SUM(grand_total) as invoiced,
            SUM(grand_total - outstanding_amount) as collected
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND event_registration IN %(names)s
        GROUP BY event_registration
    """, {"names": event_names}, as_dict=1)
    total_invoiced = {r.event_registration: flt(r.invoiced) for r in invoice_rows}
    income_via_invoice = {r.event_registration: flt(r.collected) for r in invoice_rows}

    income_direct = {
        r.event_registration: flt(r.total) for r in frappe.db.sql("""
            SELECT pe.event_registration, SUM(pe.paid_amount) as total
            FROM `tabPayment Entry` pe
            WHERE pe.docstatus = 1 AND pe.payment_type = 'Receive'
            AND pe.event_registration IN %(names)s
            AND NOT EXISTS (SELECT 1 FROM `tabPayment Entry Reference` per WHERE per.parent = pe.name)
            GROUP BY pe.event_registration
        """, {"names": event_names}, as_dict=1)
    }

    trainer_rows = {
        r.event_registration: r for r in frappe.db.sql("""
            SELECT event_registration, SUM(total_amount) as billed, SUM(paid_amount) as paid
            FROM `tabEvent Trainer`
            WHERE event_registration IN %(names)s
            GROUP BY event_registration
        """, {"names": event_names}, as_dict=1)
    }

    other_billed = {
        r.event_registration: flt(r.total) for r in frappe.db.sql("""
            SELECT event_registration, SUM(grand_total) as total
            FROM `tabPurchase Invoice`
            WHERE docstatus = 1 AND event_registration IN %(names)s
            AND (event_trainer IS NULL OR event_trainer = '')
            GROUP BY event_registration
        """, {"names": event_names}, as_dict=1)
    }

    other_paid_via_invoice = {
        r.event_registration: flt(r.total) for r in frappe.db.sql("""
            SELECT event_registration, SUM(grand_total - outstanding_amount) as total
            FROM `tabPurchase Invoice`
            WHERE docstatus = 1 AND event_registration IN %(names)s
            AND (event_trainer IS NULL OR event_trainer = '')
            GROUP BY event_registration
        """, {"names": event_names}, as_dict=1)
    }

    # Supplier paid via a standalone Payment Entry never allocated against
    # its Purchase Invoice - same gap as the income side's "collected direct".
    other_paid_direct = {
        r.event_registration: flt(r.total) for r in frappe.db.sql("""
            SELECT pe.event_registration, SUM(pe.paid_amount) as total
            FROM `tabPayment Entry` pe
            WHERE pe.docstatus = 1 AND pe.payment_type = 'Pay'
            AND pe.event_registration IN %(names)s
            AND (pe.event_trainer IS NULL OR pe.event_trainer = '')
            AND NOT EXISTS (SELECT 1 FROM `tabPayment Entry Reference` per WHERE per.parent = pe.name)
            GROUP BY pe.event_registration
        """, {"names": event_names}, as_dict=1)
    }

    expense_entry_paid = get_expense_entry_totals_by_event(event_names)

    data = []
    for event in events:
        income = income_via_invoice.get(event.name, 0) + income_direct.get(event.name, 0)

        trainer_row = trainer_rows.get(event.name)
        t_billed = flt(trainer_row.billed) if trainer_row else 0
        t_paid = flt(trainer_row.paid) if trainer_row else 0

        ee_total = expense_entry_paid.get(event.name, 0)
        o_billed = other_billed.get(event.name, 0) + ee_total
        o_paid = other_paid_via_invoice.get(event.name, 0) + other_paid_direct.get(event.name, 0) + ee_total

        total_expenses_billed = t_billed + o_billed
        total_expenses = t_paid + o_paid
        net_profit = income - total_expenses

        event["total_invoiced"] = total_invoiced.get(event.name, 0)
        event["income_collected"] = income
        event["amount_due"] = max(total_invoiced.get(event.name, 0) - income, 0)
        event["trainer_billed"] = t_billed
        event["trainer_paid"] = t_paid
        event["other_billed"] = o_billed
        event["other_paid"] = o_paid
        event["total_expenses_billed"] = total_expenses_billed
        event["total_expenses"] = total_expenses
        event["amount_owed"] = max(total_expenses_billed - total_expenses, 0)
        event["net_profit"] = net_profit
        event["margin"] = round((net_profit / income * 100), 1) if income else 0
        data.append(event)

    return data
