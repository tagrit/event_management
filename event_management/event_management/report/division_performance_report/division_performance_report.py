import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Division", "fieldname": "division", "fieldtype": "Link", "options": "Division", "width": 120},
        {"label": "Total Events", "fieldname": "event_count", "fieldtype": "Int", "width": 100},
        {"label": "Total Delegates", "fieldname": "total_delegates", "fieldtype": "Int", "width": 120},
        {"label": "Confirmation Rate", "fieldname": "confirmation_rate", "fieldtype": "Percent", "width": 130},
        {"label": "Budgeted Revenue", "fieldname": "budgeted_revenue", "fieldtype": "Currency", "width": 140},
        {"label": "Income Collected", "fieldname": "income_collected", "fieldtype": "Currency", "width": 140},
        {"label": "Expenses Paid", "fieldname": "expenses_paid", "fieldtype": "Currency", "width": 130},
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

    where_clause = " AND ".join(conditions)

    divisions = frappe.db.sql(f"""
        SELECT
            er.division,
            COUNT(DISTINCT er.name) as event_count,
            COUNT(ed.name) as total_delegates,
            COALESCE(SUM(ed.confirmed), 0) as confirmed_delegates,
            SUM(er.revenue) as budgeted_revenue
        FROM `tabEvent Registration` er
        LEFT JOIN `tabEvent Delegate` ed ON ed.parent = er.name
        WHERE {where_clause}
        GROUP BY er.division
        ORDER BY event_count DESC
    """, values, as_dict=1)

    if not divisions:
        return []

    division_names = [d.division for d in divisions if d.division]

    income = {
        r.division: flt(r.total) for r in frappe.db.sql(f"""
            SELECT er.division, SUM(si.grand_total - si.outstanding_amount) as total
            FROM `tabSales Invoice` si
            INNER JOIN `tabEvent Registration` er ON er.name = si.event_registration
            WHERE si.docstatus = 1 AND {where_clause}
            GROUP BY er.division
        """, values, as_dict=1)
    }

    income_direct = {
        r.division: flt(r.total) for r in frappe.db.sql(f"""
            SELECT er.division, SUM(pe.paid_amount) as total
            FROM `tabPayment Entry` pe
            INNER JOIN `tabEvent Registration` er ON er.name = pe.event_registration
            WHERE pe.docstatus = 1 AND pe.payment_type = 'Receive' AND {where_clause}
            AND NOT EXISTS (SELECT 1 FROM `tabPayment Entry Reference` per WHERE per.parent = pe.name)
            GROUP BY er.division
        """, values, as_dict=1)
    }

    trainer_paid = {
        r.division: flt(r.total) for r in frappe.db.sql(f"""
            SELECT er.division, SUM(et.paid_amount) as total
            FROM `tabEvent Trainer` et
            INNER JOIN `tabEvent Registration` er ON er.name = et.event_registration
            WHERE {where_clause}
            GROUP BY er.division
        """, values, as_dict=1)
    }

    other_paid = {
        r.division: flt(r.total) for r in frappe.db.sql(f"""
            SELECT er.division, SUM(pi.grand_total - pi.outstanding_amount) as total
            FROM `tabPurchase Invoice` pi
            INNER JOIN `tabEvent Registration` er ON er.name = pi.event_registration
            WHERE pi.docstatus = 1 AND (pi.event_trainer IS NULL OR pi.event_trainer = '') AND {where_clause}
            GROUP BY er.division
        """, values, as_dict=1)
    }

    data = []
    for row in divisions:
        div = row.division
        collected = income.get(div, 0) + income_direct.get(div, 0)
        expenses = trainer_paid.get(div, 0) + other_paid.get(div, 0)
        net_profit = collected - expenses

        row["income_collected"] = collected
        row["expenses_paid"] = expenses
        row["net_profit"] = net_profit
        row["margin"] = round((net_profit / collected * 100), 1) if collected else 0
        row["confirmation_rate"] = round((row.confirmed_delegates / row.total_delegates * 100), 1) if row.total_delegates else 0
        data.append(row)

    return data
