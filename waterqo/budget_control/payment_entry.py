import frappe
from waterqo.budget_control.utils import recalculate_project_budget

def on_submit_payment_entry(doc, method=None):
	"""Recalculates Project actual costs upon Payment Entry submission."""
	affected_projects = set()
	if doc.project:
		affected_projects.add(doc.project)

	for ref in doc.get("references", []):
		if ref.get("project"):
			affected_projects.add(ref.get("project"))

	for proj in affected_projects:
		recalculate_project_budget(proj)

def on_cancel_payment_entry(doc, method=None):
	"""Recalculates Project actual costs upon Payment Entry cancellation."""
	affected_projects = set()
	if doc.project:
		affected_projects.add(doc.project)

	for ref in doc.get("references", []):
		if ref.get("project"):
			affected_projects.add(ref.get("project"))

	for proj in affected_projects:
		recalculate_project_budget(proj)
