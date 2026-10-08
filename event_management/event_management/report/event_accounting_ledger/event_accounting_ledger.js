frappe.query_reports["Event Accounting Ledger"] = {
    filters: [
        {
            fieldname: "event_registration",
            label: __("Event"),
            fieldtype: "Link",
            options: "Event Registration",
            reqd: 1
        }
    ]
};
