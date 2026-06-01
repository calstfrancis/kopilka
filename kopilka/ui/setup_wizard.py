"""First-launch setup wizard."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib
from pathlib import Path

from kopilka.storage.json_io import load_config, save_config, set_budget_path


def _detect_pcloud() -> str:
    """Try to find the pCloud Drive folder."""
    home = Path.home()
    for candidate in ["pCloud Drive", "pCloud", "pCloudDrive"]:
        p = home / candidate
        if p.is_dir():
            return str(p)
    return ""


class SetupWizard(Adw.Dialog):
    """First-launch wizard to configure names and pCloud path."""

    def __init__(self, budget, on_complete):
        super().__init__()
        self.budget = budget
        self.on_complete = on_complete
        self._pcloud_path = _detect_pcloud()

        self.set_title("Welcome to Kopilka")
        self.set_content_width(500)
        self.set_content_height(620)
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

        # Users group
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

        # Pre-fill from existing config
        config = load_config()
        if config.get("user1_name"):
            self.user1_row.set_text(config["user1_name"])
        if config.get("user2_name"):
            self.user2_row.set_text(config["user2_name"])

        # pCloud group
        pcloud_group = Adw.PreferencesGroup()
        pcloud_group.set_title("Sync with pCloud (optional)")
        pcloud_group.set_description(
            "Choose your pCloud Drive folder to keep the budget in sync between devices"
        )
        page.add(pcloud_group)

        self.sync_row = Adw.ActionRow()
        self.sync_row.set_title("pCloud Folder")
        self.sync_row.set_subtitle(self._pcloud_path or "Not selected")

        choose_btn = Gtk.Button(label="Choose…")
        choose_btn.set_valign(Gtk.Align.CENTER)
        choose_btn.connect("clicked", self._on_choose_folder)
        self.sync_row.add_suffix(choose_btn)
        pcloud_group.add(self.sync_row)

        if self._pcloud_path:
            detected_row = Adw.ActionRow()
            detected_row.set_title("pCloud detected automatically")
            detected_row.add_css_class("success")
            pcloud_group.add(detected_row)

        skip_sync_row = Adw.SwitchRow()
        skip_sync_row.set_title("Skip sync for now")
        skip_sync_row.set_subtitle("You can set this up later in Settings")
        skip_sync_row.set_active(not bool(self._pcloud_path))
        skip_sync_row.connect("notify::active", self._on_skip_toggled)
        self._skip_sync = not bool(self._pcloud_path)
        self._skip_sync_row = skip_sync_row
        pcloud_group.add(skip_sync_row)

    def _on_skip_toggled(self, row, _param):
        self._skip_sync = row.get_active()

    def _on_choose_folder(self, _btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Select pCloud Sync Folder")
        dialog.select_folder(self.get_root(), None, self._folder_chosen)

    def _folder_chosen(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self._pcloud_path = folder.get_path()
                self.sync_row.set_subtitle(self._pcloud_path)
                self._skip_sync_row.set_active(False)
        except GLib.Error:
            pass

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

        if not self._skip_sync and self._pcloud_path:
            config["sync_path"] = self._pcloud_path
            self.budget.sync_path = self._pcloud_path
            set_budget_path(f"{self._pcloud_path}/budget.json")

        save_config(config)

        if self.on_complete:
            self.on_complete()

        self.force_close()
