import frappe

from event_management.event_management.utils import get_event_voucher_list


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": "Account", "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 180},
        {"label": "Voucher Type", "fieldname": "voucher_type", "fieldtype": "Data", "width": 120},
        {"label": "Voucher No", "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 160},
        {"label": "Against", "fieldname": "against", "fieldtype": "Data", "width": 160},
        {"label": "Party Type", "fieldname": "party_type", "fieldtype": "Data", "width": 90},
        {"label": "Party", "fieldname": "party", "fieldtype": "Dynamic Link", "options": "party_type", "width": 150},
        {"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": "Credit", "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": "Remarks", "fieldname": "remarks", "fieldtype": "Data", "width": 200},
    ]


def get_data(filters):
    event_registration_name = filters.get("event_registration")
    if not event_registration_name:
        return []

    vouchers = get_event_voucher_list(event_registration_name)
    if not vouchers:
        return []

    placeholders = ", ".join(["(%s, %s)"] * len(vouchers))
    params = [item for pair in vouchers for item in pair]

    return frappe.db.sql(f"""
        SELECT posting_date, account, voucher_type, voucher_no, against,
            party_type, party, debit, credit, remarks
        FROM `tabGL Entry`
        WHERE is_cancelled = 0
        AND (voucher_type, voucher_no) IN ({placeholders})
        ORDER BY posting_date, voucher_type, voucher_no
    """, params, as_dict=1)
