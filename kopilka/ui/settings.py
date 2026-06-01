"""Settings view."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib

from kopilka.storage.json_io import load_config, save_config, set_budget_path


class SettingsView(Gtk.ScrolledWindow):
    def __init__(self, budget, on_change):
        super().__init__()
        self.budget = budget
        self.on_change = on_change

        self.set_hexpand(True)
        self.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)
        self.set_child(clamp)

        page = Adw.PreferencesPage()
        clamp.set_child(page)

        config = load_config()

        # Users group
        users_group = Adw.PreferencesGroup()
        users_group.set_title("Users")
        users_group.set_description("Names shown in income and spending tracking")
        page.add(users_group)

        self.user1_row = Adw.EntryRow()
        self.user1_row.set_title("Your Name")
        self.user1_row.set_text(config.get("user1_name", budget.couple[0] if budget.couple else ""))
        users_group.add(self.user1_row)

        self.user2_row = Adw.EntryRow()
        self.user2_row.set_title("Partner's Name")
        self.user2_row.set_text(config.get("user2_name", budget.couple[1] if len(budget.couple) > 1 else ""))
        users_group.add(self.user2_row)

        save_users_btn = Gtk.Button(label="Save Names")
        save_users_btn.add_css_class("suggested-action")
        save_users_btn.set_halign(Gtk.Align.END)
        save_users_btn.set_tooltip_text("Save display names — updates income and spending records")
        save_users_btn.connect("clicked", self._on_save_users)
        users_group.set_header_suffix(save_users_btn)

        # Sync group
        sync_group = Adw.PreferencesGroup()
        sync_group.set_title("pCloud Sync")
        sync_group.set_description("Sync budget with your partner via pCloud Drive")
        page.add(sync_group)

        self.sync_row = Adw.ActionRow()
        self.sync_row.set_title("Sync Folder")
        self.sync_row.set_subtitle(budget.sync_path or "Not configured")
        choose_btn = Gtk.Button(label="Choose…")
        choose_btn.set_valign(Gtk.Align.CENTER)
        choose_btn.set_tooltip_text("Select a pCloud shared folder — budget.json will be read and written there")
        choose_btn.connect("clicked", self._on_choose_folder)
        self.sync_row.add_suffix(choose_btn)
        sync_group.add(self.sync_row)

        clear_sync_btn = Gtk.Button(label="Clear Sync Path")
        clear_sync_btn.add_css_class("destructive-action")
        clear_sync_btn.set_halign(Gtk.Align.END)
        clear_sync_btn.set_tooltip_text("Stop syncing — budget stays local, pCloud folder is not changed")
        clear_sync_btn.connect("clicked", self._on_clear_sync)
        sync_group.set_header_suffix(clear_sync_btn)

        # Danger group
        danger_group = Adw.PreferencesGroup()
        danger_group.set_title("Data")
        page.add(danger_group)

        clear_spending_btn = Gtk.Button(label="Clear All Spending Entries")
        clear_spending_btn.add_css_class("destructive-action")
        clear_spending_btn.set_halign(Gtk.Align.FILL)
        clear_spending_btn.set_margin_top(8)
        clear_spending_btn.set_tooltip_text("Permanently delete every logged purchase — cannot be undone")
        clear_spending_btn.connect("clicked", self._on_clear_spending)
        danger_group.add(clear_spending_btn)

    def _on_save_users(self, _btn):
        name1 = self.user1_row.get_text().strip()
        name2 = self.user2_row.get_text().strip()
        if not name1 or not name2:
            return

        config = load_config()
        config["user1_name"] = name1
        config["user2_name"] = name2
        save_config(config)

        self.budget.couple = [name1, name2]
        self.on_change()

        toast = Adw.Toast()
        toast.set_title("Names saved")
        self.get_root().add_toast(toast)

    def _on_choose_folder(self, _btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Select pCloud Sync Folder")
        dialog.select_folder(self.get_root(), None, self._folder_chosen)

    def _folder_chosen(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                self.budget.sync_path = path
                self.sync_row.set_subtitle(path)

                config = load_config()
                config["sync_path"] = path
                save_config(config)
                set_budget_path(f"{path}/budget.json")

                self.on_change()

                toast = Adw.Toast()
                toast.set_title(f"Sync folder set to {path}")
                self.get_root().add_toast(toast)
        except GLib.Error:
            pass

    def _on_clear_sync(self, _btn):
        self.budget.sync_path = ""
        self.sync_row.set_subtitle("Not configured")
        self.on_change()

    def _on_clear_spending(self, _btn):
        dlg = Adw.AlertDialog()
        dlg.set_heading("Clear Spending Log?")
        dlg.set_body("This will permanently delete all spending entries. This cannot be undone.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("delete", "Delete All")
        dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("cancel")
        dlg.connect("response", self._on_clear_confirmed)
        dlg.present(self.get_root())

    def _on_clear_confirmed(self, dlg, response):
        if response == "delete":
            self.budget.spending.clear()
            self.on_change()

            toast = Adw.Toast()
            toast.set_title("Spending log cleared")
            self.get_root().add_toast(toast)
