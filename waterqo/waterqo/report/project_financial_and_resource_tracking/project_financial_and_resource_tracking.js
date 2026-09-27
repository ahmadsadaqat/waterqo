frappe.query_reports["Project Financial and Resource Tracking"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"get_value": function () {
				const input_val = this.get_input_value ? this.get_input_value() : null;
				if (input_val) return input_val;
				if (this.value) return this.value;
				const url_params = new URLSearchParams(window.location.search);
				return url_params.get("company") || frappe.defaults.get_user_default("Company") || null;
			}
		},
		{
			"fieldname": "project",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "Project",
			"get_value": function () {
				const input_val = this.get_input_value ? this.get_input_value() : null;
				if (input_val) return input_val;
				if (this._initial_route_value) return this._initial_route_value;
				if (this.value) return this.value;
				const url_params = new URLSearchParams(window.location.search);
				return url_params.get("project") || null;
			},
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
	"onload": async function (report) {
		const project_filter = report.get_filter("project");
		const company_filter = report.get_filter("company");

		const url_params = new URLSearchParams(window.location.search);
		const route_project = (frappe.route_options && frappe.route_options.project) || url_params.get("project") || project_filter?.value;
		const route_company = (frappe.route_options && frappe.route_options.company) || url_params.get("company") || company_filter?.value;

		if (route_company && company_filter) {
			company_filter.value = route_company;
			if (company_filter.set_input_value) company_filter.set_input_value(route_company);
			if (company_filter.$input) company_filter.$input.val(route_company);
		}

		if (route_project && project_filter) {
			project_filter._initial_route_value = route_project;
			project_filter.value = route_project;

			if (frappe.utils && frappe.utils.add_link_title) {
				frappe.utils.add_link_title("Project", route_project, route_project);
			}
			if (project_filter.set_input_value) project_filter.set_input_value(route_project);
			if (project_filter.$input) {
				project_filter.$input.val(route_project);
				project_filter.$input.one("input change", function () {
					delete project_filter._initial_route_value;
				});
			}

			if (frappe.utils && frappe.utils.fetch_link_title) {
				try {
					const title = await frappe.utils.fetch_link_title("Project", route_project);
					if (title && project_filter.set_input_value) {
						project_filter.set_input_value(title);
					}
				} catch (e) {}
			}
		}

		// Safety check: if data was already queried before the project filter settled, auto-refresh once
		setTimeout(() => {
			if (route_project && report.data && report.data.length > 1) {
				const current_filtered = report.data.every((r) => r.project === route_project);
				if (!current_filtered) {
					report.refresh();
				}
			}
		}, 300);
	},
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
