import frappe
from frappe import _
from frappe.utils import flt, fmt_money
from waterqo.budget_control.utils import recalculate_project_budget, recalculate_task_budget

def validate_journal_entry(doc, method=None):
	"""Auto-populates Project from Task on Journal Entry accounts, validates consistency and budget limits."""
	for row in doc.accounts:
		if row.task and not row.project:
			row.project = frappe.db.get_value("Task", row.task, "project")

		if row.task:
			task_proj = frappe.db.get_value("Task", row.task, "project")
			if not task_proj:
				frappe.throw(
					_("Row #{0}: Task '{1}' is not associated with any Project.").format(row.idx, row.task),
					title=_("Invalid Task"),
				)
			if row.project and row.project != task_proj:
				frappe.throw(
					_("Row #{0}: Selected Task '{1}' belongs to Project '{2}', but Project '{3}' was selected.")
					.format(row.idx, row.task, task_proj, row.project),
					title=_("Project Task Mismatch"),
				)

	# Budget Validation for Journal Entry debit costs
	check_journal_entry_budgets(doc)

def check_journal_entry_budgets(doc):
	"""Validates that Journal Entry debit costs do not exceed remaining Task or Project budgets."""
	task_costs = {}
	project_costs = {}

	for row in doc.accounts:
		net_debit = flt(row.debit) - flt(row.credit)
		if net_debit > 0:
			if row.project:
				project_costs[row.project] = project_costs.get(row.project, 0.0) + net_debit
			if row.task:
				task_costs[row.task] = task_costs.get(row.task, 0.0) + net_debit

	# Validate Task Budgets
	for tsk, cost in task_costs.items():
		task_proj = frappe.db.get_value("Task", tsk, "project")
		task_remaining = flt(frappe.db.get_value("Task", tsk, "custom_remaining_task_budget"))

		if cost > task_remaining:
			excess = cost - task_remaining
			company = frappe.db.get_value("Project", task_proj, "company") if task_proj else doc.company
			currency = frappe.db.get_value("Company", company, "default_currency") if company else (frappe.db.get_default("currency") or "")

			frappe.throw(
				_(
					"Task Budget Exceeded for Task '{0}' in Journal Entry.<br>"
					"Remaining Task Budget: {1}<br>"
					"Journal Entry Cost: {2}<br>"
					"Excess Amount: {3}"
				).format(
					tsk,
					fmt_money(task_remaining, currency=currency),
					fmt_money(cost, currency=currency),
					fmt_money(excess, currency=currency),
				),
				title=_("Task Budget Exceeded"),
			)

	# Validate Project Budgets
	for proj, total_cost in project_costs.items():
		proj_remaining = flt(frappe.db.get_value("Project", proj, "custom_remaining_project_budget"))

		if total_cost > proj_remaining:
			excess = total_cost - proj_remaining
			company = frappe.db.get_value("Project", proj, "company") or doc.company
			currency = frappe.db.get_value("Company", company, "default_currency") if company else (frappe.db.get_default("currency") or "")

			frappe.throw(
				_(
					"Project Budget Exceeded for Project '{0}' in Journal Entry.<br>"
					"Remaining Project Budget: {1}<br>"
					"Journal Entry Cost: {2}<br>"
					"Excess Amount: {3}"
				).format(
					proj,
					fmt_money(proj_remaining, currency=currency),
					fmt_money(total_cost, currency=currency),
					fmt_money(excess, currency=currency),
				),
				title=_("Project Budget Exceeded"),
			)

def on_submit_journal_entry(doc, method=None):
	"""Recalculates Project and Task actual costs upon Journal Entry submission."""
	affected_projects = set(row.project for row in doc.accounts if row.project)
	affected_tasks = set(row.task for row in doc.accounts if row.task)

	for proj in affected_projects:
		recalculate_project_budget(proj)

	for tsk in affected_tasks:
		recalculate_task_budget(tsk, update_parents=True)

def on_cancel_journal_entry(doc, method=None):
	"""Recalculates Project and Task actual costs upon Journal Entry cancellation."""
	affected_projects = set(row.project for row in doc.accounts if row.project)
	affected_tasks = set(row.task for row in doc.accounts if row.task)

	for proj in affected_projects:
		recalculate_project_budget(proj)

	for tsk in affected_tasks:
		recalculate_task_budget(tsk, update_parents=True)
