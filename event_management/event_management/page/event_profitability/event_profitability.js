frappe.pages['event-profitability'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Event Profitability',
        single_column: true
    });

    wrapper.event_profitability = new EventProfitability(page);
};

frappe.pages['event-profitability'].on_page_show = function (wrapper) {
    if (wrapper.event_profitability) {
        wrapper.event_profitability.refresh();
    }
};

function ep_escape(text) {
    if (text === undefined || text === null) return '';
    if (frappe.utils && typeof frappe.utils.escape_html === 'function') {
        return frappe.utils.escape_html(text);
    }
    return $('<div>').text(text).html();
}

const EP_PALETTE = {
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

class EventProfitability {
    constructor(page) {
        this.page = page;
        this.make();
    }

    make() {
        this.inject_styles();
        this.$container = $('<div class="ep-wrap">').appendTo(this.page.main);
        this.refresh();
    }

    refresh() {
        const event_name = frappe.get_route()[1];
        if (!event_name) {
            this.$container.html('<div class="ep-empty">No event specified. Open this report from an Event Registration record.</div>');
            return;
        }
        this.event_name = event_name;
        this.page.set_title(__('Event Profitability'));
        this.load_data();
    }

    load_data() {
        this.$container.html('<div class="ep-empty">Loading financial summary...</div>');
        frappe.call({
            method: 'event_management.event_management.doctype.event_registration.event_registration.get_event_financial_summary',
            args: { event_registration_name: this.event_name },
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
            ${this.render_header(d.event)}
            ${this.render_kpis(d)}
            <div class="ep-grid-2">
                ${this.render_income(d.income, d.event.budgeted_revenue)}
                ${this.render_expense_summary(d.expenses)}
            </div>
            ${this.render_trainer_table(d.expenses.trainers.detail)}
            ${this.render_other_expenses(d.expenses.other)}
            ${this.render_net_profit_statement(d)}
        `);

        this.page.clear_menu();
        this.page.clear_inner_toolbar();
        this.page.add_inner_button(__('Open Event'), () => frappe.set_route('Form', 'Event Registration', this.event_name));
        this.page.add_inner_button(__('Print'), () => window.print());
    }

    render_header(event) {
        return `
        <div class="ep-card ep-header-card">
            <div class="ep-header-info">
                <h2>${ep_escape(event.event_name || event.name)}</h2>
                <div class="ep-header-meta">
                    ${event.organization_name ? `<span class="ep-chip">${ep_escape(event.organization_name)}</span>` : ''}
                    ${event.division ? `<span class="ep-chip ep-chip-muted">${ep_escape(event.division)}</span>` : ''}
                    <span class="ep-chip ep-chip-muted">${event.number_of_delegates || 0} delegate(s)</span>
                </div>
                <div class="ep-contact-row">
                    <span><i class="fa fa-calendar"></i> ${frappe.datetime.str_to_user(event.start_date)} to ${frappe.datetime.str_to_user(event.end_date)}</span>
                </div>
            </div>
        </div>`;
    }

    render_kpis(d) {
        const profit_tone = d.net_profit >= 0 ? 'green' : 'red';
        return `
        <div class="ep-kpi-row">
            ${this.kpi_card('Total Collected', format_currency(d.income.total_collected, 'KES'), 'fa-money', 'primary')}
            ${this.kpi_card('Total Expenses Paid', format_currency(d.expenses.total_paid, 'KES'), 'fa-shopping-cart', 'orange')}
            ${this.kpi_card('Net Profit', format_currency(d.net_profit, 'KES'), 'fa-line-chart', profit_tone)}
            ${this.kpi_card('Profit Margin', `${d.profit_margin}%`, 'fa-percent', profit_tone)}
        </div>`;
    }

    kpi_card(label, value, icon, tone) {
        return `
        <div class="ep-kpi-card ep-tone-${tone}">
            <div class="ep-kpi-icon"><i class="fa ${icon}"></i></div>
            <div class="ep-kpi-value">${value}</div>
            <div class="ep-kpi-label">${label}</div>
        </div>`;
    }

    render_income(income, budgeted_revenue) {
        const variance = income.total_collected - budgeted_revenue;
        const variance_class = variance >= 0 ? 'ep-amount-pos' : 'ep-amount-neg';
        return `
        <div class="ep-card">
            <h4 class="ep-card-title"><i class="fa fa-arrow-down"></i> Income</h4>
            <table class="ep-table">
                <tbody>
                    <tr><td>Budgeted Revenue</td><td class="ep-num">${format_currency(budgeted_revenue, 'KES')}</td></tr>
                    <tr><td>Total Invoiced</td><td class="ep-num">${format_currency(income.total_invoiced, 'KES')}</td></tr>
                    <tr><td>Collected via Invoice</td><td class="ep-num">${format_currency(income.collected_via_invoice, 'KES')}</td></tr>
                    <tr><td>Collected Directly (no invoice)</td><td class="ep-num">${format_currency(income.collected_direct, 'KES')}</td></tr>
                    <tr><td>Invoice Outstanding</td><td class="ep-num">${format_currency(income.invoice_outstanding, 'KES')}</td></tr>
                    <tr class="ep-row-total"><td><strong>Total Collected</strong></td><td class="ep-num"><strong>${format_currency(income.total_collected, 'KES')}</strong></td></tr>
                    <tr><td>Variance vs Budget</td><td class="ep-num ${variance_class}">${variance >= 0 ? '+' : ''}${format_currency(variance, 'KES')}</td></tr>
                </tbody>
            </table>
        </div>`;
    }

    render_expense_summary(expenses) {
        return `
        <div class="ep-card">
            <h4 class="ep-card-title"><i class="fa fa-arrow-up"></i> Expenses</h4>
            <table class="ep-table">
                <tbody>
                    <tr><td>Trainer Costs (Contracted)</td><td class="ep-num">${format_currency(expenses.trainers.contracted, 'KES')}</td></tr>
                    <tr><td>Trainer Costs (Paid)</td><td class="ep-num">${format_currency(expenses.trainers.paid, 'KES')}</td></tr>
                    <tr><td>Other Expenses (Billed)</td><td class="ep-num">${format_currency(expenses.other.billed, 'KES')}</td></tr>
                    <tr><td>Other Expenses (Paid)</td><td class="ep-num">${format_currency(expenses.other.paid, 'KES')}</td></tr>
                    <tr class="ep-row-total"><td><strong>Total Expenses Paid</strong></td><td class="ep-num"><strong>${format_currency(expenses.total_paid, 'KES')}</strong></td></tr>
                </tbody>
            </table>
        </div>`;
    }

    render_trainer_table(trainers) {
        const rows = (trainers || []).map(t => `
            <tr>
                <td><a href="/app/event-trainer/${t.name}">${ep_escape(t.trainer_name)}</a></td>
                <td class="ep-num">${format_currency(t.total_amount, 'KES')}</td>
                <td class="ep-num">${format_currency(t.paid_amount || 0, 'KES')}</td>
                <td>${this.status_badge(t.payment_status)}</td>
            </tr>
        `).join('') || `<tr><td colspan="4" class="ep-empty-row">No trainers assigned to this event.</td></tr>`;

        return `
        <div class="ep-card">
            <h4 class="ep-card-title"><i class="fa fa-graduation-cap"></i> Trainer Costs</h4>
            <table class="ep-table">
                <thead><tr><th>Trainer</th><th>Contracted</th><th>Paid</th><th>Status</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    render_other_expenses(other) {
        const category_rows = (other.breakdown || []).map(b => `
            <tr>
                <td>${ep_escape(b.category)}</td>
                <td class="ep-num">${format_currency(b.amount, 'KES')}</td>
            </tr>
        `).join('') || `<tr><td colspan="2" class="ep-empty-row">No other expenses (hotel, delegate materials, etc.) tagged to this event yet.</td></tr>`;

        const invoice_rows = (other.invoices || []).map(inv => `
            <tr>
                <td><a href="/app/purchase-invoice/${inv.name}" target="_blank">${inv.name}</a></td>
                <td>${ep_escape(inv.supplier_name)}</td>
                <td class="ep-num">${format_currency(inv.grand_total, 'KES')}</td>
                <td class="ep-num">${format_currency(inv.outstanding_amount, 'KES')}</td>
            </tr>
        `).join('') || '';

        return `
        <div class="ep-grid-2">
            <div class="ep-card">
                <h4 class="ep-card-title"><i class="fa fa-tags"></i> Other Expenses by Account</h4>
                <div class="ep-subtext" style="margin-bottom: 10px;">Hotel, delegate materials (bags/books/pens), and other non-trainer costs tagged to this event via Purchase Invoice, grouped by expense account.</div>
                <table class="ep-table">
                    <thead><tr><th>Account</th><th>Amount</th></tr></thead>
                    <tbody>${category_rows}</tbody>
                </table>
            </div>
            <div class="ep-card">
                <h4 class="ep-card-title"><i class="fa fa-file-text-o"></i> Other Expense Invoices</h4>
                ${invoice_rows ? `
                <table class="ep-table">
                    <thead><tr><th>Invoice</th><th>Supplier</th><th>Total</th><th>Outstanding</th></tr></thead>
                    <tbody>${invoice_rows}</tbody>
                </table>` : `<div class="ep-empty-row">No invoices yet.</div>`}
            </div>
        </div>`;
    }

    render_net_profit_statement(d) {
        const profit_class = d.net_profit >= 0 ? 'ep-amount-pos' : 'ep-amount-neg';
        return `
        <div class="ep-card ep-profit-card">
            <h4 class="ep-card-title"><i class="fa fa-calculator"></i> Net Profit Statement</h4>
            <table class="ep-table ep-statement-table">
                <tbody>
                    <tr><td>Total Income Collected</td><td class="ep-num">${format_currency(d.income.total_collected, 'KES')}</td></tr>
                    <tr><td>Less: Trainer Costs Paid</td><td class="ep-num">- ${format_currency(d.expenses.trainers.paid, 'KES')}</td></tr>
                    <tr><td>Less: Other Expenses Paid</td><td class="ep-num">- ${format_currency(d.expenses.other.paid, 'KES')}</td></tr>
                    <tr class="ep-row-total"><td><strong>Net Profit</strong></td><td class="ep-num ${profit_class}"><strong>${format_currency(d.net_profit, 'KES')}</strong></td></tr>
                    <tr><td>Profit Margin</td><td class="ep-num"><strong>${d.profit_margin}%</strong></td></tr>
                </tbody>
            </table>
        </div>`;
    }

    status_badge(status) {
        const map = {
            'Paid': 'ep-badge-green',
            'Partially Paid': 'ep-badge-orange',
            'Unpaid': 'ep-badge-red'
        };
        return `<span class="ep-badge ${map[status] || 'ep-badge-muted'}">${status || 'Unpaid'}</span>`;
    }

    inject_styles() {
        if (document.getElementById('event-profitability-styles')) return;
        $(`<style id="event-profitability-styles">
            .ep-wrap { padding-bottom: 40px; }
            .ep-empty { padding: 60px 0; text-align: center; color: ${EP_PALETTE.slate}; }
            .ep-card {
                background: white;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(30, 58, 138, 0.06);
                border: 1px solid ${EP_PALETTE.border};
                padding: 22px;
                margin-bottom: 20px;
            }
            .ep-header-card {
                background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
                color: white;
                border: none;
            }
            .ep-header-info h2 { margin: 0 0 8px 0; color: white; }
            .ep-header-meta { margin-bottom: 8px; }
            .ep-chip {
                display: inline-block; background: rgba(255,255,255,0.18);
                padding: 3px 10px; border-radius: 12px; font-size: 11.5px;
                margin-right: 8px;
            }
            .ep-chip-muted { background: rgba(255,255,255,0.1); }
            .ep-contact-row span { margin-right: 18px; font-size: 12.5px; opacity: 0.9; }
            .ep-kpi-row {
                display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px; margin-bottom: 20px;
            }
            .ep-kpi-card {
                border-radius: 10px; padding: 18px; text-align: center;
                border: 1px solid ${EP_PALETTE.border};
            }
            .ep-kpi-icon { font-size: 20px; margin-bottom: 8px; }
            .ep-kpi-value { font-size: 19px; font-weight: 700; margin-bottom: 4px; }
            .ep-kpi-label { font-size: 11.5px; color: ${EP_PALETTE.slate}; text-transform: uppercase; letter-spacing: 0.3px; }
            .ep-tone-primary { background: #eff6ff; } .ep-tone-primary .ep-kpi-icon, .ep-tone-primary .ep-kpi-value { color: ${EP_PALETTE.primary}; }
            .ep-tone-green { background: ${EP_PALETTE.greenBg}; } .ep-tone-green .ep-kpi-icon, .ep-tone-green .ep-kpi-value { color: ${EP_PALETTE.green}; }
            .ep-tone-orange { background: ${EP_PALETTE.orangeBg}; } .ep-tone-orange .ep-kpi-icon, .ep-tone-orange .ep-kpi-value { color: ${EP_PALETTE.orange}; }
            .ep-tone-red { background: ${EP_PALETTE.redBg}; } .ep-tone-red .ep-kpi-icon, .ep-tone-red .ep-kpi-value { color: ${EP_PALETTE.red}; }
            .ep-grid-2 {
                display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start;
            }
            @media (max-width: 900px) { .ep-grid-2 { grid-template-columns: 1fr; } }
            .ep-card-title { margin: 0 0 14px 0; color: ${EP_PALETTE.primary}; font-size: 14px; }
            .ep-card-title i { margin-right: 6px; }
            .ep-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
            .ep-table th {
                text-align: left; padding: 8px 10px; background: ${EP_PALETTE.slateBg};
                color: ${EP_PALETTE.slate}; font-size: 11px; text-transform: uppercase;
                border-bottom: 2px solid ${EP_PALETTE.border};
            }
            .ep-table td { padding: 9px 10px; border-bottom: 1px solid ${EP_PALETTE.border}; vertical-align: top; }
            .ep-num { text-align: right; }
            .ep-row-total td { border-top: 2px solid ${EP_PALETTE.border}; border-bottom: none; padding-top: 12px; }
            .ep-subtext { color: #94a3b8; font-size: 11px; }
            .ep-empty-row { text-align: center; color: #94a3b8; padding: 20px !important; }
            .ep-badge {
                display: inline-block; padding: 3px 10px; border-radius: 10px;
                font-size: 10.5px; font-weight: 600;
            }
            .ep-badge-green { background: ${EP_PALETTE.greenBg}; color: ${EP_PALETTE.green}; }
            .ep-badge-orange { background: ${EP_PALETTE.orangeBg}; color: ${EP_PALETTE.orange}; }
            .ep-badge-red { background: ${EP_PALETTE.redBg}; color: ${EP_PALETTE.red}; }
            .ep-badge-muted { background: #f1f5f9; color: #64748b; }
            .ep-amount-pos { color: ${EP_PALETTE.green}; font-weight: 600; }
            .ep-amount-neg { color: ${EP_PALETTE.red}; font-weight: 600; }
            .ep-profit-card { border: 2px solid ${EP_PALETTE.primary}; }
            .ep-statement-table td { font-size: 13.5px; padding: 11px 10px; }
            @media print {
                .page-head, .page-sidebar, .std-toolbar, .page-actions { display: none !important; }
                .ep-card { box-shadow: none; }
            }
        </style>`).appendTo('head');
    }
}
