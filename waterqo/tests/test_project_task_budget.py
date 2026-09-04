import unittest
import frappe
from frappe.utils import flt, nowdate, random_string
from waterqo.setup import setup_project_task_budget_control

class TestProjectTaskBudgetControl(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		setup_project_task_budget_control()
		cls.company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.get_all("Company")[0].name
		cls.currency = frappe.db.get_value("Company", cls.company, "default_currency") or "PKR"

		# Setup test warehouses
		cls.source_wh = cls.create_warehouse("_Test Source WH - " + random_string(4))
		cls.target_wh = cls.create_warehouse("_Test Target WH - " + random_string(4))
		cls.expense_account = frappe.db.get_value("Company", cls.company, "stock_adjustment_account") or frappe.get_all("Account", filters={"company": cls.company, "account_type": "Expense"})[0].name

		# Setup test item
		cls.item_code = "_Test Budget Item - " + random_string(4)
		item = frappe.new_doc("Item")
		item.item_code = cls.item_code
		item.item_name = cls.item_code
		item.item_group = "All Item Groups"
		item.is_stock_item = 1
		item.stock_uom = "Nos"
		item.valuation_rate = 1000.0
		item.insert(ignore_permissions=True)

		# Add stock to source warehouse via Material Receipt
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Material Receipt"
		se.stock_entry_type = "Material Receipt"
		se.company = cls.company
		se.append("items", {
			"item_code": cls.item_code,
			"t_warehouse": cls.source_wh,
			"qty": 1000,
			"basic_rate": 1000.0,
			"cost_center": frappe.db.get_value("Company", cls.company, "cost_center") or frappe.get_all("Cost Center", filters={"company": cls.company})[0].name
		})
		se.insert(ignore_permissions=True)
		se.submit()

	@classmethod
	def create_warehouse(cls, wh_name):
		wh = frappe.new_doc("Warehouse")
		wh.warehouse_name = wh_name
		wh.company = cls.company
		wh.insert(ignore_permissions=True)
		return wh.name

	def test_01_project_budget_creation(self):
		"""1 & 2: Create Project with Rs. 1,000,000 budget and verify initial remaining budget."""
		proj = frappe.new_doc("Project")
		proj.project_name = "_Test Project Alpha " + random_string(4)
		proj.company = self.company
		proj.custom_project_budget = 1000000.0
		proj.insert(ignore_permissions=True)

		self.assertEqual(flt(proj.custom_project_budget), 1000000.0)
		self.assertEqual(flt(proj.custom_total_task_budget), 0.0)
		self.assertEqual(flt(proj.custom_unallocated_budget), 1000000.0)
		self.assertEqual(flt(proj.custom_remaining_project_budget), 1000000.0)
		self.assertEqual(flt(proj.custom_actual_project_cost), 0.0)

	def test_02_task_allocation_and_budget_violation(self):
		"""3 to 13: Task allocation, budget violation check, budget increase & reduction limits."""
		proj = frappe.new_doc("Project")
		proj.project_name = "_Test Project Beta " + random_string(4)
		proj.company = self.company
		proj.custom_project_budget = 1000000.0
		proj.insert(ignore_permissions=True)

		# 3. Create Task A = 300,000
		task_a = frappe.new_doc("Task")
		task_a.subject = "Task A"
		task_a.project = proj.name
		task_a.custom_task_budget = 300000.0
		task_a.insert(ignore_permissions=True)

		# 4. Create Task B = 400,000
		task_b = frappe.new_doc("Task")
		task_b.subject = "Task B"
		task_b.project = proj.name
		task_b.custom_task_budget = 400000.0
		task_b.insert(ignore_permissions=True)

		# 5 & 6. Verify total Task Budget = 700,000 and unallocated = 300,000
		proj.reload()
		self.assertEqual(flt(proj.custom_total_task_budget), 700000.0)
		self.assertEqual(flt(proj.custom_unallocated_budget), 300000.0)

		# 7 & 8. Attempt Task C = 400,000 -> Should be rejected
		task_c = frappe.new_doc("Task")
		task_c.subject = "Task C"
		task_c.project = proj.name
		task_c.custom_task_budget = 400000.0
		self.assertRaises(frappe.ValidationError, task_c.insert, ignore_permissions=True)

		# 9. Increase Project Budget to 1,100,000
		proj.custom_project_budget = 1100000.0
		proj.save(ignore_permissions=True)

		# 10 & 11. Create Task C = 400,000 -> Now successful
		task_c.insert(ignore_permissions=True)
		proj.reload()
		self.assertEqual(flt(proj.custom_total_task_budget), 1100000.0)

		# 12 & 13. Attempt to reduce Project Budget below allocated total (e.g. to 900,000) -> Rejected
		proj.custom_project_budget = 900000.0
		self.assertRaises(frappe.ValidationError, proj.save, ignore_permissions=True)

	def test_03_material_issue_actual_cost_and_cancellation(self):
		"""14 to 31: Material Issue actual cost, Project-only issue, Material Transfer, budget overflow & cancellation."""
		proj = frappe.new_doc("Project")
		proj.project_name = "_Test Project Gamma " + random_string(4)
		proj.company = self.company
		proj.custom_project_budget = 1000000.0
		proj.insert(ignore_permissions=True)

		task_a = frappe.new_doc("Task")
		task_a.subject = "Hardware Config"
		task_a.project = proj.name
		task_a.custom_task_budget = 300000.0
		task_a.insert(ignore_permissions=True)

		# 14-17. Issue 100,000 material to Task A
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Material Issue"
		se.stock_entry_type = "Material Issue"
		se.company = self.company
		se.project = proj.name
		se.task = task_a.name
		se.append("items", {
			"item_code": self.item_code,
			"s_warehouse": self.source_wh,
			"qty": 100, # 100 * 1000 = 100,000
			"basic_rate": 1000.0,
			"expense_account": self.expense_account,
			"cost_center": frappe.db.get_value("Company", self.company, "cost_center") or frappe.get_all("Cost Center", filters={"company": self.company})[0].name,
			"project": proj.name,
			"task": task_a.name
		})
		se.insert(ignore_permissions=True)
		se.submit()

		task_a.reload()
		proj.reload()
		self.assertEqual(flt(task_a.custom_actual_task_cost), 100000.0)
		self.assertEqual(flt(task_a.custom_remaining_task_budget), 200000.0)
		self.assertEqual(flt(proj.custom_actual_project_cost), 100000.0)

		# 18-20. Issue 50,000 with Project but no Task
		se_proj_only = frappe.new_doc("Stock Entry")
		se_proj_only.purpose = "Material Issue"
		se_proj_only.stock_entry_type = "Material Issue"
		se_proj_only.company = self.company
		se_proj_only.project = proj.name
		se_proj_only.append("items", {
			"item_code": self.item_code,
			"s_warehouse": self.source_wh,
			"qty": 50, # 50 * 1000 = 50,000
			"basic_rate": 1000.0,
			"expense_account": self.expense_account,
			"cost_center": frappe.db.get_value("Company", self.company, "cost_center") or frappe.get_all("Cost Center", filters={"company": self.company})[0].name,
			"project": proj.name
		})
		se_proj_only.insert(ignore_permissions=True)
		se_proj_only.submit()

		proj.reload()
		task_a.reload()
		self.assertEqual(flt(proj.custom_actual_project_cost), 150000.0)
		self.assertEqual(flt(task_a.custom_actual_task_cost), 100000.0)

		# 21 & 22. Material Transfer between warehouses -> Should not change budget
		se_transfer = frappe.new_doc("Stock Entry")
		se_transfer.purpose = "Material Transfer"
		se_transfer.stock_entry_type = "Material Transfer"
		se_transfer.company = self.company
		se_transfer.project = proj.name
		se_transfer.task = task_a.name
		se_transfer.append("items", {
			"item_code": self.item_code,
			"s_warehouse": self.source_wh,
			"t_warehouse": self.target_wh,
			"qty": 20,
			"basic_rate": 1000.0,
			"cost_center": frappe.db.get_value("Company", self.company, "cost_center") or frappe.get_all("Cost Center", filters={"company": self.company})[0].name,
			"project": proj.name,
			"task": task_a.name
		})
		se_transfer.insert(ignore_permissions=True)
		se_transfer.submit()

		proj.reload()
		task_a.reload()
		self.assertEqual(flt(proj.custom_actual_project_cost), 150000.0)
		self.assertEqual(flt(task_a.custom_actual_task_cost), 100000.0)

		# 23-25. Task with 200,000 remaining (300k - 100k). Attempt issue of 250,000 -> Blocked
		se_exceed = frappe.new_doc("Stock Entry")
		se_exceed.purpose = "Material Issue"
		se_exceed.stock_entry_type = "Material Issue"
		se_exceed.company = self.company
		se_exceed.project = proj.name
		se_exceed.task = task_a.name
		se_exceed.append("items", {
			"item_code": self.item_code,
			"s_warehouse": self.source_wh,
			"qty": 250, # 250 * 1000 = 250,000 > 200,000
			"basic_rate": 1000.0,
			"expense_account": self.expense_account,
			"cost_center": frappe.db.get_value("Company", self.company, "cost_center") or frappe.get_all("Cost Center", filters={"company": self.company})[0].name,
			"project": proj.name,
			"task": task_a.name
		})
		self.assertRaises(frappe.ValidationError, se_exceed.insert, ignore_permissions=True)

		# 26 & 27. Attempt transaction with Project A and Task belonging to Project B -> Rejected
		proj_other = frappe.new_doc("Project")
		proj_other.project_name = "_Test Project Other " + random_string(4)
		proj_other.company = self.company
		proj_other.custom_project_budget = 500000.0
		proj_other.insert(ignore_permissions=True)

		se_mismatch = frappe.new_doc("Stock Entry")
		se_mismatch.purpose = "Material Issue"
		se_mismatch.stock_entry_type = "Material Issue"
		se_mismatch.company = self.company
		se_mismatch.project = proj_other.name # Mismatch! task_a belongs to proj.name
		se_mismatch.task = task_a.name
		se_mismatch.append("items", {
			"item_code": self.item_code,
			"s_warehouse": self.source_wh,
			"qty": 10,
			"basic_rate": 1000.0,
			"expense_account": self.expense_account,
			"cost_center": frappe.db.get_value("Company", self.company, "cost_center") or frappe.get_all("Cost Center", filters={"company": self.company})[0].name,
			"project": proj_other.name,
			"task": task_a.name
		})
		self.assertRaises(frappe.ValidationError, se_mismatch.insert, ignore_permissions=True)

		# 28-31. Cancellation restores budget
		se.cancel()
		proj.reload()
		task_a.reload()
		self.assertEqual(flt(task_a.custom_actual_task_cost), 0.0)
		self.assertEqual(flt(task_a.custom_remaining_task_budget), 300000.0)

	def test_04_parent_task_budget(self):
		"""32 to 35: Parent task budget calculation from children and non-double-counting in Project total."""
		proj = frappe.new_doc("Project")
		proj.project_name = "_Test Project Parent " + random_string(4)
		proj.company = self.company
		proj.custom_project_budget = 1000000.0
		proj.insert(ignore_permissions=True)

		# 32. Create parent Task
		parent_task = frappe.new_doc("Task")
		parent_task.subject = "Implementation Phase"
		parent_task.project = proj.name
		parent_task.is_group = 1
		parent_task.insert(ignore_permissions=True)

		# 33. Create child Tasks with budgets
		child_1 = frappe.new_doc("Task")
		child_1.subject = "Accounting Module"
		child_1.project = proj.name
		child_1.parent_task = parent_task.name
		child_1.custom_task_budget = 200000.0
		child_1.insert(ignore_permissions=True)

		child_2 = frappe.new_doc("Task")
		child_2.subject = "Inventory Module"
		child_2.project = proj.name
		child_2.parent_task = parent_task.name
		child_2.custom_task_budget = 150000.0
		child_2.insert(ignore_permissions=True)

		# 34. Parent budget is calculated from children (200k + 150k = 350k)
		parent_task.reload()
		self.assertEqual(flt(parent_task.custom_task_budget), 350000.0)

		# 35. Project total does not double-count parent + child (Total = 350,000, not 700,000)
		proj.reload()
		self.assertEqual(flt(proj.custom_total_task_budget), 350000.0)
		self.assertEqual(flt(proj.custom_unallocated_budget), 650000.0)

	def test_05_journal_entry_actual_cost(self):
		"""36 to 40: Journal Entry cost incorporation, remaining budget updates, and cancellation restoration."""
		proj = frappe.new_doc("Project")
		proj.project_name = "_Test Project Journal " + random_string(4)
		proj.company = self.company
		proj.custom_project_budget = 500000.0
		proj.insert(ignore_permissions=True)

		task_a = frappe.new_doc("Task")
		task_a.subject = "Journal Task"
		task_a.project = proj.name
		task_a.custom_task_budget = 200000.0
		task_a.insert(ignore_permissions=True)

		credit_account = frappe.db.get_value("Company", self.company, "default_bank_account") or frappe.get_all("Account", filters={"company": self.company, "account_type": "Bank"})[0].name

		je = frappe.new_doc("Journal Entry")
		je.company = self.company
		je.posting_date = nowdate()
		je.append("accounts", {
			"account": self.expense_account,
			"debit_in_account_currency": 50000.0,
			"credit_in_account_currency": 0.0,
			"project": proj.name,
			"task": task_a.name,
			"cost_center": frappe.db.get_value("Company", self.company, "cost_center") or frappe.get_all("Cost Center", filters={"company": self.company})[0].name
		})
		je.append("accounts", {
			"account": credit_account,
			"debit_in_account_currency": 0.0,
			"credit_in_account_currency": 50000.0,
			"cost_center": frappe.db.get_value("Company", self.company, "cost_center") or frappe.get_all("Cost Center", filters={"company": self.company})[0].name
		})
		je.insert(ignore_permissions=True)
		je.submit()

		task_a.reload()
		proj.reload()
		self.assertEqual(flt(task_a.custom_actual_task_cost), 50000.0)
		self.assertEqual(flt(task_a.custom_remaining_task_budget), 150000.0)
		self.assertEqual(flt(proj.custom_actual_project_cost), 50000.0)
		self.assertEqual(flt(proj.custom_remaining_project_budget), 450000.0)

		# Cancel Journal Entry and verify restoration
		je.cancel()
		task_a.reload()
		proj.reload()
		self.assertEqual(flt(task_a.custom_actual_task_cost), 0.0)
		self.assertEqual(flt(task_a.custom_remaining_task_budget), 200000.0)
		self.assertEqual(flt(proj.custom_actual_project_cost), 0.0)
		self.assertEqual(flt(proj.custom_remaining_project_budget), 500000.0)

	def test_06_zero_budget_bypass(self):
		"""41: Unbudgeted / zero budget Project and Task do not block Journal Entry or Stock Entry."""
		proj = frappe.new_doc("Project")
		proj.project_name = "_Test Zero Budget Proj " + random_string(4)
		proj.company = self.company
		proj.custom_project_budget = 0.0
		proj.insert(ignore_permissions=True)

		task = frappe.new_doc("Task")
		task.subject = "Zero Budget Task"
		task.project = proj.name
		task.custom_task_budget = 0.0
		task.insert(ignore_permissions=True)

		# Journal Entry should pass without 'Project Budget Exceeded'
		credit_account = frappe.db.get_value("Company", self.company, "default_bank_account") or frappe.get_all("Account", filters={"company": self.company, "account_type": "Bank"})[0].name
		cost_center = frappe.db.get_value("Company", self.company, "cost_center") or frappe.get_all("Cost Center", filters={"company": self.company})[0].name

		je = frappe.new_doc("Journal Entry")
		je.company = self.company
		je.posting_date = nowdate()
		je.append("accounts", {
			"account": self.expense_account,
			"debit_in_account_currency": 1000.0,
			"credit_in_account_currency": 0.0,
			"project": proj.name,
			"task": task.name,
			"cost_center": cost_center,
		})
		je.append("accounts", {
			"account": credit_account,
			"debit_in_account_currency": 0.0,
			"credit_in_account_currency": 1000.0,
			"cost_center": cost_center,
		})
		je.insert(ignore_permissions=True)
		je.submit()

		# Stock Entry Material Issue should pass without 'Project Budget Exceeded'
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Material Issue"
		se.stock_entry_type = "Material Issue"
		se.company = self.company
		se.append("items", {
			"item_code": self.item_code,
			"s_warehouse": self.source_wh,
			"qty": 1,
			"basic_rate": 1000.0,
			"cost_center": cost_center,
			"project": proj.name,
			"task": task.name,
		})
		se.insert(ignore_permissions=True)
		se.submit()

		# Verify Project can be saved without violation
		proj.reload()
		proj.save(ignore_permissions=True)


