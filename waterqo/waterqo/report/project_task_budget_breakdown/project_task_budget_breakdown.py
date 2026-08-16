import frappe
from frappe import _
from frappe.utils import flt
from waterqo.budget_control.utils import get_task_actual_cost

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	summary = get_report_summary(data)
	return columns, data, None, chart, summary

def get_columns():
	return [
		{
			"fieldname": "project",
			"label": _("Project"),
			"fieldtype": "Link",
			"options": "Project",
			"width": 160,
		},
		{
			"fieldname": "task",
			"label": _("Task ID"),
			"fieldtype": "Link",
			"options": "Task",
			"width": 220,
		},
		{
			"fieldname": "subject",
			"label": _("Subject"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "parent_task",
			"label": _("Parent Task"),
			"fieldtype": "Link",
			"options": "Task",
			"width": 180,
		},
		{
			"fieldname": "is_group",
			"label": _("Is Group"),
			"fieldtype": "Check",
			"width": 80,
		},
		{
			"fieldname": "status",
			"label": _("Status"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "progress",
			"label": _("Progress %"),
			"fieldtype": "Percent",
			"width": 110,
		},
		{
			"fieldname": "custom_task_budget",
			"label": _("Task Budget"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{
			"fieldname": "custom_actual_task_cost",
			"label": _("Actual Task Cost"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{
			"fieldname": "custom_remaining_task_budget",
			"label": _("Remaining Budget"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 150,
		},
		{
			"fieldname": "custom_task_budget_utilization",
			"label": _("Utilization %"),
			"fieldtype": "Percent",
			"width": 130,
		},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
	]

def get_data(filters):
	conditions = get_conditions(filters)
	tasks = frappe.db.sql(
		f"""
		SELECT
			t.name as task,
			t.subject,
			t.project,
			t.parent_task,
			t.is_group,
			t.status,
			t.progress,
			t.custom_task_budget,
			t.custom_actual_task_cost,
			t.custom_remaining_task_budget,
			t.custom_task_budget_utilization,
			p.company
		FROM `tabTask` t
		LEFT JOIN `tabProject` p ON p.name = t.project
		WHERE t.docstatus < 2 {conditions}
		ORDER BY t.project, t.parent_task, t.name
	""",
		filters,
		as_dict=True,
	)

	data = []
	default_currency = frappe.db.get_default("currency") or "PKR"

	for t in tasks:
		company_currency = (
			frappe.db.get_value("Company", t.company, "default_currency")
			if t.company
			else default_currency
		)

		task_budget = flt(t.custom_task_budget)
		actual_cost = get_task_actual_cost(t.task)
		remaining = task_budget - actual_cost
		utilization = (actual_cost / task_budget * 100.0) if task_budget > 0 else 0.0

		data.append(
			{
				"project": t.project,
				"task": t.task,
				"subject": t.subject,
				"parent_task": t.parent_task,
				"is_group": t.is_group,
				"status": t.status,
				"progress": flt(t.progress),
				"custom_task_budget": task_budget,
				"custom_actual_task_cost": actual_cost,
				"custom_remaining_task_budget": remaining,
				"custom_task_budget_utilization": utilization,
				"currency": company_currency,
			}
		)

	return data

def get_conditions(filters):
	conditions = ""
	if filters:
		if filters.get("project"):
			conditions += " AND t.project = %(project)s"
		if filters.get("status") and filters.get("status") != "All":
			conditions += " AND t.status = %(status)s"
		if filters.get("task_type") == "Parent Tasks Only":
			conditions += " AND (t.is_group = 1 OR EXISTS (SELECT 1 FROM `tabTask` child WHERE child.parent_task = t.name AND child.docstatus < 2))"
		elif filters.get("task_type") == "Leaf Tasks Only":
			conditions += " AND t.is_group = 0 AND NOT EXISTS (SELECT 1 FROM `tabTask` child WHERE child.parent_task = t.name AND child.docstatus < 2)"
	return conditions

def get_chart(data):
	if not data:
		return None

	leaf_tasks = [d for d in data if not d["is_group"]][:10]
	if not leaf_tasks:
		leaf_tasks = data[:10]

	labels = [d["subject"] or d["task"] for d in leaf_tasks]
	task_budgets = [flt(d["custom_task_budget"]) for d in leaf_tasks]
	actual_costs = [flt(d["custom_actual_task_cost"]) for d in leaf_tasks]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Task Budget"), "values": task_budgets},
				{"name": _("Actual Task Cost"), "values": actual_costs},
			],
		},
		"type": "bar",
		"colors": ["#ffa000", "#e53935"],
	}

def get_report_summary(data):
	if not data:
		return []

	# Sum budgets of leaf tasks only to avoid double counting parent tasks
	leaf_data = [d for d in data if not d["is_group"]]
	if not leaf_data:
		leaf_data = data

	total_budget = sum(flt(d["custom_task_budget"]) for d in leaf_data)
	total_actual = sum(flt(d["custom_actual_task_cost"]) for d in leaf_data)
	total_remaining = sum(flt(d["custom_remaining_task_budget"]) for d in leaf_data)

	return [
		{
			"value": total_budget,
			"label": _("Total Task Budget Allocated"),
			"datatype": "Currency",
			"indicator": "Orange",
		},
		{
			"value": total_actual,
			"label": _("Total Actual Task Cost"),
			"datatype": "Currency",
			"indicator": "Red" if total_actual > total_budget else "Green",
		},
		{
			"value": total_remaining,
			"label": _("Total Remaining Task Budget"),
			"datatype": "Currency",
			"indicator": "Green" if total_remaining >= 0 else "Red",
		},
	]
