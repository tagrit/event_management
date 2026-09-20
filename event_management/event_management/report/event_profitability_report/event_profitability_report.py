import frappe
from frappe.utils import flt


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
        {"label": "Income Collected", "fieldname": "income_collected", "fieldtype": "Currency", "width": 130},
        {"label": "Trainer Costs Paid", "fieldname": "trainer_paid", "fieldtype": "Currency", "width": 130},
        {"label": "Other Expenses Paid", "fieldname": "other_paid", "fieldtype": "Currency", "width": 140},
        {"label": "Total Expenses Paid", "fieldname": "total_expenses", "fieldtype": "Currency", "width": 140},
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

    income_via_invoice = {
        r.event_registration: flt(r.total) for r in frappe.db.sql("""
            SELECT event_registration, SUM(grand_total - outstanding_amount) as total
            FROM `tabSales Invoice`
            WHERE docstatus = 1 AND event_registration IN %(names)s
            GROUP BY event_registration
        """, {"names": event_names}, as_dict=1)
    }

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

    trainer_paid = {
        r.event_registration: flt(r.total) for r in frappe.db.sql("""
            SELECT event_registration, SUM(paid_amount) as total
            FROM `tabEvent Trainer`
            WHERE event_registration IN %(names)s
            GROUP BY event_registration
        """, {"names": event_names}, as_dict=1)
    }

    other_paid = {
        r.event_registration: flt(r.total) for r in frappe.db.sql("""
            SELECT event_registration, SUM(grand_total - outstanding_amount) as total
            FROM `tabPurchase Invoice`
            WHERE docstatus = 1 AND event_registration IN %(names)s
            AND (event_trainer IS NULL OR event_trainer = '')
            GROUP BY event_registration
        """, {"names": event_names}, as_dict=1)
    }

    data = []
    for event in events:
        income = income_via_invoice.get(event.name, 0) + income_direct.get(event.name, 0)
        t_paid = trainer_paid.get(event.name, 0)
        o_paid = other_paid.get(event.name, 0)
        total_expenses = t_paid + o_paid
        net_profit = income - total_expenses

        event["income_collected"] = income
        event["trainer_paid"] = t_paid
        event["other_paid"] = o_paid
        event["total_expenses"] = total_expenses
        event["net_profit"] = net_profit
        event["margin"] = round((net_profit / income * 100), 1) if income else 0
        data.append(event)

    return data
