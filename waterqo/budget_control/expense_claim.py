import frappe
from waterqo.budget_control.utils import recalculate_project_budget, recalculate_task_budget

def on_submit_expense_claim(doc, method=None):
	"""Recalculates Project and Task actual costs upon Expense Claim submission."""
	affected_projects = set()
	affected_tasks = set()
	if getattr(doc, "project", None):
		affected_projects.add(doc.project)
	for d in doc.get("expenses", []):
		if d.get("project"):
			affected_projects.add(d.get("project"))
		if d.get("task"):
			affected_tasks.add(d.get("task"))

	for proj in affected_projects:
		recalculate_project_budget(proj)
	for tsk in affected_tasks:
		recalculate_task_budget(tsk, update_parents=True)

def on_cancel_expense_claim(doc, method=None):
	"""Recalculates Project and Task actual costs upon Expense Claim cancellation."""
	affected_projects = set()
	affected_tasks = set()
	if getattr(doc, "project", None):
		affected_projects.add(doc.project)
	for d in doc.get("expenses", []):
		if d.get("project"):
			affected_projects.add(d.get("project"))
		if d.get("task"):
			affected_tasks.add(d.get("task"))

	for proj in affected_projects:
		recalculate_project_budget(proj)
	for tsk in affected_tasks:
		recalculate_task_budget(tsk, update_parents=True)
