import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Trainer", "fieldname": "trainer", "fieldtype": "Link", "options": "Supplier", "width": 160},
        {"label": "Trainer Name", "fieldname": "trainer_name", "fieldtype": "Data", "width": 160},
        {"label": "Event", "fieldname": "event_registration", "fieldtype": "Link", "options": "Event Registration", "width": 150},
        {"label": "Event Name", "fieldname": "event_name", "fieldtype": "Data", "width": 200},
        {"label": "Division", "fieldname": "division", "fieldtype": "Link", "options": "Division", "width": 100},
        {"label": "Rate Type", "fieldname": "rate_type", "fieldtype": "Data", "width": 110},
        {"label": "Contracted Amount", "fieldname": "total_amount", "fieldtype": "Currency", "width": 130},
        {"label": "Paid Amount", "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
        {"label": "Balance", "fieldname": "balance", "fieldtype": "Currency", "width": 110},
        {"label": "Payment Status", "fieldname": "payment_status", "fieldtype": "Data", "width": 120},
        {"label": "Contract Sent", "fieldname": "contract_sent", "fieldtype": "Check", "width": 100},
        {"label": "Contract Signed", "fieldname": "contract_signed", "fieldtype": "Check", "width": 110},
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

    if filters.get("trainer"):
        conditions.append("et.trainer = %(trainer)s")
        values["trainer"] = filters.trainer

    if filters.get("division"):
        conditions.append("er.division = %(division)s")
        values["division"] = filters.division

    if filters.get("event_registration"):
        conditions.append("et.event_registration = %(event_registration)s")
        values["event_registration"] = filters.event_registration

    if filters.get("payment_status"):
        conditions.append("et.payment_status = %(payment_status)s")
        values["payment_status"] = filters.payment_status

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(f"""
        SELECT
            et.trainer, et.trainer_name, et.event_registration, et.rate_type,
            et.total_amount, et.paid_amount, et.payment_status,
            et.contract_sent, et.contract_signed,
            er.event_name, er.division
        FROM `tabEvent Trainer` et
        INNER JOIN `tabEvent Registration` er ON er.name = et.event_registration
        WHERE {where_clause}
        ORDER BY er.start_date DESC
    """, values, as_dict=1)

    for row in rows:
        row["balance"] = flt(row.total_amount) - flt(row.paid_amount)

    return rows
