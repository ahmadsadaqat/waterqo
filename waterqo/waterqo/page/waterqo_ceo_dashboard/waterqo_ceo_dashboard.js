// Copyright (c) 2026, Nexo ERP and contributors
// For license information, please see license.txt

frappe.pages["waterqo-ceo-dashboard"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("CEO Executive Dashboard"),
		single_column: true,
	});

	wrapper.ceo_dashboard = new WaterqoCEODashboard(wrapper, page);
	frappe.breadcrumbs.add("Projects");
};

class WaterqoCEODashboard {
	constructor(wrapper, page) {
		this.wrapper = wrapper;
		this.page = page;
		this.body = $(this.wrapper).find(".layout-main-section");
		this.charts = {};
		this.currency = "PKR";

		this.setup_header();
		this.render_skeleton();
		this.refresh();
	}

	setup_header() {
		const me = this;

		this.company_field = this.page.add_field({
			fieldtype: "Link",
			fieldname: "company",
			options: "Company",
			label: __("Company"),
			default: frappe.defaults.get_user_default("company"),
			change: function () {
				me.refresh();
			},
		});

		this.page.set_primary_action(
			__("Refresh"),
			function () {
				me.refresh();
			},
			"octicon octicon-sync"
		);
	}

	get_company() {
		return this.company_field ? this.company_field.get_value() : null;
	}

	render_skeleton() {
		this.body.html(`
			<div class="waterqo-ceo-dashboard">
				<div class="wqo-dashboard-header">
					<div class="wqo-dashboard-title">
						<i class="fa fa-tachometer" style="color: var(--wqo-primary);"></i>
						<span>${__("Executive Overview")}</span>
					</div>
					<div class="wqo-header-meta">
						<span class="wqo-timestamp-badge" id="wqo-last-updated">
							<i class="fa fa-clock-o"></i> ${__("Loading data...")}
						</span>
					</div>
				</div>

				<!-- 6 KPI Summary Cards Grid -->
				<div class="wqo-kpi-grid">
					<!-- KPI 1: Net Cash -->
					<div class="wqo-card wqo-kpi-card" style="--kpi-accent: #10b981; --kpi-icon-bg: rgba(16, 185, 129, 0.1);">
						<div class="wqo-kpi-top">
							<span class="wqo-kpi-label">${__("Net Cash Balance")}</span>
							<div class="wqo-kpi-icon-wrap"><i class="fa fa-university"></i></div>
						</div>
						<div class="wqo-kpi-value" id="kpi-net-cash"><span class="wqo-skeleton wqo-skeleton-value"></span></div>
						<div class="wqo-kpi-footer">
							<span>${__("Bank & Cash Accounts")}</span>
						</div>
					</div>

					<!-- KPI 2: Total Receivables -->
					<div class="wqo-card wqo-kpi-card" style="--kpi-accent: #3b82f6; --kpi-icon-bg: rgba(59, 130, 246, 0.1);">
						<div class="wqo-kpi-top">
							<span class="wqo-kpi-label">${__("Total Receivables (AR)")}</span>
							<div class="wqo-kpi-icon-wrap"><i class="fa fa-arrow-circle-down"></i></div>
						</div>
						<div class="wqo-kpi-value" id="kpi-total-ar"><span class="wqo-skeleton wqo-skeleton-value"></span></div>
						<div class="wqo-kpi-footer">
							<span>${__("Outstanding Invoices")}</span>
						</div>
					</div>

					<!-- KPI 3: Total Payables -->
					<div class="wqo-card wqo-kpi-card" style="--kpi-accent: #ef4444; --kpi-icon-bg: rgba(239, 68, 68, 0.1);">
						<div class="wqo-kpi-top">
							<span class="wqo-kpi-label">${__("Total Payables (AP)")}</span>
							<div class="wqo-kpi-icon-wrap"><i class="fa fa-arrow-circle-up"></i></div>
						</div>
						<div class="wqo-kpi-value" id="kpi-total-ap"><span class="wqo-skeleton wqo-skeleton-value"></span></div>
						<div class="wqo-kpi-footer">
							<span>${__("Outstanding Bills")}</span>
						</div>
					</div>

					<!-- KPI 4: Active Projects -->
					<div class="wqo-card wqo-kpi-card" style="--kpi-accent: #8b5cf6; --kpi-icon-bg: rgba(139, 92, 246, 0.1);">
						<div class="wqo-kpi-top">
							<span class="wqo-kpi-label">${__("Active Projects")}</span>
							<div class="wqo-kpi-icon-wrap"><i class="fa fa-tasks"></i></div>
						</div>
						<div class="wqo-kpi-value" id="kpi-active-projects"><span class="wqo-skeleton wqo-skeleton-value"></span></div>
						<div class="wqo-kpi-footer">
							<span>${__("Open & In Progress")}</span>
						</div>
					</div>

					<!-- KPI 5: Overdue Projects -->
					<div class="wqo-card wqo-kpi-card" style="--kpi-accent: #f59e0b; --kpi-icon-bg: rgba(245, 158, 11, 0.1);">
						<div class="wqo-kpi-top">
							<span class="wqo-kpi-label">${__("Overdue Projects")}</span>
							<div class="wqo-kpi-icon-wrap"><i class="fa fa-exclamation-triangle"></i></div>
						</div>
						<div class="wqo-kpi-value" id="kpi-overdue-projects"><span class="wqo-skeleton wqo-skeleton-value"></span></div>
						<div class="wqo-kpi-footer">
							<span>${__("Past Expected Date")}</span>
						</div>
					</div>

					<!-- KPI 6: Monthly Revenue -->
					<div class="wqo-card wqo-kpi-card" style="--kpi-accent: #06b6d4; --kpi-icon-bg: rgba(6, 182, 212, 0.1);">
						<div class="wqo-kpi-top">
							<span class="wqo-kpi-label">${__("Monthly Revenue")}</span>
							<div class="wqo-kpi-icon-wrap"><i class="fa fa-line-chart"></i></div>
						</div>
						<div class="wqo-kpi-value" id="kpi-monthly-rev"><span class="wqo-skeleton wqo-skeleton-value"></span></div>
						<div class="wqo-kpi-footer" id="kpi-revenue-trend">
							<span>${__("Current Month Billed")}</span>
						</div>
					</div>
				</div>

				<!-- Middle Section: Portfolio + Financial Trends -->
				<div class="wqo-middle-grid">
					<!-- Project Portfolio Table Card -->
					<div class="wqo-card">
						<div class="wqo-card-header">
							<h3 class="wqo-card-title">
								<i class="fa fa-cubes" style="color: var(--wqo-primary);"></i>
								${__("Project Portfolio Status")}
							</h3>
							<a href="/app/project" class="wqo-card-action">${__("View All")} &rarr;</a>
						</div>
						<div class="wqo-table-container" id="wqo-portfolio-table-wrap">
							<div class="wqo-skeleton wqo-skeleton-chart"></div>
						</div>
					</div>

					<!-- Financial Charts Stack -->
					<div class="wqo-charts-stack">
						<!-- Chart 1: Monthly Billed vs Expense -->
						<div class="wqo-card wqo-chart-card">
							<div class="wqo-card-header">
								<h3 class="wqo-card-title">
									<i class="fa fa-bar-chart" style="color: var(--wqo-info);"></i>
									${__("Billed vs Expenses (Last 6 Months)")}
								</h3>
							</div>
							<div id="wqo-billed-expense-chart" class="wqo-chart-container">
								<div class="wqo-skeleton wqo-skeleton-chart" style="height: 200px;"></div>
							</div>
						</div>

						<!-- Chart 2: AR & AP Aging -->
						<div class="wqo-card wqo-chart-card">
							<div class="wqo-card-header">
								<h3 class="wqo-card-title">
									<i class="fa fa-hourglass-half" style="color: var(--wqo-warning);"></i>
									${__("Receivables & Payables Aging")}
								</h3>
							</div>
							<div id="wqo-aging-chart" class="wqo-chart-container">
								<div class="wqo-skeleton wqo-skeleton-chart" style="height: 200px;"></div>
							</div>
						</div>
					</div>
				</div>

				<!-- Bottom Section: Tasks Breakdown & HRMS Snapshot -->
				<div class="wqo-bottom-grid">
					<!-- Task Completion Breakdown -->
					<div class="wqo-card">
						<div class="wqo-card-header">
							<h3 class="wqo-card-title">
								<i class="fa fa-pie-chart" style="color: var(--wqo-primary);"></i>
								${__("Task Completion Breakdown")}
							</h3>
							<a href="/app/task" class="wqo-card-action">${__("View Tasks")} &rarr;</a>
						</div>
						<div id="wqo-task-chart" class="wqo-chart-container">
							<div class="wqo-skeleton wqo-skeleton-chart" style="height: 220px;"></div>
						</div>
					</div>

					<!-- HRMS Workforce Snapshot -->
					<div class="wqo-card">
						<div class="wqo-card-header">
							<h3 class="wqo-card-title">
								<i class="fa fa-users" style="color: var(--wqo-success);"></i>
								${__("Workforce & Attendance Snapshot")}
							</h3>
							<a href="/app/attendance" class="wqo-card-action">${__("View Attendance")} &rarr;</a>
						</div>
						<div id="wqo-hrms-wrap">
							<div class="wqo-skeleton wqo-skeleton-chart" style="height: 220px;"></div>
						</div>
					</div>
				</div>
			</div>
		`);
	}

	refresh() {
		const company = this.get_company();
		const me = this;

		// Fetch all 4 APIs in parallel
		frappe.xcall("waterqo.api.ceo_dashboard.get_executive_kpis", { company: company })
			.then((data) => {
				me.render_kpis(data);
			})
			.catch((err) => {
				console.error("Error loading CEO dashboard KPIs:", err);
			});

		frappe.xcall("waterqo.api.ceo_dashboard.get_project_portfolio_status", { company: company })
			.then((data) => {
				me.render_portfolio_table(data);
			})
			.catch((err) => {
				console.error("Error loading project portfolio:", err);
			});

		frappe.xcall("waterqo.api.ceo_dashboard.get_financial_trends", { company: company })
			.then((data) => {
				me.render_financial_charts(data);
			})
			.catch((err) => {
				console.error("Error loading financial trends:", err);
			});

		frappe.xcall("waterqo.api.ceo_dashboard.get_hrms_attendance_summary", { company: company })
			.then((data) => {
				me.render_hrms_summary(data);
			})
			.catch((err) => {
				console.error("Error loading HRMS summary:", err);
			});

		const now = new Date();
		$("#wqo-last-updated").html(
			`<i class="fa fa-check-circle" style="color: var(--wqo-success);"></i> ${__("Updated")} ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
		);
	}

	render_kpis(data) {
		if (!data) return;
		this.currency = data.currency || "PKR";

		// Format numbers
		$("#kpi-net-cash").text(format_currency(data.net_cash, this.currency, 0));
		$("#kpi-total-ar").text(format_currency(data.total_ar, this.currency, 0));
		$("#kpi-total-ap").text(format_currency(data.total_ap, this.currency, 0));
		$("#kpi-active-projects").text(data.active_projects);
		$("#kpi-overdue-projects").text(data.overdue_projects);
		$("#kpi-monthly-rev").text(format_currency(data.monthly_revenue, this.currency, 0));

		// Overdue alert highlight if > 0
		if (data.overdue_projects > 0) {
			$("#kpi-overdue-projects").css("color", "var(--wqo-danger)");
		} else {
			$("#kpi-overdue-projects").css("color", "var(--wqo-text-main)");
		}

		// Revenue growth trend pill
		const growth = data.revenue_growth_pct;
		let trendHtml = `<span>${__("Current Month")}</span>`;
		if (growth !== undefined && growth !== null) {
			const isPos = growth >= 0;
			const pillClass = isPos ? "positive" : "negative";
			const arrow = isPos ? "&uarr;" : "&darr;";
			const sign = isPos ? "+" : "";
			trendHtml = `
				<span class="wqo-trend-pill ${pillClass}">
					${arrow} ${sign}${growth}%
				</span>
				<span>${__("vs last mo")}</span>
			`;
		}
		$("#kpi-revenue-trend").html(trendHtml);
	}

	render_portfolio_table(projects) {
		const $wrap = $("#wqo-portfolio-table-wrap");
		if (!projects || projects.length === 0) {
			$wrap.html(`
				<div class="wqo-empty-state">
					<i class="fa fa-folder-open-o" style="font-size: 2rem; margin-bottom: 8px; display: block; opacity: 0.5;"></i>
					${__("No active projects found for this company.")}
				</div>
			`);
			return;
		}

		let rowsHtml = "";
		projects.forEach((p) => {
			let statusClass = "open";
			const st = (p.status || "").toLowerCase();
			if (st.includes("progress")) statusClass = "in-progress";
			else if (st.includes("complete")) statusClass = "completed";
			else if (st.includes("overdue") || st.includes("cancelled")) statusClass = "overdue";

			// Utilization color
			let utilColorClass = "wqo-util-low";
			if (p.budget_utilization > 100) utilColorClass = "wqo-util-high";
			else if (p.budget_utilization >= 80) utilColorClass = "wqo-util-mid";

			const progressFillWidth = Math.min(Math.max(p.percent_complete, 0), 100);
			const utilFillWidth = Math.min(Math.max(p.budget_utilization, 0), 100);

			rowsHtml += `
				<tr>
					<td>
						<a href="/app/project/${encodeURIComponent(p.name)}" class="wqo-project-name-cell" title="${frappe.utils.escape_html(p.project_name)}">
							${frappe.utils.escape_html(p.project_name)}
						</a>
						<span class="wqo-project-sub">${frappe.utils.escape_html(p.name)}</span>
					</td>
					<td>
						<span class="wqo-badge ${statusClass}">${frappe.utils.escape_html(p.status)}</span>
					</td>
					<td>
						<div class="wqo-progress-container">
							<div class="wqo-progress-track">
								<div class="wqo-progress-fill" style="width: ${progressFillWidth}%; background-color: var(--wqo-info);"></div>
							</div>
							<span class="wqo-progress-text">${p.percent_complete}%</span>
						</div>
					</td>
					<td style="font-weight: 600;">
						${format_currency(p.budget, this.currency, 0)}
					</td>
					<td>
						${format_currency(p.actual_cost, this.currency, 0)}
					</td>
					<td>
						<div class="wqo-progress-container">
							<div class="wqo-progress-track">
								<div class="wqo-progress-fill ${utilColorClass}" style="width: ${utilFillWidth}%;"></div>
							</div>
							<span class="wqo-progress-text">${p.budget_utilization}%</span>
						</div>
					</td>
				</tr>
			`;
		});

		$wrap.html(`
			<table class="wqo-portfolio-table">
				<thead>
					<tr>
						<th>${__("Project")}</th>
						<th>${__("Status")}</th>
						<th>${__("Completion")}</th>
						<th>${__("Budget")}</th>
						<th>${__("Actual Cost")}</th>
						<th>${__("Budget Utilized")}</th>
					</tr>
				</thead>
				<tbody>
					${rowsHtml}
				</tbody>
			</table>
		`);
	}

	render_financial_charts(data) {
		if (!data) return;

		// 1. Monthly Billed vs Expense Chart
		if (data.billed_vs_expense) {
			const bData = data.billed_vs_expense;
			$("#wqo-billed-expense-chart").empty();
			this.charts.billed_expense = new frappe.Chart("#wqo-billed-expense-chart", {
				title: "",
				type: "bar",
				height: 200,
				data: {
					labels: bData.labels,
					datasets: bData.datasets,
				},
				colors: ["#3b82f6", "#f59e0b"],
				axisOptions: {
					xIsSeries: 1,
					shortenYAxisNumbers: 1,
				},
				barOptions: {
					spaceRatio: 0.35,
				},
				tooltipOptions: {
					formatTooltipY: (d) => format_currency(d, this.currency, 0),
				},
			});
		}

		// 2. AR & AP Aging Chart
		if (data.aging_chart) {
			const aData = data.aging_chart;
			$("#wqo-aging-chart").empty();
			this.charts.aging = new frappe.Chart("#wqo-aging-chart", {
				title: "",
				type: "bar",
				height: 200,
				data: {
					labels: aData.labels,
					datasets: aData.datasets,
				},
				colors: ["#10b981", "#ef4444"],
				barOptions: {
					spaceRatio: 0.4,
				},
				axisOptions: {
					shortenYAxisNumbers: 1,
				},
				tooltipOptions: {
					formatTooltipY: (d) => format_currency(d, this.currency, 0),
				},
			});
		}
	}

	render_hrms_summary(data) {
		if (!data) return;

		// 1. Tasks Donut Chart
		if (data.task_chart) {
			const tData = data.task_chart;
			$("#wqo-task-chart").empty();
			this.charts.tasks = new frappe.Chart("#wqo-task-chart", {
				title: "",
				type: "donut",
				height: 220,
				data: {
					labels: tData.labels,
					datasets: tData.datasets,
				},
				colors: ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#64748b", "#ec4899"],
				maxSlices: 6,
			});
		}

		// 2. HRMS Attendance Dial & Headcount
		const attendancePct = data.attendance_percentage || 0;
		const activeCount = data.active_employees || 0;
		const present = data.present_count || 0;
		const absent = data.absent_count || 0;
		const onLeave = data.on_leave_count || 0;

		// Circular progress circumference: 2 * PI * 60 ~= 377
		const radius = 60;
		const circumference = 2 * Math.PI * radius;
		const strokeDashoffset = circumference - (attendancePct / 100) * circumference;

		$("#wqo-hrms-wrap").html(`
			<div class="wqo-hrms-container">
				<!-- Circular Gauge -->
				<div class="wqo-attendance-dial">
					<svg class="wqo-dial-svg" width="140" height="140" viewBox="0 0 140 140">
						<circle class="wqo-dial-circle-bg" cx="70" cy="70" r="${radius}"></circle>
						<circle class="wqo-dial-circle-fill" cx="70" cy="70" r="${radius}" style="stroke-dasharray: ${circumference}; stroke-dashoffset: ${strokeDashoffset};"></circle>
					</svg>
					<div class="wqo-dial-text">
						<span class="wqo-dial-percent">${attendancePct}%</span>
						<span class="wqo-dial-label">${__("Present Today")}</span>
					</div>
				</div>

				<!-- Workforce Stats -->
				<div class="wqo-hrms-stats">
					<div class="wqo-stat-pill">
						<span class="wqo-stat-label"><i class="fa fa-id-badge"></i> ${__("Active Workforce")}</span>
						<span class="wqo-stat-num">${activeCount}</span>
					</div>
					<div class="wqo-stat-pill">
						<span class="wqo-stat-label"><span class="wqo-dot present"></span> ${__("Present Today")}</span>
						<span class="wqo-stat-num" style="color: var(--wqo-success);">${present}</span>
					</div>
					<div class="wqo-stat-pill">
						<span class="wqo-stat-label"><span class="wqo-dot absent"></span> ${__("Absent")}</span>
						<span class="wqo-stat-num" style="color: var(--wqo-danger);">${absent}</span>
					</div>
					<div class="wqo-stat-pill">
						<span class="wqo-stat-label"><span class="wqo-dot leave"></span> ${__("On Leave")}</span>
						<span class="wqo-stat-num" style="color: var(--wqo-warning);">${onLeave}</span>
					</div>
				</div>
			</div>
		`);
	}
}
