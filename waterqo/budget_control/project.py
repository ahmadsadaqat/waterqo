import frappe
from frappe import _
from frappe.utils import flt, fmt_money
from erpnext.projects.doctype.project.project import Project
from waterqo.budget_control.utils import get_project_actual_cost, get_project_task_allocation

class WaterQOProject(Project):
	def update_percent_complete(self):
		"""Overrides ERPNext standard update_percent_complete to calculate progress solely from leaf tasks."""
		calculate_and_set_project_percent_complete(self)

def calculate_and_set_project_percent_complete(doc, excluding_task: str | None = None):
	"""
	Calculates project percent_complete based solely on leaf tasks
	(tasks that are not group tasks and have no active child tasks),
	preventing parent/group container tasks from distorting project progress.
	"""
	if not doc.name:
		return

	params = {"project": doc.name}
	exclude_task_cond = ""
	exclude_child_cond = ""
	if excluding_task:
		params["excluding_task"] = excluding_task
		exclude_task_cond = "AND t.name != %(excluding_task)s"
		exclude_child_cond = "AND child.name != %(excluding_task)s"

	# Count all active non-cancelled tasks under this project (excluding excluding_task)
	total_active_tasks = frappe.db.sql(
		f"""
		SELECT count(name) FROM `tabTask` t
		WHERE t.project = %(project)s
		  AND t.docstatus < 2
		  {exclude_task_cond}
		""",
		params,
	)[0][0]

	# If status is Completed and no tasks exist, allow completion
	if doc.status == "Completed" and total_active_tasks == 0:
		doc.percent_complete_method = "Manual"
		doc.percent_complete = 100.0
		return

	if doc.percent_complete_method == "Manual":
		if doc.status == "Completed":
			doc.percent_complete = 100.0
		return

	# Query all active leaf tasks under this project
	leaf_tasks = frappe.db.sql(
		f"""
		SELECT t.name, t.status, t.progress, t.task_weight, t.is_group
		FROM `tabTask` t
		WHERE t.project = %(project)s
		  AND t.docstatus < 2
		  AND t.is_group = 0
		  {exclude_task_cond}
		  AND NOT EXISTS (
			  SELECT 1 FROM `tabTask` child
			  WHERE child.parent_task = t.name
				AND child.docstatus < 2
				{exclude_child_cond}
		  )
		""",
		params,
		as_dict=True,
	)

	# If there are active tasks but no leaf tasks found (e.g. only group tasks with 0 children)
	if not leaf_tasks and total_active_tasks > 0:
		leaf_tasks = frappe.db.sql(
			f"""
			SELECT t.name, t.status, t.progress, t.task_weight, t.is_group
			FROM `tabTask` t
			WHERE t.project = %(project)s
			  AND t.docstatus < 2
			  {exclude_task_cond}
			""",
			params,
			as_dict=True,
		)

	total_leafs = len(leaf_tasks)
	if total_leafs == 0:
		doc.percent_complete = 100.0 if doc.status == "Completed" else 0.0
	else:
		method = doc.percent_complete_method or "Task Completion"

		if method == "Task Completion":
			completed_count = sum(1 for t in leaf_tasks if t.get("status") in ("Cancelled", "Completed"))
			doc.percent_complete = round(flt((completed_count / total_leafs) * 100.0), 2)

		elif method == "Task Progress":
			total_progress = sum(
				100.0 if t.get("status") in ("Completed", "Cancelled") else min(max(flt(t.get("progress")), 0.0), 100.0)
				for t in leaf_tasks
			)
			doc.percent_complete = round(flt(total_progress / total_leafs), 2)

		elif method == "Task Weight":
			weight_sum = sum(flt(t.get("task_weight")) for t in leaf_tasks)
			if weight_sum > 0:
				pct = 0.0
				for t in leaf_tasks:
					prog = 100.0 if t.get("status") in ("Completed", "Cancelled") else min(max(flt(t.get("progress")), 0.0), 100.0)
					pct += prog * (flt(t.get("task_weight")) / weight_sum)
				doc.percent_complete = round(flt(pct), 2)
			else:
				completed_count = sum(1 for t in leaf_tasks if t.get("status") in ("Cancelled", "Completed"))
				doc.percent_complete = round(flt((completed_count / total_leafs) * 100.0), 2)

	if doc.status != "Cancelled":
		if doc.percent_complete == 100.0:
			doc.status = "Completed"
		elif doc.status == "Completed" and doc.percent_complete < 100.0:
			doc.status = "Open"

def recalculate_project_percent_complete(project_name: str, excluding_task: str | None = None):
	"""Recalculates and persists percent_complete and status for a Project based on leaf tasks."""
	if not project_name or not frappe.db.exists("Project", project_name):
		return

	proj = frappe.get_doc("Project", project_name)
	calculate_and_set_project_percent_complete(proj, excluding_task=excluding_task)
	frappe.db.set_value(
		"Project",
		project_name,
		{
			"percent_complete": proj.percent_complete,
			"status": proj.status,
		},
		update_modified=False,
	)
	frappe.clear_document_cache("Project", project_name)

def validate_project(doc, method=None):
	"""Validates Project budget, updates budget fields, and calculates leaf-task percent complete."""
	calculate_and_set_project_percent_complete(doc)

	project_budget = flt(doc.custom_project_budget)
	
	if doc.name and frappe.db.exists("Project", doc.name):
		total_task_budget = get_project_task_allocation(doc.name)
	else:
		total_task_budget = 0.0

	# Section 5: Check if Project Budget is reduced below allocated Task Budgets
	if project_budget > 0 and project_budget < total_task_budget:
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

	actual_cost = (
		get_project_actual_cost(doc.name, opening_expense=flt(doc.custom_opening_expense))
		if doc.name
		else flt(doc.custom_opening_expense)
	)
	unallocated = project_budget - total_task_budget
	remaining = project_budget - actual_cost
	utilization = (actual_cost / project_budget * 100.0) if project_budget > 0 else 0.0

	doc.custom_total_task_budget = total_task_budget
	doc.custom_unallocated_budget = unallocated
	doc.custom_actual_project_cost = actual_cost
	doc.custom_remaining_project_budget = remaining
	doc.custom_project_budget_utilization = utilization
