import frappe
from waterqo.budget_control.utils import recalculate_project_budget, recalculate_task_budget

def on_submit_purchase_invoice(doc, method=None):
	"""Recalculates Project and Task actual costs upon Purchase Invoice submission."""
	affected_projects = set()
	affected_tasks = set()
	if doc.project:
		affected_projects.add(doc.project)
	for item in doc.get("items", []):
		if item.get("project"):
			affected_projects.add(item.get("project"))
		if item.get("task"):
			affected_tasks.add(item.get("task"))

	for proj in affected_projects:
		recalculate_project_budget(proj)
	for tsk in affected_tasks:
		recalculate_task_budget(tsk, update_parents=True)

def on_cancel_purchase_invoice(doc, method=None):
	"""Recalculates Project and Task actual costs upon Purchase Invoice cancellation."""
	affected_projects = set()
	affected_tasks = set()
	if doc.project:
		affected_projects.add(doc.project)
	for item in doc.get("items", []):
		if item.get("project"):
			affected_projects.add(item.get("project"))
		if item.get("task"):
			affected_tasks.add(item.get("task"))

	for proj in affected_projects:
		recalculate_project_budget(proj)
	for tsk in affected_tasks:
		recalculate_task_budget(tsk, update_parents=True)
