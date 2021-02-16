# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

# all country info
import os
from functools import lru_cache

import frappe
from frappe.utils.deprecations import deprecated
from frappe.utils.momentjs import get_all_timezones


def get_country_info(country=None):
	data = get_all()
	data = frappe._dict(data.get(country, {}))
	if "date_format" not in data:
		data.date_format = "dd-mm-yyyy"
	if "time_format" not in data:
		data.time_format = "HH:mm:ss"
	if "currency" not in data:
		data.currency = ""
	if "number_format" in data:
		sections, data.currency_fraction_units, data.smallest_currency_fraction_value = number_format_info(data.get("number_format"))

	return data


def get_all():
	with open(os.path.join(os.path.dirname(__file__), "country_info.json")) as local_info:
		all_data = json.loads(local_info.read())
	return all_data

def number_format_info(format):
	import re
	nfsplit = re.findall("#+", format)
	sections = len(nfsplit)
	decimal_places = 0 if sections <= 2 else len(nfsplit[-1])
	fraction_units = int("1" + "0" * decimal_places)
	return sections, fraction_units, 1.0 / fraction_units

@frappe.whitelist(allow_guest=True)
def get_country_timezone_info():
	return _get_country_timezone_info()


@lru_cache(maxsize=2)
def _get_country_timezone_info():
	return {"country_info": get_all(), "all_timezones": get_all_timezones()}


@deprecated
def get_translated_dict():
	return get_translated_countries()


def get_translated_countries():
	from babel.dates import Locale

	translated_dict = {}
	locale = Locale.parse(frappe.local.lang, sep="-")

	# country names && currencies
	for country, info in get_all().items():
		country_name = locale.territories.get((info.get("code") or "").upper())
		if country_name:
			translated_dict[country] = country_name

	return translated_dict

def normalise():
	"Manual helper function to keep the fixture up-to-date & normalised"
	all_data = get_all()
	for country in all_data:
		all_data[country] = get_country_info(country)

	with open(os.path.join(os.path.dirname(__file__), "country_info.json"), "w") as local_info:
		json.dump(all_data, local_info, indent=1, sort_keys=True)

@frappe.whitelist()
def dump_fixture_from_db():
	"Update the repo fixture from the content of the db"
	frappe.only_for(["Administrator", "System Manager"])
	with open(os.path.join(os.path.dirname(__file__), "country_info.json"), "w") as fp:
		ctlist = frappe.get_all("Country", fields=["name","code","date_format","time_format","time_zones","currency"], order_by="name", as_list=False)
		fixture = {ct.pop("name"): ct for ct in ctlist}
		cylist = frappe.get_all("Currency", fields=["name","unit_name as currency_name","fraction as currency_fraction",
			"fraction_units as currency_fraction_units","smallest_currency_fraction_value","symbol as currency_symbol","number_format"], order_by="name", as_list=False)
		cys = {cy.pop("name"): cy for cy in cylist}
		for ctn, ct in fixture.items():
			ct["timezones"] = ct.pop("time_zones").split("\n")
			if ct["currency"]:
				ct.update(cys[ct["currency"]])
			else:
				ct.pop("currency")
		json.dump(fixture, fp, indent=1, sort_keys=True)

def update():
	"Manual helper function to complete the fixture number formats"
	with open(os.path.join(os.path.dirname(__file__), "currency_info.json")) as nformats:
		nformats = json.loads(nformats.read())

	all_data = get_all()

	for country in all_data:
		data = all_data[country]
		data["number_format"] = nformats.get(data.get("currency", "default"), nformats.get("default"))[
			"display"
		]

	with open(os.path.join(os.path.dirname(__file__), "country_info.json"), "w") as local_info:
		local_info.write(json.dumps(all_data, indent=1))
