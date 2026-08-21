import unittest
import frappe
from frappe.utils import flt, random_string
from waterqo.setup import setup_project_task_budget_control

class TestParentTaskAutoUpdate(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		setup_project_task_budget_control()
		cls.company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.get_all("Company")[0].name

	def setUp(self):
		frappe.db.rollback()
		self.proj = frappe.new_doc("Project")
		self.proj.project_name = "_Test Proj " + random_string(4)
		self.proj.company = self.company
		self.proj.custom_project_budget = 1000000.0
		self.proj.insert(ignore_permissions=True)

	def test_parent_task_budget_auto_calculated_from_children(self):
		# Create Parent Task
		parent = frappe.new_doc("Task")
		parent.subject = "Parent Phase 1"
		parent.project = self.proj.name
		parent.is_group = 1
		parent.insert(ignore_permissions=True)

		self.assertEqual(flt(parent.custom_task_budget), 0.0)

		# Create Child Task 1 = 200,000
		child1 = frappe.new_doc("Task")
		child1.subject = "Subtask 1"
		child1.project = self.proj.name
		child1.parent_task = parent.name
		child1.custom_task_budget = 200000.0
		child1.insert(ignore_permissions=True)

		parent.reload()
		self.assertEqual(flt(parent.custom_task_budget), 200000.0)
		self.assertEqual(flt(parent.custom_remaining_task_budget), 200000.0)

		# Create Child Task 2 = 300,000
		child2 = frappe.new_doc("Task")
		child2.subject = "Subtask 2"
		child2.project = self.proj.name
		child2.parent_task = parent.name
		child2.custom_task_budget = 300000.0
		child2.insert(ignore_permissions=True)

		parent.reload()
		self.assertEqual(flt(parent.custom_task_budget), 500000.0)
		self.assertEqual(flt(parent.custom_remaining_task_budget), 500000.0)

		# Update Child Task 1 to 250,000
		child1.custom_task_budget = 250000.0
		child1.save(ignore_permissions=True)

		parent.reload()
		self.assertEqual(flt(parent.custom_task_budget), 550000.0)
		self.assertEqual(flt(parent.custom_remaining_task_budget), 550000.0)

		# Delete Child Task 2
		frappe.delete_doc("Task", child2.name, force=True, ignore_permissions=True)
		parent.reload()
		self.assertEqual(flt(parent.custom_task_budget), 250000.0)
		self.assertEqual(flt(parent.custom_remaining_task_budget), 250000.0)


	def test_child_task_moved_between_parents(self):
		parent1 = frappe.new_doc("Task")
		parent1.subject = "Parent 1"
		parent1.project = self.proj.name
		parent1.is_group = 1
		parent1.insert(ignore_permissions=True)

		parent2 = frappe.new_doc("Task")
		parent2.subject = "Parent 2"
		parent2.project = self.proj.name
		parent2.is_group = 1
		parent2.insert(ignore_permissions=True)

		child = frappe.new_doc("Task")
		child.subject = "Moving Child"
		child.project = self.proj.name
		child.parent_task = parent1.name
		child.custom_task_budget = 150000.0
		child.insert(ignore_permissions=True)

		parent1.reload()
		parent2.reload()
		self.assertEqual(flt(parent1.custom_task_budget), 150000.0)
		self.assertEqual(flt(parent2.custom_task_budget), 0.0)

		# Move child to parent2
		child.parent_task = parent2.name
		child.save(ignore_permissions=True)

		parent1.reload()
		parent2.reload()
		self.assertEqual(flt(parent1.custom_task_budget), 0.0)
		self.assertEqual(flt(parent2.custom_task_budget), 150000.0)

	def tearDown(self):
		frappe.db.rollback()
