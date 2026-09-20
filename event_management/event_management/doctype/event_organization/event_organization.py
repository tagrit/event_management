# Copyright (c) 2025, tagrit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EventOrganization(Document):
	def before_insert(self):
		if not self.customer:
			self.customer = get_or_create_customer(self.organization)


def get_or_create_customer(organization_name):
	"""Match an existing Customer by exact name, or create one. Used both when
	a new Event Organization is created (so the operations team never has to
	think about accounting) and to backfill pre-existing organizations, so
	Finance never has to re-key an organization as a Customer from scratch."""
	existing = frappe.db.get_value("Customer", {"customer_name": organization_name}, "name")
	if existing:
		return existing

	customer_group = (
		frappe.db.get_single_value("Selling Settings", "customer_group")
		or frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
	)
	territory = (
		frappe.db.get_single_value("Selling Settings", "territory")
		or frappe.db.get_value("Territory", {"is_group": 0}, "name")
	)

	if not customer_group or not territory:
		frappe.throw(
			"Cannot auto-create a Customer for this organization: no default "
			"Customer Group or Territory is configured in Selling Settings."
		)

	customer = frappe.get_doc({
		"doctype": "Customer",
		"customer_name": organization_name,
		"customer_group": customer_group,
		"territory": territory,
		"customer_type": "Company",
	})
	customer.insert(ignore_permissions=True)
	return customer.name
