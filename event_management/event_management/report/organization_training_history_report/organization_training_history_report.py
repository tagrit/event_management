import frappe

from event_management.event_management.utils import is_finance_user


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    columns = [
        {"label": "Organization", "fieldname": "organization_name", "fieldtype": "Link", "options": "Event Organization", "width": 200},
        {"label": "Total Trainings", "fieldname": "event_count", "fieldtype": "Int", "width": 120},
        {"label": "Total Delegates", "fieldname": "total_delegates", "fieldtype": "Int", "width": 120},
        {"label": "Confirmed Delegates", "fieldname": "confirmed_delegates", "fieldtype": "Int", "width": 140},
        {"label": "Last Training Date", "fieldname": "last_training_date", "fieldtype": "Date", "width": 140},
    ]

    if is_finance_user():
        columns.insert(4, {"label": "Total Revenue (Budgeted)", "fieldname": "total_revenue", "fieldtype": "Currency", "width": 160})

    return columns


def get_data(filters):
    conditions = ["er.docstatus = 1"]
    values = {}

    if filters.get("from_date"):
        conditions.append("er.start_date >= %(from_date)s")
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        conditions.append("er.start_date <= %(to_date)s")
        values["to_date"] = filters.to_date

    if filters.get("organization_name"):
        conditions.append("er.organization_name = %(organization_name)s")
        values["organization_name"] = filters.organization_name

    if filters.get("division"):
        conditions.append("er.division = %(division)s")
        values["division"] = filters.division

    where_clause = " AND ".join(conditions)

    return frappe.db.sql(f"""
        SELECT
            er.organization_name,
            COUNT(DISTINCT er.name) as event_count,
            COUNT(ed.name) as total_delegates,
            COALESCE(SUM(ed.confirmed), 0) as confirmed_delegates,
            SUM(er.revenue) as total_revenue,
            MAX(er.start_date) as last_training_date
        FROM `tabEvent Registration` er
        LEFT JOIN `tabEvent Delegate` ed ON ed.parent = er.name
        WHERE {where_clause}
        GROUP BY er.organization_name
        ORDER BY event_count DESC
    """, values, as_dict=1)
