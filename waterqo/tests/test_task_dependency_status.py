import unittest
import frappe
from frappe.utils import random_string
from waterqo.setup import setup_project_task_budget_control

class TestTaskDependencyStatus(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		setup_project_task_budget_control()
		cls.company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.get_all("Company")[0].name

	def setUp(self):
		frappe.db.rollback()
		self.proj = frappe.new_doc("Project")
		self.proj.project_name = "_Test Proj Dep " + random_string(4)
		self.proj.company = self.company
		self.proj.custom_project_budget = 1000000.0
		self.proj.insert(ignore_permissions=True)

	def test_task_auto_completed_when_all_dependencies_completed(self):
		task1 = frappe.new_doc("Task")
		task1.subject = "Prerequisite Task 1"
		task1.project = self.proj.name
		task1.status = "Open"
		task1.insert(ignore_permissions=True)

		task2 = frappe.new_doc("Task")
		task2.subject = "Dependent Task 2"
		task2.project = self.proj.name
		task2.status = "Open"
		task2.append("depends_on", {"task": task1.name})
		task2.insert(ignore_permissions=True)

		self.assertEqual(task2.status, "Open")

		# Complete task1
		task1.status = "Completed"
		task1.save(ignore_permissions=True)

		task2.reload()
		self.assertEqual(task2.status, "Completed")
		self.assertEqual(task2.progress, 100.0)

	def test_task_reopened_when_dependency_reopened(self):
		task1 = frappe.new_doc("Task")
		task1.subject = "Prerequisite Task 1"
		task1.project = self.proj.name
		task1.status = "Open"
		task1.insert(ignore_permissions=True)

		task2 = frappe.new_doc("Task")
		task2.subject = "Dependent Task 2"
		task2.project = self.proj.name
		task2.status = "Open"
		task2.append("depends_on", {"task": task1.name})
		task2.insert(ignore_permissions=True)

		# Complete task1 -> task2 completes
		task1.status = "Completed"
		task1.save(ignore_permissions=True)

		task2.reload()
		self.assertEqual(task2.status, "Completed")

		# Reopen task1
		task1.status = "Open"
		task1.save(ignore_permissions=True)

		task2.reload()
		self.assertIn(task2.status, ("Open", "Working"))

	def test_multi_dependency_auto_completion(self):
		task_a = frappe.new_doc("Task")
		task_a.subject = "Task A"
		task_a.project = self.proj.name
		task_a.status = "Open"
		task_a.insert(ignore_permissions=True)

		task_b = frappe.new_doc("Task")
		task_b.subject = "Task B"
		task_b.project = self.proj.name
		task_b.status = "Open"
		task_b.insert(ignore_permissions=True)

		task_c = frappe.new_doc("Task")
		task_c.subject = "Task C"
		task_c.project = self.proj.name
		task_c.status = "Open"
		task_c.append("depends_on", {"task": task_a.name})
		task_c.append("depends_on", {"task": task_b.name})
		task_c.insert(ignore_permissions=True)

		# Complete only Task A -> Task C must NOT complete
		task_a.status = "Completed"
		task_a.save(ignore_permissions=True)

		task_c.reload()
		self.assertNotEqual(task_c.status, "Completed")

		# Complete Task B -> Task C must auto complete
		task_b.status = "Completed"
		task_b.save(ignore_permissions=True)

		task_c.reload()
		self.assertEqual(task_c.status, "Completed")
		self.assertEqual(task_c.progress, 100.0)

	def test_parent_task_completed_when_all_child_tasks_completed(self):
		parent = frappe.new_doc("Task")
		parent.subject = "Parent Milestone"
		parent.project = self.proj.name
		parent.is_group = 1
		parent.status = "Open"
		parent.insert(ignore_permissions=True)

		child1 = frappe.new_doc("Task")
		child1.subject = "Child 1"
		child1.project = self.proj.name
		child1.parent_task = parent.name
		child1.status = "Open"
		child1.insert(ignore_permissions=True)

		child2 = frappe.new_doc("Task")
		child2.subject = "Child 2"
		child2.project = self.proj.name
		child2.parent_task = parent.name
		child2.status = "Open"
		child2.insert(ignore_permissions=True)

		# Complete Child 1
		child1.status = "Completed"
		child1.save(ignore_permissions=True)

		parent.reload()
		self.assertNotEqual(parent.status, "Completed")

		# Complete Child 2
		child2.status = "Completed"
		child2.save(ignore_permissions=True)

		parent.reload()
		self.assertEqual(parent.status, "Completed")
		self.assertEqual(parent.progress, 100.0)

	def tearDown(self):
		frappe.db.rollback()
