frappe.query_reports["Event Summary Report"] = {
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
            fieldname: "division",
            label: __("Division"),
            fieldtype: "Link",
            options: "Division"
        },
        {
            fieldname: "organization_name",
            label: __("Organization"),
            fieldtype: "Link",
            options: "Event Organization"
        },
        {
            fieldname: "event_location",
            label: __("Location"),
            fieldtype: "Link",
            options: "Event Location"
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nDraft\nConfirmed\nPending Confirmation"
        }
    ]
};
