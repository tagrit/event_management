frappe.listview_settings['Event Registration'] = {
    onload: function (listview) {
        listview.page.add_inner_button(__('This Week'), () => apply_period_filter(listview, 'week'), __('Filter By Period'));
        listview.page.add_inner_button(__('This Month'), () => apply_period_filter(listview, 'month'), __('Filter By Period'));
        listview.page.add_inner_button(__('This Year'), () => apply_period_filter(listview, 'year'), __('Filter By Period'));
        listview.page.add_inner_button(__('Clear Period'), () => clear_period_filter(listview), __('Filter By Period'));
    }
};

function get_period_range(period) {
    const today = new Date();
    const year = today.getFullYear();
    const month = today.getMonth();
    let start, end;

    if (period === 'week') {
        const day = today.getDay();
        const diff_to_monday = day === 0 ? 6 : day - 1;
        start = new Date(year, month, today.getDate() - diff_to_monday);
        end = new Date(year, month, start.getDate() + 6);
    } else if (period === 'month') {
        start = new Date(year, month, 1);
        end = new Date(year, month + 1, 0);
    } else if (period === 'year') {
        start = new Date(year, 0, 1);
        end = new Date(year, 11, 31);
    }

    return [format_date(start), format_date(end)];
}

function format_date(date) {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

function apply_period_filter(listview, period) {
    const [start, end] = get_period_range(period);
    clear_period_filter(listview);
    listview.filter_area.add([[listview.doctype, 'start_date', 'Between', [start, end]]]);
}

function clear_period_filter(listview) {
    try {
        listview.filter_area.remove('start_date');
    } catch (e) {
        // no existing start_date filter to remove
    }
}
