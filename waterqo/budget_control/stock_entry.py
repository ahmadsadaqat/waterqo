import frappe
from frappe import _
from frappe.utils import flt, fmt_money, now_datetime
from waterqo.budget_control.utils import recalculate_project_budget, recalculate_task_budget

def validate_stock_entry(doc, method=None):
	"""Auto-populates Project from Task, validates Project-Task consistency, and checks budget limits."""
	# Populate header task/project to items if missing
	for item in doc.items:
		if not item.task and doc.task:
			item.task = doc.task

		if item.task and not item.project:
			item.project = frappe.db.get_value("Task", item.task, "project")

		if not item.project and doc.project:
			item.project = doc.project

		# If header project is empty but item project is present, inherit header project
		if not doc.project and item.project:
			doc.project = item.project

		# Validate Task-Project compatibility
		if item.task:
			task_proj = frappe.db.get_value("Task", item.task, "project")
			if not task_proj:
				frappe.throw(
					_("Row #{0}: Task '{1}' is not associated with any Project.").format(item.idx, item.task),
					title=_("Invalid Task"),
				)
			if item.project and item.project != task_proj:
				frappe.throw(
					_("Row #{0}: Selected Task '{1}' belongs to Project '{2}', but Project '{3}' was selected.")
					.format(item.idx, item.task, task_proj, item.project),
					title=_("Project Task Mismatch"),
				)

	# Budget Validation for Material Issue transactions
	if doc.purpose == "Material Issue":
		check_material_issue_budgets(doc)

def check_material_issue_budgets(doc):
	"""Validates that Material Issue transaction costs do not exceed remaining Task or Project budgets."""
	# Group issue amounts by (project, task) and project
	task_costs = {}
	project_costs = {}

	for item in doc.items:
		item_cost = flt(item.basic_amount) or flt(item.amount)
		if item.project:
			project_costs[item.project] = project_costs.get(item.project, 0.0) + item_cost
		if item.task:
			task_costs[item.task] = task_costs.get(item.task, 0.0) + item_cost

	# Validate Task Budgets
	for tsk, cost in task_costs.items():
		task_data = frappe.db.get_value(
			"Task",
			tsk,
			["custom_task_budget", "custom_remaining_task_budget", "project"],
			as_dict=True,
		)
		if not task_data or flt(task_data.custom_task_budget) <= 0:
			continue

		task_proj = task_data.project
		task_remaining = flt(task_data.custom_remaining_task_budget)
		
		if cost > task_remaining:
			excess = cost - task_remaining
			company = frappe.db.get_value("Project", task_proj, "company") if task_proj else doc.company
			currency = frappe.db.get_value("Company", company, "default_currency") if company else (frappe.db.get_default("currency") or "")
			if not doc.custom_allow_budget_override:
				frappe.throw(
					_(
						"Task Budget Exceeded for Task '{0}'.<br>"
						"Remaining Task Budget: {1}<br>"
						"Transaction Cost: {2}<br>"
						"Excess Amount: {3}"
					).format(
						tsk,
						fmt_money(task_remaining, currency=currency),
						fmt_money(cost, currency=currency),
						fmt_money(excess, currency=currency),
					),
					title=_("Task Budget Exceeded"),
				)
			else:
				log_budget_override(doc, task_proj, tsk, task_remaining, cost, excess)

	# Validate Project Budgets
	for proj, total_cost in project_costs.items():
		proj_data = frappe.db.get_value(
			"Project",
			proj,
			["custom_project_budget", "custom_remaining_project_budget", "company"],
			as_dict=True,
		)
		if not proj_data or flt(proj_data.custom_project_budget) <= 0:
			continue

		proj_remaining = flt(proj_data.custom_remaining_project_budget)
		
		if total_cost > proj_remaining:
			excess = total_cost - proj_remaining
			company = proj_data.company or doc.company
			currency = frappe.db.get_value("Company", company, "default_currency") if company else (frappe.db.get_default("currency") or "")
			if not doc.custom_allow_budget_override:
				frappe.throw(
					_(
						"Project Budget Exceeded for Project '{0}'.<br>"
						"Remaining Project Budget: {1}<br>"
						"Transaction Cost: {2}<br>"
						"Excess Amount: {3}"
					).format(
						proj,
						fmt_money(proj_remaining, currency=currency),
						fmt_money(total_cost, currency=currency),
						fmt_money(excess, currency=currency),
					),
					title=_("Project Budget Exceeded"),
				)
			else:
				log_budget_override(doc, proj, None, proj_remaining, total_cost, excess)

def log_budget_override(doc, project, task, old_budget, new_budget, override_amount):
	"""Logs authorized budget override event to Project Budget Override Log."""
	if not doc.custom_budget_override_reason:
		frappe.throw(
			_("Please provide a Budget Override Reason before submitting with override enabled."),
			title=_("Override Reason Required"),
		)

	# Ensure user has System Manager or Projects Manager role
	user_roles = frappe.get_roles(frappe.session.user)
	if not any(role in user_roles for role in ["System Manager", "Projects Manager"]):
		frappe.throw(
			_("Only Users with 'System Manager' or 'Projects Manager' roles are authorized to override budget limits."),
			title=_("Unauthorized Budget Override"),
		)

	override_log = frappe.new_doc("Project Budget Override Log")
	override_log.user = frappe.session.user
	override_log.posting_date = now_datetime()
	override_log.project = project
	override_log.task = task
	override_log.voucher_type = doc.doctype
	override_log.voucher_no = doc.name or "Draft"
	override_log.old_budget = old_budget
	override_log.new_budget = new_budget
	override_log.override_amount = override_amount
	override_log.reason = doc.custom_budget_override_reason
	override_log.insert(ignore_permissions=True)

def on_submit_stock_entry(doc, method=None):
	"""Recalculates Project and Task actual costs and budget fields upon Stock Entry submission."""
	if doc.purpose == "Material Issue":
		affected_projects = set(item.project for item in doc.items if item.project)
		affected_tasks = set(item.task for item in doc.items if item.task)

		for proj in affected_projects:
			recalculate_project_budget(proj)

		for tsk in affected_tasks:
			recalculate_task_budget(tsk, update_parents=True)

def on_cancel_stock_entry(doc, method=None):
	"""Recalculates Project and Task actual costs and budget fields upon Stock Entry cancellation."""
	if doc.purpose == "Material Issue":
		affected_projects = set(item.project for item in doc.items if item.project)
		affected_tasks = set(item.task for item in doc.items if item.task)

		for proj in affected_projects:
			recalculate_project_budget(proj)

		for tsk in affected_tasks:
			recalculate_task_budget(tsk, update_parents=True)
