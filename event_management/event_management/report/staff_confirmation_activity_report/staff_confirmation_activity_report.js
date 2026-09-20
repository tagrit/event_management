frappe.query_reports["Staff Confirmation Activity Report"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.now_date(), -12)
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.now_date(), 12)
        },
        {
            fieldname: "staff",
            label: __("Staff (Confirmed By)"),
            fieldtype: "Link",
            options: "User"
        },
        {
            fieldname: "division",
            label: __("Division"),
            fieldtype: "Link",
            options: "Division"
        }
    ]
};
