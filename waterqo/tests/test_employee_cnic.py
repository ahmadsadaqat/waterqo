import unittest
import frappe
from frappe.utils import random_string
from waterqo.setup import setup_custom_fields

class TestEmployeeCNIC(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		setup_custom_fields()
		cls.company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.get_all("Company")[0].name

	def _create_employee(self, first_name=None, cnic=None, **kwargs):
		emp = frappe.new_doc("Employee")
		emp.first_name = first_name or ("_Test Emp " + random_string(4))
		emp.company = self.company
		emp.gender = "Male"
		emp.date_of_birth = "1990-01-01"
		emp.date_of_joining = "2020-01-01"
		if cnic is not None:
			emp.custom_cnic = cnic
		for k, v in kwargs.items():
			setattr(emp, k, v)
		return emp

	def test_valid_cnic_formatting(self):
		emp = self._create_employee(cnic="1234512345671")
		emp.insert(ignore_permissions=True)
		self.assertEqual(emp.custom_cnic, "12345-1234567-1")

	def test_invalid_cnic_length_throws_error(self):
		emp = self._create_employee(cnic="123456789")  # only 9 digits
		self.assertRaises(frappe.ValidationError, emp.insert, ignore_permissions=True)

	def test_duplicate_cnic_throws_error(self):
		unique_cnic = "35201-1234567-1"
		emp1 = self._create_employee(cnic=unique_cnic)
		emp1.insert(ignore_permissions=True)

		emp2 = self._create_employee(cnic=unique_cnic)
		self.assertRaises(frappe.ValidationError, emp2.insert, ignore_permissions=True)

	def test_cnic_override_allows_duplicate_with_reason(self):
		unique_cnic = "35201-9876543-1"
		emp1 = self._create_employee(cnic=unique_cnic)
		emp1.insert(ignore_permissions=True)

		emp2 = self._create_employee(
			cnic=unique_cnic,
			custom_allow_cnic_override=1,
			custom_cnic_override_reason="Approved duplicate for contractor",
		)
		emp2.insert(ignore_permissions=True)
		self.assertEqual(emp2.custom_cnic, unique_cnic)


	def tearDown(self):
		frappe.db.rollback()
