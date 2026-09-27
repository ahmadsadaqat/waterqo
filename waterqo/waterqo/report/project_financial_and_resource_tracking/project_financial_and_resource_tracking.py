import frappe
from frappe import _
from frappe.utils import flt
from waterqo.budget_control.utils import get_project_actual_cost


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	summary = get_report_summary(data)
	chart = get_chart(data)
	return columns, data, None, chart, summary


def get_columns():
	return [
		{
			"fieldname": "project",
			"label": _("Project"),
			"fieldtype": "Link",
			"options": "Project",
			"width": 140,
		},
		{
			"fieldname": "project_name",
			"label": _("Project Name"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "status",
			"label": _("Status"),
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"fieldname": "percent_complete",
			"label": _("% Complete"),
			"fieldtype": "Percent",
			"width": 95,
		},
		{
			"fieldname": "customer",
			"label": _("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
			"width": 140,
		},
		{
			"fieldname": "custom_project_budget",
			"label": _("Budget"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 125,
		},
		{
			"fieldname": "so_amount",
			"label": _("SO Amount"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 125,
		},
		{
			"fieldname": "billed_amount",
			"label": _("Invoiced Amount"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 130,
		},
		{
			"fieldname": "payments_received",
			"label": _("Payments Received"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 135,
		},
		{
			"fieldname": "outstanding_amount",
			"label": _("Outstanding Amount"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 135,
		},
		{
			"fieldname": "material_consumption",
			"label": _("Material Consumption"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 145,
		},
		{
			"fieldname": "actual_expenses",
			"label": _("Actual Expenses"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 135,
		},
		{
			"fieldname": "remaining_budget",
			"label": _("Remaining Budget"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 135,
		},
		{
			"fieldname": "budget_utilization",
			"label": _("Utilization %"),
			"fieldtype": "Percent",
			"width": 100,
		},
		{
			"fieldname": "gross_margin",
			"label": _("Gross Margin"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 125,
		},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Data",
			"hidden": 1,
		},
	]


def get_data(filters):
	conditions = []
	params = {}

	if filters.get("company"):
		conditions.append("p.company = %(company)s")
		params["company"] = filters.get("company")

	if filters.get("project"):
		conditions.append("p.name = %(project)s")
		params["project"] = filters.get("project")

	if filters.get("status") and filters.get("status") != "All":
		conditions.append("p.status = %(status)s")
		params["status"] = filters.get("status")

	if filters.get("customer"):
		conditions.append("p.customer = %(customer)s")
		params["customer"] = filters.get("customer")

	if filters.get("from_date"):
		conditions.append("(p.expected_start_date >= %(from_date)s OR p.actual_start_date >= %(from_date)s)")
		params["from_date"] = filters.get("from_date")

	if filters.get("to_date"):
		conditions.append("(p.expected_end_date <= %(to_date)s OR p.actual_end_date <= %(to_date)s)")
		params["to_date"] = filters.get("to_date")

	where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

	projects = frappe.db.sql(
		f"""
		SELECT
			p.name AS project,
			p.project_name,
			p.status,
			p.percent_complete,
			p.company,
			p.customer,
			p.custom_project_budget,
			p.estimated_costing,
			p.custom_opening_expense
		FROM `tabProject` p
		{where_clause}
		ORDER BY p.creation DESC
		""",
		params,
		as_dict=True,
	)

	if not projects:
		return []

	project_names = [p.project for p in projects]

	# 1. Sales Order Amount (base_net_total)
	so_data = frappe.db.sql(
		"""
		SELECT project, COALESCE(SUM(base_net_total), 0) AS so_amount
		FROM `tabSales Order`
		WHERE docstatus = 1 AND project IN %(projects)s
		GROUP BY project
		""",
		{"projects": project_names},
		as_dict=True,
	)
	so_map = {d.project: flt(d.so_amount) for d in so_data}

	# 2. Sales Invoice Billed Amount and Outstanding Amount (Header level)
	si_data = frappe.db.sql(
		"""
		SELECT
			project,
			COALESCE(SUM(base_grand_total), 0) AS billed_amount,
			COALESCE(SUM(outstanding_amount), 0) AS outstanding_amount
		FROM `tabSales Invoice`
		WHERE docstatus = 1 AND project IN %(projects)s
		GROUP BY project
		""",
		{"projects": project_names},
		as_dict=True,
	)
	si_map = {d.project: d for d in si_data}

	# Also check item-level project billing where header project was not set or differs
	sii_data = frappe.db.sql(
		"""
		SELECT
			sii.project,
			COALESCE(SUM(sii.base_net_amount), 0) AS line_billed
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1
		  AND sii.project IN %(projects)s
		  AND (si.project IS NULL OR si.project != sii.project)
		GROUP BY sii.project
		""",
		{"projects": project_names},
		as_dict=True,
	)
	for d in sii_data:
		curr = si_map.get(d.project, frappe._dict(billed_amount=0.0, outstanding_amount=0.0))
		curr.billed_amount = flt(curr.billed_amount) + flt(d.line_billed)
		si_map[d.project] = curr

	# 3. Direct unallocated customer payments received (Payment Entry where payment_type = 'Receive')
	pe_advances = frappe.db.sql(
		"""
		SELECT
			pe.project,
			COALESCE(SUM(pe.received_amount), 0) AS advance_received
		FROM `tabPayment Entry` pe
		WHERE pe.docstatus = 1
		  AND pe.payment_type = 'Receive'
		  AND pe.project IN %(projects)s
		  AND NOT EXISTS (
			  SELECT 1 FROM `tabPayment Entry Reference` per
			  WHERE per.parent = pe.name AND per.reference_doctype = 'Sales Invoice'
		  )
		GROUP BY pe.project
		""",
		{"projects": project_names},
		as_dict=True,
	)
	advance_map = {d.project: flt(d.advance_received) for d in pe_advances}

	# 4. Material Consumption (Stock Entry Material Issue total incoming value from GL Entry)
	mat_data = frappe.db.sql(
		"""
		SELECT
			gle.project,
			COALESCE(SUM(gle.debit), 0) AS material_cost
		FROM `tabGL Entry` gle
		INNER JOIN `tabStock Entry` se ON se.name = gle.voucher_no AND gle.voucher_type = 'Stock Entry'
		WHERE gle.docstatus = 1
		  AND gle.is_cancelled = 0
		  AND gle.debit > 0
		  AND se.purpose = 'Material Issue'
		  AND gle.project IN %(projects)s
		GROUP BY gle.project
		""",
		{"projects": project_names},
		as_dict=True,
	)
	mat_map = {d.project: flt(d.material_cost) for d in mat_data}

	# Company Currency Map cache
	companies = list(set(p.company for p in projects if p.company))
	currency_map = {}
	if companies:
		for c in frappe.db.get_all("Company", filters={"name": ["in", companies]}, fields=["name", "default_currency"]):
			currency_map[c.name] = c.default_currency or "PKR"

	result = []
	for p in projects:
		comp_currency = currency_map.get(p.company) or frappe.db.get_default("currency") or "PKR"
		budget = flt(p.custom_project_budget) if flt(p.custom_project_budget) > 0 else flt(p.estimated_costing)

		so_amt = flt(so_map.get(p.project, 0.0), 2)
		si_info = si_map.get(p.project, {})
		billed = flt(si_info.get("billed_amount", 0.0), 2)
		outstanding = flt(si_info.get("outstanding_amount", 0.0), 2)

		# Customer payments received against invoices plus direct advances
		inv_payments = max(billed - outstanding, 0.0)
		adv_payments = flt(advance_map.get(p.project, 0.0), 2)
		payments_received = flt(inv_payments + adv_payments, 2)

		mat_consumption = flt(mat_map.get(p.project, 0.0), 2)

		# Comprehensive actual expenses (Material Issue, Journal Entry, Payment Entry Pay, Purchase Invoice, Expense Claim, etc.)
		actual_expenses = flt(get_project_actual_cost(p.project, opening_expense=flt(p.custom_opening_expense)), 2)

		remaining_budget = flt(budget - actual_expenses, 2)
		utilization = flt((actual_expenses / budget * 100.0), 1) if budget > 0 else 0.0

		# Gross margin: Revenue (Invoiced, or SO if uninvoiced) minus Actual Expenses
		effective_revenue = billed if billed > 0 else so_amt
		gross_margin = flt(effective_revenue - actual_expenses, 2)

		result.append(
			{
				"project": p.project,
				"project_name": p.project_name or p.project,
				"status": p.status,
				"percent_complete": flt(p.percent_complete, 1),
				"customer": p.customer,
				"custom_project_budget": budget,
				"so_amount": so_amt,
				"billed_amount": billed,
				"payments_received": payments_received,
				"outstanding_amount": outstanding,
				"material_consumption": mat_consumption,
				"actual_expenses": actual_expenses,
				"remaining_budget": remaining_budget,
				"budget_utilization": utilization,
				"gross_margin": gross_margin,
				"currency": comp_currency,
			}
		)

	return result


def get_report_summary(data):
	if not data:
		return []

	total_budget = sum(flt(d["custom_project_budget"]) for d in data)
	total_billed = sum(flt(d["billed_amount"]) for d in data)
	total_payments = sum(flt(d["payments_received"]) for d in data)
	total_outstanding = sum(flt(d["outstanding_amount"]) for d in data)
	total_actual = sum(flt(d["actual_expenses"]) for d in data)
	total_material = sum(flt(d["material_consumption"]) for d in data)
	total_remaining = sum(flt(d["remaining_budget"]) for d in data)
	overall_margin = sum(flt(d["gross_margin"]) for d in data)

	currency = data[0].get("currency", "PKR") if data else "PKR"

	return [
		{
			"value": total_budget,
			"label": _("Total Budget"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": total_billed,
			"label": _("Total Invoiced"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": total_payments,
			"label": _("Payments Received"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green",
		},
		{
			"value": total_outstanding,
			"label": _("Outstanding Amount"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Orange" if total_outstanding > 0 else "Grey",
		},
		{
			"value": total_actual,
			"label": _("Actual Expenses"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Red" if total_actual > total_budget and total_budget > 0 else "Blue",
		},
		{
			"value": total_material,
			"label": _("Material Consumption"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": total_remaining,
			"label": _("Remaining Budget"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green" if total_remaining >= 0 else "Red",
		},
		{
			"value": overall_margin,
			"label": _("Gross Margin"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green" if overall_margin >= 0 else "Red",
		},
	]


def get_chart(data):
	if not data:
		return None

	top_data = sorted(data, key=lambda x: flt(x["custom_project_budget"]) + flt(x["actual_expenses"]), reverse=True)[:10]

	labels = [d["project_name"][:18] for d in top_data]
	billed_values = [flt(d["billed_amount"]) for d in top_data]
	actual_values = [flt(d["actual_expenses"]) for d in top_data]
	material_values = [flt(d["material_consumption"]) for d in top_data]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Invoiced (Revenue)"), "values": billed_values},
				{"name": _("Actual Expenses"), "values": actual_values},
				{"name": _("Material Consumption"), "values": material_values},
			],
		},
		"type": "bar",
		"colors": ["#10b981", "#ef4444", "#3b82f6"],
	}
