frappe.query_reports["Project Financial and Resource Tracking"] = {
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
			"options": "Project",
			"get_query": function () {
				const company = frappe.query_report.get_filter_value("company");
				if (company) {
					return {
						filters: { company: company }
					};
				}
			}
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": ["All", "Open", "Completed", "Cancelled"],
			"default": "All"
		},
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date"
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date"
		}
	],
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "remaining_budget") {
			if (data && data.remaining_budget < 0) {
				value = `<span style="color: var(--text-danger, #e11d48); font-weight: bold;">${value}</span>`;
			} else if (data && data.remaining_budget > 0) {
				value = `<span style="color: var(--text-success, #059669); font-weight: 500;">${value}</span>`;
			}
		} else if (column.fieldname === "budget_utilization") {
			if (data && data.budget_utilization > 100) {
				value = `<span style="color: var(--text-danger, #e11d48); font-weight: bold;">${value}</span>`;
			}
		} else if (column.fieldname === "outstanding_amount") {
			if (data && data.outstanding_amount > 0) {
				value = `<span style="color: var(--text-warning, #d97706); font-weight: 500;">${value}</span>`;
			}
		}
		return value;
	}
};
