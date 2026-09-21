// Copyright (c) 2026, Nexo ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Stock Entry", {
	refresh(frm) {
		fetch_material_request_employee(frm);
	},
	onload_post_render(frm) {
		fetch_material_request_employee(frm);
	}
});

frappe.ui.form.on("Stock Entry Detail", {
	material_request(frm, cdt, cdn) {
		fetch_material_request_employee(frm);
	},
	items_add(frm) {
		fetch_material_request_employee(frm);
	}
});

function fetch_material_request_employee(frm) {
	if (frm.doc.custom_material_issue_request) return;
	if (!frm.doc.items || !frm.doc.items.length) return;

	let mr = null;
	for (let item of frm.doc.items) {
		if (item.material_request) {
			mr = item.material_request;
			break;
		}
	}

	if (mr) {
		frappe.call({
			method: "waterqo.budget_control.stock_entry.get_material_request_employee",
			args: { material_request: mr },
			callback: function (r) {
				if (r.message && !frm.doc.custom_material_issue_request) {
					frm.set_value("custom_material_issue_request", r.message);
				}
			}
		});
	}
}
