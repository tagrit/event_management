frappe.pages['event-dashboard'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Event Management Analytics',
        single_column: true
    });

    wrapper.event_dashboard = new EventDashboard(page);
};

frappe.pages['event-dashboard'].on_page_show = function (wrapper) {
    if (wrapper.event_dashboard) {
        wrapper.event_dashboard.refresh();
    }
};

function ed_escape(text) {
    if (text === undefined || text === null) return '';
    if (frappe.utils && typeof frappe.utils.escape_html === 'function') {
        return frappe.utils.escape_html(text);
    }
    return $('<div>').text(text).html();
}

const ED_PALETTE = {
    primary: '#1e3a8a',
    primaryLight: '#3b82f6',
    green: '#16a34a',
    greenBg: '#f0fdf4',
    orange: '#d97706',
    orangeBg: '#fffbeb',
    red: '#dc2626',
    redBg: '#fef2f2',
    purple: '#8b5cf6',
    teal: '#0d9488',
    slate: '#475569',
    slateBg: '#f8fafc',
    border: '#e2e8f0'
};

const ED_CHART_COLORS = ['#3b82f6', '#16a34a', '#d97706', '#dc2626', '#8b5cf6', '#0d9488', '#ec4899', '#64748b'];

class EventDashboard {
    constructor(page) {
        this.page = page;
        this.is_finance_user = frappe.user.has_role(['Accounts User', 'Accounts Manager', 'Auditor']);
        this.make();
    }

    make() {
        this.inject_styles();
        this.$container = $('<div class="ed-wrap">').appendTo(this.page.main);
        this.refresh();
    }

    refresh() {
        this.page.set_title(__('Event Management Analytics'));
        this.load_data();
    }

    load_data() {
        this.$container.html('<div class="ed-empty">Loading analytics...</div>');
        frappe.call({
            method: 'event_management.event_management.doctype.event_registration.event_registration.get_dashboard_data',
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
            ${this.render_header()}
            ${this.render_kpis(d.summary)}
            ${this.is_finance_user ? this.render_financial_kpis(d.financial) : ''}
            <div class="ed-grid-2">
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-bar-chart"></i> Events per Month</h4>
                    <div id="ed-chart-events-month"></div>
                </div>
                ${this.is_finance_user ? `
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-line-chart"></i> Revenue per Month (Budgeted)</h4>
                    <div id="ed-chart-revenue-month"></div>
                </div>` : `
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-pie-chart"></i> Event Status</h4>
                    <div id="ed-chart-event-status"></div>
                </div>`}
            </div>
            <div class="ed-grid-3">
                ${this.is_finance_user ? `
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-pie-chart"></i> Event Status</h4>
                    <div id="ed-chart-event-status"></div>
                </div>` : ''}
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-pie-chart"></i> Delegate Confirmation</h4>
                    <div id="ed-chart-delegate-status"></div>
                </div>
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-pie-chart"></i> Setup Type</h4>
                    <div id="ed-chart-setup-type"></div>
                </div>
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-pie-chart"></i> Event Type</h4>
                    <div id="ed-chart-event-type"></div>
                </div>
            </div>
            <div class="ed-grid-2">
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-sitemap"></i> Events by Division</h4>
                    <div id="ed-chart-division"></div>
                </div>
                ${this.is_finance_user ? `
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-pie-chart"></i> Trainer Payment Status</h4>
                    <div id="ed-chart-trainer-payment"></div>
                </div>` : `
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-map-marker"></i> Top Locations</h4>
                    ${this.render_locations_table(d.top_locations)}
                </div>`}
            </div>
            <div class="ed-grid-2">
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-building"></i> Top Organizations</h4>
                    ${this.render_organizations_table(d.top_organizations)}
                </div>
                ${this.is_finance_user ? `
                <div class="ed-card">
                    <h4 class="ed-card-title"><i class="fa fa-map-marker"></i> Top Locations</h4>
                    ${this.render_locations_table(d.top_locations)}
                </div>` : ''}
            </div>
        `);

        this.page.clear_menu();
        this.page.clear_inner_toolbar();
        this.page.add_inner_button(__('Refresh'), () => this.load_data());

        this.render_charts(d);
    }

    render_header() {
        const today = frappe.datetime.str_to_user(frappe.datetime.now_date());
        return `
        <div class="ed-card ed-header-card">
            <div>
                <h2>Event Management Analytics</h2>
                <div class="ed-header-sub">Full performance overview across every event, delegate, and trainer &middot; as of ${today}</div>
            </div>
        </div>`;
    }

    render_kpis(summary) {
        return `
        <div class="ed-kpi-row">
            ${this.kpi_card('Total Delegates', summary.total_delegates, 'fa-users', 'primary')}
            ${this.kpi_card('Confirmation Rate', summary.confirmation_rate + '%', 'fa-check-circle', 'green')}
            ${this.kpi_card('Confirmed Events', summary.confirmed_events, 'fa-calendar-check-o', 'green')}
            ${this.kpi_card('Pending Confirmation', summary.pending_events, 'fa-clock-o', 'orange')}
            ${this.kpi_card('Draft Events', summary.draft_events, 'fa-file-o', 'slate')}
            ${this.kpi_card('Upcoming (30 days)', summary.upcoming_events, 'fa-calendar', 'purple')}
        </div>`;
    }

    render_financial_kpis(financial) {
        const profit_tone = financial.net_profit >= 0 ? 'green' : 'red';
        return `
        <div class="ed-kpi-row">
            ${this.kpi_card('Income Collected', format_currency(financial.income_collected, 'KES'), 'fa-money', 'primary')}
            ${this.kpi_card('Expenses Paid', format_currency(financial.expenses_paid, 'KES'), 'fa-shopping-cart', 'orange')}
            ${this.kpi_card('Net Profit', format_currency(financial.net_profit, 'KES'), 'fa-line-chart', profit_tone)}
            ${this.kpi_card('Profit Margin', financial.profit_margin + '%', 'fa-percent', profit_tone)}
        </div>`;
    }

    kpi_card(label, value, icon, tone) {
        return `
        <div class="ed-kpi-card ed-tone-${tone}">
            <div class="ed-kpi-icon"><i class="fa ${icon}"></i></div>
            <div class="ed-kpi-value">${value}</div>
            <div class="ed-kpi-label">${label}</div>
        </div>`;
    }

    render_organizations_table(orgs) {
        const show_revenue = this.is_finance_user;
        const rows = (orgs || []).map(org => `
            <tr>
                <td>${ed_escape(org.organization_name)}</td>
                <td class="ed-num">${org.event_count}</td>
                ${show_revenue ? `<td class="ed-num">${format_currency(org.total_revenue, 'KES')}</td>` : ''}
            </tr>
        `).join('') || `<tr><td colspan="${show_revenue ? 3 : 2}" class="ed-empty-row">No data yet.</td></tr>`;

        return `
        <table class="ed-table">
            <thead><tr><th>Organization</th><th>Events</th>${show_revenue ? '<th>Revenue</th>' : ''}</tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
    }

    render_locations_table(locations) {
        const rows = (locations || []).map(loc => `
            <tr>
                <td>${ed_escape(loc.event_location)}</td>
                <td class="ed-num">${loc.event_count}</td>
            </tr>
        `).join('') || `<tr><td colspan="2" class="ed-empty-row">No data yet.</td></tr>`;

        return `
        <table class="ed-table">
            <thead><tr><th>Location</th><th>Events</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
    }

    render_charts(d) {
        this.render_bar_chart('ed-chart-events-month', 'Events', d.charts.events_by_month, 'month', 'count', ED_PALETTE.primaryLight);

        if (this.is_finance_user) {
            this.render_bar_chart('ed-chart-revenue-month', 'Revenue', d.charts.revenue_by_month, 'month', 'revenue', ED_PALETTE.green);

            this.render_pie_chart('ed-chart-trainer-payment', d.trainer_payment_breakdown, 'payment_status', 'count');
        }

        this.render_pie_chart('ed-chart-event-status', [
            { label: 'Confirmed', count: d.summary.confirmed_events },
            { label: 'Pending', count: d.summary.pending_events },
            { label: 'Draft', count: d.summary.draft_events }
        ], 'label', 'count');

        this.render_pie_chart('ed-chart-delegate-status', [
            { label: 'Confirmed', count: d.summary.confirmed_delegates },
            { label: 'Pending', count: d.summary.pending_delegates }
        ], 'label', 'count');

        this.render_pie_chart('ed-chart-setup-type', d.setup_breakdown, 'setup', 'count');
        this.render_pie_chart('ed-chart-event-type', d.type_breakdown, 'type', 'count');
        this.render_bar_chart('ed-chart-division', 'Events', d.division_breakdown, 'division', 'event_count', ED_PALETTE.purple);
    }

    render_bar_chart(container_id, dataset_name, rows, label_key, value_key, color) {
        const el = document.getElementById(container_id);
        if (!el) return;
        rows = (rows || []).filter(r => r[label_key]);
        if (!rows.length) {
            el.innerHTML = '<div class="ed-empty-row">No data yet.</div>';
            return;
        }
        new frappe.Chart(el, {
            data: {
                labels: rows.map(r => r[label_key]),
                datasets: [{ name: dataset_name, values: rows.map(r => frappe.utils.flt(r[value_key])) }]
            },
            type: 'bar',
            height: 240,
            colors: [color],
            axisOptions: { xIsSeries: false }
        });
    }

    render_pie_chart(container_id, rows, label_key, value_key) {
        const el = document.getElementById(container_id);
        if (!el) return;
        rows = (rows || []).filter(r => r[label_key] && frappe.utils.flt(r[value_key]) > 0);
        if (!rows.length) {
            el.innerHTML = '<div class="ed-empty-row">No data yet.</div>';
            return;
        }
        new frappe.Chart(el, {
            data: {
                labels: rows.map(r => r[label_key]),
                datasets: [{ values: rows.map(r => frappe.utils.flt(r[value_key])) }]
            },
            type: 'pie',
            height: 240,
            colors: ED_CHART_COLORS
        });
    }

    inject_styles() {
        if (document.getElementById('event-dashboard-styles')) return;
        $(`<style id="event-dashboard-styles">
            .ed-wrap { padding-bottom: 40px; }
            .ed-empty { padding: 60px 0; text-align: center; color: ${ED_PALETTE.slate}; }
            .ed-card {
                background: white;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(30, 58, 138, 0.06);
                border: 1px solid ${ED_PALETTE.border};
                padding: 22px;
                margin-bottom: 20px;
            }
            .ed-header-card {
                background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
                color: white;
                border: none;
            }
            .ed-header-card h2 { margin: 0 0 6px 0; color: white; }
            .ed-header-sub { font-size: 12.5px; opacity: 0.9; }
            .ed-kpi-row {
                display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
                gap: 14px; margin-bottom: 20px;
            }
            .ed-kpi-card {
                border-radius: 10px; padding: 16px; text-align: center;
                border: 1px solid ${ED_PALETTE.border};
            }
            .ed-kpi-icon { font-size: 18px; margin-bottom: 6px; }
            .ed-kpi-value { font-size: 17px; font-weight: 700; margin-bottom: 4px; }
            .ed-kpi-label { font-size: 10.5px; color: ${ED_PALETTE.slate}; text-transform: uppercase; letter-spacing: 0.3px; }
            .ed-tone-primary { background: #eff6ff; } .ed-tone-primary .ed-kpi-icon, .ed-tone-primary .ed-kpi-value { color: ${ED_PALETTE.primary}; }
            .ed-tone-green { background: ${ED_PALETTE.greenBg}; } .ed-tone-green .ed-kpi-icon, .ed-tone-green .ed-kpi-value { color: ${ED_PALETTE.green}; }
            .ed-tone-orange { background: ${ED_PALETTE.orangeBg}; } .ed-tone-orange .ed-kpi-icon, .ed-tone-orange .ed-kpi-value { color: ${ED_PALETTE.orange}; }
            .ed-tone-red { background: ${ED_PALETTE.redBg}; } .ed-tone-red .ed-kpi-icon, .ed-tone-red .ed-kpi-value { color: ${ED_PALETTE.red}; }
            .ed-tone-purple { background: #f5f3ff; } .ed-tone-purple .ed-kpi-icon, .ed-tone-purple .ed-kpi-value { color: ${ED_PALETTE.purple}; }
            .ed-tone-slate { background: ${ED_PALETTE.slateBg}; } .ed-tone-slate .ed-kpi-icon, .ed-tone-slate .ed-kpi-value { color: ${ED_PALETTE.slate}; }
            .ed-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start; }
            .ed-grid-3 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; align-items: start; }
            @media (max-width: 1100px) { .ed-grid-3 { grid-template-columns: 1fr 1fr; } }
            @media (max-width: 900px) { .ed-grid-2 { grid-template-columns: 1fr; } .ed-grid-3 { grid-template-columns: 1fr; } }
            .ed-card-title { margin: 0 0 14px 0; color: ${ED_PALETTE.primary}; font-size: 13.5px; }
            .ed-card-title i { margin-right: 6px; }
            .ed-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
            .ed-table th {
                text-align: left; padding: 8px 10px; background: ${ED_PALETTE.slateBg};
                color: ${ED_PALETTE.slate}; font-size: 11px; text-transform: uppercase;
                border-bottom: 2px solid ${ED_PALETTE.border};
            }
            .ed-table td { padding: 9px 10px; border-bottom: 1px solid ${ED_PALETTE.border}; }
            .ed-num { text-align: right; }
            .ed-empty-row { text-align: center; color: #94a3b8; padding: 30px 0; }
        </style>`).appendTo('head');
    }
}
