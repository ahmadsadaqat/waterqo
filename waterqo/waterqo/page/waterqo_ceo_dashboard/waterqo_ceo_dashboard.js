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

	$(wrapper).on("destroy", function () {
		if (wrapper.ceo_dashboard && wrapper.ceo_dashboard.chartsStackObserver) {
			wrapper.ceo_dashboard.chartsStackObserver.disconnect();
		}
		$(window).off("resize.wqo_ceo_dashboard");
	});
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

	get_general_ledger_url(account = null) {
		const company = this.get_company() || "";
		const to_date = (typeof frappe !== "undefined" && frappe.datetime) ? frappe.datetime.get_today() : new Date().toISOString().slice(0, 10);
		const from_date = (typeof frappe !== "undefined" && frappe.datetime) ? frappe.datetime.add_months(to_date, -1) : new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);

		const params = new URLSearchParams();
		if (company) {
			params.set("company", company);
		}
		params.set("from_date", from_date);
		params.set("to_date", to_date);
		if (account) {
			params.set("account", JSON.stringify([account]));
		}
		params.set("categorize_by", "Categorize by Voucher (Consolidated)");
		params.set("include_dimensions", "1");
		params.set("include_default_book_entries", "1");

		return `/app/query-report/General%20Ledger?${params.toString()}`;
	}

	get_attendance_url() {
		const company = this.get_company() || "";
		const hasAttendance =
			typeof frappe !== "undefined" &&
			frappe.boot &&
			frappe.boot.user &&
			frappe.boot.user.can_read &&
			frappe.boot.user.can_read.includes("Attendance");

		if (hasAttendance) {
			const now = new Date();
			const currentMonth = now.getMonth() + 1;
			const currentYear = now.getFullYear();

			const params = new URLSearchParams();
			if (company) {
				params.set("company", company);
			}
			params.set("filter_based_on", "Month");
			params.set("month", currentMonth);
			params.set("year", currentYear);

			return `/app/query-report/Monthly%20Attendance%20Sheet?${params.toString()}`;
		}

		// Fallback when HRMS / Attendance is not installed on the site
		const params = new URLSearchParams();
		if (company) {
			params.set("company", company);
		}
		params.set("status", "Active");
		return `/app/employee?${params.toString()}`;
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
					<div class="wqo-card wqo-portfolio-card">
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

				<!-- Section: Bank & Treasury Management -->
				<div class="wqo-section-heading">
					<div class="wqo-section-title">
						<i class="fa fa-university" style="color: var(--wqo-primary);"></i>
						<span>${__("Bank & Treasury Management")}</span>
					</div>
					<div class="wqo-section-actions">
						<a href="/app/bank-reconciliation-tool" class="wqo-card-action">
							<i class="fa fa-refresh"></i> ${__("Reconciliation Tool")} &rarr;
						</a>
						<a href="/app/bank-account" class="wqo-card-action">
							<i class="fa fa-university"></i> ${__("Bank Accounts")} &rarr;
						</a>
					</div>
				</div>

				<!-- Bank Row 1: Current Balances & Reconciliation Status -->
				<div class="wqo-banking-grid">
					<!-- Card 1: Bank-wise Current Balance -->
					<div class="wqo-card wqo-bank-card">
						<div class="wqo-card-header">
							<h3 class="wqo-card-title">
								<i class="fa fa-money" style="color: #10b981;"></i>
								${__("Bank-wise Current Balance")}
							</h3>
							<a href="${this.get_general_ledger_url()}" id="wqo-gl-card-action" class="wqo-card-action">${__("General Ledger")} &rarr;</a>
						</div>
						<div id="wqo-bank-balances-wrap" class="wqo-bank-content-wrap">
							<div class="wqo-skeleton wqo-skeleton-chart" style="height: 240px;"></div>
						</div>
					</div>

					<!-- Card 2: Bank Reconciliation Status -->
					<div class="wqo-card wqo-bank-card">
						<div class="wqo-card-header">
							<h3 class="wqo-card-title">
								<i class="fa fa-check-square-o" style="color: #3b82f6;"></i>
								${__("Bank Reconciliation Status")}
							</h3>
							<a href="/app/query-report/Bank%20Reconciliation%20Statement" class="wqo-card-action">${__("Statement")} &rarr;</a>
						</div>
						<div id="wqo-bank-reconciliation-wrap" class="wqo-bank-content-wrap">
							<div class="wqo-skeleton wqo-skeleton-chart" style="height: 240px;"></div>
						</div>
					</div>
				</div>

				<!-- Bank Row 2: Monthly Opening/Closing & Payment/Receipt Summary -->
				<div class="wqo-banking-grid">
					<!-- Card 3: Opening and Closing Balances (Monthly) -->
					<div class="wqo-card wqo-bank-card">
						<div class="wqo-card-header">
							<h3 class="wqo-card-title">
								<i class="fa fa-calendar-check-o" style="color: #8b5cf6;"></i>
								${__("Monthly Opening & Closing Balances")}
							</h3>
							<span class="wqo-badge wqo-badge-neutral" id="wqo-bank-month-badge">${__("Current Month")}</span>
						</div>
						<div id="wqo-bank-opening-closing-wrap" class="wqo-bank-content-wrap">
							<div class="wqo-skeleton wqo-skeleton-chart" style="height: 240px;"></div>
						</div>
					</div>

					<!-- Card 4: Bank-wise Payment & Receipt Summary (Monthly) -->
					<div class="wqo-card wqo-bank-card">
						<div class="wqo-card-header">
							<h3 class="wqo-card-title">
								<i class="fa fa-bar-chart" style="color: #06b6d4;"></i>
								${__("Payment & Receipt Summary (Monthly)")}
							</h3>
							<span class="wqo-badge wqo-badge-neutral" id="wqo-bank-summary-badge">${__("Inflow vs Outflow")}</span>
						</div>
						<div id="wqo-bank-payment-receipt-chart" class="wqo-chart-container" style="min-height: 200px;">
							<div class="wqo-skeleton wqo-skeleton-chart" style="height: 200px;"></div>
						</div>
						<div id="wqo-bank-payment-receipt-totals" class="wqo-bank-totals-pills"></div>
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
							<a href="${this.get_attendance_url()}" id="wqo-attendance-card-action" class="wqo-card-action">${__("View Attendance")} &rarr;</a>
						</div>
						<div id="wqo-hrms-wrap">
							<div class="wqo-skeleton wqo-skeleton-chart" style="height: 220px;"></div>
						</div>
					</div>
				</div>
			</div>
		`);
		this.setup_resize_observer();
	}

	refresh() {
		const company = this.get_company();
		const me = this;

		this.body.find("#wqo-gl-card-action").attr("href", this.get_general_ledger_url());
		this.body.find("#wqo-attendance-card-action").attr("href", this.get_attendance_url());

		// Fetch all 4 APIs in parallel
		frappe.xcall("waterqo.api.ceo_dashboard.get_executive_kpis", { company: company })
			.then((data) => {
				me.render_kpis(data);
			})
			.catch((err) => {
				console.error("Error loading CEO dashboard KPIs:", err);
			});

		frappe.xcall("waterqo.api.ceo_dashboard.get_project_portfolio_status", { company: company, limit: 100 })
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

		// Fetch Bank Treasury APIs
		frappe.xcall("waterqo.api.ceo_dashboard.get_bank_current_balances_and_reconciliation", { company: company })
			.then((data) => {
				me.render_bank_balances(data);
				me.render_bank_reconciliation(data);
			})
			.catch((err) => {
				console.error("Error loading bank balances and reconciliation:", err);
			});

		frappe.xcall("waterqo.api.ceo_dashboard.get_bank_monthly_balances_and_summary", { company: company })
			.then((data) => {
				me.render_bank_opening_closing(data);
				me.render_bank_payment_receipt_summary(data);
			})
			.catch((err) => {
				console.error("Error loading bank monthly summary:", err);
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
		this.sync_portfolio_card_height();
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

		this.sync_portfolio_card_height();
		setTimeout(() => {
			this.sync_portfolio_card_height();
		}, 150);
	}

	setup_resize_observer() {
		const me = this;
		if (window.ResizeObserver) {
			const stackEl = this.body.find(".wqo-charts-stack")[0];
			if (stackEl) {
				if (this.chartsStackObserver) {
					this.chartsStackObserver.disconnect();
				}
				this.chartsStackObserver = new ResizeObserver(() => {
					me.sync_portfolio_card_height();
				});
				this.chartsStackObserver.observe(stackEl);
			}
		}

		$(window).off("resize.wqo_ceo_dashboard").on("resize.wqo_ceo_dashboard", () => {
			me.sync_portfolio_card_height();
		});
	}

	sync_portfolio_card_height() {
		const $portfolioCard = this.body.find(".wqo-portfolio-card");
		const $chartsStack = this.body.find(".wqo-charts-stack");
		const $tableWrap = this.body.find("#wqo-portfolio-table-wrap");

		if (!$portfolioCard.length || !$chartsStack.length || !$tableWrap.length) return;

		const stackHeight = Math.round($chartsStack.outerHeight());
		if (stackHeight > 300) {
			const headerHeight = $portfolioCard.find(".wqo-card-header").outerHeight(true) || 50;
			const cardPadding = 38; // 18px top + 18px bottom + 2px border
			const availableHeight = stackHeight - headerHeight - cardPadding - 4;
			const tableHeight = Math.max(availableHeight, 350);
			$tableWrap.css("max-height", tableHeight + "px");
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

	render_bank_balances(data) {
		const $wrap = $("#wqo-bank-balances-wrap");
		if (!data || !data.bank_accounts || data.bank_accounts.length === 0) {
			$wrap.html(`
				<div class="wqo-empty-state">
					<i class="fa fa-university" style="font-size: 2rem; margin-bottom: 8px; display: block; opacity: 0.5;"></i>
					${__("No bank ledger accounts found for this company.")}
				</div>
			`);
			return;
		}

		const currency = data.currency || this.currency || "PKR";
		const netBalance = data.net_bank_balance || 0;
		const netClass = netBalance >= 0 ? "positive" : "negative";

		let accountsHtml = "";
		data.bank_accounts.forEach((b) => {
			const isPositive = b.current_balance >= 0;
			const balClass = isPositive ? "wqo-bal-positive" : "wqo-bal-negative";
			const shareWidth = Math.min(Math.max(b.share_pct || 0, 0), 100);
			const subLabel = b.bank_account_no ? `${b.account} • ${b.bank_account_no}` : b.account;
			const glUrl = this.get_general_ledger_url(b.account);

			accountsHtml += `
				<div class="wqo-bank-item">
					<div class="wqo-bank-item-info">
						<div class="wqo-bank-icon"><i class="fa fa-university"></i></div>
						<div class="wqo-bank-details">
							<a href="${glUrl}" class="wqo-bank-name" title="${frappe.utils.escape_html(b.bank_name)}">
								${frappe.utils.escape_html(b.bank_name)}
							</a>
							<span class="wqo-bank-sub">${frappe.utils.escape_html(subLabel)}</span>
						</div>
					</div>
					<div class="wqo-bank-item-balance">
						<span class="wqo-bank-amount ${balClass}">
							${format_currency(b.current_balance, b.account_currency || currency, 0)}
						</span>
						<div class="wqo-bank-share-wrap" title="${__("Share of liquid funds: {0}%", [b.share_pct])}">
							<div class="wqo-bank-share-bar" style="width: ${shareWidth}%;"></div>
							<span class="wqo-bank-share-text">${b.share_pct}%</span>
						</div>
					</div>
				</div>
			`;
		});

		$wrap.html(`
			<div class="wqo-bank-balances-container">
				<div class="wqo-bank-net-banner ${netClass}">
					<div class="wqo-net-banner-text">
						<span class="wqo-net-banner-label">${__("Total Liquid Bank Balance")}</span>
						<span class="wqo-net-banner-val">${format_currency(netBalance, currency, 0)}</span>
					</div>
					<span class="wqo-net-banner-count">${__("{0} Bank Ledgers", [data.bank_accounts.length])}</span>
				</div>
				<div class="wqo-bank-list">
					${accountsHtml}
				</div>
			</div>
		`);
	}

	render_bank_reconciliation(data) {
		const $wrap = $("#wqo-bank-reconciliation-wrap");
		if (!data || !data.reconciliation) {
			$wrap.html(`
				<div class="wqo-empty-state">
					<i class="fa fa-check-circle-o" style="font-size: 2rem; margin-bottom: 8px; display: block; opacity: 0.5;"></i>
					${__("No reconciliation data available.")}
				</div>
			`);
			return;
		}

		const recon = data.reconciliation;
		const currency = data.currency || this.currency || "PKR";
		const rate = flt(recon.reconciliation_rate || 0, 1);

		let statusLabel = __("Fully Cleared");
		let statusColor = "var(--wqo-success)";
		let statusClass = "positive";
		if (rate < 50) {
			statusLabel = __("Action Required");
			statusColor = "var(--wqo-danger)";
			statusClass = "negative";
		} else if (rate < 90) {
			statusLabel = __("Partially Cleared");
			statusColor = "var(--wqo-warning)";
			statusClass = "warning";
		}

		let btHtml = "";
		if (recon.bank_transactions && recon.bank_transactions.length > 0) {
			let btBadges = recon.bank_transactions.map(bt => `
				<span class="wqo-recon-bt-tag ${(bt.status || "").toLowerCase()}">
					${frappe.utils.escape_html(bt.status)}: <strong>${bt.count}</strong>
				</span>
			`).join("");
			btHtml = `
				<div class="wqo-recon-bt-section">
					<span class="wqo-recon-bt-title">${__("Statement Transactions:")}</span>
					<div class="wqo-recon-bt-tags">${btBadges}</div>
				</div>
			`;
		}

		$wrap.html(`
			<div class="wqo-recon-container">
				<!-- Clearance Rate Meter -->
				<div class="wqo-recon-meter-header">
					<div class="wqo-recon-rate-block">
						<span class="wqo-recon-rate-num" style="color: ${statusColor};">${rate}%</span>
						<span class="wqo-trend-pill ${statusClass}">${statusLabel}</span>
					</div>
					<div class="wqo-recon-meta">
						<span>${__("{0} of {1} Vouchers Cleared", [recon.cleared_vouchers, recon.total_vouchers])}</span>
					</div>
				</div>
				<div class="wqo-recon-meter-track">
					<div class="wqo-recon-meter-fill" style="width: ${rate}%; background-color: ${statusColor};"></div>
				</div>

				<!-- Clearance Metrics Grid -->
				<div class="wqo-recon-metrics-grid">
					<div class="wqo-recon-metric-card">
						<span class="wqo-metric-label"><i class="fa fa-check text-success"></i> ${__("Cleared Vouchers")}</span>
						<span class="wqo-metric-val text-success">${recon.cleared_vouchers}</span>
					</div>
					<div class="wqo-recon-metric-card">
						<span class="wqo-metric-label"><i class="fa fa-clock-o text-warning"></i> ${__("Uncleared Vouchers")}</span>
						<span class="wqo-metric-val text-warning">${recon.uncleared_vouchers}</span>
					</div>
					<div class="wqo-recon-metric-card">
						<span class="wqo-metric-label"><i class="fa fa-arrow-down text-info"></i> ${__("Uncleared Receipts (In Transit)")}</span>
						<span class="wqo-metric-val">${format_currency(recon.uncleared_receipts, currency, 0)}</span>
					</div>
					<div class="wqo-recon-metric-card">
						<span class="wqo-metric-label"><i class="fa fa-arrow-up text-danger"></i> ${__("Uncleared Payments (Unpresented)")}</span>
						<span class="wqo-metric-val">${format_currency(recon.uncleared_payments, currency, 0)}</span>
					</div>
				</div>

				${btHtml}

				<div class="wqo-recon-footer-action">
					<a href="/app/bank-reconciliation-tool" class="btn btn-xs btn-default wqo-recon-btn">
						<i class="fa fa-external-link"></i> ${__("Open Bank Reconciliation Tool")}
					</a>
				</div>
			</div>
		`);
	}

	render_bank_opening_closing(data) {
		const $wrap = $("#wqo-bank-opening-closing-wrap");
		if (data && data.month_label) {
			$("#wqo-bank-month-badge").text(data.month_label);
		}

		if (!data || !data.opening_closing_summary || data.opening_closing_summary.length === 0) {
			$wrap.html(`
				<div class="wqo-empty-state">
					<i class="fa fa-calendar-o" style="font-size: 2rem; margin-bottom: 8px; display: block; opacity: 0.5;"></i>
					${__("No monthly bank ledger data found for this company.")}
				</div>
			`);
			return;
		}

		let rowsHtml = "";
		data.opening_closing_summary.forEach((row) => {
			const netIsPos = row.net_change >= 0;
			const netClass = netIsPos ? "positive" : "negative";
			const netSign = netIsPos ? "+" : "";
			const glUrl = this.get_general_ledger_url(row.account);

			rowsHtml += `
				<tr>
					<td>
						<a href="${glUrl}" class="wqo-project-name-cell" title="${frappe.utils.escape_html(row.account_name)}">
							${frappe.utils.escape_html(row.account_name)}
						</a>
						<span class="wqo-project-sub">${frappe.utils.escape_html(row.account)}</span>
					</td>
					<td>${format_currency(row.opening_balance, row.currency, 0)}</td>
					<td style="color: var(--wqo-success); font-weight: 500;">
						+${format_currency(row.receipts, row.currency, 0)}
					</td>
					<td style="color: var(--wqo-danger); font-weight: 500;">
						-${format_currency(row.payments, row.currency, 0)}
					</td>
					<td>
						<span class="wqo-trend-pill ${netClass}">
							${netSign}${format_currency(row.net_change, row.currency, 0)}
						</span>
					</td>
					<td style="font-weight: 700;">
						${format_currency(row.closing_balance, row.currency, 0)}
					</td>
				</tr>
			`;
		});

		// Totals row
		const totals = data.totals || {};
		const totalNetIsPos = (totals.net_change || 0) >= 0;
		const totalNetClass = totalNetIsPos ? "positive" : "negative";
		const totalNetSign = totalNetIsPos ? "+" : "";
		const currency = this.currency || "PKR";

		const footerHtml = `
			<tr class="wqo-table-totals-row">
				<td><strong>${__("Total")}</strong></td>
				<td><strong>${format_currency(totals.total_opening, currency, 0)}</strong></td>
				<td style="color: var(--wqo-success); font-weight: 700;">+${format_currency(totals.total_receipts, currency, 0)}</td>
				<td style="color: var(--wqo-danger); font-weight: 700;">-${format_currency(totals.total_payments, currency, 0)}</td>
				<td>
					<span class="wqo-trend-pill ${totalNetClass}">
						${totalNetSign}${format_currency(totals.net_change, currency, 0)}
					</span>
				</td>
				<td><strong>${format_currency(totals.total_closing, currency, 0)}</strong></td>
			</tr>
		`;

		$wrap.html(`
			<div class="wqo-table-container">
				<table class="wqo-portfolio-table wqo-bank-table">
					<thead>
						<tr>
							<th>${__("Bank Ledger")}</th>
							<th>${__("Opening Balance")}</th>
							<th>${__("Receipts (+)")}</th>
							<th>${__("Payments (-)")}</th>
							<th>${__("Net Change")}</th>
							<th>${__("Closing Balance")}</th>
						</tr>
					</thead>
					<tbody>
						${rowsHtml}
					</tbody>
					<tfoot>
						${footerHtml}
					</tfoot>
				</table>
			</div>
		`);
	}

	render_bank_payment_receipt_summary(data) {
		if (data && data.month_label) {
			$("#wqo-bank-summary-badge").text(data.month_label);
		}

		const chartEl = $("#wqo-bank-payment-receipt-chart");
		chartEl.empty();

		if (!data || !data.payment_receipt_chart || !data.payment_receipt_chart.labels || data.payment_receipt_chart.labels.length === 0) {
			chartEl.html(`
				<div class="wqo-empty-state">
					<i class="fa fa-bar-chart" style="font-size: 2rem; margin-bottom: 8px; display: block; opacity: 0.5;"></i>
					${__("No payment or receipt transactions in this period.")}
				</div>
			`);
			$("#wqo-bank-payment-receipt-totals").empty();
			return;
		}

		const chartData = data.payment_receipt_chart;
		this.charts.bank_payment_receipt = new frappe.Chart("#wqo-bank-payment-receipt-chart", {
			title: "",
			type: "bar",
			height: 200,
			data: {
				labels: chartData.labels,
				datasets: chartData.datasets,
			},
			colors: ["#10b981", "#ef4444"],
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

		// Totals Pills
		const totals = data.totals || {};
		const netIsPos = (totals.net_change || 0) >= 0;
		const netClass = netIsPos ? "positive" : "negative";
		const netSign = netIsPos ? "+" : "";
		const currency = this.currency || "PKR";

		$("#wqo-bank-payment-receipt-totals").html(`
			<div class="wqo-bank-total-pill">
				<span class="wqo-bt-label"><i class="fa fa-arrow-circle-down text-success"></i> ${__("Total Inflow (Receipts)")}</span>
				<span class="wqo-bt-val text-success">${format_currency(totals.total_receipts, currency, 0)}</span>
			</div>
			<div class="wqo-bank-total-pill">
				<span class="wqo-bt-label"><i class="fa fa-arrow-circle-up text-danger"></i> ${__("Total Outflow (Payments)")}</span>
				<span class="wqo-bt-val text-danger">${format_currency(totals.total_payments, currency, 0)}</span>
			</div>
			<div class="wqo-bank-total-pill">
				<span class="wqo-bt-label"><i class="fa fa-exchange"></i> ${__("Net Cash Flow")}</span>
				<span class="wqo-bt-val ${netClass}">${netSign}${format_currency(totals.net_change, currency, 0)}</span>
			</div>
		`);
	}
}
