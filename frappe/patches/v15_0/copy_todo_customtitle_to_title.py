import frappe

def execute():
	# Check if custom_title field exists
	from_field = "custom_title"
	try:
		frappe.db.get_all("ToDo", pluck=from_field)
	except Exception:
		return

	# copy custom title to title
	result = frappe.db.sql(f"UPDATE `tabToDo` SET title={from_field}")

	# remove custom title field
	try:
		doc = frappe.get_last_doc("Custom Field", filters={"dt": "ToDo", "fieldname": from_field})
		doc.delete()
	except Exception:
		pass
