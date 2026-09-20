import frappe


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Staff", "fieldname": "confirmed_by", "fieldtype": "Link", "options": "User", "width": 200},
        {"label": "Delegates Confirmed", "fieldname": "delegates_confirmed", "fieldtype": "Int", "width": 150},
        {"label": "Events Involved", "fieldname": "events_involved", "fieldtype": "Int", "width": 130},
        {"label": "Last Confirmation Date", "fieldname": "last_confirmation_date", "fieldtype": "Datetime", "width": 170},
    ]


def get_data(filters):
    conditions = ["er.docstatus = 1", "ed.confirmed = 1", "ed.confirmed_by IS NOT NULL", "ed.confirmed_by != ''"]
    values = {}

    if filters.get("from_date"):
        conditions.append("er.start_date >= %(from_date)s")
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        conditions.append("er.start_date <= %(to_date)s")
        values["to_date"] = filters.to_date

    if filters.get("staff"):
        conditions.append("ed.confirmed_by = %(staff)s")
        values["staff"] = filters.staff

    if filters.get("division"):
        conditions.append("er.division = %(division)s")
        values["division"] = filters.division

    where_clause = " AND ".join(conditions)

    return frappe.db.sql(f"""
        SELECT
            ed.confirmed_by,
            COUNT(ed.name) as delegates_confirmed,
            COUNT(DISTINCT ed.parent) as events_involved,
            MAX(ed.confirmation_date) as last_confirmation_date
        FROM `tabEvent Delegate` ed
        INNER JOIN `tabEvent Registration` er ON er.name = ed.parent
        WHERE {where_clause}
        GROUP BY ed.confirmed_by
        ORDER BY delegates_confirmed DESC
    """, values, as_dict=1)
