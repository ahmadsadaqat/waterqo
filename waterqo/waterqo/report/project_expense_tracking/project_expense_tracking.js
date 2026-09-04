frappe.query_reports["Project Expense Tracking"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname": "project",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "Project"
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -3)
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "status",
			"label": __("Project Status"),
			"fieldtype": "Select",
			"options": ["All", "Open", "Completed", "Cancelled"],
			"default": "All"
		},
		{
			"fieldname": "expense_type",
			"label": __("Expense Type"),
			"fieldtype": "Select",
			"options": [
				"All",
				"Material Issue",
				"Journal Entry",
				"Timesheet",
				"Expense Claim",
				"Purchase Invoice"
			],
			"default": "All"
		}
	]
};
