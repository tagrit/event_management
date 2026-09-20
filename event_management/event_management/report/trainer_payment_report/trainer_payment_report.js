frappe.query_reports["Trainer Payment Report"] = {
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
            fieldname: "trainer",
            label: __("Trainer"),
            fieldtype: "Link",
            options: "Supplier",
            get_query: () => ({ filters: { is_trainer: 1 } })
        },
        {
            fieldname: "division",
            label: __("Division"),
            fieldtype: "Link",
            options: "Division"
        },
        {
            fieldname: "event_registration",
            label: __("Event"),
            fieldtype: "Link",
            options: "Event Registration"
        },
        {
            fieldname: "payment_status",
            label: __("Payment Status"),
            fieldtype: "Select",
            options: "\nPaid\nPartially Paid\nUnpaid"
        }
    ]
};
