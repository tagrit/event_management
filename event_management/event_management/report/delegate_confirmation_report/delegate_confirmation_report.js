frappe.query_reports["Delegate Confirmation Report"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("Event From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.now_date(), -12)
        },
        {
            fieldname: "to_date",
            label: __("Event To Date"),
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
            fieldname: "event_registration",
            label: __("Event"),
            fieldtype: "Link",
            options: "Event Registration"
        },
        {
            fieldname: "confirmed",
            label: __("Confirmation Status"),
            fieldtype: "Select",
            options: "\nConfirmed\nPending"
        },
        {
            fieldname: "confirmed_by",
            label: __("Confirmed By (Staff)"),
            fieldtype: "Link",
            options: "User"
        }
    ]
};
