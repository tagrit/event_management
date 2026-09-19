frappe.pages['trainer-profile'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Trainer Profile',
        single_column: true
    });

    wrapper.trainer_profile = new TrainerProfile(page);
};

frappe.pages['trainer-profile'].on_page_show = function (wrapper) {
    if (wrapper.trainer_profile) {
        wrapper.trainer_profile.refresh();
    }
};

const PALETTE = {
    primary: '#1e3a8a',
    primaryLight: '#3b82f6',
    green: '#16a34a',
    greenBg: '#f0fdf4',
    orange: '#d97706',
    orangeBg: '#fffbeb',
    red: '#dc2626',
    redBg: '#fef2f2',
    slate: '#475569',
    slateBg: '#f8fafc',
    border: '#e2e8f0'
};

class TrainerProfile {
    constructor(page) {
        this.page = page;
        this.make();
    }

    make() {
        this.inject_styles();
        this.$container = $('<div class="trainer-profile-wrap">').appendTo(this.page.main);
        this.refresh();
    }

    refresh() {
        const trainer = frappe.get_route()[1];
        if (!trainer) {
            this.$container.html('<div class="tp-empty">No trainer specified. Open this page from a Supplier record.</div>');
            return;
        }
        this.trainer = trainer;
        this.page.set_title(`Trainer Profile`);
        this.load_data();
    }

    load_data() {
        this.$container.html('<div class="tp-empty">Loading trainer profile...</div>');
        frappe.call({
            method: 'event_management.event_management.doctype.event_trainer.event_trainer.get_trainer_profile',
            args: { trainer: this.trainer },
            callback: (r) => {
                if (r.message) {
                    this.data = r.message;
                    this.render();
                }
            }
        });
    }

    render() {
        const d = this.data;
        this.$container.html(`
            ${this.render_header(d.trainer)}
            ${this.render_kpis(d.kpis)}
            <div class="tp-grid-2">
                ${this.render_events_table(d.assignments)}
                ${this.render_documents(d.trainer, d.documents)}
            </div>
            ${this.render_ledger(d.ledger, d.kpis)}
        `);

        this.page.clear_menu();
        this.page.clear_inner_toolbar();
        this.page.set_primary_action(__('Record Payment'), () => this.show_payment_dialog(), 'fa fa-money');
        this.page.add_inner_button(__('Open Supplier Record'), () => frappe.set_route('Form', 'Supplier', this.trainer));
    }

    render_header(trainer) {
        const initials = (trainer.supplier_name || '?').split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
        return `
        <div class="tp-card tp-header-card">
            <div class="tp-avatar">${initials}</div>
            <div class="tp-header-info">
                <h2>${frappe.utils.escape_html(trainer.supplier_name)}</h2>
                <div class="tp-header-meta">
                    ${trainer.area_of_expertise ? `<span class="tp-chip">${frappe.utils.escape_html(trainer.area_of_expertise)}</span>` : ''}
                    ${trainer.rate_type ? `<span class="tp-chip tp-chip-muted">${trainer.rate_type}${trainer.rate ? ' · ' + format_currency(trainer.rate, 'KES') : ''}</span>` : ''}
                </div>
                <div class="tp-contact-row">
                    ${trainer.email ? `<span><i class="fa fa-envelope"></i> ${frappe.utils.escape_html(trainer.email)}</span>` : ''}
                    ${trainer.mobile_no ? `<span><i class="fa fa-phone"></i> ${frappe.utils.escape_html(trainer.mobile_no)}</span>` : ''}
                </div>
            </div>
            ${trainer.cv_attachment ? `<a class="tp-cv-btn" href="${trainer.cv_attachment}" target="_blank"><i class="fa fa-file-text"></i> View CV</a>` : ''}
        </div>`;
    }

    render_kpis(kpis) {
        return `
        <div class="tp-kpi-row">
            ${this.kpi_card('Events Trained', kpis.total_events, 'fa-calendar', 'primary')}
            ${this.kpi_card('Total Earned', format_currency(kpis.total_earned, 'KES'), 'fa-briefcase', 'primary')}
            ${this.kpi_card('Total Paid', format_currency(kpis.total_paid, 'KES'), 'fa-check-circle', 'green')}
            ${this.kpi_card('Outstanding Balance', format_currency(kpis.total_outstanding, 'KES'), 'fa-clock-o', kpis.total_outstanding > 0 ? 'orange' : 'green')}
        </div>`;
    }

    kpi_card(label, value, icon, tone) {
        return `
        <div class="tp-kpi-card tp-tone-${tone}">
            <div class="tp-kpi-icon"><i class="fa ${icon}"></i></div>
            <div class="tp-kpi-value">${value}</div>
            <div class="tp-kpi-label">${label}</div>
        </div>`;
    }

    render_events_table(assignments) {
        const rows = (assignments || []).map(a => `
            <tr>
                <td>
                    <a href="/app/event-registration/${a.event_registration}">${frappe.utils.escape_html(a.event_name || a.event_registration)}</a>
                    <div class="tp-subtext">${a.event_venue || ''}${a.event_venue && a.event_location ? ', ' : ''}${a.event_location || ''}</div>
                </td>
                <td class="tp-subtext">${frappe.datetime.str_to_user(a.event_start_date)}</td>
                <td>${format_currency(a.total_amount, 'KES')}</td>
                <td>${this.status_badge(a.payment_status)}</td>
                <td>${a.contract_signed
                    ? '<span class="tp-badge tp-badge-green"><i class="fa fa-check"></i> Signed</span>'
                    : (a.contract_sent ? '<span class="tp-badge tp-badge-orange">Awaiting Signature</span>' : '<span class="tp-badge tp-badge-muted">Not Sent</span>')}
                </td>
            </tr>
        `).join('') || `<tr><td colspan="5" class="tp-empty-row">No events trained yet.</td></tr>`;

        return `
        <div class="tp-card">
            <h4 class="tp-card-title"><i class="fa fa-graduation-cap"></i> Events Trained</h4>
            <table class="tp-table">
                <thead>
                    <tr><th>Event</th><th>Date</th><th>Amount</th><th>Payment</th><th>Contract</th></tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    render_documents(trainer, documents) {
        const rows = (documents || []).map(doc => `
            <div class="tp-doc-row">
                <i class="fa fa-file-o"></i>
                <div class="tp-doc-info">
                    <a href="${doc.file}" target="_blank">${frappe.utils.escape_html(doc.document_name || 'Document')}</a>
                    ${doc.description ? `<div class="tp-subtext">${frappe.utils.escape_html(doc.description)}</div>` : ''}
                </div>
            </div>
        `).join('') || `<div class="tp-empty-row">No additional documents uploaded.</div>`;

        return `
        <div class="tp-card">
            <h4 class="tp-card-title"><i class="fa fa-folder-open"></i> CV &amp; Documents</h4>
            ${trainer.cv_attachment ? `
                <div class="tp-doc-row">
                    <i class="fa fa-file-text"></i>
                    <div class="tp-doc-info"><a href="${trainer.cv_attachment}" target="_blank">CV / Resume</a></div>
                </div>` : ''}
            ${rows}
        </div>`;
    }

    render_ledger(ledger, kpis) {
        const rows = (ledger || []).map(row => `
            <tr>
                <td>${row.date}</td>
                <td><span class="tp-badge ${row.type === 'Payment' ? 'tp-badge-green' : 'tp-badge-muted'}">${row.type}</span></td>
                <td>${frappe.utils.escape_html(row.description || '')}</td>
                <td class="${row.amount < 0 ? 'tp-amount-neg' : 'tp-amount-pos'}">${row.amount < 0 ? '-' : ''}${format_currency(Math.abs(row.amount), 'KES')}</td>
                <td><strong>${format_currency(row.balance, 'KES')}</strong></td>
            </tr>
        `).join('') || `<tr><td colspan="5" class="tp-empty-row">No invoices or payments recorded yet.</td></tr>`;

        return `
        <div class="tp-card">
            <h4 class="tp-card-title"><i class="fa fa-file-text-o"></i> Payment Statement</h4>
            <table class="tp-table">
                <thead>
                    <tr><th>Date</th><th>Type</th><th>Description</th><th>Amount</th><th>Balance</th></tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
            <div class="tp-statement-footer">
                Current outstanding balance: <strong>${format_currency(kpis.total_outstanding, 'KES')}</strong>
            </div>
        </div>`;
    }

    status_badge(status) {
        const map = {
            'Paid': 'tp-badge-green',
            'Partially Paid': 'tp-badge-orange',
            'Unpaid': 'tp-badge-red'
        };
        return `<span class="tp-badge ${map[status] || 'tp-badge-muted'}">${status || 'Unpaid'}</span>`;
    }

    show_payment_dialog() {
        const outstanding = (this.data.assignments || []).filter(a => a.payment_status !== 'Paid');

        if (!outstanding.length) {
            frappe.msgprint(__('This trainer has no outstanding balance on any event.'));
            return;
        }

        const options = outstanding.map(a => ({
            label: `${a.event_name} — Outstanding: ${format_currency(a.total_amount - a.paid_amount, 'KES')}`,
            value: a.name
        }));

        const d = new frappe.ui.Dialog({
            title: __('Record Payment'),
            fields: [
                {
                    label: 'Event / Assignment',
                    fieldname: 'event_trainer',
                    fieldtype: 'Select',
                    options: options.map(o => o.label),
                    reqd: 1
                },
                {
                    label: 'Amount',
                    fieldname: 'amount',
                    fieldtype: 'Currency',
                    reqd: 1
                },
                {
                    label: 'Reference No',
                    fieldname: 'reference_no',
                    fieldtype: 'Data'
                },
                {
                    label: 'Remarks',
                    fieldname: 'remarks',
                    fieldtype: 'Small Text'
                }
            ],
            primary_action_label: __('Create Payment Entry'),
            primary_action: (values) => {
                const selected = options.find(o => o.label === values.event_trainer);
                if (!selected) return;

                frappe.call({
                    method: 'event_management.event_management.doctype.event_trainer.event_trainer.create_trainer_payment_entry',
                    args: {
                        event_trainer_name: selected.value,
                        amount: values.amount,
                        reference_no: values.reference_no,
                        remarks: values.remarks
                    },
                    freeze: true,
                    freeze_message: __('Creating Payment Entry...'),
                    callback: (r) => {
                        if (r.message) {
                            d.hide();
                            frappe.set_route('Form', 'Payment Entry', r.message);
                        }
                    }
                });
            }
        });

        d.fields_dict.event_trainer.$input.on('change', () => {
            const selected = options.find(o => o.label === d.get_value('event_trainer'));
            if (selected) {
                const a = outstanding.find(x => x.name === selected.value);
                d.set_value('amount', a.total_amount - a.paid_amount);
            }
        });

        d.show();
        d.set_value('event_trainer', options[0].label);
        d.fields_dict.event_trainer.$input.trigger('change');
    }

    inject_styles() {
        if (document.getElementById('trainer-profile-styles')) return;
        $(`<style id="trainer-profile-styles">
            .trainer-profile-wrap { padding-bottom: 40px; }
            .tp-empty { padding: 60px 0; text-align: center; color: ${PALETTE.slate}; }
            .tp-card {
                background: white;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(30, 58, 138, 0.06);
                border: 1px solid ${PALETTE.border};
                padding: 22px;
                margin-bottom: 20px;
            }
            .tp-header-card {
                display: flex;
                align-items: center;
                gap: 20px;
                background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
                color: white;
                border: none;
            }
            .tp-avatar {
                width: 64px; height: 64px; border-radius: 50%;
                background: rgba(255,255,255,0.2);
                display: flex; align-items: center; justify-content: center;
                font-size: 22px; font-weight: 700; flex-shrink: 0;
            }
            .tp-header-info { flex: 1; }
            .tp-header-info h2 { margin: 0 0 8px 0; color: white; }
            .tp-header-meta { margin-bottom: 8px; }
            .tp-chip {
                display: inline-block; background: rgba(255,255,255,0.18);
                padding: 3px 10px; border-radius: 12px; font-size: 11.5px;
                margin-right: 8px;
            }
            .tp-chip-muted { background: rgba(255,255,255,0.1); }
            .tp-contact-row span { margin-right: 18px; font-size: 12.5px; opacity: 0.9; }
            .tp-cv-btn {
                background: white; color: ${PALETTE.primary};
                padding: 8px 16px; border-radius: 6px; font-weight: 600;
                text-decoration: none; font-size: 12.5px; flex-shrink: 0;
            }
            .tp-kpi-row {
                display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px; margin-bottom: 20px;
            }
            .tp-kpi-card {
                border-radius: 10px; padding: 18px; text-align: center;
                border: 1px solid ${PALETTE.border};
            }
            .tp-kpi-icon { font-size: 20px; margin-bottom: 8px; }
            .tp-kpi-value { font-size: 19px; font-weight: 700; margin-bottom: 4px; }
            .tp-kpi-label { font-size: 11.5px; color: ${PALETTE.slate}; text-transform: uppercase; letter-spacing: 0.3px; }
            .tp-tone-primary { background: #eff6ff; } .tp-tone-primary .tp-kpi-icon, .tp-tone-primary .tp-kpi-value { color: ${PALETTE.primary}; }
            .tp-tone-green { background: ${PALETTE.greenBg}; } .tp-tone-green .tp-kpi-icon, .tp-tone-green .tp-kpi-value { color: ${PALETTE.green}; }
            .tp-tone-orange { background: ${PALETTE.orangeBg}; } .tp-tone-orange .tp-kpi-icon, .tp-tone-orange .tp-kpi-value { color: ${PALETTE.orange}; }
            .tp-grid-2 {
                display: grid; grid-template-columns: 2fr 1fr; gap: 20px; align-items: start;
            }
            @media (max-width: 900px) { .tp-grid-2 { grid-template-columns: 1fr; } }
            .tp-card-title { margin: 0 0 14px 0; color: ${PALETTE.primary}; font-size: 14px; }
            .tp-card-title i { margin-right: 6px; }
            .tp-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
            .tp-table th {
                text-align: left; padding: 8px 10px; background: ${PALETTE.slateBg};
                color: ${PALETTE.slate}; font-size: 11px; text-transform: uppercase;
                border-bottom: 2px solid ${PALETTE.border};
            }
            .tp-table td { padding: 10px; border-bottom: 1px solid ${PALETTE.border}; vertical-align: top; }
            .tp-subtext { color: #94a3b8; font-size: 11px; margin-top: 2px; }
            .tp-empty-row { text-align: center; color: #94a3b8; padding: 20px !important; }
            .tp-badge {
                display: inline-block; padding: 3px 10px; border-radius: 10px;
                font-size: 10.5px; font-weight: 600;
            }
            .tp-badge-green { background: ${PALETTE.greenBg}; color: ${PALETTE.green}; }
            .tp-badge-orange { background: ${PALETTE.orangeBg}; color: ${PALETTE.orange}; }
            .tp-badge-red { background: ${PALETTE.redBg}; color: ${PALETTE.red}; }
            .tp-badge-muted { background: #f1f5f9; color: #64748b; }
            .tp-doc-row { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid ${PALETTE.border}; }
            .tp-doc-row:last-child { border-bottom: none; }
            .tp-doc-row i { color: ${PALETTE.primaryLight}; font-size: 16px; }
            .tp-amount-pos { color: ${PALETTE.orange}; font-weight: 600; }
            .tp-amount-neg { color: ${PALETTE.green}; font-weight: 600; }
            .tp-statement-footer {
                text-align: right; padding-top: 14px; margin-top: 4px;
                border-top: 2px solid ${PALETTE.border}; font-size: 13px;
            }
        </style>`).appendTo('head');
    }
}
