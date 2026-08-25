# Copyright (c) 2026, Nexo ERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	add_months,
	cint,
	flt,
	get_first_day,
	get_last_day,
	getdate,
	nowdate,
)


def _check_dashboard_permissions():
	"""Validate that the user has the CEO role or System Manager/Administrator."""
	if frappe.session.user == "Administrator":
		return
	roles = frappe.get_roles()
	allowed_roles = ["CEO", "System Manager"]
	if not any(role in roles for role in allowed_roles):
		frappe.throw(
			_("Access restricted: The Executive CEO Dashboard is only accessible to users with the CEO role."),
			frappe.PermissionError,
		)


def _get_active_company(company=None):
	"""Return the company to filter on, or None if no valid company found."""
	if company and frappe.db.exists("Company", company):
		return company
	user_default = frappe.defaults.get_user_default("company")
	if user_default and frappe.db.exists("Company", user_default):
		return user_default
	default_company = frappe.db.get_single_value("Global Defaults", "default_company")
	if default_company and frappe.db.exists("Company", default_company):
		return default_company
	# Fallback to the first company in database if exists
	first_comp = frappe.db.get_all("Company", limit=1, pluck="name")
	return first_comp[0] if first_comp else None


@frappe.whitelist()
def get_executive_kpis(company=None):
	"""
	Returns 6 executive KPIs:
	1. Net Cash: Sum of balances across all bank & cash accounts from GL Entry.
	2. Total Receivables (AR): Sum of outstanding_amount from submitted Sales Invoice.
	3. Total Payables (AP): Sum of outstanding_amount from submitted Purchase Invoice.
	4. Active Projects: Count of Project with status in ['Open', 'In Progress'].
	5. Overdue Projects: Count of Project where expected_end_date < CURRENT_DATE and status not completed/cancelled.
	6. Monthly Revenue: Sum of base_grand_total from Sales Invoice for current month with trend vs last month.
	"""
	_check_dashboard_permissions()
	comp = _get_active_company(company)

	# 1. Net Cash from GL Entry
	cash_res = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON acc.name = gle.account
		WHERE gle.docstatus = 1
		  AND gle.is_cancelled = 0
		  AND acc.account_type IN ('Bank', 'Cash')
		  AND (%(company)s IS NULL OR gle.company = %(company)s)
	""",
		{"company": comp},
	)
	net_cash = flt(cash_res[0][0]) if cash_res else 0.0

	# 2. Total Receivables (AR)
	ar_res = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(outstanding_amount), 0)
		FROM `tabSales Invoice`
		WHERE docstatus = 1
		  AND status != 'Paid'
		  AND outstanding_amount > 0
		  AND (%(company)s IS NULL OR company = %(company)s)
	""",
		{"company": comp},
	)
	total_ar = flt(ar_res[0][0]) if ar_res else 0.0

	# 3. Total Payables (AP)
	ap_res = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(outstanding_amount), 0)
		FROM `tabPurchase Invoice`
		WHERE docstatus = 1
		  AND status != 'Paid'
		  AND outstanding_amount > 0
		  AND (%(company)s IS NULL OR company = %(company)s)
	""",
		{"company": comp},
	)
	total_ap = flt(ap_res[0][0]) if ap_res else 0.0

	# 4. Active Projects
	active_proj_res = frappe.db.sql(
		"""
		SELECT COUNT(name)
		FROM `tabProject`
		WHERE status IN ('Open', 'In Progress')
		  AND docstatus < 2
		  AND (%(company)s IS NULL OR company = %(company)s)
	""",
		{"company": comp},
	)
	active_projects = cint(active_proj_res[0][0]) if active_proj_res else 0

	# 5. Overdue Projects
	overdue_proj_res = frappe.db.sql(
		"""
		SELECT COUNT(name)
		FROM `tabProject`
		WHERE expected_end_date IS NOT NULL
		  AND expected_end_date < CURRENT_DATE
		  AND status NOT IN ('Completed', 'Cancelled')
		  AND docstatus < 2
		  AND (%(company)s IS NULL OR company = %(company)s)
	""",
		{"company": comp},
	)
	overdue_projects = cint(overdue_proj_res[0][0]) if overdue_proj_res else 0

	# 6. Monthly Revenue (Current vs Previous Month)
	today = nowdate()
	first_day_curr = get_first_day(today)
	last_day_curr = get_last_day(today)

	curr_rev_res = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(base_grand_total), 0)
		FROM `tabSales Invoice`
		WHERE docstatus = 1
		  AND posting_date >= %(start)s
		  AND posting_date <= %(end)s
		  AND (%(company)s IS NULL OR company = %(company)s)
	""",
		{"start": first_day_curr, "end": last_day_curr, "company": comp},
	)
	monthly_revenue = flt(curr_rev_res[0][0]) if curr_rev_res else 0.0

	first_day_prev = get_first_day(add_months(today, -1))
	last_day_prev = get_last_day(add_months(today, -1))

	prev_rev_res = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(base_grand_total), 0)
		FROM `tabSales Invoice`
		WHERE docstatus = 1
		  AND posting_date >= %(start)s
		  AND posting_date <= %(end)s
		  AND (%(company)s IS NULL OR company = %(company)s)
	""",
		{"start": first_day_prev, "end": last_day_prev, "company": comp},
	)
	prev_revenue = flt(prev_rev_res[0][0]) if prev_rev_res else 0.0

	rev_change_pct = 0.0
	if prev_revenue > 0:
		rev_change_pct = flt(((monthly_revenue - prev_revenue) / prev_revenue) * 100, 1)
	elif monthly_revenue > 0:
		rev_change_pct = 100.0

	# Currency
	currency = "PKR"
	if comp:
		currency = frappe.get_cached_value("Company", comp, "default_currency") or "PKR"

	return {
		"company": comp,
		"currency": currency,
		"net_cash": net_cash,
		"total_ar": total_ar,
		"total_ap": total_ap,
		"active_projects": active_projects,
		"overdue_projects": overdue_projects,
		"monthly_revenue": monthly_revenue,
		"prev_monthly_revenue": prev_revenue,
		"revenue_growth_pct": rev_change_pct,
	}


@frappe.whitelist()
def get_project_portfolio_status(company=None):
	"""
	Fetch top active projects with:
	- name, project_name, percent_complete, status, expected_end_date
	- budget vs actual: linked Sales Invoice totals (billed revenue) vs linked Purchase Invoice + Stock Entry costs
	"""
	_check_dashboard_permissions()
	comp = _get_active_company(company)

	projects = frappe.db.sql(
		"""
		SELECT
			p.name,
			p.project_name,
			COALESCE(p.percent_complete, 0) as percent_complete,
			p.status,
			p.expected_end_date,
			p.company,
			COALESCE(p.custom_project_budget, p.estimated_costing, 0) as budget
		FROM `tabProject` p
		WHERE p.status NOT IN ('Completed', 'Cancelled')
		  AND p.docstatus < 2
		  AND (%(company)s IS NULL OR p.company = %(company)s)
		ORDER BY p.creation DESC
		LIMIT 15
	""",
		{"company": comp},
		as_dict=True,
	)

	result = []
	for p in projects:
		proj_id = p.name
		budget = flt(p.budget)

		# Billed Revenue from Sales Invoice
		si_res = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(base_grand_total), 0)
			FROM `tabSales Invoice`
			WHERE project = %s AND docstatus = 1
		""",
			(proj_id,),
		)
		billed_revenue = flt(si_res[0][0]) if si_res else 0.0

		# Actual Cost from GL Entry (Stock Entry Material Issue + Journal Entry + Purchase Invoice)
		gle_res = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
			FROM `tabGL Entry` gle
			LEFT JOIN `tabStock Entry` se ON se.name = gle.voucher_no AND gle.voucher_type = 'Stock Entry'
			WHERE gle.docstatus = 1
			  AND gle.is_cancelled = 0
			  AND gle.debit > 0
			  AND gle.project = %s
			  AND (
				  (gle.voucher_type = 'Stock Entry' AND se.purpose = 'Material Issue')
				  OR (gle.voucher_type = 'Journal Entry')
				  OR (gle.voucher_type = 'Purchase Invoice')
			  )
		""",
			(proj_id,),
		)
		actual_cost_gle = flt(gle_res[0][0]) if gle_res else 0.0

		# Direct Purchase Invoice + Stock Entry calculation fallback / supplement
		pi_res = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(base_grand_total), 0)
			FROM `tabPurchase Invoice`
			WHERE project = %s AND docstatus = 1
		""",
			(proj_id,),
		)
		pi_cost = flt(pi_res[0][0]) if pi_res else 0.0

		se_res = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(total_incoming_value), 0)
			FROM `tabStock Entry`
			WHERE project = %s AND purpose = 'Material Issue' AND docstatus = 1
		""",
			(proj_id,),
		)
		se_cost = flt(se_res[0][0]) if se_res else 0.0

		direct_cost = pi_cost + se_cost
		actual_cost = max(actual_cost_gle, direct_cost)

		utilization = flt((actual_cost / budget * 100), 1) if budget > 0 else 0.0

		result.append(
			{
				"name": p.name,
				"project_name": p.project_name or p.name,
				"percent_complete": flt(p.percent_complete, 1),
				"status": p.status,
				"expected_end_date": str(p.expected_end_date) if p.expected_end_date else None,
				"budget": budget,
				"actual_cost": actual_cost,
				"billed_revenue": billed_revenue,
				"budget_utilization": utilization,
			}
		)

	return result


@frappe.whitelist()
def get_financial_trends(company=None):
	"""
	Returns:
	1. Monthly Billed vs Expense: Monthly aggregated totals of submitted Sales Invoice vs Purchase Invoice for the last 6 months.
	2. AR & AP Aging: Outstanding bucket distribution (0-30, 31-60, 61-90, 90+ days) based on due_date.
	"""
	_check_dashboard_permissions()
	comp = _get_active_company(company)

	# 1. 6-Month Billed vs Expense
	labels = []
	billed_values = []
	expense_values = []
	today = getdate(nowdate())

	for i in range(5, -1, -1):
		target_date = add_months(today, -i)
		m_start = get_first_day(target_date)
		m_end = get_last_day(target_date)
		month_label = target_date.strftime("%b %Y")
		labels.append(month_label)

		# Billed total
		si_total = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(base_grand_total), 0)
			FROM `tabSales Invoice`
			WHERE docstatus = 1
			  AND posting_date >= %(start)s
			  AND posting_date <= %(end)s
			  AND (%(company)s IS NULL OR company = %(company)s)
		""",
			{"start": m_start, "end": m_end, "company": comp},
		)
		billed_values.append(flt(si_total[0][0]) if si_total else 0.0)

		# Expense total
		pi_total = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(base_grand_total), 0)
			FROM `tabPurchase Invoice`
			WHERE docstatus = 1
			  AND posting_date >= %(start)s
			  AND posting_date <= %(end)s
			  AND (%(company)s IS NULL OR company = %(company)s)
		""",
			{"start": m_start, "end": m_end, "company": comp},
		)
		expense_values.append(flt(pi_total[0][0]) if pi_total else 0.0)

	billed_vs_expense = {
		"labels": labels,
		"datasets": [
			{"name": _("Billed (Revenue)"), "values": billed_values},
			{"name": _("Expenses (Purchases)"), "values": expense_values},
		],
	}

	# 2. AR & AP Aging
	ar_aging_res = frappe.db.sql(
		"""
		SELECT
			COALESCE(SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, posting_date)) <= 30 THEN outstanding_amount ELSE 0 END), 0) AS b0_30,
			COALESCE(SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, posting_date)) BETWEEN 31 AND 60 THEN outstanding_amount ELSE 0 END), 0) AS b31_60,
			COALESCE(SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, posting_date)) BETWEEN 61 AND 90 THEN outstanding_amount ELSE 0 END), 0) AS b61_90,
			COALESCE(SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, posting_date)) > 90 THEN outstanding_amount ELSE 0 END), 0) AS b90_plus
		FROM `tabSales Invoice`
		WHERE docstatus = 1
		  AND status != 'Paid'
		  AND outstanding_amount > 0
		  AND (%(company)s IS NULL OR company = %(company)s)
	""",
		{"company": comp},
		as_dict=True,
	)

	ap_aging_res = frappe.db.sql(
		"""
		SELECT
			COALESCE(SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, posting_date)) <= 30 THEN outstanding_amount ELSE 0 END), 0) AS b0_30,
			COALESCE(SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, posting_date)) BETWEEN 31 AND 60 THEN outstanding_amount ELSE 0 END), 0) AS b31_60,
			COALESCE(SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, posting_date)) BETWEEN 61 AND 90 THEN outstanding_amount ELSE 0 END), 0) AS b61_90,
			COALESCE(SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, posting_date)) > 90 THEN outstanding_amount ELSE 0 END), 0) AS b90_plus
		FROM `tabPurchase Invoice`
		WHERE docstatus = 1
		  AND status != 'Paid'
		  AND outstanding_amount > 0
		  AND (%(company)s IS NULL OR company = %(company)s)
	""",
		{"company": comp},
		as_dict=True,
	)

	ar_row = ar_aging_res[0] if ar_aging_res else {}
	ap_row = ap_aging_res[0] if ap_aging_res else {}

	aging_chart = {
		"labels": [_("0-30 Days"), _("31-60 Days"), _("61-90 Days"), _("90+ Days")],
		"datasets": [
			{
				"name": _("Receivables (AR)"),
				"values": [
					flt(ar_row.get("b0_30", 0)),
					flt(ar_row.get("b31_60", 0)),
					flt(ar_row.get("b61_90", 0)),
					flt(ar_row.get("b90_plus", 0)),
				],
			},
			{
				"name": _("Payables (AP)"),
				"values": [
					flt(ap_row.get("b0_30", 0)),
					flt(ap_row.get("b31_60", 0)),
					flt(ap_row.get("b61_90", 0)),
					flt(ap_row.get("b90_plus", 0)),
				],
			},
		],
	}

	return {
		"billed_vs_expense": billed_vs_expense,
		"aging_chart": aging_chart,
	}


@frappe.whitelist()
def get_hrms_attendance_summary(company=None):
	"""
	Returns HRMS attendance & Task stats:
	- Total active employees
	- Today's attendance percentage & counts (present, absent, on leave)
	- Task completion breakdown grouped by status
	"""
	_check_dashboard_permissions()
	comp = _get_active_company(company)

	active_employees = 0
	present_count = 0
	absent_count = 0
	on_leave_count = 0
	attendance_pct = 0.0

	# 1. HRMS Employee & Attendance
	try:
		emp_filters = {"status": "Active"}
		if comp:
			emp_filters["company"] = comp
		active_employees = frappe.db.count("Employee", filters=emp_filters)

		today = nowdate()
		att_summary = frappe.db.sql(
			"""
			SELECT
				SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
				SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
				SUM(CASE WHEN a.status IN ('On Leave', 'Half Day') THEN 1 ELSE 0 END) as leave_count
			FROM `tabAttendance` a
			LEFT JOIN `tabEmployee` e ON e.name = a.employee
			WHERE a.attendance_date = %(today)s
			  AND a.docstatus < 2
			  AND (%(company)s IS NULL OR e.company = %(company)s OR a.company = %(company)s)
		""",
			{"today": today, "company": comp},
			as_dict=True,
		)

		if att_summary and att_summary[0]:
			present_count = cint(att_summary[0].get("present_count") or 0)
			absent_count = cint(att_summary[0].get("absent_count") or 0)
			on_leave_count = cint(att_summary[0].get("leave_count") or 0)

		if active_employees > 0:
			attendance_pct = flt((present_count / active_employees) * 100, 1)
	except Exception as e:
		frappe.log_error(f"Error fetching attendance summary: {e}", "CEO Dashboard")

	# 2. Task completion stats
	task_labels = []
	task_values = []
	try:
		task_sql = """
			SELECT status, COUNT(name) as count
			FROM `tabTask`
			WHERE docstatus < 2
			GROUP BY status
			ORDER BY count DESC
		"""
		tasks_by_status = frappe.db.sql(task_sql, as_dict=True)
		for row in tasks_by_status:
			status_name = row.status or "Open"
			task_labels.append(status_name)
			task_values.append(cint(row.count))
	except Exception as e:
		frappe.log_error(f"Error fetching task breakdown: {e}", "CEO Dashboard")

	# Default if no tasks found
	if not task_labels:
		task_labels = ["No Tasks"]
		task_values = [0]

	return {
		"active_employees": active_employees,
		"present_count": present_count,
		"absent_count": absent_count,
		"on_leave_count": on_leave_count,
		"attendance_percentage": attendance_pct,
		"task_chart": {
			"labels": task_labels,
			"datasets": [
				{
					"name": _("Tasks"),
					"values": task_values,
				}
			],
		},
	}
