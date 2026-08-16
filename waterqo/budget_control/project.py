import frappe
from frappe import _
from frappe.utils import flt, fmt_money
from waterqo.budget_control.utils import get_project_actual_cost, get_project_task_allocation

def validate_project(doc, method=None):
	"""Validates Project budget and updates calculated budget fields on save."""
	project_budget = flt(doc.custom_project_budget)
	
	if doc.name and frappe.db.exists("Project", doc.name):
		total_task_budget = get_project_task_allocation(doc.name)
	else:
		total_task_budget = 0.0

	# Section 5: Check if Project Budget is reduced below allocated Task Budgets
	if project_budget < total_task_budget:
		currency = frappe.db.get_value("Company", doc.company, "default_currency") if doc.company else (frappe.db.get_default("currency") or "")
		frappe.throw(
			_(
				"Project Budget cannot be less than the Total Task Budget already allocated to Tasks.<br>"
				"Current Task Allocation: {0}<br>"
				"New Project Budget: {1}<br>"
				"Required minimum: {2}"
			).format(
				fmt_money(total_task_budget, currency=currency),
				fmt_money(project_budget, currency=currency),
				fmt_money(total_task_budget, currency=currency),
			),
			title=_("Project Budget Violation"),
		)

	actual_cost = get_project_actual_cost(doc.name) if doc.name else 0.0
	unallocated = project_budget - total_task_budget
	remaining = project_budget - actual_cost
	utilization = (actual_cost / project_budget * 100.0) if project_budget > 0 else 0.0

	doc.custom_total_task_budget = total_task_budget
	doc.custom_unallocated_budget = unallocated
	doc.custom_actual_project_cost = actual_cost
	doc.custom_remaining_project_budget = remaining
	doc.custom_project_budget_utilization = utilization
