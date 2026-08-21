frappe.ui.form.on("Employee", {
	custom_cnic: function (frm) {
		if (!frm.doc.custom_cnic) return;

		let val = frm.doc.custom_cnic.trim();
		let digits = val.replace(/\D/g, "");

		if (digits.length === 13) {
			let formatted = `${digits.substring(0, 5)}-${digits.substring(5, 12)}-${digits.substring(12, 13)}`;
			if (frm.doc.custom_cnic !== formatted) {
				frm.set_value("custom_cnic", formatted);
			}
		}
	}
});
