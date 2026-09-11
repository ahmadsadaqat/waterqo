frappe.ui.form.on("Task", {
	refresh: function (frm) {
		waterqo_toggle_task_group_fields(frm);
	},
	is_group: function (frm) {
		waterqo_toggle_task_group_fields(frm);
	}
});

function waterqo_toggle_task_group_fields(frm) {
	if (frm.doc.is_group) {
		frm.set_df_property("progress", "read_only", 1);
		frm.set_df_property("custom_task_budget", "read_only", 1);
		frm.set_intro(__("This is a Group Task. Progress and budget are calculated automatically from its child tasks."), "blue");
	} else if (frm.doc.name && !frm.is_new()) {
		frappe.db.count("Task", {
			filters: {
				parent_task: frm.doc.name,
				docstatus: ["<", 2]
			}
		}).then(count => {
			if (count > 0) {
				frm.set_df_property("progress", "read_only", 1);
				frm.set_df_property("custom_task_budget", "read_only", 1);
				frm.set_intro(__("This task has child tasks. Progress and budget are calculated automatically from its child tasks."), "blue");
			} else {
				frm.set_df_property("progress", "read_only", 0);
				frm.set_df_property("custom_task_budget", "read_only", 0);
			}
		});
	} else {
		frm.set_df_property("progress", "read_only", 0);
		frm.set_df_property("custom_task_budget", "read_only", 0);
	}
}
