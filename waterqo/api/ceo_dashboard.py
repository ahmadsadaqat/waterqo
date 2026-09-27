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
def get_project_portfolio_status(company=None, limit=100):
	"""
	Fetch top active projects with:
	- name, project_name, percent_complete, status, expected_end_date
	- budget vs actual: linked Sales Invoice totals (billed revenue) vs linked Purchase Invoice + Stock Entry costs
	"""
	_check_dashboard_permissions()
	comp = _get_active_company(company)
	max_limit = cint(limit) if limit else 100

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
		LIMIT %(limit)s
	""",
		{"company": comp, "limit": max_limit},
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

		# Actual Cost from Opening Expense and qualifying transactions (Material Issue, Journal Entry, Payment Entry, Purchase Invoice, etc.)
		from waterqo.budget_control.utils import get_project_actual_cost
		actual_cost_gle = get_project_actual_cost(proj_id)

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


@frappe.whitelist()
def get_bank_current_balances_and_reconciliation(company=None):
	"""
	Returns:
	1. Bank-wise current balance: list of bank child/final ledgers with balances, currency, company, share %.
	2. Bank reconciliation status: cleared vs uncleared counts & amounts from Payment Entry & Journal Entry,
	   plus Bank Transaction reconciliation summary if present.
	"""
	_check_dashboard_permissions()
	comp = _get_active_company(company)

	# 1. Fetch all Bank Child / Final Ledgers
	bank_accounts = frappe.db.sql(
		"""
		SELECT
			acc.name as account,
			acc.account_name,
			acc.account_currency,
			acc.company,
			acc.parent_account,
			COALESCE(SUM(gle.debit - gle.credit), 0) as current_balance,
			COALESCE(SUM(gle.debit), 0) as total_debit,
			COALESCE(SUM(gle.credit), 0) as total_credit
		FROM `tabAccount` acc
		LEFT JOIN `tabGL Entry` gle ON gle.account = acc.name
			AND gle.docstatus = 1
			AND gle.is_cancelled = 0
		WHERE acc.account_type = 'Bank'
		  AND acc.is_group = 0
		  AND (%(company)s IS NULL OR acc.company = %(company)s)
		GROUP BY acc.name, acc.account_name, acc.account_currency, acc.company, acc.parent_account
		ORDER BY current_balance DESC, acc.name ASC
	""",
		{"company": comp},
		as_dict=True,
	)

	total_positive_balance = sum(flt(b.current_balance) for b in bank_accounts if flt(b.current_balance) > 0)
	net_bank_balance = sum(flt(b.current_balance) for b in bank_accounts)

	# Fetch linked Bank Account doctype records if any exist
	bank_meta = {}
	if frappe.db.table_exists("Bank Account"):
		acc_names = [b.account for b in bank_accounts]
		if acc_names:
			ba_records = frappe.db.get_all(
				"Bank Account",
				filters={"account": ["in", acc_names]},
				fields=["name", "bank", "account", "bank_account_no", "is_company_account"],
			)
			for ba in ba_records:
				bank_meta[ba.account] = ba

	for b in bank_accounts:
		b.current_balance = flt(b.current_balance, 2)
		b.total_debit = flt(b.total_debit, 2)
		b.total_credit = flt(b.total_credit, 2)
		b.share_pct = (
			flt((b.current_balance / total_positive_balance * 100), 1)
			if total_positive_balance > 0 and b.current_balance > 0
			else 0.0
		)
		b_extra = bank_meta.get(b.account)
		b.bank_name = b_extra.bank if b_extra and b_extra.bank else b.account_name
		b.bank_account_no = b_extra.bank_account_no if b_extra and b_extra.bank_account_no else ""

	# 2. Bank Reconciliation Status
	acc_tuple = tuple(b.account for b in bank_accounts) if bank_accounts else ("",)

	# A. Payment Entry clearance
	pe_stats = frappe.db.sql(
		"""
		SELECT
			COUNT(name) as total_count,
			SUM(CASE WHEN clearance_date IS NOT NULL THEN 1 ELSE 0 END) as cleared_count,
			SUM(CASE WHEN clearance_date IS NULL THEN 1 ELSE 0 END) as uncleared_count,
			SUM(CASE WHEN clearance_date IS NOT NULL THEN base_paid_amount ELSE 0 END) as cleared_paid,
			SUM(CASE WHEN clearance_date IS NOT NULL THEN base_received_amount ELSE 0 END) as cleared_received,
			SUM(CASE WHEN clearance_date IS NULL AND paid_from IN %(accounts)s THEN base_paid_amount ELSE 0 END) as uncleared_payments,
			SUM(CASE WHEN clearance_date IS NULL AND paid_to IN %(accounts)s THEN base_received_amount ELSE 0 END) as uncleared_receipts
		FROM `tabPayment Entry`
		WHERE docstatus = 1
		  AND (paid_from IN %(accounts)s OR paid_to IN %(accounts)s)
		  AND (%(company)s IS NULL OR company = %(company)s)
	""",
		{"accounts": acc_tuple, "company": comp},
		as_dict=True,
	)
	pe_row = pe_stats[0] if pe_stats else {}

	# B. Journal Entry clearance
	je_stats = frappe.db.sql(
		"""
		SELECT
			COUNT(DISTINCT jv.name) as total_count,
			SUM(CASE WHEN jv.clearance_date IS NOT NULL THEN 1 ELSE 0 END) as cleared_count,
			SUM(CASE WHEN jv.clearance_date IS NULL THEN 1 ELSE 0 END) as uncleared_count,
			SUM(CASE WHEN jv.clearance_date IS NULL AND jvd.credit > 0 THEN jvd.credit ELSE 0 END) as uncleared_payments,
			SUM(CASE WHEN jv.clearance_date IS NULL AND jvd.debit > 0 THEN jvd.debit ELSE 0 END) as uncleared_receipts
		FROM `tabJournal Entry Account` jvd
		INNER JOIN `tabJournal Entry` jv ON jv.name = jvd.parent
		WHERE jv.docstatus = 1
		  AND jvd.account IN %(accounts)s
		  AND (%(company)s IS NULL OR jv.company = %(company)s)
	""",
		{"accounts": acc_tuple, "company": comp},
		as_dict=True,
	)
	je_row = je_stats[0] if je_stats else {}

	total_vouchers = cint(pe_row.get("total_count") or 0) + cint(je_row.get("total_count") or 0)
	cleared_vouchers = cint(pe_row.get("cleared_count") or 0) + cint(je_row.get("cleared_count") or 0)
	uncleared_vouchers = cint(pe_row.get("uncleared_count") or 0) + cint(je_row.get("uncleared_count") or 0)

	uncleared_payments = flt(pe_row.get("uncleared_payments") or 0) + flt(je_row.get("uncleared_payments") or 0)
	uncleared_receipts = flt(pe_row.get("uncleared_receipts") or 0) + flt(je_row.get("uncleared_receipts") or 0)

	reconciliation_rate = (
		flt((cleared_vouchers / total_vouchers * 100), 1) if total_vouchers > 0 else 100.0
	)

	# C. Bank Transaction Status (if any)
	bt_distribution = []
	if frappe.db.table_exists("Bank Transaction"):
		bt_rows = frappe.db.sql(
			"""
			SELECT
				bt.status,
				COUNT(bt.name) as count,
				COALESCE(SUM(bt.unallocated_amount), 0) as unallocated_amount,
				COALESCE(SUM(bt.allocated_amount), 0) as allocated_amount
			FROM `tabBank Transaction` bt
			LEFT JOIN `tabBank Account` ba ON ba.name = bt.bank_account
			WHERE bt.docstatus < 2
			  AND (%(company)s IS NULL OR bt.company = %(company)s)
			  AND (ba.account IN %(accounts)s OR bt.bank_account IS NULL)
			GROUP BY bt.status
		""",
			{"accounts": acc_tuple, "company": comp},
			as_dict=True,
		)
		bt_distribution = [
			{
				"status": r.status or "Unreconciled",
				"count": cint(r.count),
				"unallocated_amount": flt(r.unallocated_amount, 2),
				"allocated_amount": flt(r.allocated_amount, 2),
			}
			for r in bt_rows
		]

	currency = "PKR"
	if comp:
		currency = frappe.get_cached_value("Company", comp, "default_currency") or "PKR"

	return {
		"company": comp,
		"currency": currency,
		"net_bank_balance": net_bank_balance,
		"bank_accounts": bank_accounts,
		"reconciliation": {
			"total_vouchers": total_vouchers,
			"cleared_vouchers": cleared_vouchers,
			"uncleared_vouchers": uncleared_vouchers,
			"uncleared_payments": uncleared_payments,
			"uncleared_receipts": uncleared_receipts,
			"reconciliation_rate": reconciliation_rate,
			"bank_transactions": bt_distribution,
		},
	}


@frappe.whitelist()
def get_bank_monthly_balances_and_summary(company=None, month=None, year=None):
	"""
	Returns:
	1. Opening and Closing Balances per bank child ledger for the specified/current month.
	2. Payment and Receipt summary per bank child ledger with chart datasets.
	"""
	_check_dashboard_permissions()
	comp = _get_active_company(company)

	today = getdate(nowdate())
	y = cint(year) if year else today.year
	m = cint(month) if month else today.month
	target_date = getdate(f"{y}-{m:02d}-01")
	m_start = get_first_day(target_date)
	m_end = get_last_day(target_date)
	month_label = target_date.strftime("%B %Y")

	# Fetch Bank Child Ledgers
	bank_accounts = frappe.db.sql(
		"""
		SELECT name as account, account_name, account_currency, company, parent_account
		FROM `tabAccount`
		WHERE account_type = 'Bank'
		  AND is_group = 0
		  AND (%(company)s IS NULL OR company = %(company)s)
		ORDER BY account_name ASC
	""",
		{"company": comp},
		as_dict=True,
	)

	if not bank_accounts:
		return {
			"company": comp,
			"month_label": month_label,
			"opening_closing_summary": [],
			"payment_receipt_chart": {"labels": [], "datasets": []},
			"totals": {
				"total_opening": 0.0,
				"total_receipts": 0.0,
				"total_payments": 0.0,
				"net_change": 0.0,
				"total_closing": 0.0,
			},
		}

	# 1. Opening Balances (posting_date < m_start OR is_opening = 'Yes' on or before m_end)
	opening_sql = """
		SELECT gle.account, COALESCE(SUM(gle.debit - gle.credit), 0) as opening_balance
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON acc.name = gle.account
		WHERE gle.docstatus = 1 AND gle.is_cancelled = 0
		  AND acc.account_type = 'Bank' AND acc.is_group = 0
		  AND (
		      gle.posting_date < %(start)s
		      OR (gle.posting_date <= %(end)s AND gle.is_opening = 'Yes')
		  )
		  AND (%(company)s IS NULL OR gle.company = %(company)s)
		GROUP BY gle.account
	"""
	opening_map = {
		r.account: flt(r.opening_balance, 2)
		for r in frappe.db.sql(opening_sql, {"start": m_start, "end": m_end, "company": comp}, as_dict=True)
	}

	# 2. Monthly Activities (posting_date BETWEEN m_start AND m_end, excluding opening entries)
	activity_sql = """
		SELECT
			gle.account,
			COALESCE(SUM(gle.debit), 0) as receipts,
			COALESCE(SUM(gle.credit), 0) as payments,
			COUNT(CASE WHEN gle.debit > 0 THEN 1 END) as receipt_count,
			COUNT(CASE WHEN gle.credit > 0 THEN 1 END) as payment_count
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON acc.name = gle.account
		WHERE gle.docstatus = 1 AND gle.is_cancelled = 0
		  AND acc.account_type = 'Bank' AND acc.is_group = 0
		  AND gle.posting_date >= %(start)s AND gle.posting_date <= %(end)s
		  AND (gle.is_opening IS NULL OR gle.is_opening != 'Yes')
		  AND (%(company)s IS NULL OR gle.company = %(company)s)
		GROUP BY gle.account
	"""
	activity_map = {
		r.account: r
		for r in frappe.db.sql(activity_sql, {"start": m_start, "end": m_end, "company": comp}, as_dict=True)
	}

	summary_rows = []
	chart_labels = []
	chart_receipts = []
	chart_payments = []

	total_opening = 0.0
	total_receipts = 0.0
	total_payments = 0.0
	total_closing = 0.0

	for b in bank_accounts:
		acc_id = b.account
		op_bal = opening_map.get(acc_id, 0.0)
		act = activity_map.get(acc_id, {})
		receipts = flt(act.get("receipts", 0.0), 2)
		payments = flt(act.get("payments", 0.0), 2)
		rec_count = cint(act.get("receipt_count", 0))
		pay_count = cint(act.get("payment_count", 0))
		net_change = flt(receipts - payments, 2)
		cl_bal = flt(op_bal + net_change, 2)

		total_opening += op_bal
		total_receipts += receipts
		total_payments += payments
		total_closing += cl_bal

		row = {
			"account": acc_id,
			"account_name": b.account_name or acc_id,
			"currency": b.account_currency or "PKR",
			"opening_balance": op_bal,
			"receipts": receipts,
			"payments": payments,
			"receipt_count": rec_count,
			"payment_count": pay_count,
			"net_change": net_change,
			"closing_balance": cl_bal,
		}
		summary_rows.append(row)

		display_name = b.account_name or acc_id.split(" - ")[0]
		chart_labels.append(display_name)
		chart_receipts.append(receipts)
		chart_payments.append(payments)

	payment_receipt_chart = {
		"labels": chart_labels,
		"datasets": [
			{"name": _("Receipts (Inflow)"), "values": chart_receipts},
			{"name": _("Payments (Outflow)"), "values": chart_payments},
		],
	}

	return {
		"company": comp,
		"month_label": month_label,
		"opening_closing_summary": summary_rows,
		"payment_receipt_chart": payment_receipt_chart,
		"totals": {
			"total_opening": flt(total_opening, 2),
			"total_receipts": flt(total_receipts, 2),
			"total_payments": flt(total_payments, 2),
			"net_change": flt(total_receipts - total_payments, 2),
			"total_closing": flt(total_closing, 2),
		},
	}

