// Copyright (c) 2021, Frappe Technologies and contributors
// For license information, please see license.txt
frappe.listview_settings['Country'] = {
	hide_name_column: true,
	onload: function(listview) {
		if (frappe.user.has_role(['Administrator', 'System Manager'])) {
			listview.page.add_menu_item('Dump Fixture', () => {
				frappe.call({method: 'frappe.geo.country_info.dump_fixture_from_db'});
			});
		}
	}
};
