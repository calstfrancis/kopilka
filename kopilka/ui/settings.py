"""Settings view."""

import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib

from kopilka.storage.json_io import load_config, save_config
from kopilka.logic.webdav_sync import PROVIDERS, WebDAVSyncManager, build_from_config


_PROVIDER_KEYS = list(PROVIDERS.keys())
_PROVIDER_LABELS = [PROVIDERS[k]["label"] for k in _PROVIDER_KEYS]


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

        # ── Users ──────────────────────────────────────────────────────────────
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

        # ── WebDAV Sync ────────────────────────────────────────────────────────
        sync_group = Adw.PreferencesGroup()
        sync_group.set_title("WebDAV Sync")
        sync_group.set_description(
            "Sync the budget with your partner via a shared WebDAV folder.\n"
            "Supports pCloud, Nextcloud, Disroot, and any WebDAV server."
        )
        page.add(sync_group)

        # Provider selector
        provider_model = Gtk.StringList()
        for label in _PROVIDER_LABELS:
            provider_model.append(label)

        self._provider_row = Adw.ComboRow()
        self._provider_row.set_title("Provider")
        self._provider_row.set_model(provider_model)
        self._provider_row.set_tooltip_text(
            "Choose your sync provider — URL will be pre-filled for known providers"
        )
        saved_provider = config.get("webdav_provider", "pcloud")
        if saved_provider in _PROVIDER_KEYS:
            self._provider_row.set_selected(_PROVIDER_KEYS.index(saved_provider))
        self._provider_row.connect("notify::selected", self._on_provider_changed)
        sync_group.add(self._provider_row)

        # Server URL
        self._url_row = Adw.EntryRow()
        self._url_row.set_title("Server URL")
        self._url_row.set_tooltip_text(
            "Base WebDAV URL — e.g. https://webdav.pcloud.com  or  "
            "https://cloud.example.com/remote.php/webdav"
        )
        self._url_row.set_text(config.get("webdav_url", PROVIDERS[saved_provider]["url"]))
        sync_group.add(self._url_row)

        # Remote path
        self._path_row = Adw.EntryRow()
        self._path_row.set_title("Remote Path")
        self._path_row.set_tooltip_text(
            "Path to budget.json relative to the WebDAV root — "
            "e.g. Kopilka/budget.json"
        )
        self._path_row.set_text(
            config.get("webdav_remote_path", PROVIDERS[saved_provider]["path_hint"])
        )
        sync_group.add(self._path_row)

        # Username
        self._user_row = Adw.EntryRow()
        self._user_row.set_title("Username")
        self._user_row.set_tooltip_text("Your account email or username for this server")
        self._user_row.set_text(config.get("webdav_username", ""))
        sync_group.add(self._user_row)

        # Password
        self._pass_row = Adw.PasswordEntryRow()
        self._pass_row.set_title("Password")
        self._pass_row.set_tooltip_text(
            "Account password or app-specific password. "
            "Stored locally only — never written to the synced budget file."
        )
        self._pass_row.set_text(config.get("webdav_password", ""))
        sync_group.add(self._pass_row)

        # Buttons row
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(4)

        self._test_spinner = Gtk.Spinner()
        self._test_spinner.set_visible(False)
        btn_box.append(self._test_spinner)

        self._test_status = Gtk.Label()
        self._test_status.add_css_class("dim-label")
        self._test_status.set_visible(False)
        btn_box.append(self._test_status)

        clear_sync_btn = Gtk.Button(label="Clear")
        clear_sync_btn.add_css_class("destructive-action")
        clear_sync_btn.set_tooltip_text("Remove WebDAV credentials and disable sync")
        clear_sync_btn.connect("clicked", self._on_clear_sync)
        btn_box.append(clear_sync_btn)

        test_btn = Gtk.Button(label="Test Connection")
        test_btn.add_css_class("suggested-action")
        test_btn.set_tooltip_text("Verify credentials by connecting to the server")
        test_btn.connect("clicked", self._on_test_connection)
        btn_box.append(test_btn)

        save_sync_btn = Gtk.Button(label="Save")
        save_sync_btn.set_tooltip_text("Save WebDAV settings")
        save_sync_btn.connect("clicked", self._on_save_sync)
        btn_box.append(save_sync_btn)

        btn_row = Adw.ActionRow()
        btn_row.set_activatable(False)
        btn_row.add_suffix(btn_box)
        sync_group.add(btn_row)

        # ── Dashboard ──────────────────────────────────────────────────────────
        dash_group = Adw.PreferencesGroup()
        dash_group.set_title("Dashboard")
        page.add(dash_group)

        self._bills_spin = Adw.SpinRow.new_with_range(1, 90, 1)
        self._bills_spin.set_title("Upcoming bills look-ahead (days)")
        self._bills_spin.set_subtitle("How many days ahead to show bills in the dashboard")
        self._bills_spin.set_digits(0)
        self._bills_spin.set_value(getattr(budget, "bills_look_ahead_days", 7))
        self._bills_spin.set_tooltip_text(
            "Bills due within this many days appear in the dashboard reminder section."
        )
        self._bills_spin.connect("notify::value", self._on_bills_lookhead_changed)
        dash_group.add(self._bills_spin)

        # ── Danger ────────────────────────────────────────────────────────────
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

    # ── Users ──────────────────────────────────────────────────────────────────

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

    # ── WebDAV ─────────────────────────────────────────────────────────────────

    def _on_provider_changed(self, row, _param):
        idx = row.get_selected()
        key = _PROVIDER_KEYS[idx]
        preset = PROVIDERS[key]
        if preset["url"]:
            self._url_row.set_text(preset["url"])
        if preset["path_hint"] and not self._path_row.get_text():
            self._path_row.set_text(preset["path_hint"])

    def _on_save_sync(self, _btn):
        config = load_config()
        idx = self._provider_row.get_selected()
        config["webdav_provider"]     = _PROVIDER_KEYS[idx]
        config["webdav_url"]          = self._url_row.get_text().strip().rstrip("/")
        config["webdav_remote_path"]  = self._path_row.get_text().strip().lstrip("/")
        config["webdav_username"]     = self._user_row.get_text().strip()
        config["webdav_password"]     = self._pass_row.get_text()
        # Clear cached ETag so next upload doesn't use a stale value
        config.pop("webdav_etag", None)
        save_config(config)

        toast = Adw.Toast()
        toast.set_title("Sync settings saved — uploading…")
        self.get_root().add_toast(toast)

        # Trigger an immediate upload so the folder and file are created now.
        # _webdav_upload_async in AppWindow always reloads config from disk,
        # so it will pick up the credentials we just saved.
        self.on_change()

    def _on_clear_sync(self, _btn):
        config = load_config()
        for key in ("webdav_url", "webdav_remote_path", "webdav_username",
                    "webdav_password", "webdav_provider", "webdav_etag"):
            config.pop(key, None)
        save_config(config)

        self._url_row.set_text("")
        self._path_row.set_text("")
        self._user_row.set_text("")
        self._pass_row.set_text("")
        self._test_status.set_visible(False)

        toast = Adw.Toast()
        toast.set_title("Sync disabled")
        self.get_root().add_toast(toast)

    def _on_test_connection(self, _btn):
        # Build a temporary manager from what's currently in the form
        config = {
            "webdav_url":         self._url_row.get_text().strip().rstrip("/"),
            "webdav_remote_path": self._path_row.get_text().strip().lstrip("/"),
            "webdav_username":    self._user_row.get_text().strip(),
            "webdav_password":    self._pass_row.get_text(),
        }
        mgr = build_from_config(config)

        self._test_spinner.set_visible(True)
        self._test_spinner.start()
        self._test_status.set_visible(False)

        threading.Thread(
            target=self._run_test,
            args=(mgr,),
            daemon=True,
        ).start()

    def _run_test(self, mgr: WebDAVSyncManager):
        ok, msg = mgr.test_connection()
        GLib.idle_add(self._show_test_result, ok, msg)

    def _show_test_result(self, ok: bool, msg: str):
        self._test_spinner.stop()
        self._test_spinner.set_visible(False)
        self._test_status.set_text(msg)
        self._test_status.remove_css_class("success")
        self._test_status.remove_css_class("error")
        self._test_status.add_css_class("success" if ok else "error")
        self._test_status.set_visible(True)
        return GLib.SOURCE_REMOVE

    # ── Dashboard ──────────────────────────────────────────────────────────────

    def _on_bills_lookhead_changed(self, spin, _param):
        self.budget.bills_look_ahead_days = int(spin.get_value())
        self.on_change()

    # ── Danger ────────────────────────────────────────────────────────────────

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
