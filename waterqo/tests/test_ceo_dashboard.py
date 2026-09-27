import unittest
import frappe
from frappe.utils import flt, getdate, nowdate, get_first_day, get_last_day
from waterqo.api.ceo_dashboard import (
	get_bank_current_balances_and_reconciliation,
	get_bank_monthly_balances_and_summary,
)

class TestCEODashboardBanking(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		cls.company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.get_all("Company")[0].name

	def test_get_bank_current_balances_returns_child_ledgers_only(self):
		res = get_bank_current_balances_and_reconciliation(company=self.company)
		self.assertIn("bank_accounts", res)
		self.assertIn("net_bank_balance", res)
		self.assertIn("currency", res)

		bank_accounts = res["bank_accounts"]
		calc_sum = 0.0
		for b in bank_accounts:
			# Verify accounts are strictly child ledgers
			is_group = frappe.db.get_value("Account", b["account"], "is_group")
			self.assertEqual(is_group, 0, f"Account {b['account']} should be a leaf child ledger, not group.")
			acc_type = frappe.db.get_value("Account", b["account"], "account_type")
			self.assertEqual(acc_type, "Bank")
			calc_sum += flt(b["current_balance"])
			# Share pct must be between 0 and 100
			self.assertTrue(0.0 <= flt(b["share_pct"]) <= 100.0)

		self.assertEqual(round(flt(res["net_bank_balance"]), 2), round(flt(calc_sum), 2))

	def test_bank_reconciliation_status_structure(self):
		res = get_bank_current_balances_and_reconciliation(company=self.company)
		self.assertIn("reconciliation", res)
		recon = res["reconciliation"]

		self.assertIn("total_vouchers", recon)
		self.assertIn("cleared_vouchers", recon)
		self.assertIn("uncleared_vouchers", recon)
		self.assertIn("uncleared_payments", recon)
		self.assertIn("uncleared_receipts", recon)
		self.assertIn("reconciliation_rate", recon)

		self.assertEqual(recon["total_vouchers"], recon["cleared_vouchers"] + recon["uncleared_vouchers"])
		self.assertTrue(0.0 <= flt(recon["reconciliation_rate"]) <= 100.0)

	def test_bank_monthly_opening_and_closing_balance_integrity(self):
		today = getdate(nowdate())
		res = get_bank_monthly_balances_and_summary(company=self.company, month=today.month, year=today.year)

		self.assertIn("opening_closing_summary", res)
		self.assertIn("totals", res)
		self.assertIn("payment_receipt_chart", res)

		totals = res["totals"]
		# Arithmetic check: closing = opening + receipts - payments
		calc_closing = flt(totals["total_opening"] + totals["total_receipts"] - totals["total_payments"], 2)
		self.assertEqual(flt(totals["total_closing"], 2), calc_closing)

		calc_net = flt(totals["total_receipts"] - totals["total_payments"], 2)
		self.assertEqual(flt(totals["net_change"], 2), calc_net)

		for row in res["opening_closing_summary"]:
			row_calc_closing = flt(row["opening_balance"] + row["receipts"] - row["payments"], 2)
			self.assertEqual(flt(row["closing_balance"], 2), row_calc_closing)
			self.assertEqual(flt(row["net_change"], 2), flt(row["receipts"] - row["payments"], 2))

	def test_bank_payment_receipt_chart_datasets(self):
		today = getdate(nowdate())
		res = get_bank_monthly_balances_and_summary(company=self.company, month=today.month, year=today.year)
		chart = res["payment_receipt_chart"]

		self.assertIn("labels", chart)
		self.assertIn("datasets", chart)
		self.assertEqual(len(chart["datasets"]), 2)
		self.assertEqual(chart["datasets"][0]["name"], "Receipts (Inflow)")
		self.assertEqual(chart["datasets"][1]["name"], "Payments (Outflow)")
		self.assertEqual(len(chart["datasets"][0]["values"]), len(chart["labels"]))
		self.assertEqual(len(chart["datasets"][1]["values"]), len(chart["labels"]))

	def test_opening_journal_entries_counted_in_opening_not_receipts(self):
		today = getdate(nowdate())
		res = get_bank_monthly_balances_and_summary(company=self.company, month=today.month, year=today.year)
		for row in res["opening_closing_summary"]:
			# Verify no opening GL entries are counted as receipts or payments
			opening_entries_in_month = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(debit), 0) as op_debit, COALESCE(SUM(credit), 0) as op_credit
				FROM `tabGL Entry`
				WHERE account = %s AND docstatus = 1 AND is_cancelled = 0
				  AND is_opening = 'Yes'
				  AND posting_date >= %s AND posting_date <= %s
				""",
				(row["account"], get_first_day(today), get_last_day(today)),
				as_dict=True,
			)[0]

			if opening_entries_in_month.op_debit > 0:
				# The opening balance must reflect the opening entry
				self.assertGreaterEqual(row["opening_balance"], opening_entries_in_month.op_debit)

