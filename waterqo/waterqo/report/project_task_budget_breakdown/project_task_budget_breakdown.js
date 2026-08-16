frappe.query_reports["Project Task Budget Breakdown"] = {
	"filters": [
		{
			"fieldname": "project",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "Project"
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": ["All", "Open", "Working", "Pending Review", "Overdue", "Completed", "Cancelled"],
			"default": "All"
		},
		{
			"fieldname": "task_type",
			"label": __("Task Type"),
			"fieldtype": "Select",
			"options": ["All", "Parent Tasks Only", "Leaf Tasks Only"],
			"default": "All"
		}
	]
};
