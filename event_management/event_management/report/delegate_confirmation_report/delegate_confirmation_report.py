import frappe


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "First Name", "fieldname": "first_name", "fieldtype": "Data", "width": 120},
        {"label": "Last Name", "fieldname": "last_name", "fieldtype": "Data", "width": 120},
        {"label": "Email", "fieldname": "email", "fieldtype": "Data", "width": 180},
        {"label": "Phone", "fieldname": "phone", "fieldtype": "Data", "width": 120},
        {"label": "Event", "fieldname": "parent", "fieldtype": "Link", "options": "Event Registration", "width": 150},
        {"label": "Event Name", "fieldname": "event_name", "fieldtype": "Data", "width": 200},
        {"label": "Organization", "fieldname": "organization_name", "fieldtype": "Link", "options": "Event Organization", "width": 150},
        {"label": "Division", "fieldname": "division", "fieldtype": "Link", "options": "Division", "width": 100},
        {"label": "Confirmed", "fieldname": "confirmed_label", "fieldtype": "Data", "width": 100},
        {"label": "Confirmed By", "fieldname": "confirmed_by", "fieldtype": "Link", "options": "User", "width": 150},
        {"label": "Confirmation Date", "fieldname": "confirmation_date", "fieldtype": "Datetime", "width": 160},
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

    if filters.get("event_registration"):
        conditions.append("er.name = %(event_registration)s")
        values["event_registration"] = filters.event_registration

    if filters.get("confirmed") == "Confirmed":
        conditions.append("ed.confirmed = 1")
    elif filters.get("confirmed") == "Pending":
        conditions.append("ed.confirmed = 0")

    if filters.get("confirmed_by"):
        conditions.append("ed.confirmed_by = %(confirmed_by)s")
        values["confirmed_by"] = filters.confirmed_by

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(f"""
        SELECT
            ed.first_name, ed.last_name, ed.email, ed.phone,
            ed.parent, ed.confirmed, ed.confirmed_by, ed.confirmation_date,
            er.event_name, er.organization_name, er.division
        FROM `tabEvent Delegate` ed
        INNER JOIN `tabEvent Registration` er ON er.name = ed.parent
        WHERE {where_clause}
        ORDER BY er.start_date DESC, ed.idx
    """, values, as_dict=1)

    for row in rows:
        row["confirmed_label"] = "Confirmed" if row.confirmed else "Pending"

    return rows
