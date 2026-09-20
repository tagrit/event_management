import frappe
from frappe.utils import flt

from event_management.event_management.utils import is_finance_user


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    columns = [
        {"label": "Trainer", "fieldname": "trainer", "fieldtype": "Link", "options": "Supplier", "width": 180},
        {"label": "Area of Expertise", "fieldname": "area_of_expertise", "fieldtype": "Data", "width": 180},
        {"label": "Events Trained", "fieldname": "event_count", "fieldtype": "Int", "width": 110},
        {"label": "Email", "fieldname": "email_id", "fieldtype": "Data", "width": 180},
        {"label": "Mobile", "fieldname": "mobile_no", "fieldtype": "Data", "width": 120},
    ]

    if is_finance_user():
        columns[3:3] = [
            {"label": "Total Contracted", "fieldname": "total_earned", "fieldtype": "Currency", "width": 130},
            {"label": "Total Paid", "fieldname": "total_paid", "fieldtype": "Currency", "width": 120},
            {"label": "Outstanding", "fieldname": "outstanding", "fieldtype": "Currency", "width": 120},
        ]

    return columns


def get_data(filters):
    conditions = ["s.is_trainer = 1"]
    values = {}

    if filters.get("trainer"):
        conditions.append("s.name = %(trainer)s")
        values["trainer"] = filters.trainer

    join_conditions = ["et.trainer = s.name"]

    if filters.get("from_date"):
        join_conditions.append("er.start_date >= %(from_date)s")
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        join_conditions.append("er.start_date <= %(to_date)s")
        values["to_date"] = filters.to_date

    if filters.get("division"):
        join_conditions.append("er.division = %(division)s")
        values["division"] = filters.division

    where_clause = " AND ".join(conditions)
    join_clause = " AND ".join(join_conditions)

    rows = frappe.db.sql(f"""
        SELECT
            s.name as trainer, s.supplier_name, s.area_of_expertise, s.email_id, s.mobile_no,
            COUNT(DISTINCT et.name) as event_count,
            SUM(et.total_amount) as total_earned,
            SUM(et.paid_amount) as total_paid
        FROM `tabSupplier` s
        LEFT JOIN `tabEvent Trainer` et ON {join_clause}
        LEFT JOIN `tabEvent Registration` er ON er.name = et.event_registration
        WHERE {where_clause}
        GROUP BY s.name
        ORDER BY event_count DESC
    """, values, as_dict=1)

    for row in rows:
        row["total_earned"] = flt(row.total_earned)
        row["total_paid"] = flt(row.total_paid)
        row["outstanding"] = row["total_earned"] - row["total_paid"]

    return rows
