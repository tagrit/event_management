import frappe

from event_management.event_management.utils import is_finance_user


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    columns = [
        {"label": "Event", "fieldname": "name", "fieldtype": "Link", "options": "Event Registration", "width": 160},
        {"label": "Event Name", "fieldname": "event_name", "fieldtype": "Data", "width": 220},
        {"label": "Organization", "fieldname": "organization_name", "fieldtype": "Link", "options": "Event Organization", "width": 160},
        {"label": "Division", "fieldname": "division", "fieldtype": "Link", "options": "Division", "width": 100},
        {"label": "Location", "fieldname": "event_location", "fieldtype": "Link", "options": "Event Location", "width": 120},
        {"label": "Start Date", "fieldname": "start_date", "fieldtype": "Date", "width": 100},
        {"label": "End Date", "fieldname": "end_date", "fieldtype": "Date", "width": 100},
        {"label": "Setup", "fieldname": "setup", "fieldtype": "Data", "width": 90},
        {"label": "Type", "fieldname": "type", "fieldtype": "Data", "width": 90},
        {"label": "Delegates", "fieldname": "number_of_delegates", "fieldtype": "Int", "width": 90},
        {"label": "Confirmed", "fieldname": "confirmed_delegates", "fieldtype": "Int", "width": 90},
        {"label": "Pending", "fieldname": "pending_delegates", "fieldtype": "Int", "width": 90},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 130},
    ]

    if is_finance_user():
        columns.append({"label": "Revenue (Budgeted)", "fieldname": "revenue", "fieldtype": "Currency", "width": 130})

    return columns


def get_data(filters):
    conditions, values = build_conditions(filters)

    rows = frappe.db.sql(f"""
        SELECT
            er.name, er.event_name, er.organization_name, er.division, er.event_location,
            er.start_date, er.end_date, er.setup, er.type, er.number_of_delegates,
            er.revenue, er.docstatus, er.all_confirmed,
            COALESCE(SUM(ed.confirmed), 0) as confirmed_delegates,
            COUNT(ed.name) - COALESCE(SUM(ed.confirmed), 0) as pending_delegates
        FROM `tabEvent Registration` er
        LEFT JOIN `tabEvent Delegate` ed ON ed.parent = er.name
        WHERE {conditions}
        GROUP BY er.name
        ORDER BY er.start_date DESC
    """, values, as_dict=1)

    status_filter = filters.get("status")
    result = []
    for row in rows:
        if row.docstatus == 0:
            row["status"] = "Draft"
        elif row.all_confirmed:
            row["status"] = "Confirmed"
        else:
            row["status"] = "Pending Confirmation"

        if status_filter and row["status"] != status_filter:
            continue

        result.append(row)

    return result


def build_conditions(filters):
    conditions = ["er.docstatus < 2"]
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

    if filters.get("event_location"):
        conditions.append("er.event_location = %(event_location)s")
        values["event_location"] = filters.event_location

    return " AND ".join(conditions), values
