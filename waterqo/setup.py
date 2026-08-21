import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def setup_project_task_budget_control():
	"""Sets up custom fields and accounting dimensions required for Project & Task Budget Control."""
	setup_custom_fields()
	setup_task_accounting_dimension()
	frappe.clear_cache()

def setup_custom_fields():
	custom_fields = {
		"Project": [
			{
				"fieldname": "custom_budget_section",
				"fieldtype": "Section Break",
				"label": "Budget Control",
				"insert_after": "cost_center",
			},
			{
				"fieldname": "custom_project_budget",
				"fieldtype": "Currency",
				"label": "Project Budget",
				"insert_after": "custom_budget_section",
				"description": "Maximum total budget available for the Project",
			},
			{
				"fieldname": "custom_total_task_budget",
				"fieldtype": "Currency",
				"label": "Total Task Budget",
				"read_only": 1,
				"insert_after": "custom_project_budget",
				"description": "Sum of budgets allocated to Tasks",
			},
			{
				"fieldname": "custom_unallocated_budget",
				"fieldtype": "Currency",
				"label": "Unallocated Budget",
				"read_only": 1,
				"insert_after": "custom_total_task_budget",
				"description": "Project Budget - Total Task Budget",
			},
			{
				"fieldname": "custom_column_break_budget",
				"fieldtype": "Column Break",
				"insert_after": "custom_unallocated_budget",
			},
			{
				"fieldname": "custom_actual_project_cost",
				"fieldtype": "Currency",
				"label": "Actual Project Cost",
				"read_only": 1,
				"insert_after": "custom_column_break_budget",
				"description": "Actual cost incurred from Material Issue transactions",
			},
			{
				"fieldname": "custom_remaining_project_budget",
				"fieldtype": "Currency",
				"label": "Remaining Project Budget",
				"read_only": 1,
				"insert_after": "custom_actual_project_cost",
				"description": "Project Budget - Actual Project Cost",
			},
			{
				"fieldname": "custom_project_budget_utilization",
				"fieldtype": "Percent",
				"label": "Budget Utilization %",
				"read_only": 1,
				"insert_after": "custom_remaining_project_budget",
				"description": "(Actual Project Cost / Project Budget) * 100",
			},
		],
		"Task": [
			{
				"fieldname": "custom_task_budget_section",
				"fieldtype": "Section Break",
				"label": "Budget Control",
				"insert_after": "sb_costing",
			},
			{
				"fieldname": "custom_task_budget",
				"fieldtype": "Currency",
				"label": "Task Budget",
				"insert_after": "custom_task_budget_section",
				"description": "Budget allocated to this Task (Calculated for Parent Tasks)",
			},
			{
				"fieldname": "custom_actual_task_cost",
				"fieldtype": "Currency",
				"label": "Actual Task Cost",
				"read_only": 1,
				"insert_after": "custom_task_budget",
				"description": "Actual cost incurred for this Task from Material Issue transactions",
			},
			{
				"fieldname": "custom_column_break_task_budget",
				"fieldtype": "Column Break",
				"insert_after": "custom_actual_task_cost",
			},
			{
				"fieldname": "custom_remaining_task_budget",
				"fieldtype": "Currency",
				"label": "Remaining Budget",
				"read_only": 1,
				"insert_after": "custom_column_break_task_budget",
				"description": "Task Budget - Actual Task Cost",
			},
			{
				"fieldname": "custom_task_budget_utilization",
				"fieldtype": "Percent",
				"label": "Budget Utilization %",
				"read_only": 1,
				"insert_after": "custom_remaining_task_budget",
				"description": "(Actual Task Cost / Task Budget) * 100",
			},
		],
		"Stock Entry": [
			{
				"fieldname": "custom_budget_control_section",
				"fieldtype": "Section Break",
				"label": "Budget Control",
				"insert_after": "remarks",
			},
			{
				"fieldname": "custom_allow_budget_override",
				"fieldtype": "Check",
				"label": "Allow Budget Override",
				"insert_after": "custom_budget_control_section",
				"description": "Allow transaction even if budget is exceeded (Requires Authorization)",
			},
			{
				"fieldname": "custom_budget_override_reason",
				"fieldtype": "Small Text",
				"label": "Budget Override Reason",
				"insert_after": "custom_allow_budget_override",
				"depends_on": "eval:doc.custom_allow_budget_override == 1",
			},
		],
		"Employee": [
			{
				"fieldname": "custom_cnic_section",
				"fieldtype": "Section Break",
				"label": "CNIC Details",
				"insert_after": "personal_details",
			},
			{
				"fieldname": "custom_cnic",
				"fieldtype": "Data",
				"label": "CNIC Number",
				"insert_after": "custom_cnic_section",
				"description": "13-digit National Identity Card Number (e.g., 12345-1234567-1)",
			},
			{
				"fieldname": "custom_allow_cnic_override",
				"fieldtype": "Check",
				"label": "Allow CNIC Override",
				"insert_after": "custom_cnic",
				"description": "Bypass CNIC format and duplicate validation checks",
			},
			{
				"fieldname": "custom_cnic_override_reason",
				"fieldtype": "Small Text",
				"label": "CNIC Override Reason",
				"insert_after": "custom_allow_cnic_override",
				"depends_on": "eval:doc.custom_allow_cnic_override == 1",
				"mandatory_depends_on": "eval:doc.custom_allow_cnic_override == 1",
			},
		],
	}

	create_custom_fields(custom_fields, ignore_validate=True)

def setup_task_accounting_dimension():
	"""Ensures Task is registered as an Accounting Dimension in ERPNext."""
	if not frappe.db.exists("Accounting Dimension", {"document_type": "Task"}):
		dim = frappe.new_doc("Accounting Dimension")
		dim.document_type = "Task"
		dim.label = "Task"
		dim.fieldname = "task"
		dim.insert(ignore_permissions=True)
		frappe.db.commit()
	
	doc = frappe.get_doc("Accounting Dimension", {"document_type": "Task"})
	from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import make_dimension_in_accounting_doctypes
	make_dimension_in_accounting_doctypes(doc)
