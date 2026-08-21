import frappe
from frappe import _
from frappe.utils import flt, fmt_money
from waterqo.budget_control.utils import (
	get_task_actual_cost,
	recalculate_project_budget,
	recalculate_task_budget,
)

def autoname_task(doc, method=None):
	"""Generates Task name based on Project + Parent Task + Subject with duplicate suffix handling."""
	if doc.flags.in_test and doc.name and not doc.name.startswith("new-task"):
		# In unit tests if name is pre-assigned, keep it unless it needs formatting
		pass

	# Inherit project from parent_task if missing
	if not doc.project and doc.parent_task:
		doc.project = frappe.db.get_value("Task", doc.parent_task, "project")

	parts = []
	if doc.project:
		parts.append(doc.project)

	if doc.parent_task:
		parent_subject = frappe.db.get_value("Task", doc.parent_task, "subject") or doc.parent_task
		parts.append(parent_subject)

	if doc.subject:
		parts.append(doc.subject)

	base_name = " - ".join(parts) if parts else (doc.subject or "Task")

	candidate = base_name
	count = 1
	while True:
		existing = frappe.db.get_value("Task", candidate, "name")
		if not existing or existing == doc.name:
			doc.name = candidate
			break
		candidate = f"{base_name} - T{count:03d}"
		count += 1

def validate_task(doc, method=None):
	"""Enforces Project assignment, Parent Task hierarchy, and Task Budget allocation rules."""
	if doc.name and frappe.db.exists("Task", doc.name):
		doc._previous_parent_task = frappe.db.get_value("Task", doc.name, "parent_task")
		doc._previous_project = frappe.db.get_value("Task", doc.name, "project")
	else:
		doc._previous_parent_task = None
		doc._previous_project = None

	# Rule 1 — Inherit/validate Project from Parent Task
	if doc.parent_task:
		parent_proj = frappe.db.get_value("Task", doc.parent_task, "project")
		if not doc.project:
			doc.project = parent_proj
		elif parent_proj and doc.project != parent_proj:
			frappe.throw(
				_("Task Project '{0}' does not match Parent Task Project '{1}'.").format(doc.project, parent_proj),
				title=_("Project Mismatch"),
			)


	# Parent Tasks: compute budget from children if group or has children
	has_children = False
	if doc.name and frappe.db.exists("Task", doc.name):
		has_children = bool(
			frappe.db.exists("Task", {"parent_task": doc.name, "docstatus": ["<", 2], "name": ["!=", doc.name]})
		)

	if doc.is_group or has_children:
		child_budgets = frappe.db.get_all(
			"Task",
			filters={"parent_task": doc.name, "docstatus": ["<", 2], "name": ["!=", doc.name]},
			fields=["custom_task_budget"],
		)
		doc.custom_task_budget = sum(flt(c.custom_task_budget) for c in child_budgets)

	# Rule 2 — Total Task Budget cannot exceed Project Budget
	if doc.project:
		proj_budget = flt(frappe.db.get_value("Project", doc.project, "custom_project_budget"))

		# Sum existing leaf task budgets in the project excluding current doc
		existing_tasks = frappe.db.sql(
			"""
			SELECT SUM(t.custom_task_budget)
			FROM `tabTask` t
			WHERE t.project = %s
			  AND t.name != %s
			  AND t.docstatus < 2
			  AND NOT EXISTS (
				  SELECT 1 FROM `tabTask` child
				  WHERE child.parent_task = t.name
					AND child.docstatus < 2
					AND child.name != %s
			  )
		""",
			(doc.project, doc.name or "", doc.name or ""),
		)
		existing_task_budget = (
			flt(existing_tasks[0][0]) if existing_tasks and existing_tasks[0][0] is not None else 0.0
		)

		doc_leaf_budget = 0.0 if (doc.is_group or has_children) else flt(doc.custom_task_budget)
		new_total = existing_task_budget + doc_leaf_budget

		if proj_budget > 0 and new_total > proj_budget:
			available_allocation = max(0.0, proj_budget - existing_task_budget)
			requested_task_budget = flt(doc.custom_task_budget)
			excess_amount = new_total - proj_budget
			company = frappe.db.get_value("Project", doc.project, "company")
			currency = frappe.db.get_value("Company", company, "default_currency") if company else (frappe.db.get_default("currency") or "")

			frappe.throw(
				_(
					"Total Task Budget cannot exceed Project Budget.<br>"
					"Project Budget: {0}<br>"
					"Existing Allocated Task Budget: {1}<br>"
					"Available Allocation: {2}<br>"
					"Requested Task Budget: {3}<br>"
					"Excess Amount: {4}"
				).format(
					fmt_money(proj_budget, currency=currency),
					fmt_money(existing_task_budget, currency=currency),
					fmt_money(available_allocation, currency=currency),
					fmt_money(requested_task_budget, currency=currency),
					fmt_money(excess_amount, currency=currency),
				),
				title=_("Task Budget Exceeded"),
			)

	actual_cost = get_task_actual_cost(doc.name) if doc.name else 0.0
	doc.custom_actual_task_cost = actual_cost
	doc.custom_remaining_task_budget = flt(doc.custom_task_budget) - actual_cost
	doc.custom_task_budget_utilization = (
		(actual_cost / flt(doc.custom_task_budget) * 100.0) if flt(doc.custom_task_budget) > 0 else 0.0
	)

def on_update_task(doc, method=None):
	"""Triggers parent task and project budget updates after Task is saved."""
	# Recalculate current parent task
	if doc.parent_task:
		recalculate_task_budget(doc.parent_task, update_parents=True)

	# Check if parent_task changed to update previous parent task
	prev_parent = getattr(doc, "_previous_parent_task", None)
	if prev_parent and prev_parent != doc.parent_task:
		recalculate_task_budget(prev_parent, update_parents=True)

	prev_project = getattr(doc, "_previous_project", None)
	if prev_project and prev_project != doc.project:
		recalculate_project_budget(prev_project)

	if doc.project:
		recalculate_project_budget(doc.project)


def on_trash_task(doc, method=None):
	"""Triggers parent task and project budget updates after Task is deleted."""
	if doc.parent_task:
		recalculate_task_budget(doc.parent_task, update_parents=True, excluding_task=doc.name)
	if doc.project:
		recalculate_project_budget(doc.project, excluding_task=doc.name)


