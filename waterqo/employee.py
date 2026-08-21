import re
import frappe
from frappe import _

def validate_employee(doc, method=None):
	"""Validates CNIC format, auto-formats 13-digit numbers, and ensures uniqueness across employees."""
	if not doc.get("custom_cnic"):
		return

	raw_cnic = str(doc.custom_cnic).strip()

	if doc.get("custom_allow_cnic_override"):
		if not doc.get("custom_cnic_override_reason"):
			frappe.throw(
				_("CNIC Override Reason is mandatory when Allow CNIC Override is checked."),
				title=_("CNIC Override Reason Required"),
			)
		return

	# Extract only numeric digits
	digits = re.sub(r"\D", "", raw_cnic)

	if len(digits) != 13:
		frappe.throw(
			_("CNIC Number must be exactly 13 digits (e.g., 12345-1234567-1). Entered: '{0}'").format(raw_cnic),
			title=_("Invalid CNIC Format"),
		)

	# Format as XXXXX-XXXXXXX-X
	formatted_cnic = f"{digits[:5]}-{digits[5:12]}-{digits[12]}"
	doc.custom_cnic = formatted_cnic

	# Duplicate CNIC check
	existing = frappe.db.get_value(
		"Employee",
		{"custom_cnic": formatted_cnic, "name": ["!=", doc.name or ""]},
		["name", "employee_name"],
		as_dict=True,
	)

	if existing:
		emp_label = existing.employee_name or existing.name
		frappe.throw(
			_("CNIC '{0}' is already registered for Employee '{1}' ({2}).").format(
				formatted_cnic, emp_label, existing.name
			),
			title=_("Duplicate CNIC"),
		)
