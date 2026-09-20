frappe.query_reports["Organization Training History Report"] = {
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
            fieldname: "organization_name",
            label: __("Organization"),
            fieldtype: "Link",
            options: "Event Organization"
        },
        {
            fieldname: "division",
            label: __("Division"),
            fieldtype: "Link",
            options: "Division"
        }
    ]
};
