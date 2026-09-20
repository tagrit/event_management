frappe.ui.form.on('Event Trainer', {
    refresh: function(frm) {
        // Make email and mobile_no fields editable
        frm.set_df_property('email', 'read_only', 0);
        frm.set_df_property('mobile_no', 'read_only', 0);
    },


   trainer: function(frm) {
    // Capture the trainer ID immediately to avoid scope issues
    const selected_trainer = frm.doc.trainer;

       if (selected_trainer) {

        // 1. Try Supplier first
        frappe.db.get_value('Supplier', selected_trainer, ['email_id', 'mobile_no'], (r) => {
            let email = r ? r.email_id : null;
            let mobile = r ? r.mobile_no : null;

            if (!email || !mobile) {
                // 2. Fallback using the captured variable 'selected_trainer'
                frappe.db.get_list('Event Trainer', {
                    filters: {
                        'trainer': selected_trainer,
                        'name': ['!=', frm.doc.name] // Filter out current record
                    },
                    fields: ['email', 'mobile_no'],
                    order_by: 'creation desc',
                    limit: 1
                }).then(records => {
                    // Log the captured variable, not the doc property
                    console.log("Using captured trainer ID:", selected_trainer);
                    console.log("Historical records found:", records);

                    if (records && records.length > 0) {
                        const last_record = records[0];
                        if (!email) email = last_record.email;
                        if (!mobile) mobile = last_record.mobile_no;
                    }

                    frm.set_value('email', email || '');
                    frm.set_value('mobile_no', mobile || '');
                });
            } else {
                frm.set_value('email', email);
                frm.set_value('mobile_no', mobile);
            }
        });
    }
},

    validate: function(frm) {
        // Ensure email and mobile are filled before saving
        if (!frm.doc.email) {
            frappe.msgprint(__('Email is mandatory. Please enter the trainer\'s email address.'));
            frappe.validated = false;
        }
        if (!frm.doc.mobile_no) {
            frappe.msgprint(__('Mobile number is mandatory. Please enter the trainer\'s mobile number.'));
            frappe.validated = false;
        }
    }
});
