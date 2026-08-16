import frappe
from frappe.utils import flt

def get_project_actual_cost(project_name: str) -> float:
	"""Calculates total actual cost for a Project from qualifying Material Issue and Journal Entry GL Entries."""
	if not project_name:
		return 0.0

	res = frappe.db.sql(
		"""
		SELECT SUM(gle.debit - gle.credit)
		FROM `tabGL Entry` gle
		LEFT JOIN `tabStock Entry` se ON se.name = gle.voucher_no AND gle.voucher_type = 'Stock Entry'
		WHERE gle.docstatus = 1
		  AND gle.is_cancelled = 0
		  AND gle.debit > 0
		  AND gle.project = %s
		  AND (
			  (gle.voucher_type = 'Stock Entry' AND se.purpose = 'Material Issue')
			  OR (gle.voucher_type = 'Journal Entry')
		  )
	""",
		(project_name,),
	)
	return flt(res[0][0]) if res and res[0][0] is not None else 0.0

def get_task_actual_cost(task_name: str) -> float:
	"""Calculates total actual cost for a Task from qualifying Material Issue and Journal Entry GL Entries."""
	if not task_name:
		return 0.0

	res = frappe.db.sql(
		"""
		SELECT SUM(gle.debit - gle.credit)
		FROM `tabGL Entry` gle
		LEFT JOIN `tabStock Entry` se ON se.name = gle.voucher_no AND gle.voucher_type = 'Stock Entry'
		WHERE gle.docstatus = 1
		  AND gle.is_cancelled = 0
		  AND gle.debit > 0
		  AND gle.task = %s
		  AND (
			  (gle.voucher_type = 'Stock Entry' AND se.purpose = 'Material Issue')
			  OR (gle.voucher_type = 'Journal Entry')
		  )
	""",
		(task_name,),
	)
	return flt(res[0][0]) if res and res[0][0] is not None else 0.0

def get_project_task_allocation(project_name: str) -> float:
	"""Calculates total allocated budget across all leaf Tasks belonging to a Project."""
	if not project_name:
		return 0.0

	res = frappe.db.sql(
		"""
		SELECT SUM(t.custom_task_budget)
		FROM `tabTask` t
		WHERE t.project = %s
		  AND t.docstatus < 2
		  AND NOT EXISTS (
			  SELECT 1 FROM `tabTask` child
			  WHERE child.parent_task = t.name
				AND child.docstatus < 2
		  )
	""",
		(project_name,),
	)
	return flt(res[0][0]) if res and res[0][0] is not None else 0.0

def recalculate_task_budget(task_name: str, update_parents: bool = True):
	"""Recalculates actual cost, remaining budget, utilization, and parent budget for a Task."""
	if not task_name or not frappe.db.exists("Task", task_name):
		return

	task_doc = frappe.get_doc("Task", task_name)
	
	# Check if task is a parent task
	child_tasks = frappe.db.get_all(
		"Task",
		filters={"parent_task": task_name, "docstatus": ["<", 2]},
		fields=["custom_task_budget"],
	)

	if child_tasks:
		# Parent Task budget = SUM(child Task budgets)
		calculated_budget = sum(flt(c.custom_task_budget) for c in child_tasks)
		frappe.db.set_value("Task", task_name, "custom_task_budget", calculated_budget, update_modified=False)
		task_budget = calculated_budget
	else:
		task_budget = flt(task_doc.custom_task_budget)

	actual_cost = get_task_actual_cost(task_name)
	remaining_budget = task_budget - actual_cost
	utilization = (actual_cost / task_budget * 100.0) if task_budget > 0 else 0.0

	frappe.db.set_value(
		"Task",
		task_name,
		{
			"custom_actual_task_cost": actual_cost,
			"custom_remaining_task_budget": remaining_budget,
			"custom_task_budget_utilization": utilization,
		},
		update_modified=False,
	)

	if update_parents and task_doc.parent_task:
		recalculate_task_budget(task_doc.parent_task, update_parents=True)

def recalculate_project_budget(project_name: str):
	"""Recalculates total task budget, unallocated budget, actual cost, remaining budget, and utilization for a Project."""
	if not project_name or not frappe.db.exists("Project", project_name):
		return

	project_doc = frappe.get_doc("Project", project_name)
	project_budget = flt(project_doc.custom_project_budget)
	total_task_budget = get_project_task_allocation(project_name)
	unallocated_budget = project_budget - total_task_budget
	actual_project_cost = get_project_actual_cost(project_name)
	remaining_project_budget = project_budget - actual_project_cost
	utilization = (actual_project_cost / project_budget * 100.0) if project_budget > 0 else 0.0

	frappe.db.set_value(
		"Project",
		project_name,
		{
			"custom_total_task_budget": total_task_budget,
			"custom_unallocated_budget": unallocated_budget,
			"custom_actual_project_cost": actual_project_cost,
			"custom_remaining_project_budget": remaining_project_budget,
			"custom_project_budget_utilization": utilization,
		},
		update_modified=False,
	)
