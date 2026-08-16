import frappe
from frappe import _
from frappe.utils import flt
from waterqo.budget_control.utils import (
	get_project_actual_cost,
	get_project_task_allocation,
)

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
			"label": _("Project ID"),
			"fieldtype": "Link",
			"options": "Project",
			"width": 180,
		},
		{
			"fieldname": "project_name",
			"label": _("Project Name"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "status",
			"label": _("Status"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "percent_complete",
			"label": _("Completion %"),
			"fieldtype": "Percent",
			"width": 110,
		},
		{
			"fieldname": "custom_project_budget",
			"label": _("Project Budget"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{
			"fieldname": "custom_total_task_budget",
			"label": _("Task Budget Allocated"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 160,
		},
		{
			"fieldname": "custom_unallocated_budget",
			"label": _("Unallocated Budget"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 150,
		},
		{
			"fieldname": "custom_actual_project_cost",
			"label": _("Actual Cost"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{
			"fieldname": "custom_remaining_project_budget",
			"label": _("Remaining Budget"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 150,
		},
		{
			"fieldname": "custom_project_budget_utilization",
			"label": _("Budget Utilization %"),
			"fieldtype": "Percent",
			"width": 140,
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
	projects = frappe.db.sql(
		f"""
		SELECT
			p.name as project,
			p.project_name,
			p.status,
			p.percent_complete,
			p.company,
			p.custom_project_budget,
			p.custom_total_task_budget,
			p.custom_unallocated_budget,
			p.custom_actual_project_cost,
			p.custom_remaining_project_budget,
			p.custom_project_budget_utilization
		FROM `tabProject` p
		WHERE 1=1 {conditions}
		ORDER BY p.creation DESC
	""",
		filters,
		as_dict=True,
	)

	data = []
	default_currency = frappe.db.get_default("currency") or "PKR"

	for p in projects:
		company_currency = (
			frappe.db.get_value("Company", p.company, "default_currency")
			if p.company
			else default_currency
		)

		proj_budget = flt(p.custom_project_budget)
		total_task_alloc = get_project_task_allocation(p.project)
		unallocated = proj_budget - total_task_alloc
		actual_cost = get_project_actual_cost(p.project)
		remaining = proj_budget - actual_cost
		utilization = (actual_cost / proj_budget * 100.0) if proj_budget > 0 else 0.0

		data.append(
			{
				"project": p.project,
				"project_name": p.project_name,
				"status": p.status,
				"percent_complete": flt(p.percent_complete),
				"custom_project_budget": proj_budget,
				"custom_total_task_budget": total_task_alloc,
				"custom_unallocated_budget": unallocated,
				"custom_actual_project_cost": actual_cost,
				"custom_remaining_project_budget": remaining,
				"custom_project_budget_utilization": utilization,
				"currency": company_currency,
			}
		)

	return data

def get_conditions(filters):
	conditions = ""
	if filters:
		if filters.get("company"):
			conditions += " AND p.company = %(company)s"
		if filters.get("project"):
			conditions += " AND p.name = %(project)s"
		if filters.get("status") and filters.get("status") != "All":
			conditions += " AND p.status = %(status)s"
		if filters.get("from_date"):
			conditions += " AND p.expected_start_date >= %(from_date)s"
		if filters.get("to_date"):
			conditions += " AND p.expected_end_date <= %(to_date)s"
	return conditions

def get_chart(data):
	if not data:
		return None

	labels = [d["project_name"] or d["project"] for d in data[:10]]
	project_budgets = [flt(d["custom_project_budget"]) for d in data[:10]]
	task_budgets = [flt(d["custom_total_task_budget"]) for d in data[:10]]
	actual_costs = [flt(d["custom_actual_project_cost"]) for d in data[:10]]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Project Budget"), "values": project_budgets},
				{"name": _("Task Budget Allocated"), "values": task_budgets},
				{"name": _("Actual Cost"), "values": actual_costs},
			],
		},
		"type": "bar",
		"colors": ["#5e64ff", "#ffa000", "#e53935"],
	}

def get_report_summary(data):
	if not data:
		return []

	total_budget = sum(flt(d["custom_project_budget"]) for d in data)
	total_allocated = sum(flt(d["custom_total_task_budget"]) for d in data)
	total_actual = sum(flt(d["custom_actual_project_cost"]) for d in data)
	total_remaining = sum(flt(d["custom_remaining_project_budget"]) for d in data)

	return [
		{
			"value": total_budget,
			"label": _("Total Project Budget"),
			"datatype": "Currency",
			"indicator": "Blue",
		},
		{
			"value": total_allocated,
			"label": _("Total Task Budget Allocated"),
			"datatype": "Currency",
			"indicator": "Orange",
		},
		{
			"value": total_actual,
			"label": _("Total Actual Cost"),
			"datatype": "Currency",
			"indicator": "Red" if total_actual > total_budget else "Green",
		},
		{
			"value": total_remaining,
			"label": _("Total Remaining Budget"),
			"datatype": "Currency",
			"indicator": "Green" if total_remaining >= 0 else "Red",
		},
	]
