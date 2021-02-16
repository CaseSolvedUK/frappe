from __future__ import unicode_literals
"""
Update the currency info with the name for money_in_words
"""
import frappe
from frappe.utils.install import import_country_and_currency

def execute():
	frappe.reload_doc("Geo", "doctype", "Country")
	frappe.reload_doc("Geo", "doctype", "Currency")
	import_country_and_currency()
