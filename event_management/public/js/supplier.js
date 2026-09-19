frappe.ui.form.on('Supplier', {
    refresh: function (frm) {
        if (frm.doc.is_trainer && !frm.is_new()) {
            frm.add_custom_button(__('View Trainer Profile'), function () {
                frappe.set_route('trainer-profile', frm.doc.name);
            });
        }
    }
});
