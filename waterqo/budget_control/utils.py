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

def get_all_child_tasks(task_name: str, excluding_task: str | None = None) -> list[str]:
	"""Recursively fetches all child task names under a parent task."""
	if not task_name:
		return []
	filters = {"parent_task": task_name, "docstatus": ["<", 2]}
	if excluding_task:
		filters["name"] = ["!=", excluding_task]

	children = frappe.db.get_all(
		"Task",
		filters=filters,
		pluck="name",
	)
	all_children = list(children)
	for child in children:
		all_children.extend(get_all_child_tasks(child, excluding_task=excluding_task))
	return all_children

def get_task_actual_cost(task_name: str, excluding_task: str | None = None) -> float:
	"""Calculates total actual cost for a Task (including its sub-tasks if parent) from qualifying Material Issue and Journal Entry GL Entries."""
	if not task_name:
		return 0.0

	all_task_names = get_all_child_tasks(task_name, excluding_task=excluding_task)
	if excluding_task != task_name:
		all_task_names.append(task_name)

	if not all_task_names:
		return 0.0

	res = frappe.db.sql(
		"""
		SELECT SUM(gle.debit - gle.credit)
		FROM `tabGL Entry` gle
		LEFT JOIN `tabStock Entry` se ON se.name = gle.voucher_no AND gle.voucher_type = 'Stock Entry'
		WHERE gle.docstatus = 1
		  AND gle.is_cancelled = 0
		  AND gle.debit > 0
		  AND gle.task IN %s
		  AND (
			  (gle.voucher_type = 'Stock Entry' AND se.purpose = 'Material Issue')
			  OR (gle.voucher_type = 'Journal Entry')
		  )
	""",
		(tuple(all_task_names),),
	)
	return flt(res[0][0]) if res and res[0][0] is not None else 0.0

def get_project_task_allocation(project_name: str, excluding_task: str | None = None) -> float:
	"""Calculates total allocated budget across all leaf Tasks belonging to a Project."""
	if not project_name:
		return 0.0

	conditions = ""
	params = [project_name]
	if excluding_task:
		conditions = "AND t.name != %s"
		params.append(excluding_task)

	child_condition = "AND child.name != %s" if excluding_task else ""
	if excluding_task:
		params.append(excluding_task)

	res = frappe.db.sql(
		f"""
		SELECT SUM(t.custom_task_budget)
		FROM `tabTask` t
		WHERE t.project = %s
		  {conditions}
		  AND t.docstatus < 2
		  AND NOT EXISTS (
			  SELECT 1 FROM `tabTask` child
			  WHERE child.parent_task = t.name
				AND child.docstatus < 2
				{child_condition}
		  )
	""",
		tuple(params),
	)
	return flt(res[0][0]) if res and res[0][0] is not None else 0.0

def recalculate_task_budget(task_name: str, update_parents: bool = True, excluding_task: str | None = None):
	"""Recalculates actual cost, remaining budget, utilization, and parent budget for a Task."""
	if not task_name or not frappe.db.exists("Task", task_name):
		return

	task_doc = frappe.get_doc("Task", task_name)

	filters = {"parent_task": task_name, "docstatus": ["<", 2]}
	if excluding_task:
		filters["name"] = ["!=", excluding_task]

	child_tasks = frappe.db.get_all(
		"Task",
		filters=filters,
		fields=["custom_task_budget"],
	)

	if child_tasks or task_doc.is_group:
		# Parent Task budget = SUM(child Task budgets)
		calculated_budget = sum(flt(c.custom_task_budget) for c in child_tasks)
		frappe.db.set_value("Task", task_name, "custom_task_budget", calculated_budget, update_modified=False)
		task_budget = calculated_budget
	else:
		task_budget = flt(task_doc.custom_task_budget)

	actual_cost = get_task_actual_cost(task_name, excluding_task=excluding_task)
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
		recalculate_task_budget(task_doc.parent_task, update_parents=True, excluding_task=excluding_task)

def recalculate_project_budget(project_name: str, excluding_task: str | None = None):
	"""Recalculates total task budget, unallocated budget, actual cost, remaining budget, and utilization for a Project."""
	if not project_name or not frappe.db.exists("Project", project_name):
		return

	project_doc = frappe.get_doc("Project", project_name)
	project_budget = flt(project_doc.custom_project_budget)
	total_task_budget = get_project_task_allocation(project_name, excluding_task=excluding_task)
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

