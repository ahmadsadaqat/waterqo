import frappe
from frappe import _
from frappe.utils import flt, fmt_money


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	summary = get_report_summary(data)
	chart = get_chart(data)
	return columns, data, None, chart, summary


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

def get_columns():
	return [
		{
			"fieldname": "project",
			"label": _("Project"),
			"fieldtype": "Link",
			"options": "Project",
			"width": 170,
		},
		{
			"fieldname": "project_name",
			"label": _("Project Name"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "task",
			"label": _("Task"),
			"fieldtype": "Link",
			"options": "Task",
			"width": 180,
		},
		{
			"fieldname": "posting_date",
			"label": _("Date"),
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"fieldname": "expense_type",
			"label": _("Expense Type"),
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"fieldname": "voucher_type",
			"label": _("Voucher Type"),
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "voucher_no",
			"label": _("Voucher No"),
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 200,
		},
		{
			"fieldname": "party",
			"label": _("Party / Employee"),
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"fieldname": "description",
			"label": _("Description"),
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"fieldname": "amount",
			"label": _("Amount"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 130,
		},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
	]


# ---------------------------------------------------------------------------
# Data Aggregation
# ---------------------------------------------------------------------------

def get_data(filters):
	rows = []

	# ── Lookup helpers ──────────────────────────────────────────────────────
	expense_type_filter = filters.get("expense_type", "All")

	def _want(label):
		return expense_type_filter in ("All", label)

	# ── Fetch projects ──────────────────────────────────────────────────────
	projects = _get_projects(filters)
	if not projects:
		return []

	project_map = {p.name: p for p in projects}
	project_names = list(project_map.keys())

	# ── Opening Expense (from Project custom field) ─────────────────────────
	if _want("Opening Expense"):
		for proj in projects:
			opening = flt(proj.get("custom_opening_expense"))
			if opening:
				rows.append(_row(
					project=proj.name,
					project_name=proj.project_name,
					task=None,
					posting_date=proj.expected_start_date,
					expense_type="Opening Expense",
					voucher_type="Project",
					voucher_no=proj.name,
					party=None,
					description=_("Opening expense recorded on project"),
					amount=opening,
					currency=proj._currency,
				))

	# ── Material Issue (Stock Entry) ────────────────────────────────────────
	if _want("Material Issue"):
		rows.extend(_get_material_issue(filters, project_names, project_map))

	# ── Journal Entry ───────────────────────────────────────────────────────
	if _want("Journal Entry"):
		rows.extend(_get_journal_entries(filters, project_names, project_map))

	# ── Timesheet ───────────────────────────────────────────────────────────
	if _want("Timesheet"):
		rows.extend(_get_timesheets(filters, project_names, project_map))

	# ── Expense Claim ────────────────────────────────────────────────────────
	if _want("Expense Claim"):
		rows.extend(_get_expense_claims(filters, project_names, project_map))

	# ── Purchase Invoice ─────────────────────────────────────────────────────
	if _want("Purchase Invoice"):
		rows.extend(_get_purchase_invoices(filters, project_names, project_map))

	# Sort: project → date → voucher_no
	rows.sort(key=lambda r: (
		r["project"] or "",
		str(r["posting_date"] or ""),
		r["voucher_no"] or "",
	))

	return rows


# ---------------------------------------------------------------------------
# Project list helper
# ---------------------------------------------------------------------------

def _get_projects(filters):
	conditions = ["p.docstatus < 2"]
	params = {}

	if filters.get("company"):
		conditions.append("p.company = %(company)s")
		params["company"] = filters["company"]

	if filters.get("project"):
		conditions.append("p.name = %(project)s")
		params["project"] = filters["project"]

	if filters.get("status") and filters["status"] != "All":
		conditions.append("p.status = %(status)s")
		params["status"] = filters["status"]

	where = " AND ".join(conditions)
	projects = frappe.db.sql(
		f"""
		SELECT
			p.name,
			p.project_name,
			p.company,
			p.status,
			p.expected_start_date,
			p.estimated_costing,
			p.custom_project_budget,
			p.custom_opening_expense,
			p.total_costing_amount,
			p.total_expense_claim,
			p.total_purchase_cost,
			p.total_consumed_material_cost
		FROM `tabProject` p
		WHERE {where}
		ORDER BY p.name
		""",
		params,
		as_dict=True,
	)

	default_currency = frappe.db.get_default("currency") or "PKR"
	currency_cache = {}
	for p in projects:
		company = p.company
		if company not in currency_cache:
			currency_cache[company] = (
				frappe.db.get_value("Company", company, "default_currency") or default_currency
			)
		p._currency = currency_cache[company]

	return projects


# ---------------------------------------------------------------------------
# Source: Material Issue (Stock Entry)
# ---------------------------------------------------------------------------

def _get_material_issue(filters, project_names, project_map):
	conditions, params = _date_conditions(filters, "se.posting_date")
	params["project_names"] = project_names

	rows_raw = frappe.db.sql(
		f"""
		SELECT
			sed.project,
			sed.task,
			se.name         AS voucher_no,
			se.posting_date,
			sed.item_code,
			sed.item_name,
			(IFNULL(sed.basic_amount, 0))   AS amount,
			se.company
		FROM `tabStock Entry Detail` sed
		INNER JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.docstatus = 1
		  AND se.purpose = 'Material Issue'
		  AND sed.project IN %(project_names)s
		  {conditions}
		ORDER BY se.posting_date, se.name
		""",
		params,
		as_dict=True,
	)

	result = []
	for r in rows_raw:
		proj = project_map.get(r.project) or frappe._dict()
		result.append(_row(
			project=r.project,
			project_name=proj.project_name,
			task=r.task,
			posting_date=r.posting_date,
			expense_type="Material Issue",
			voucher_type="Stock Entry",
			voucher_no=r.voucher_no,
			party=None,
			description=f"{r.item_code or ''} — {r.item_name or ''}",
			amount=flt(r.amount),
			currency=proj._currency,
		))
	return result


# ---------------------------------------------------------------------------
# Source: Journal Entry
# ---------------------------------------------------------------------------

def _get_journal_entries(filters, project_names, project_map):
	conditions, params = _date_conditions(filters, "je.posting_date")
	params["project_names"] = project_names

	rows_raw = frappe.db.sql(
		f"""
		SELECT
			jea.project,
			jea.task,
			je.name              AS voucher_no,
			je.posting_date,
			jea.account,
			jea.party,
			jea.party_type,
			(jea.debit - jea.credit) AS net_debit,
			je.company,
			je.user_remark
		FROM `tabJournal Entry Account` jea
		INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
		WHERE je.docstatus = 1
		  AND jea.project IN %(project_names)s
		  AND (jea.debit - jea.credit) > 0
		  {conditions}
		ORDER BY je.posting_date, je.name
		""",
		params,
		as_dict=True,
	)

	result = []
	for r in rows_raw:
		proj = project_map.get(r.project) or frappe._dict()
		party_label = f"{r.party_type}: {r.party}" if r.party else ""
		description = r.user_remark or r.account or ""
		result.append(_row(
			project=r.project,
			project_name=proj.project_name,
			task=r.task,
			posting_date=r.posting_date,
			expense_type="Journal Entry",
			voucher_type="Journal Entry",
			voucher_no=r.voucher_no,
			party=party_label,
			description=description,
			amount=flt(r.net_debit),
			currency=proj._currency,
		))
	return result


# ---------------------------------------------------------------------------
# Source: Timesheet (costing amount)
# ---------------------------------------------------------------------------

def _get_timesheets(filters, project_names, project_map):
	conditions, params = _date_conditions(filters, "ts.start_date")
	params["project_names"] = project_names

	rows_raw = frappe.db.sql(
		f"""
		SELECT
			tsd.project,
			tsd.task,
			ts.name             AS voucher_no,
			ts.start_date       AS posting_date,
			ts.employee,
			ts.employee_name,
			tsd.hours,
			tsd.base_costing_amount   AS amount,
			ts.company
		FROM `tabTimesheet Detail` tsd
		INNER JOIN `tabTimesheet` ts ON ts.name = tsd.parent
		WHERE ts.docstatus = 1
		  AND tsd.project IN %(project_names)s
		  AND IFNULL(tsd.base_costing_amount, 0) > 0
		  {conditions}
		ORDER BY ts.start_date, ts.name
		""",
		params,
		as_dict=True,
	)

	result = []
	for r in rows_raw:
		proj = project_map.get(r.project) or frappe._dict()
		employee_label = f"{r.employee_name or ''} ({r.employee or ''})".strip(" ()")
		result.append(_row(
			project=r.project,
			project_name=proj.project_name,
			task=r.task,
			posting_date=r.posting_date,
			expense_type="Timesheet",
			voucher_type="Timesheet",
			voucher_no=r.voucher_no,
			party=employee_label,
			description=_("Timesheet costing — {0} hrs").format(flt(r.hours, 2)),
			amount=flt(r.amount),
			currency=proj._currency,
		))
	return result


# ---------------------------------------------------------------------------
# Source: Expense Claim
# ---------------------------------------------------------------------------

def _get_expense_claims(filters, project_names, project_map):
	conditions, params = _date_conditions(filters, "ec.posting_date")
	params["project_names"] = project_names

	rows_raw = frappe.db.sql(
		f"""
		SELECT
			ecd.project,
			ecd.task,
			ec.name              AS voucher_no,
			ec.posting_date,
			ec.employee,
			ec.employee_name,
			ecd.expense_type,
			ecd.expense_date,
			ecd.sanctioned_amount AS amount,
			ec.company
		FROM `tabExpense Claim Detail` ecd
		INNER JOIN `tabExpense Claim` ec ON ec.name = ecd.parent
		WHERE ec.docstatus = 1
		  AND ec.approval_status = 'Approved'
		  AND ecd.project IN %(project_names)s
		  AND IFNULL(ecd.sanctioned_amount, 0) > 0
		  {conditions}
		ORDER BY ec.posting_date, ec.name
		""",
		params,
		as_dict=True,
	)

	result = []
	for r in rows_raw:
		proj = project_map.get(r.project) or frappe._dict()
		employee_label = f"{r.employee_name or ''} ({r.employee or ''})".strip(" ()")
		result.append(_row(
			project=r.project,
			project_name=proj.project_name,
			task=r.task,
			posting_date=r.posting_date or r.expense_date,
			expense_type="Expense Claim",
			voucher_type="Expense Claim",
			voucher_no=r.voucher_no,
			party=employee_label,
			description=r.expense_type or "",
			amount=flt(r.amount),
			currency=proj._currency,
		))
	return result


# ---------------------------------------------------------------------------
# Source: Purchase Invoice
# ---------------------------------------------------------------------------

def _get_purchase_invoices(filters, project_names, project_map):
	conditions, params = _date_conditions(filters, "pi.posting_date")
	params["project_names"] = project_names

	rows_raw = frappe.db.sql(
		f"""
		SELECT
			pii.project,
			pi.name              AS voucher_no,
			pi.posting_date,
			pi.supplier          AS party,
			pi.supplier_name,
			pii.item_code,
			pii.item_name,
			pii.base_net_amount  AS amount,
			pi.company
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
		WHERE pi.docstatus = 1
		  AND pii.project IN %(project_names)s
		  AND IFNULL(pii.base_net_amount, 0) > 0
		  {conditions}
		ORDER BY pi.posting_date, pi.name
		""",
		params,
		as_dict=True,
	)

	result = []
	for r in rows_raw:
		proj = project_map.get(r.project) or frappe._dict()
		supplier_label = f"{r.supplier_name or ''} ({r.party or ''})".strip(" ()")
		result.append(_row(
			project=r.project,
			project_name=proj.project_name,
			task=None,
			posting_date=r.posting_date,
			expense_type="Purchase Invoice",
			voucher_type="Purchase Invoice",
			voucher_no=r.voucher_no,
			party=supplier_label,
			description=f"{r.item_code or ''} — {r.item_name or ''}",
			amount=flt(r.amount),
			currency=proj._currency,
		))
	return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(*, project, project_name, task, posting_date, expense_type,
		 voucher_type, voucher_no, party, description, amount, currency):
	return {
		"project": project,
		"project_name": project_name or "",
		"task": task or "",
		"posting_date": posting_date,
		"expense_type": expense_type,
		"voucher_type": voucher_type,
		"voucher_no": voucher_no,
		"party": party or "",
		"description": description or "",
		"amount": amount,
		"currency": currency or "",
	}


def _date_conditions(filters, date_col):
	"""Returns (extra_sql_condition_string, updated_params_dict)."""
	conditions = ""
	params = {}
	if filters.get("from_date"):
		conditions += f" AND {date_col} >= %(from_date)s"
		params["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions += f" AND {date_col} <= %(to_date)s"
		params["to_date"] = filters["to_date"]
	return conditions, params


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def get_chart(data):
	if not data:
		return None

	type_totals = {}
	for row in data:
		t = row["expense_type"]
		type_totals[t] = type_totals.get(t, 0.0) + flt(row["amount"])

	if not type_totals:
		return None

	labels = list(type_totals.keys())
	values = [type_totals[l] for l in labels]

	return {
		"data": {
			"labels": labels,
			"datasets": [{"name": _("Amount"), "values": values}],
		},
		"type": "pie",
		"colors": ["#5e64ff", "#ffa000", "#2db7f5", "#e53935", "#43a047", "#8e24aa"],
	}


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def get_report_summary(data):
	if not data:
		return []

	total = sum(flt(r["amount"]) for r in data)

	type_totals = {}
	for row in data:
		t = row["expense_type"]
		type_totals[t] = type_totals.get(t, 0.0) + flt(row["amount"])

	summary = [
		{
			"value": total,
			"label": _("Total Project Expenses"),
			"datatype": "Currency",
			"indicator": "Blue",
		},
	]

	indicator_map = {
		"Opening Expense": "Grey",
		"Material Issue": "Orange",
		"Journal Entry": "Purple",
		"Timesheet": "Cyan",
		"Expense Claim": "Yellow",
		"Purchase Invoice": "Red",
	}

	for expense_type, amount in sorted(type_totals.items()):
		summary.append({
			"value": amount,
			"label": _(expense_type),
			"datatype": "Currency",
			"indicator": indicator_map.get(expense_type, "Green"),
		})

	return summary
