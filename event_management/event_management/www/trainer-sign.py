import frappe
from event_management.event_management.doctype.event_trainer.event_trainer import get_contract_for_signing


def get_context(context):
    context.no_cache = 1
    token = frappe.form_dict.get("token")
    result = get_contract_for_signing(token)
    context.update(result)
    context.token = token
    return context
