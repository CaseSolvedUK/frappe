# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import sys
import select
import getpass

import frappe
from frappe.geo.doctype.country.country import import_country_and_currency
from frappe.utils.password import update_password
from frappe.utils import now_datetime
from datetime import timedelta


def before_install():
	frappe.reload_doc("core", "doctype", "doctype_state")
	frappe.reload_doc("core", "doctype", "docfield")
	frappe.reload_doc("core", "doctype", "docperm")
	frappe.reload_doc("core", "doctype", "doctype_action")
	frappe.reload_doc("core", "doctype", "doctype_link")
	frappe.reload_doc("desk", "doctype", "form_tour_step")
	frappe.reload_doc("desk", "doctype", "form_tour")
	frappe.reload_doc("core", "doctype", "doctype")
	frappe.clear_cache()


def after_install():
	create_user_type()
	install_basic_docs()

	from frappe.core.doctype.file.utils import make_home_folder
	from frappe.core.doctype.language.language import sync_languages

	make_home_folder()
	import_country_and_currency()
	sync_languages()

	# save default print setting
	print_settings = frappe.get_doc("Print Settings")
	print_settings.save()

	# all roles to admin
	frappe.get_doc("User", "Administrator").add_roles(*frappe.get_all("Role", pluck="name"))

	# update admin password
	update_password("Administrator", get_admin_password())

	if not frappe.conf.skip_setup_wizard:
		# only set home_page if the value doesn't exist in the db
		if not frappe.db.get_default("desktop:home_page"):
			frappe.db.set_default("desktop:home_page", "setup-wizard")

	# clear test log
	with open(frappe.get_site_path(".test_log"), "w") as f:
		f.write("")

	add_standard_navbar_items()

	frappe.db.commit()


def create_user_type():
	for user_type in ["System User", "Website User"]:
		if not frappe.db.exists("User Type", user_type):
			frappe.get_doc({"doctype": "User Type", "name": user_type, "is_standard": 1}).insert(
				ignore_permissions=True
			)


def install_basic_docs():
	# core users / roles
	install_docs = [
		{
			"doctype": "User",
			"name": "Administrator",
			"first_name": "Administrator",
			"email": "admin@example.com",
			"enabled": 1,
			"is_admin": 1,
			"roles": [{"role": "Administrator"}],
			"thread_notify": 0,
			"send_me_a_copy": 0,
		},
		{
			"doctype": "User",
			"name": "Guest",
			"first_name": "Guest",
			"email": "guest@example.com",
			"enabled": 1,
			"is_guest": 1,
			"roles": [{"role": "Guest"}],
			"thread_notify": 0,
			"send_me_a_copy": 0,
		},
		{"doctype": "Role", "role_name": "Report Manager"},
		{"doctype": "Role", "role_name": "Translator"},
		{
			"doctype": "Workflow State",
			"workflow_state_name": "Pending",
			"icon": "question-sign",
			"style": "",
		},
		{
			"doctype": "Workflow State",
			"workflow_state_name": "Approved",
			"icon": "ok-sign",
			"style": "Success",
		},
		{
			"doctype": "Workflow State",
			"workflow_state_name": "Rejected",
			"icon": "remove",
			"style": "Danger",
		},
		{"doctype": "Workflow Action Master", "workflow_action_name": "Approve"},
		{"doctype": "Workflow Action Master", "workflow_action_name": "Reject"},
		{"doctype": "Workflow Action Master", "workflow_action_name": "Review"},
	]

	for d in install_docs:
		try:
			frappe.get_doc(d).insert(ignore_if_duplicate=True)
		except frappe.NameError:
			pass


def get_admin_password():
	def ask_admin_password():
		admin_password = getpass.getpass("Set Administrator password: ")
		admin_password2 = getpass.getpass("Re-enter Administrator password: ")
		if not admin_password == admin_password2:
			print("\nPasswords do not match")
			return ask_admin_password()
		return admin_password

	admin_password = frappe.conf.get("admin_password")
	if not admin_password:
		return ask_admin_password()
	return admin_password


def before_tests():
	if len(frappe.get_installed_apps()) > 1:
		# don't run before tests if any other app is installed
		return

	frappe.db.truncate("Custom Field")
	frappe.db.truncate("Event")

	frappe.clear_cache()

	# complete setup if missing
	if not frappe.is_setup_complete():
		complete_setup_wizard()

	frappe.db.set_single_value("Website Settings", "disable_signup", 0)
	frappe.db.commit()
	frappe.clear_cache()


def complete_setup_wizard():
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	setup_complete(
		{
			"language": "English",
			"email": "test@erpnext.com",
			"full_name": "Test User",
			"password": "test",
			"country": "United States",
			"timezone": "America/New_York",
			"currency": "USD",
		}
	)


def import_country_and_currency():
	from frappe.geo.country_info import get_all
	from frappe.utils import update_progress_bar

	data = get_all()

	print("\nOverwriting your existing Country & Currency data in 10 seconds, press Enter to abort...")
	r, w, x = select.select([sys.stdin], [], [], 10)
	if r:
		overwrite = False
		r[0].read()
	else:
		overwrite = True

	for i, name in enumerate(data):
		update_progress_bar("Updating country info", i, len(data))
		country = frappe._dict(data[name])
		add_country_and_currency(name, country, overwrite)

	del_orphaned_currencies()
	print("")

	# enable frequently used currencies
	for currency in ("INR", "USD", "GBP", "EUR", "AED", "AUD", "JPY", "CNY", "CHF"):
		frappe.db.set_value("Currency", currency, "enabled", 1)

def add_country_and_currency(name, country, overwrite=False):
	data = {
		"country_name": name,
		"code": country.code,
		"date_format": country.date_format or "dd-mm-yyyy",
		"time_format": country.time_format or "HH:mm:ss",
		"time_zones": "\n".join(country.timezones or []),
		"docstatus": 0
	}
	try:
		doc = frappe.get_last_doc("Country", filters={"code": country.code})
		if overwrite:
			doc.update(data).save()
	except frappe.exceptions.DoesNotExistError:
		frappe.get_doc(doctype="Country", **data).db_insert()

	if country.currency:
		try:
			exists = True
			doc = frappe.get_cached_doc("Currency", country.currency)
			recent = doc.modified > (now_datetime() - timedelta(minutes=5))
		except frappe.exceptions.DoesNotExistError:
			exists = False
			recent = False
			doc = frappe.get_doc({
				"doctype": "Currency",
				"currency_name": country.currency})

		if not exists or (overwrite and not recent):
			if country.currency_name:
				doc.unit_name = country.currency_name
			if country.currency_fraction:
				doc.fraction = country.currency_fraction
			if country.currency_fraction_units:
				doc.fraction_units = country.currency_fraction_units
			if country.smallest_currency_fraction_value:
				doc.smallest_currency_fraction_value = country.smallest_currency_fraction_value
			if country.currency_symbol:
				doc.symbol = country.currency_symbol
			if country.number_format:
				doc.number_format = country.number_format
			doc.docstatus = 0
			if exists:
				doc.save()
			else:
				doc.insert()
		frappe.db.set_value("Country", name, "currency", country.currency)

def del_orphaned_currencies():
	used = set(c[0] for c in frappe.get_all("Country", fields=['currency'], as_list=True) if c[0])
	whole = set(c[0] for c in frappe.get_all("Currency", fields=['currency_name'], as_list=True) if c[0])
	orphans = list(whole - used)
	if orphans:
		frappe.db.delete("Currency", {'currency_name': ['in', orphans]})

def add_standard_navbar_items():
	navbar_settings = frappe.get_single("Navbar Settings")

	# don't add settings/help options if they're already present
	if navbar_settings.settings_dropdown and navbar_settings.help_dropdown:
		return

	navbar_settings.settings_dropdown = []
	navbar_settings.help_dropdown = []

	for item in frappe.get_hooks("standard_navbar_items"):
		navbar_settings.append("settings_dropdown", item)

	for item in frappe.get_hooks("standard_help_items"):
		navbar_settings.append("help_dropdown", item)

	navbar_settings.save()
