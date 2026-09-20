frappe.ui.form.on('Event Registration', {
    location: function(frm) {
        frm.set_value('venue', '');
        
        if (frm.doc.location) {
            frm.set_query('venue', function() {
                return {
                    filters: {
                        'location': frm.doc.location
                    }
                };
            });
        }
    },
    
    number_of_delegates: function(frm) {
        calculate_revenue(frm);
    },
    
    charges_per_delegate: function(frm) {
        calculate_revenue(frm);
    },
    
    refresh: function(frm) {
        if (frm.doc.docstatus === 1) {
            load_confirmation_summary(frm);
        }
        
        if ((frm.doc.docstatus === 1 || frm.doc.amended_from) && !frm.doc.welcome_email_sent) {
            frm.add_custom_button(__('Send Welcome Email to Confirmed'), function() {
                frm.set_df_property('send_welcome_email_btn'); 
                
                frappe.confirm(__('Are you sure you want to send welcome emails?'), () => {
                    frappe.call({
                        method: 'event_management.event_management.doctype.event_registration.event_registration.send_welcome_email_to_confirmed',
                        args: {
                            event_name: frm.doc.name
                        },
                        btn: $('.primary-action'),
                        callback: function(r) {
                            frm.reload_doc();
                        },
                        error: function() {
                            frm.set_df_property('send_welcome_email_btn', 'disabled', 0);
                        }
                    });
                });
            });
        }
        
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Send Confirmation Report'), function() {
                frappe.call({
                    method: 'event_management.event_management.doctype.event_registration.event_registration.send_confirmation_list_email',
                    callback: function(r) {
                        frappe.msgprint(__('Report sent!'));
                    }
                });
            }, __('Actions'));
        }
        
        if (frm.doc.all_confirmed && frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Add Trainer'), function() {
                frappe.new_doc('Event Trainer', {
                    event_registration: frm.doc.name
                });
            }, __("Training Management"));

            frm.add_custom_button(__('View Trainers'), function() {
                show_trainers_dialog(frm);
            }, __("Training Management"));
        }
        
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Trainer Summary'), function() {
                show_trainer_payment_summary(frm);
            }, __("Training Management"));
        }
    }
});

function calculate_revenue(frm) {
    if (frm.doc.number_of_delegates && frm.doc.charges_per_delegate) {
        let revenue = frm.doc.number_of_delegates * frm.doc.charges_per_delegate;
        frm.set_value('revenue', revenue);
    }
}

function load_confirmation_summary(frm) {
    frappe.call({
        method: 'event_management.event_management.doctype.event_registration.event_registration.get_confirmation_summary',
        args: {
            event_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                display_confirmation_summary(frm, r.message);
            }
        }
    });
}

function display_confirmation_summary(frm, data) {
    let html = `
        <div style="padding: 15px; background-color: #f8f9fa; border-radius: 5px; margin-top: 10px;">
            <h4 style="margin-top: 0;">Confirmation Status</h4>
            
            <div style="display: flex; gap: 20px; margin: 15px 0;">
                <div style="flex: 1; text-align: center; padding: 15px; background-color: #4CAF50; color: white; border-radius: 5px;">
                    <div style="font-size: 24px; font-weight: bold;">${data.confirmed}</div>
                    <div>Confirmed</div>
                </div>
                <div style="flex: 1; text-align: center; padding: 15px; background-color: #ff9800; color: white; border-radius: 5px;">
                    <div style="font-size: 24px; font-weight: bold;">${data.pending}</div>
                    <div>Pending</div>
                </div>
                <div style="flex: 1; text-align: center; padding: 15px; background-color: #2196F3; color: white; border-radius: 5px;">
                    <div style="font-size: 24px; font-weight: bold;">${data.percentage}%</div>
                    <div>Completion</div>
                </div>
            </div>
            
            <table style="width: 100%; margin-top: 15px; border-collapse: collapse;">
                <thead>
                    <tr style="background-color: #e9ecef;">
                        <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Delegate</th>
                        <th style="padding: 8px; text-align: center; border: 1px solid #ddd;">Status</th>
                        <th style="padding: 8px; text-align: center; border: 1px solid #ddd;">Confirmed On</th>
                        <th style="padding: 8px; text-align: center; border: 1px solid #ddd;">Action</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    data.delegates.forEach(function(delegate) {
        let status_color = delegate.confirmed ? '#d4edda' : '#fff3cd';
        let status_icon = delegate.confirmed ? '✓' : '✗';
        let status_text = delegate.confirmed ? 'Confirmed' : 'Pending';
        let conf_date = delegate.confirmation_date || 'N/A';
        let resend_btn = !delegate.confirmed ? 
            `<button class="btn btn-xs btn-default" onclick="resend_invitation('${frm.doc.name}', '${delegate.email}')">Resend</button>` : 
            '-';
        
        html += `
            <tr style="background-color: ${status_color};">
                <td style="padding: 8px; border: 1px solid #ddd;">${delegate.name}</td>
                <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">${status_icon} ${status_text}</td>
                <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">${conf_date}</td>
                <td style="padding: 8px; text-align: center; border: 1px solid #ddd;">${resend_btn}</td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    frm.get_field('confirmation_summary').$wrapper.html(html);
}

window.resend_invitation = function(event_name, email) {
    frappe.call({
        method: 'event_management.event_management.doctype.event_registration.event_registration.resend_invitation',
        args: {
            event_name: event_name,
            delegate_email: email
        },
        callback: function(r) {
            frappe.show_alert({
                message: 'Invitation resent!',
                indicator: 'green'
            });
        }
    });
};

function show_trainers_dialog(frm) {
    // Force reload from database to get fresh data
    frappe.call({
        method: 'event_management.event_management.doctype.event_trainer.event_trainer.get_trainers_with_fresh_status',
        args: {
            event_registration: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                show_trainers_table(frm, r.message);
            } else {
                frappe.msgprint(__('No trainers assigned yet. Click "Add Trainers" to assign.'));
            }
        }
    });
}

function show_trainers_table(frm, trainers) {
    let html = `
        <div id="trainers-table-container">
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>Trainer Name</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>Rate Type</th>
                    <th>Amount</th>
                    <th>Paid</th>
                    <th>Balance</th>
                    <th>Contract</th>
                    <th>Payment</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="trainers-tbody">
    `;
    
    trainers.forEach(trainer => {
        const contract_badge = trainer.contract_sent 
            ? '<span class="badge badge-success">Sent</span>' 
            : '<span class="badge badge-warning">Pending</span>';
        
        const payment_color = {
            'Paid': 'success',
            'Partially Paid': 'warning',
            'Unpaid': 'danger'
        }[trainer.payment_status] || 'secondary';
        
        const payment_badge = `<span class="badge badge-${payment_color}">${trainer.payment_status}</span>`;
        const balance = trainer.total_amount - (trainer.paid_amount || 0);
        
        html += `
            <tr data-trainer="${trainer.name}">
                <td><a href="/app/event-trainer/${trainer.name}">${trainer.trainer_name}</a></td>
                <td>${trainer.email || '-'}</td>
                <td>${trainer.mobile_no || '-'}</td>
                <td>${trainer.rate_type}</td>
                <td>${format_currency(trainer.total_amount)}</td>
                <td class="text-success">${format_currency(trainer.paid_amount || 0)}</td>
                <td class="text-danger">${format_currency(balance)}</td>
                <td>${contract_badge}</td>
                <td>${payment_badge}</td>
                <td style="text-align: center;">
                    <div class="dropdown">
                        <button class="btn btn-default btn-sm" type="button" 
                                data-toggle="dropdown" aria-haspopup="true" aria-expanded="false"
                                style="padding: 4px 8px; background: transparent; border: none; font-size: 18px; color: #8d99a6;">
                            ⋮
                        </button>
                        <ul class="dropdown-menu dropdown-menu-right" style="min-width: 180px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); border-radius: 6px;">
                            <li>
                                <a href="#" onclick="event.preventDefault(); frappe.set_route('Form', 'Event Trainer', '${trainer.name}');"
                                   style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                    <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                                        <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/>
                                    </svg>
                                    <span>View Details</span>
                                </a>
                            </li>
                            <li class="divider" style="margin: 4px 0;"></li>
                            <li>
                                <a href="#" onclick="event.preventDefault(); send_contract('${trainer.name}');"
                                   style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                    <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd"/>
                                    </svg>
                                    <span>Send Contract</span>
                                </a>
                            </li>
                            <li>
                                <a href="#" onclick="event.preventDefault(); create_invoice('${trainer.name}');"
                                   style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                    <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                        <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
                                        <path fill-rule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clip-rule="evenodd"/>
                                    </svg>
                                    <span>Create Invoice</span>
                                </a>
                            </li>
                            <li>
                                <a href="#" onclick="event.preventDefault(); make_payment('${trainer.name}');"
                                   style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                    <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                        <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z"/>
                                        <path fill-rule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z" clip-rule="evenodd"/>
                                    </svg>
                                    <span>Record Payment</span>
                                </a>
                            </li>
                            <li class="divider" style="margin: 4px 0;"></li>
                            <li>
                                <a href="#" onclick="event.preventDefault(); view_payments('${trainer.name}');"
                                   style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                    <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
                                    </svg>
                                    <span>Payment History</span>
                                </a>
                            </li>
                        </ul>
                    </div>
                </td>
            </tr>
        `;
    });
    
    html += '</tbody></table></div>';
    
    const dialog = new frappe.ui.Dialog({
        title: __('Event Trainers'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'trainers_html',
                options: html
            }
        ],
        primary_action_label: __('Add New Trainer'),
        primary_action: function() {
            dialog.hide();
            frappe.new_doc('Event Trainer', {
                event_registration: frm.doc.name
            });
        }
    });
    
    // Store dialog reference globally for refresh
    window.current_trainers_dialog = dialog;
    window.current_event_registration = frm.doc.name;
    
    dialog.show();
}

// NEW: Function to refresh trainers dialog
window.refresh_trainers_dialog = function() {
    if (window.current_trainers_dialog && window.current_event_registration) {
        frappe.call({
            method: 'event_management.event_management.doctype.event_trainer.event_trainer.get_trainers_with_fresh_status',
            args: {
                event_registration: window.current_event_registration
            },
            callback: function(r) {
                if (r.message && window.current_trainers_dialog) {
                    // Update the table content
                    let html = '';
                    r.message.forEach(trainer => {
                        const contract_badge = trainer.contract_sent 
                            ? '<span class="badge badge-success">Sent</span>' 
                            : '<span class="badge badge-warning">Pending</span>';
                        
                        const payment_color = {
                            'Paid': 'success',
                            'Partially Paid': 'warning',
                            'Unpaid': 'danger'
                        }[trainer.payment_status] || 'secondary';
                        
                        const payment_badge = `<span class="badge badge-${payment_color}">${trainer.payment_status}</span>`;
                        const balance = trainer.total_amount - (trainer.paid_amount || 0);
                        
                        html += `
                            <tr data-trainer="${trainer.name}">
                                <td><a href="/app/event-trainer/${trainer.name}">${trainer.trainer_name}</a></td>
                                <td>${trainer.email || '-'}</td>
                                <td>${trainer.mobile_no || '-'}</td>
                                <td>${trainer.rate_type}</td>
                                <td>${format_currency(trainer.total_amount)}</td>
                                <td class="text-success">${format_currency(trainer.paid_amount || 0)}</td>
                                <td class="text-danger">${format_currency(balance)}</td>
                                <td>${contract_badge}</td>
                                <td>${payment_badge}</td>
                                <td style="text-align: center;">
                    <div class="dropdown">
                        <button class="btn btn-default btn-sm" type="button" 
                                data-toggle="dropdown" aria-haspopup="true" aria-expanded="false"
                                style="padding: 4px 8px; background: transparent; border: none; font-size: 18px; color: #8d99a6;">
                            ⋮
                        </button>
                        <ul class="dropdown-menu dropdown-menu-right" style="min-width: 180px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); border-radius: 6px;">
                            <li>
                                <a href="#" onclick="event.preventDefault(); frappe.set_route('Form', 'Event Trainer', '${trainer.name}');"
                                   style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                    <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                                        <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/>
                                    </svg>
                                    <span>View Details</span>
                                </a>
                            </li>
                            <li class="divider" style="margin: 4px 0;"></li>
                            <li>
                                <a href="#" onclick="event.preventDefault(); send_contract('${trainer.name}');"
                                   style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                    <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd"/>
                                    </svg>
                                    <span>Send Contract</span>
                                </a>
                            </li>
                            <li>
                                <a href="#" onclick="event.preventDefault(); create_invoice('${trainer.name}');"
                                   style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                    <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                        <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
                                        <path fill-rule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clip-rule="evenodd"/>
                                    </svg>
                                    <span>Create Invoice</span>
                                </a>
                            </li>
                            <li>
                                <a href="#" onclick="event.preventDefault(); make_payment('${trainer.name}');"
                                   style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                    <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                        <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z"/>
                                        <path fill-rule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z" clip-rule="evenodd"/>
                                    </svg>
                                    <span>Record Payment</span>
                                </a>
                            </li>
                            <li class="divider" style="margin: 4px 0;"></li>
                            <li>
                                <a href="#" onclick="event.preventDefault(); view_payments('${trainer.name}');"
                                   style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                    <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
                                    </svg>
                                    <span>Payment History</span>
                                </a>
                            </li>
                        </ul>
                    </div>
                </td>
                            </tr>
                        `;
                    });
                    
                    // Update tbody content
                    $('#trainers-tbody').html(html);
                }
            }
        });
    }
}

window.send_contract = function(event_trainer_name) {
    frappe.confirm(__('Send contract to this trainer?'), function() {
        frappe.call({
            method: 'event_management.event_management.doctype.event_trainer.event_trainer.send_trainer_contract',
            args: { event_trainer_name: event_trainer_name },
            callback: function(r) {
                if (!r.exc) {
                    frappe.show_alert({
                        message: __('Contract sent successfully'),
                        indicator: 'green'
                    });
                    // Refresh the dialog
                    window.refresh_trainers_dialog();
                }
            }
        });
    });
}

// FIXED: Check for existing invoice before creating
window.create_invoice = function(event_trainer_name) {
    // First check if invoice already exists
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Purchase Invoice',
            filters: {
                event_trainer: event_trainer_name,
                docstatus: ['<', 2]  // Draft or Submitted (not cancelled)
            },
            fields: ['name', 'docstatus', 'grand_total', 'outstanding_amount'],
            limit: 1
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                const existing_invoice = r.message[0];
                const status = existing_invoice.docstatus === 0 ? 'Draft' : 'Submitted';
                
                frappe.confirm(
                    __('An invoice ({0}) already exists for this trainer in {1} status. Do you want to open it instead?', 
                       [existing_invoice.name, status]),
                    function() {
                        // Open existing invoice
                        frappe.set_route('Form', 'Purchase Invoice', existing_invoice.name);
                    },
                    function() {
                        // User chose not to open - do nothing
                    }
                );
            } else {
                // No existing invoice, create new one
                create_new_invoice(event_trainer_name);
            }
        }
    });
}

function create_new_invoice(event_trainer_name) {
    frappe.call({
        method: 'event_management.event_management.doctype.event_trainer.event_trainer.make_purchase_invoice',
        args: { source_name: event_trainer_name },
        freeze: true,
        freeze_message: __('Creating Purchase Invoice...'),
        callback: function(r) {
            if (r.message) {
                frappe.model.sync(r.message);
                frappe.set_route('Form', r.message.doctype, r.message.name);
            }
        },
        error: function() {
            frappe.msgprint(__('Failed to create invoice'));
        }
    });
}

// UPDATED: Payment creation with dialog refresh
window.make_payment = function(event_trainer_name) {
    frappe.call({
        method: 'event_management.event_management.doctype.event_trainer.event_trainer.get_trainer_payment_summary',
        args: { event_trainer_name: event_trainer_name },
        callback: function(r) {
            if (r.message) {
                show_make_payment_dialog(event_trainer_name, r.message);
            }
        }
    });
}

// UPDATED: Payment dialog with auto-refresh after payment
function show_make_payment_dialog(event_trainer_name, data) {
    const balance = data.balance;
    
    // Build invoice options for dropdown
    let invoice_options = [{ label: __('None (Direct Payment)'), value: '' }];
    if (data.invoices && data.invoices.length > 0) {
        data.invoices.forEach(inv => {
            if (inv.outstanding_amount > 0) {
                invoice_options.push({
                    label: `${inv.name} (Outstanding: ${format_currency(inv.outstanding_amount)})`,
                    value: inv.name
                });
            }
        });
    }
    
    const d = new frappe.ui.Dialog({
        title: __('Record Payment - {0}', [data.trainer_name]),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'payment_info',
                options: `
                    <div style="background-color: #f8f9fa; padding: 15px; margin-bottom: 15px; border-radius: 5px;">
                        <p><strong>Event:</strong> ${data.event_name}</p>
                        <p><strong>Total Amount:</strong> ${format_currency(data.total_amount)}</p>
                        <p><strong>Total Invoiced:</strong> ${format_currency(data.total_invoiced)}</p>
                        <p><strong>Paid:</strong> <span class="text-success">${format_currency(data.total_paid)}</span></p>
                        <p><strong>Outstanding:</strong> <span class="text-warning">${format_currency(data.total_outstanding)}</span></p>
                        <p><strong>Balance:</strong> <span class="text-danger">${format_currency(balance)}</span></p>
                    </div>
                `
            },
            {
                label: 'Link to Invoice',
                fieldname: 'link_invoice',
                fieldtype: 'Select',
                options: invoice_options.map(o => o.label),
                description: 'Select an invoice to link this payment'
            },
            {
                label: 'Payment Amount',
                fieldname: 'amount',
                fieldtype: 'Currency',
                reqd: 1,
                default: data.total_outstanding > 0 ? data.total_outstanding : (balance > 0 ? balance : 0)
            },
            {
                label: 'Reference No',
                fieldname: 'reference_no',
                fieldtype: 'Data',
                description: 'Payment reference number (optional)'
            },
            {
                label: 'Remarks',
                fieldname: 'remarks',
                fieldtype: 'Small Text',
                default: `Payment for training - ${data.event_name}`
            }
        ],
        primary_action_label: __('Create Payment Entry'),
        primary_action: function(values) {
            if (values.amount <= 0) {
                frappe.msgprint(__('Payment amount must be greater than zero'));
                return;
            }
            
            // Get actual invoice name from selected option
            const selected_option = invoice_options.find(o => o.label === values.link_invoice);
            const invoice_name = selected_option ? selected_option.value : null;
            
            frappe.call({
                method: 'event_management.event_management.doctype.event_trainer.event_trainer.create_trainer_payment_entry',
                args: {
                    event_trainer_name: event_trainer_name,
                    amount: values.amount,
                    reference_no: values.reference_no || event_trainer_name,
                    remarks: values.remarks,
                    link_to_invoice: invoice_name
                },
                freeze: true,
                freeze_message: __('Creating Payment Entry...'),
                callback: function(r) {
                            if (r.message) {
                                d.hide();
                                frappe.show_alert({
                                    message: __('Payment Entry {0} created successfully!', [r.message]),
                                    indicator: 'green'
                                }, 3);
                                
                                // Just navigate to the payment - don't auto-submit
                                frappe.set_route('Form', 'Payment Entry', r.message);
                                
                                // Refresh dialogs after a delay
                                setTimeout(function() {
                                    window.refresh_trainers_dialog();
                                }, 2000);
                            }
                        }
            });
        }
    });
    
    // ADDED: Update amount when invoice is selected
    d.fields_dict.link_invoice.$input.on('change', function() {
        const selected_label = d.get_value('link_invoice');
        const selected_option = invoice_options.find(o => o.label === selected_label);
        
        if (selected_option && selected_option.value) {
            const invoice = data.invoices.find(inv => inv.name === selected_option.value);
            if (invoice && invoice.outstanding_amount > 0) {
                d.set_value('amount', invoice.outstanding_amount);
            }
        }
    });
    
    d.show();
}

// UPDATED: View payments with refresh capability
window.view_payments = function(event_trainer_name) {
    frappe.call({
        method: 'event_management.event_management.doctype.event_trainer.event_trainer.get_trainer_payment_summary',
        args: { event_trainer_name: event_trainer_name },
        callback: function(r) {
            if (r.message) {
                show_payment_summary_dialog(r.message, event_trainer_name);
            }
        }
    });
}

// UPDATED: Payment summary dialog with refresh button
function show_payment_summary_dialog(data, event_trainer_name) {
    let html = `
        <div class="row">
            <div class="col-sm-6">
                <h5>Trainer: ${data.trainer_name}</h5>
                <p><strong>Event:</strong> ${data.event_name}</p>
            </div>
            <div class="col-sm-6">
                <table class="table table-sm">
                    <tr>
                        <td><strong>Contract Amount:</strong></td>
                        <td>${format_currency(data.total_amount)}</td>
                    </tr>
                    <tr>
                        <td><strong>Total Invoiced:</strong></td>
                        <td>${format_currency(data.total_invoiced)}</td>
                    </tr>
                    <tr>
                        <td><strong>Total Paid:</strong></td>
                        <td class="text-success"><strong>${format_currency(data.total_paid)}</strong></td>
                    </tr>
                    <tr>
                        <td><strong>Outstanding:</strong></td>
                        <td class="text-warning">${format_currency(data.total_outstanding)}</td>
                    </tr>
                    <tr>
                        <td><strong>Balance:</strong></td>
                        <td class="text-danger"><strong>${format_currency(data.balance)}</strong></td>
                    </tr>
                    <tr>
                        <td colspan="2">
                            <span class="badge badge-${data.payment_status === 'Paid' ? 'success' : (data.payment_status === 'Partially Paid' ? 'warning' : 'danger')}" style="font-size: 14px;">
                                ${data.payment_status}
                            </span>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
        <hr>
    `;
    
    // ADDED: Invoices section
    if (data.invoices && data.invoices.length > 0) {
        html += `<h6>Invoices</h6><table class="table table-bordered table-sm">
            <thead><tr><th>Date</th><th>Invoice</th><th>Total</th><th>Outstanding</th><th>Status</th><th>Action</th></tr></thead><tbody>`;
        
        data.invoices.forEach(invoice => {
            const status_color = invoice.status === 'Paid' ? 'success' : (invoice.status === 'Unpaid' ? 'danger' : 'warning');
            html += `<tr>
                <td>${frappe.datetime.str_to_user(invoice.posting_date)}</td>
                <td><a href="/app/purchase-invoice/${invoice.name}" target="_blank">${invoice.name}</a></td>
                <td>${format_currency(invoice.grand_total)}</td>
                <td><strong>${format_currency(invoice.outstanding_amount)}</strong></td>
                <td><span class="badge badge-${status_color}">${invoice.status}</span></td>
                <td>
                    <button class="btn btn-xs btn-default" onclick="frappe.set_route('Form', 'Purchase Invoice', '${invoice.name}')">View</button>
                    ${invoice.outstanding_amount > 0 ? `<button class="btn btn-xs btn-success" onclick="pay_invoice('${invoice.name}')">Pay</button>` : ''}
                </td>
            </tr>`;
        });
        html += '</tbody></table><hr>';
    }
    
    // Payment history section
    if (data.payments && data.payments.length > 0) {
        html += `<h6>Payment History</h6><table class="table table-bordered table-sm">
            <thead><tr><th>Date</th><th>Reference</th><th>Amount</th><th>Remarks</th><th>Action</th></tr></thead><tbody>`;
        
        data.payments.forEach(payment => {
            html += `<tr>
                <td>${frappe.datetime.str_to_user(payment.posting_date)}</td>
                <td><a href="/app/payment-entry/${payment.name}" target="_blank">${payment.reference_no || payment.name}</a></td>
                <td><strong>${format_currency(payment.paid_amount)}</strong></td>
                <td>${payment.remarks || '-'}</td>
                <td><button class="btn btn-xs btn-default" onclick="frappe.set_route('Form', 'Payment Entry', '${payment.name}')">View</button></td>
            </tr>`;
        });
        html += '</tbody></table>';
    } else {
        html += '<p class="text-muted">No payments recorded yet.</p>';
    }
    
    const payment_dialog = new frappe.ui.Dialog({
        title: __('Payment Summary'),
        size: 'extra-large',
        fields: [{ 
            fieldtype: 'HTML', 
            fieldname: 'summary_html', 
            options: html 
        }],
        primary_action_label: __('Refresh'),
        primary_action: function() {
            // Refresh the data
            frappe.call({
                method: 'event_management.event_management.doctype.event_trainer.event_trainer.get_trainer_payment_summary',
                args: { event_trainer_name: event_trainer_name },
                callback: function(r) {
                    if (r.message) {
                        payment_dialog.hide();
                        show_payment_summary_dialog(r.message, event_trainer_name);
                        // Also refresh the main trainers dialog
                        window.refresh_trainers_dialog();
                    }
                }
            });
        }
    });
    
    payment_dialog.show();
}

// NEW: Function to pay invoice directly
window.pay_invoice = function(invoice_name) {
    frappe.call({
        method: 'event_management.event_management.doctype.event_trainer.event_trainer.make_payment_entry_from_invoice',
        args: { purchase_invoice_name: invoice_name },
        callback: function(r) {
            if (r.message) {
                frappe.model.sync(r.message);
                frappe.set_route('Form', 'Payment Entry', r.message.name);
            }
        }
    });
}

function show_trainer_payment_summary(frm) {
    frappe.call({
        method: 'event_management.event_management.doctype.event_trainer.event_trainer.get_trainers_with_fresh_status',
        args: {
            event_registration: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                let total_contract = 0, total_paid = 0;
                let html = `
                    <div style="margin-bottom: 15px;">
                        <button class="btn btn-sm btn-default" onclick="window.refresh_trainer_summary_dialog()">
                            <i class="fa fa-refresh"></i> Refresh
                        </button>
                    </div>
                    <table class="table table-bordered">
                    <thead><tr>
                        <th>Trainer</th>
                        <th>Email</th>
                        <th>Phone</th>
                        <th>Contract Amount</th>
                        <th>Paid</th>
                        <th>Balance</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr></thead><tbody>`;
                
                r.message.forEach(trainer => {
                    const balance = trainer.total_amount - (trainer.paid_amount || 0);
                    total_contract += trainer.total_amount;
                    total_paid += (trainer.paid_amount || 0);
                    
                    const payment_color = {
                        'Paid': 'success',
                        'Partially Paid': 'warning',
                        'Unpaid': 'danger'
                    }[trainer.payment_status] || 'secondary';
                    
                    html += `<tr>
                        <td><a href="/app/event-trainer/${trainer.name}">${trainer.trainer_name}</a></td>
                        <td>${trainer.email || '-'}</td>
                        <td>${trainer.mobile_no || '-'}</td>
                        <td>${format_currency(trainer.total_amount)}</td>
                        <td class="text-success">${format_currency(trainer.paid_amount || 0)}</td>
                        <td class="text-danger">${format_currency(balance)}</td>
                        <td><span class="badge badge-${payment_color}">${trainer.payment_status}</span></td>
                                <td style="text-align: center;">
                            <div class="dropdown">
                                <button class="btn btn-default btn-sm" type="button" 
                                        data-toggle="dropdown" aria-haspopup="true" aria-expanded="false"
                                        style="padding: 4px 8px; background: transparent; border: none; font-size: 18px; color: #8d99a6;">
                                    ⋮
                                </button>
                                <ul class="dropdown-menu dropdown-menu-right" style="min-width: 180px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); border-radius: 6px;">
                                    <li>
                                        <a href="#" onclick="event.preventDefault(); frappe.set_route('Form', 'Event Trainer', '${trainer.name}');"
                                           style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                            <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                                <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                                                <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/>
                                            </svg>
                                            <span>View Details</span>
                                        </a>
                                    </li>
                                    <li class="divider" style="margin: 4px 0;"></li>
                                    <li>
                                        <a href="#" onclick="event.preventDefault(); make_payment('${trainer.name}');"
                                           style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                            <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                                <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z"/>
                                                <path fill-rule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z" clip-rule="evenodd"/>
                                            </svg>
                                            <span>Record Payment</span>
                                        </a>
                                    </li>
                                    <li>
                                        <a href="#" onclick="event.preventDefault(); view_payments('${trainer.name}');"
                                           style="padding: 10px 16px; display: flex; align-items: center; gap: 12px; color: #36414c; font-size: 14px;">
                                            <svg style="width: 16px; height: 16px; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
                                                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
                                            </svg>
                                            <span>Payment History</span>
                                        </a>
                                    </li>
                                </ul>
                            </div>
                        </td>
                    </tr>`;
                });
                
                html += `<tr class="font-weight-bold" style="background-color: #f8f9fa;">
                    <td colspan="3"><strong>TOTAL</strong></td>
                    <td><strong>${format_currency(total_contract)}</strong></td>
                    <td class="text-success"><strong>${format_currency(total_paid)}</strong></td>
                    <td class="text-danger"><strong>${format_currency(total_contract - total_paid)}</strong></td>
                    <td colspan="2"></td>
                </tr></tbody></table>`;
                
                window.trainer_summary_dialog = new frappe.ui.Dialog({
                    title: __('Trainer Payment Summary'),
                    fields: [{ fieldtype: 'HTML', fieldname: 'summary', options: html }],
                    size: 'extra-large'
                });
                
                window.trainer_summary_dialog.show();
            } else {
                frappe.msgprint(__('No trainers assigned to this event yet.'));
            }
        }
    });
}

// NEW: Refresh function for trainer summary dialog
window.refresh_trainer_summary_dialog = function() {
    if (window.trainer_summary_dialog && window.current_event_registration) {
        frappe.call({
            method: 'event_management.event_management.doctype.event_trainer.event_trainer.get_trainers_with_fresh_status',
            args: {
                event_registration: window.current_event_registration
            },
            callback: function(r) {
                if (r.message && window.trainer_summary_dialog) {
                    // Rebuild the table
                    let total_contract = 0, total_paid = 0;
                    let html = `
                        <div style="margin-bottom: 15px;">
                            <button class="btn btn-sm btn-default" onclick="window.refresh_trainer_summary_dialog()">
                                <i class="fa fa-refresh"></i> Refresh
                            </button>
                        </div>
                        <table class="table table-bordered">
                        <thead><tr>
                            <th>Trainer</th>
                            <th>Email</th>
                            <th>Phone</th>
                            <th>Contract Amount</th>
                            <th>Paid</th>
                            <th>Balance</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr></thead><tbody>`;
                    
                    r.message.forEach(trainer => {
                        const balance = trainer.total_amount - (trainer.paid_amount || 0);
                        total_contract += trainer.total_amount;
                        total_paid += (trainer.paid_amount || 0);
                        
                        const payment_color = {
                            'Paid': 'success',
                            'Partially Paid': 'warning',
                            'Unpaid': 'danger'
                        }[trainer.payment_status] || 'secondary';
                        
                        html += `<tr>
                            <td><a href="/app/event-trainer/${trainer.name}">${trainer.trainer_name}</a></td>
                            <td>${trainer.email || '-'}</td>
                            <td>${trainer.mobile_no || '-'}</td>
                            <td>${format_currency(trainer.total_amount)}</td>
                            <td class="text-success">${format_currency(trainer.paid_amount || 0)}</td>
                            <td class="text-danger">${format_currency(balance)}</td>
                            <td><span class="badge badge-${payment_color}">${trainer.payment_status}</span></td>
                            <td>
                                <button class="btn btn-xs btn-success" onclick="make_payment('${trainer.name}')">
                                    Pay
                                </button>
                                <button class="btn btn-xs btn-info" onclick="view_payments('${trainer.name}')">
                                    View
                                </button>
                            </td>
                        </tr>`;
                    });
                    
                    html += `<tr class="font-weight-bold" style="background-color: #f8f9fa;">
                        <td colspan="3"><strong>TOTAL</strong></td>
                        <td><strong>${format_currency(total_contract)}</strong></td>
                        <td class="text-success"><strong>${format_currency(total_paid)}</strong></td>
                        <td class="text-danger"><strong>${format_currency(total_contract - total_paid)}</strong></td>
                        <td colspan="2"></td>
                    </tr></tbody></table>`;
                    
                    // Update the dialog content
                    window.trainer_summary_dialog.fields_dict.summary.$wrapper.html(html);
                    
                    frappe.show_alert({
                        message: __('Summary refreshed'),
                        indicator: 'green'
                    }, 2);
                }
            }
        });
    }
}