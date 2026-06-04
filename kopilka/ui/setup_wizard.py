"""First-launch setup wizard."""

import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib

from kopilka.storage.json_io import load_config, save_config
from kopilka.logic.webdav_sync import PROVIDERS, build_from_config


_PROVIDER_KEYS = list(PROVIDERS.keys())
_PROVIDER_LABELS = [PROVIDERS[k]["label"] for k in _PROVIDER_KEYS]


class SetupWizard(Adw.Dialog):
    """First-launch wizard: names + optional WebDAV sync setup."""

    def __init__(self, budget, on_complete):
        super().__init__()
        self.budget = budget
        self.on_complete = on_complete

        self.set_title("Welcome to Kopilka")
        self.set_content_width(520)
        self.set_content_height(680)
        self.set_can_close(False)

        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        toolbar_view.add_top_bar(header)

        done_btn = Gtk.Button(label="Get Started")
        done_btn.add_css_class("suggested-action")
        done_btn.connect("clicked", self._on_done)
        header.pack_end(done_btn)

        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        toolbar_view.set_content(outer_box)

        banner = Adw.Banner()
        banner.set_title("Set up your shared budget in seconds")
        banner.set_revealed(True)
        banner.set_use_markup(False)
        outer_box.append(banner)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        outer_box.append(scroll)

        page = Adw.PreferencesPage()
        scroll.set_child(page)

        # ── Who's using it ─────────────────────────────────────────────────────
        users_group = Adw.PreferencesGroup()
        users_group.set_title("Who's using Kopilka?")
        users_group.set_description("Enter both names — you can change these later in Settings")
        page.add(users_group)

        self.user1_row = Adw.EntryRow()
        self.user1_row.set_title("Your Name")
        users_group.add(self.user1_row)

        self.user2_row = Adw.EntryRow()
        self.user2_row.set_title("Partner's Name")
        users_group.add(self.user2_row)

        config = load_config()
        if config.get("user1_name"):
            self.user1_row.set_text(config["user1_name"])
        if config.get("user2_name"):
            self.user2_row.set_text(config["user2_name"])

        # ── Sync setup ─────────────────────────────────────────────────────────
        sync_group = Adw.PreferencesGroup()
        sync_group.set_title("Sync with your partner (optional)")
        sync_group.set_description(
            "Share the budget over WebDAV — supports pCloud, Nextcloud, Disroot, "
            "and any WebDAV server. You can set this up later in Settings."
        )
        page.add(sync_group)

        skip_row = Adw.SwitchRow()
        skip_row.set_title("Skip sync for now")
        skip_row.set_subtitle("Configure it later in Settings")
        skip_row.set_active(True)
        skip_row.connect("notify::active", self._on_skip_toggled)
        self._skip_sync = True
        sync_group.add(skip_row)

        # Provider
        provider_model = Gtk.StringList()
        for label in _PROVIDER_LABELS:
            provider_model.append(label)

        self._provider_row = Adw.ComboRow()
        self._provider_row.set_title("Provider")
        self._provider_row.set_model(provider_model)
        self._provider_row.set_tooltip_text("Choose your sync provider")
        self._provider_row.connect("notify::selected", self._on_provider_changed)
        sync_group.add(self._provider_row)

        # URL
        self._url_row = Adw.EntryRow()
        self._url_row.set_title("Server URL")
        self._url_row.set_text(PROVIDERS["pcloud"]["url"])
        self._url_row.set_tooltip_text("WebDAV server base URL")
        sync_group.add(self._url_row)

        # Remote path
        self._path_row = Adw.EntryRow()
        self._path_row.set_title("Remote Path")
        self._path_row.set_text(PROVIDERS["pcloud"]["path_hint"])
        self._path_row.set_tooltip_text("Path to budget.json on the server, e.g. Kopilka/budget.json")
        sync_group.add(self._path_row)

        # Username
        self._user_row = Adw.EntryRow()
        self._user_row.set_title("Username")
        self._user_row.set_tooltip_text("Account username or email")
        sync_group.add(self._user_row)

        # Password
        self._pass_row = Adw.PasswordEntryRow()
        self._pass_row.set_title("Password")
        self._pass_row.set_tooltip_text(
            "Account password or app-specific password — stored locally only"
        )
        sync_group.add(self._pass_row)

        # Test connection row
        test_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        test_box.set_halign(Gtk.Align.END)
        test_box.set_margin_top(4)

        self._test_spinner = Gtk.Spinner()
        self._test_spinner.set_visible(False)
        test_box.append(self._test_spinner)

        self._test_label = Gtk.Label()
        self._test_label.add_css_class("dim-label")
        self._test_label.set_visible(False)
        test_box.append(self._test_label)

        test_btn = Gtk.Button(label="Test Connection")
        test_btn.add_css_class("suggested-action")
        test_btn.set_tooltip_text("Verify credentials before saving")
        test_btn.connect("clicked", self._on_test)
        test_box.append(test_btn)

        test_action_row = Adw.ActionRow()
        test_action_row.set_activatable(False)
        test_action_row.add_suffix(test_box)
        sync_group.add(test_action_row)

        # Sensitivity — hide sync fields when skipping
        self._sync_rows = [
            self._provider_row, self._url_row, self._path_row,
            self._user_row, self._pass_row, test_action_row,
        ]
        self._set_sync_sensitive(False)

    def _on_skip_toggled(self, row, _param):
        self._skip_sync = row.get_active()
        self._set_sync_sensitive(not self._skip_sync)

    def _set_sync_sensitive(self, sensitive: bool):
        for row in self._sync_rows:
            row.set_sensitive(sensitive)

    def _on_provider_changed(self, row, _param):
        idx = row.get_selected()
        key = _PROVIDER_KEYS[idx]
        preset = PROVIDERS[key]
        if preset["url"]:
            self._url_row.set_text(preset["url"])
        if preset["path_hint"]:
            self._path_row.set_text(preset["path_hint"])

    def _on_test(self, _btn):
        config = {
            "webdav_url":         self._url_row.get_text().strip().rstrip("/"),
            "webdav_remote_path": self._path_row.get_text().strip().lstrip("/"),
            "webdav_username":    self._user_row.get_text().strip(),
            "webdav_password":    self._pass_row.get_text(),
        }
        mgr = build_from_config(config)

        self._test_spinner.set_visible(True)
        self._test_spinner.start()
        self._test_label.set_visible(False)

        threading.Thread(target=self._run_test, args=(mgr,), daemon=True).start()

    def _run_test(self, mgr):
        ok, msg = mgr.test_connection()
        GLib.idle_add(self._show_test_result, ok, msg)

    def _show_test_result(self, ok: bool, msg: str):
        self._test_spinner.stop()
        self._test_spinner.set_visible(False)
        self._test_label.set_text(msg)
        self._test_label.remove_css_class("success")
        self._test_label.remove_css_class("error")
        self._test_label.add_css_class("success" if ok else "error")
        self._test_label.set_visible(True)
        return GLib.SOURCE_REMOVE

    def _on_done(self, _btn):
        name1 = self.user1_row.get_text().strip()
        name2 = self.user2_row.get_text().strip()

        if not name1:
            self.user1_row.add_css_class("error")
            return
        self.user1_row.remove_css_class("error")

        if not name2:
            self.user2_row.add_css_class("error")
            return
        self.user2_row.remove_css_class("error")

        config = load_config()
        config["user1_name"] = name1
        config["user2_name"] = name2
        self.budget.couple = [name1, name2]

        if not self._skip_sync:
            idx = self._provider_row.get_selected()
            config["webdav_provider"]    = _PROVIDER_KEYS[idx]
            config["webdav_url"]         = self._url_row.get_text().strip().rstrip("/")
            config["webdav_remote_path"] = self._path_row.get_text().strip().lstrip("/")
            config["webdav_username"]    = self._user_row.get_text().strip()
            config["webdav_password"]    = self._pass_row.get_text()
            config.pop("webdav_etag", None)

        save_config(config)

        if self.on_complete:
            self.on_complete()

        self.force_close()
