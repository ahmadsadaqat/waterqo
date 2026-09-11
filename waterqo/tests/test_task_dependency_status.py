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

	def test_parent_task_progress_updates_when_child_completed(self):
		parent = frappe.new_doc("Task")
		parent.subject = "Parent Phase"
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

		parent.reload()
		self.assertEqual(parent.progress, 0.0)

		# Complete Child 1 (1 of 2 -> 50%)
		child1.status = "Completed"
		child1.save(ignore_permissions=True)

		parent.reload()
		self.assertEqual(parent.progress, 50.0)
		self.assertEqual(parent.status, "Working")

		# Complete Child 2 (2 of 2 -> 100%)
		child2.status = "Completed"
		child2.save(ignore_permissions=True)

		parent.reload()
		self.assertEqual(parent.progress, 100.0)
		self.assertEqual(parent.status, "Completed")

	def test_parent_task_progress_with_partial_child_progress(self):
		parent = frappe.new_doc("Task")
		parent.subject = "Parent Phase Partial"
		parent.project = self.proj.name
		parent.is_group = 1
		parent.insert(ignore_permissions=True)

		child1 = frappe.new_doc("Task")
		child1.subject = "Child Part 1"
		child1.project = self.proj.name
		child1.parent_task = parent.name
		child1.progress = 40.0
		child1.status = "Working"
		child1.insert(ignore_permissions=True)

		parent.reload()
		# Only child1 exists so far -> 40%
		self.assertEqual(parent.progress, 40.0)

		child2 = frappe.new_doc("Task")
		child2.subject = "Child Part 2"
		child2.project = self.proj.name
		child2.parent_task = parent.name
		child2.progress = 80.0
		child2.status = "Working"
		child2.insert(ignore_permissions=True)

		parent.reload()
		# (40 + 80) / 2 = 60%
		self.assertEqual(parent.progress, 60.0)
		self.assertEqual(parent.status, "Working")

	def test_parent_task_progress_weighted(self):
		parent = frappe.new_doc("Task")
		parent.subject = "Parent Weighted"
		parent.project = self.proj.name
		parent.is_group = 1
		parent.insert(ignore_permissions=True)

		child1 = frappe.new_doc("Task")
		child1.subject = "Child Weighted 1"
		child1.project = self.proj.name
		child1.parent_task = parent.name
		child1.task_weight = 1.0
		child1.insert(ignore_permissions=True)

		child2 = frappe.new_doc("Task")
		child2.subject = "Child Weighted 2"
		child2.project = self.proj.name
		child2.parent_task = parent.name
		child2.task_weight = 3.0
		child2.insert(ignore_permissions=True)

		# Complete Child 1 (weight 1 of 4 = 25%)
		child1.status = "Completed"
		child1.save(ignore_permissions=True)

		parent.reload()
		self.assertEqual(parent.progress, 25.0)

	def test_parent_task_progress_on_child_deletion(self):
		parent = frappe.new_doc("Task")
		parent.subject = "Parent Deletion Test"
		parent.project = self.proj.name
		parent.is_group = 1
		parent.insert(ignore_permissions=True)

		child1 = frappe.new_doc("Task")
		child1.subject = "Child Del 1"
		child1.project = self.proj.name
		child1.parent_task = parent.name
		child1.status = "Completed"
		child1.insert(ignore_permissions=True)

		child2 = frappe.new_doc("Task")
		child2.subject = "Child Del 2"
		child2.project = self.proj.name
		child2.parent_task = parent.name
		child2.status = "Open"
		child2.insert(ignore_permissions=True)

		parent.reload()
		self.assertEqual(parent.progress, 50.0)

		# Delete child2 -> remaining child1 is Completed -> parent becomes 100% and Completed
		frappe.delete_doc("Task", child2.name, force=True, ignore_permissions=True)

		parent.reload()
		self.assertEqual(parent.progress, 100.0)
		self.assertEqual(parent.status, "Completed")

	def test_multi_level_progress_rollup(self):
		# Grandparent -> Parent -> Child1 & Child2
		grandparent = frappe.new_doc("Task")
		grandparent.subject = "Grandparent Phase"
		grandparent.project = self.proj.name
		grandparent.is_group = 1
		grandparent.insert(ignore_permissions=True)

		parent = frappe.new_doc("Task")
		parent.subject = "Parent Milestone"
		parent.project = self.proj.name
		parent.parent_task = grandparent.name
		parent.is_group = 1
		parent.insert(ignore_permissions=True)

		child1 = frappe.new_doc("Task")
		child1.subject = "Subtask 1"
		child1.project = self.proj.name
		child1.parent_task = parent.name
		child1.insert(ignore_permissions=True)

		child2 = frappe.new_doc("Task")
		child2.subject = "Subtask 2"
		child2.project = self.proj.name
		child2.parent_task = parent.name
		child2.insert(ignore_permissions=True)

		# Complete Subtask 1 (Parent has 2 children -> 50%)
		# Grandparent has 1 child (Parent at 50%) -> Grandparent = 50%
		child1.status = "Completed"
		child1.save(ignore_permissions=True)

		parent.reload()
		grandparent.reload()
		self.assertEqual(parent.progress, 50.0)
		self.assertEqual(grandparent.progress, 50.0)

		# Complete Subtask 2 -> Parent = 100%, Grandparent = 100%
		child2.status = "Completed"
		child2.save(ignore_permissions=True)

		parent.reload()
		grandparent.reload()
		self.assertEqual(parent.progress, 100.0)
		self.assertEqual(parent.status, "Completed")
		self.assertEqual(grandparent.progress, 100.0)
		self.assertEqual(grandparent.status, "Completed")

	def test_project_percent_complete_with_parent_and_child_tasks(self):
		"""
		Tests that in a project with 1 parent task and 3 child tasks (weights 10, 20, 70):
		- Parent task container is excluded from project task count.
		- When 70% child task completes, parent progress is 70% and project percent_complete is 33.33% (not 25%).
		- When 20% child task completes, project percent_complete is 66.67%.
		- When 10% child task completes, parent is 100% and project percent_complete is 100.0% (Completed).
		"""
		parent = frappe.new_doc("Task")
		parent.subject = "Parent Phase"
		parent.project = self.proj.name
		parent.is_group = 1
		parent.insert(ignore_permissions=True)

		child1 = frappe.new_doc("Task")
		child1.subject = "Child 10"
		child1.project = self.proj.name
		child1.parent_task = parent.name
		child1.task_weight = 10.0
		child1.insert(ignore_permissions=True)

		child2 = frappe.new_doc("Task")
		child2.subject = "Child 20"
		child2.project = self.proj.name
		child2.parent_task = parent.name
		child2.task_weight = 20.0
		child2.insert(ignore_permissions=True)

		child3 = frappe.new_doc("Task")
		child3.subject = "Child 70"
		child3.project = self.proj.name
		child3.parent_task = parent.name
		child3.task_weight = 70.0
		child3.insert(ignore_permissions=True)

		self.proj.reload()
		self.assertEqual(self.proj.percent_complete, 0.0)

		# 1. Complete child3 (70% weight)
		child3.status = "Completed"
		child3.save(ignore_permissions=True)

		parent.reload()
		self.proj.reload()
		self.assertEqual(parent.progress, 70.0)
		self.assertEqual(parent.status, "Working")
		# 1 out of 3 leaf tasks completed = 33.33% (NOT 25%)
		self.assertEqual(self.proj.percent_complete, 33.33)
		self.assertEqual(self.proj.status, "Open")

		# 2. Complete child2 (20% weight)
		child2.status = "Completed"
		child2.save(ignore_permissions=True)

		parent.reload()
		self.proj.reload()
		self.assertEqual(parent.progress, 90.0)
		self.assertEqual(parent.status, "Working")
		# 2 out of 3 leaf tasks completed = 66.67% (NOT 50%)
		self.assertEqual(self.proj.percent_complete, 66.67)

		# 3. Complete child1 (10% weight)
		child1.status = "Completed"
		child1.save(ignore_permissions=True)

		parent.reload()
		self.proj.reload()
		self.assertEqual(parent.progress, 100.0)
		self.assertEqual(parent.status, "Completed")
		# 3 out of 3 leaf tasks completed = 100.0%
		self.assertEqual(self.proj.percent_complete, 100.0)
		self.assertEqual(self.proj.status, "Completed")

		# 4. Reopen child1 -> rolls back to 66.67% and Open
		child1.status = "Open"
		child1.progress = 0.0
		child1.save(ignore_permissions=True)

		parent.reload()
		self.proj.reload()
		self.assertEqual(parent.progress, 90.0)
		self.assertEqual(parent.status, "Working")
		self.assertEqual(self.proj.percent_complete, 66.67)
		self.assertEqual(self.proj.status, "Open")

	def test_project_percent_complete_with_task_weight_method(self):
		"""
		Tests that when project percent_complete_method is 'Task Weight':
		- Progress is weighted solely across leaf tasks.
		- Completing the 70% leaf task produces 70.0% project progress.
		"""
		proj = frappe.new_doc("Project")
		proj.project_name = "_Test Weighted Proj " + random_string(4)
		proj.company = self.company
		proj.percent_complete_method = "Task Weight"
		proj.insert(ignore_permissions=True)

		parent = frappe.new_doc("Task")
		parent.subject = "Parent Group"
		parent.project = proj.name
		parent.is_group = 1
		parent.insert(ignore_permissions=True)

		child1 = frappe.new_doc("Task")
		child1.subject = "Leaf 10"
		child1.project = proj.name
		child1.parent_task = parent.name
		child1.task_weight = 10.0
		child1.insert(ignore_permissions=True)

		child2 = frappe.new_doc("Task")
		child2.subject = "Leaf 20"
		child2.project = proj.name
		child2.parent_task = parent.name
		child2.task_weight = 20.0
		child2.insert(ignore_permissions=True)

		child3 = frappe.new_doc("Task")
		child3.subject = "Leaf 70"
		child3.project = proj.name
		child3.parent_task = parent.name
		child3.task_weight = 70.0
		child3.insert(ignore_permissions=True)

		# Complete Leaf 70
		child3.status = "Completed"
		child3.save(ignore_permissions=True)

		proj.reload()
		self.assertEqual(proj.percent_complete, 70.0)

		# Complete Leaf 20
		child2.status = "Completed"
		child2.save(ignore_permissions=True)

		proj.reload()
		self.assertEqual(proj.percent_complete, 90.0)

		# Complete Leaf 10
		child1.status = "Completed"
		child1.save(ignore_permissions=True)

		proj.reload()
		self.assertEqual(proj.percent_complete, 100.0)
		self.assertEqual(proj.status, "Completed")

	def tearDown(self):
		frappe.db.rollback()

