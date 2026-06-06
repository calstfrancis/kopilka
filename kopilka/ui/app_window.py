"""Main application window."""

import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib, Gio, PangoCairo
import importlib.resources

from kopilka.ui.dashboard import Dashboard
from kopilka.ui.views import IncomeView, ExpenseView, DebtView, CategoryView
from kopilka.ui.spending_log import SpendingLogView
from kopilka.ui.reports import ReportsView
from kopilka.ui.savings import SavingsView
from kopilka.ui.settings import SettingsView
from kopilka.storage.json_io import (
    load_budget, save_budget, is_first_launch,
    get_budget_path, load_config, save_config,
)
from kopilka.logic.sync import SyncManager
from kopilka.logic.webdav_sync import (
    WebDAVSyncManager, ConflictError, conflict_files_local, build_from_config,
)


NAV_PAGES = [
    ("dashboard",  "go-home-symbolic",             "Dashboard"),
    ("income",     "value-increase-symbolic",       "Income"),
    ("expenses",   "value-decrease-symbolic",       "Expenses"),
    ("debt",       "alarm-symbolic",                "Debt"),
    ("categories", "tag-symbolic",                 "Categories"),
    ("log",        "view-list-symbolic",            "Spending Log"),
    ("reports",    "view-sort-descending-symbolic", "Reports"),
    ("savings",    "starred-symbolic",              "Savings & Goals"),
    ("settings",   "preferences-system-symbolic",   "Settings"),
]


class AppWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)

        self.budget, _load_err = load_budget()
        self._load_error = _load_err
        self._budget_path = get_budget_path()
        self._load_mtime = SyncManager.get_file_mtime(self._budget_path)
        cfg = load_config()
        self._current_user = cfg.get("user1_name", self.budget.couple[0])
        self._webdav = build_from_config(cfg)
        self._webdav_uploading = False

        self.set_title("Kopilka")
        self.set_default_size(1200, 800)

        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        self._split_view = Adw.OverlaySplitView()
        self._split_view.set_show_sidebar(True)
        self._split_view.set_sidebar_width_fraction(0.22)
        self._split_view.set_min_sidebar_width(190)
        self._split_view.set_max_sidebar_width(260)
        self._toast_overlay.set_child(self._split_view)

        self._gost_provider = Gtk.CssProvider()
        try:
            font_ref = importlib.resources.files("kopilka.data.fonts").joinpath("gosttypeb.ttf")
            PangoCairo.FontMap.get_default().add_font_file(str(font_ref))
            self._gost_provider.load_from_string("* { font-family: 'GOST type B', monospace; }")
        except Exception:
            self._gost_provider.load_from_string("* { font-family: monospace; }")

        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_end_title_buttons(False)
        sidebar_box.append(sidebar_header)

        self._sidebar_title = Adw.WindowTitle()
        self._sidebar_title.set_title("Kopilka")
        self._sidebar_title.set_subtitle(
            " & ".join(self.budget.couple) if self.budget.couple else "Budget"
        )
        sidebar_header.set_title_widget(self._sidebar_title)

        # Budget file menu
        budget_menu = Gio.Menu()
        budget_menu.append("New Budget…", "win.new-budget")
        budget_menu.append("Open Budget…", "win.open-budget")
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_menu_model(budget_menu)
        menu_btn.set_tooltip_text("Budget files")
        sidebar_header.pack_end(menu_btn)

        new_action = Gio.SimpleAction.new("new-budget", None)
        new_action.connect("activate", self._on_new_budget)
        self.add_action(new_action)

        open_action = Gio.SimpleAction.new("open-budget", None)
        open_action.connect("activate", self._on_open_budget)
        self.add_action(open_action)

        self._nav_listbox = Gtk.ListBox()
        self._nav_listbox.add_css_class("navigation-sidebar")
        self._nav_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._nav_listbox.set_vexpand(True)
        self._nav_listbox.connect("row-selected", self._on_nav_selected)
        sidebar_box.append(self._nav_listbox)

        self._nav_rows = {}
        for page_id, icon_name, label_text in NAV_PAGES:
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row_box.set_margin_top(9)
            row_box.set_margin_bottom(9)
            row_box.set_margin_start(14)
            row_box.set_margin_end(14)

            img = Gtk.Image.new_from_icon_name(icon_name)
            img.set_icon_size(Gtk.IconSize.NORMAL)
            row_box.append(img)

            lbl = Gtk.Label(label=label_text)
            lbl.set_xalign(0)
            lbl.set_hexpand(True)
            row_box.append(lbl)

            row.set_child(row_box)
            self._nav_listbox.append(row)
            self._nav_rows[page_id] = row

        # ── Sidebar bottom toggles ────────────────────────────────────────────
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sidebar_box.append(sep)

        toggles_lb = Gtk.ListBox()
        toggles_lb.add_css_class("boxed-list")
        toggles_lb.set_selection_mode(Gtk.SelectionMode.NONE)
        toggles_lb.set_margin_top(8)
        toggles_lb.set_margin_bottom(12)
        toggles_lb.set_margin_start(8)
        toggles_lb.set_margin_end(8)

        simple_row = Adw.ActionRow()
        simple_row.set_title("Simple")
        simple_row.set_subtitle("Hide breakdown & bills")
        self._simple_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self._simple_switch.connect("notify::active", self._on_simple_toggled)
        simple_row.add_suffix(self._simple_switch)
        simple_row.set_activatable_widget(self._simple_switch)
        toggles_lb.append(simple_row)

        gost_row = Adw.ActionRow()
        gost_row.set_title("Gost Type B")
        gost_row.set_subtitle("Technical drafting typeface")
        self._gost_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self._gost_switch.connect("notify::active", self._on_font_toggled)
        gost_row.add_suffix(self._gost_switch)
        gost_row.set_activatable_widget(self._gost_switch)
        toggles_lb.append(gost_row)

        sidebar_box.append(toggles_lb)

        self._split_view.set_sidebar(sidebar_box)

        # ── Content area ─────────────────────────────────────────────────────
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        content_header = Adw.HeaderBar()

        toggle_btn = Gtk.ToggleButton()
        toggle_btn.set_icon_name("sidebar-show-symbolic")
        toggle_btn.set_tooltip_text("Toggle sidebar")
        toggle_btn.set_active(True)
        toggle_btn.connect("toggled", lambda b: self._split_view.set_show_sidebar(b.get_active()))
        content_header.pack_start(toggle_btn)

        self._page_title = Adw.WindowTitle()
        self._page_title.set_title("Dashboard")
        content_header.set_title_widget(self._page_title)

        self._sync_spinner = Gtk.Spinner()
        self._sync_spinner.set_tooltip_text("Syncing to WebDAV…")
        self._sync_spinner.set_visible(False)
        content_header.pack_end(self._sync_spinner)

        content_box.append(content_header)

        # Reload banner (hidden until a newer version of the file is detected)
        self._reload_banner = Adw.Banner()
        self._reload_banner.set_button_label("Reload")
        self._reload_banner.connect("button-clicked", self._on_reload_clicked)
        content_box.append(self._reload_banner)

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(150)
        self._stack.set_hexpand(True)
        self._stack.set_vexpand(True)
        content_box.append(self._stack)

        self._split_view.set_content(content_box)

        # ── Views ─────────────────────────────────────────────────────────────
        self.dashboard = Dashboard(self.budget, on_change=self._on_budget_change)
        self._stack.add_named(self.dashboard, "dashboard")

        self.income_view = IncomeView(self.budget, self._on_budget_change)
        self._stack.add_named(self.income_view, "income")

        self.expense_view = ExpenseView(self.budget, self._on_budget_change)
        self._stack.add_named(self.expense_view, "expenses")

        self.debt_view = DebtView(self.budget, self._on_budget_change)
        self._stack.add_named(self.debt_view, "debt")

        self.category_view = CategoryView(self.budget, self._on_budget_change)
        self._stack.add_named(self.category_view, "categories")

        self.log_view = SpendingLogView(self.budget, self._on_budget_change)
        self._stack.add_named(self.log_view, "log")

        self.reports_view = ReportsView(self.budget, self._on_budget_change)
        self._stack.add_named(self.reports_view, "reports")

        self.savings_view = SavingsView(self.budget, self._on_budget_change)
        self._stack.add_named(self.savings_view, "savings")

        self.settings_view = SettingsView(self.budget, self._on_budget_change)
        self._stack.add_named(self.settings_view, "settings")

        self._nav_listbox.select_row(self._nav_rows["dashboard"])

        self.connect("notify::is-active", self._on_focus_changed)

        # Ctrl+Shift+L — quick log purchase from anywhere
        log_shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Primary><Shift>l"),
            Gtk.CallbackAction.new(self._shortcut_log_purchase),
        )
        shortcut_ctl = Gtk.ShortcutController()
        shortcut_ctl.set_scope(Gtk.ShortcutScope.GLOBAL)
        shortcut_ctl.add_shortcut(log_shortcut)
        self.add_controller(shortcut_ctl)

        GLib.idle_add(self._on_startup)

    # ── Sync ──────────────────────────────────────────────────────────────────

    def _on_startup(self):
        """Run once after window is mapped: wizard check then conflict check."""
        if self._load_error:
            toast = Adw.Toast()
            toast.set_title(self._load_error)
            toast.set_timeout(0)  # stay until dismissed
            self._toast_overlay.add_toast(toast)
        if is_first_launch():
            from kopilka.ui.setup_wizard import SetupWizard
            SetupWizard(self.budget, self._on_wizard_complete).present(self)
        else:
            # Check for local conflict copies (from previous WebDAV conflict saves)
            conflicts = conflict_files_local(self._budget_path)
            if conflicts:
                self._show_conflict_dialog(conflicts)
        return GLib.SOURCE_REMOVE

    def _on_focus_changed(self, _win, _param):
        if not self.is_active():
            return
        cfg = load_config()
        self._webdav = build_from_config(cfg)
        if self._webdav.is_configured():
            # Check remote ETag in background so focus-gain is instant
            threading.Thread(target=self._check_webdav_remote, daemon=True).start()
        elif SyncManager.is_externally_modified(self._budget_path, self._load_mtime):
            # Fallback: local mtime check (no WebDAV configured)
            meta = SyncManager.peek_metadata(self._budget_path)
            who = meta["last_modified_by"]
            when = SyncManager.friendly_time(meta["last_modified"])
            msg = f"Budget updated by {who}"
            if when:
                msg += f" — {when}"
            GLib.idle_add(self._show_reload_banner, msg)

    def _check_webdav_remote(self):
        """Background thread: PROPFIND remote ETag; notify UI if newer."""
        try:
            if self._webdav.is_remote_newer():
                meta = self._webdav.peek_remote_metadata()
                who = meta["last_modified_by"]
                when = SyncManager.friendly_time(meta["last_modified"])
                msg = f"Budget updated by {who}"
                if when:
                    msg += f" — {when}"
                GLib.idle_add(self._show_reload_banner, msg)
        except Exception:
            pass

    def _show_reload_banner(self, msg: str):
        self._reload_banner.set_title(msg)
        self._reload_banner.set_revealed(True)
        return GLib.SOURCE_REMOVE

    def _on_reload_clicked(self, _banner):
        self._reload_banner.set_revealed(False)
        if self._webdav.is_configured():
            threading.Thread(target=self._webdav_download_and_reload, daemon=True).start()
        else:
            self.budget, _ = load_budget()
            self._load_mtime = SyncManager.get_file_mtime(self._budget_path)
            self._refresh_all_views()
            toast = Adw.Toast()
            toast.set_title("Budget reloaded")
            self._toast_overlay.add_toast(toast)

    def _webdav_download_and_reload(self):
        """Background thread: download from WebDAV then refresh UI."""
        try:
            new_etag = self._webdav.download(self._budget_path)
            cfg = load_config()
            cfg["webdav_etag"] = new_etag
            save_config(cfg)
            self._webdav = build_from_config(cfg)
            GLib.idle_add(self._finish_reload, "Budget reloaded from WebDAV", None)
        except Exception as e:
            GLib.idle_add(self._finish_reload, None, str(e))

    def _finish_reload(self, success_msg: str | None, error_msg: str | None):
        if success_msg:
            self.budget, _ = load_budget()
            self._load_mtime = SyncManager.get_file_mtime(self._budget_path)
            self._refresh_all_views()
        toast = Adw.Toast()
        toast.set_title(success_msg or f"Reload failed: {error_msg}")
        self._toast_overlay.add_toast(toast)
        return GLib.SOURCE_REMOVE

    def _show_conflict_dialog(self, conflict_paths):
        names = "\n".join(p.name for p in conflict_paths[:3])
        dlg = Adw.AlertDialog()
        dlg.set_heading("Sync Conflict")
        dlg.set_body(
            "Conflicting versions of your budget were saved locally:\n\n"
            f"{names}\n\n"
            "Keep your current version and delete the conflict files, "
            "or open the folder to compare them manually."
        )
        dlg.add_response("keep", "Keep Current")
        dlg.add_response("open_folder", "Open Folder")
        dlg.set_default_response("keep")
        dlg.set_close_response("keep")
        dlg.connect("response", self._on_conflict_response, conflict_paths)
        dlg.present(self)

    def _on_conflict_response(self, _dlg, response, conflict_paths):
        if response == "open_folder":
            import subprocess
            folder = str(conflict_paths[0].parent)
            subprocess.Popen(["xdg-open", folder])
        elif response == "keep":
            for p in conflict_paths:
                try:
                    p.unlink()
                except OSError:
                    pass

    def _webdav_upload_async(self):
        """Fire-and-forget background upload. Shows spinner while in progress."""
        cfg = load_config()
        self._webdav = build_from_config(cfg)
        if not self._webdav.is_configured() or self._webdav_uploading:
            return
        self._webdav_uploading = True
        self._sync_spinner.set_visible(True)
        self._sync_spinner.start()
        threading.Thread(target=self._webdav_upload_worker, daemon=True).start()

    def _webdav_upload_worker(self):
        try:
            new_etag = self._webdav.upload(self._budget_path)
            cfg = load_config()
            cfg["webdav_etag"] = new_etag
            save_config(cfg)
            self._webdav = build_from_config(cfg)
            GLib.idle_add(self._on_upload_done, None)
        except ConflictError:
            # Remote changed — save conflict copy and notify user
            try:
                conflict_path = self._webdav.save_conflict_copy(self._budget_path)
                GLib.idle_add(self._on_upload_conflict, conflict_path)
            except Exception as e:
                GLib.idle_add(self._on_upload_done, f"Conflict — could not fetch remote: {e}")
        except Exception as e:
            GLib.idle_add(self._on_upload_done, str(e))

    def _on_upload_done(self, error: str | None):
        self._webdav_uploading = False
        self._sync_spinner.stop()
        self._sync_spinner.set_visible(False)
        if error:
            toast = Adw.Toast()
            toast.set_title(f"Sync failed: {error}")
            self._toast_overlay.add_toast(toast)
        return GLib.SOURCE_REMOVE

    def _on_upload_conflict(self, conflict_path):
        self._webdav_uploading = False
        self._sync_spinner.stop()
        self._sync_spinner.set_visible(False)
        self._show_conflict_dialog([conflict_path])
        return GLib.SOURCE_REMOVE

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_nav_selected(self, _listbox, row):
        if row is None:
            return
        for page_id, nav_row in self._nav_rows.items():
            if nav_row is row:
                self._stack.set_visible_child_name(page_id)
                for pid, _icon, label in NAV_PAGES:
                    if pid == page_id:
                        self._page_title.set_title(label)
                        break
                break

    # ── Budget change ─────────────────────────────────────────────────────────

    def _on_budget_change(self):
        SyncManager.update_metadata(self.budget, self._current_user)
        save_budget(self.budget)
        self._load_mtime = SyncManager.get_file_mtime(self._budget_path)
        self._reload_banner.set_revealed(False)
        self._refresh_all_views()
        self._webdav_upload_async()

    def _on_wizard_complete(self):
        cfg = load_config()
        self._current_user = cfg.get("user1_name", self.budget.couple[0])
        self._webdav = build_from_config(cfg)
        self._on_budget_change()

    def _propagate_budget(self):
        """Push the current budget object to every view that caches it."""
        for view in (
            self.income_view, self.expense_view, self.debt_view,
            self.category_view, self.log_view, self.reports_view,
            self.savings_view, self.settings_view,
        ):
            view.budget = self.budget

    def _refresh_all_views(self):
        self._propagate_budget()
        self.dashboard.refresh(self.budget)
        self.income_view.refresh()
        self.expense_view.refresh()
        self.debt_view.refresh()
        self.category_view.refresh()
        self.log_view.refresh()
        self.reports_view.refresh()
        self.savings_view.refresh()
        self._refresh_sidebar_subtitle()

    def _refresh_sidebar_subtitle(self):
        subtitle = " & ".join(self.budget.couple) if self.budget.couple else "Budget"
        self._sidebar_title.set_subtitle(subtitle)

    # ── First launch ──────────────────────────────────────────────────────────

    def _check_first_launch(self):
        if is_first_launch():
            from kopilka.ui.setup_wizard import SetupWizard
            SetupWizard(self.budget, self._on_wizard_complete).present(self)
        return GLib.SOURCE_REMOVE

    # ── Multiple budgets ──────────────────────────────────────────────────────

    def _on_new_budget(self, _action, _param):
        dialog = Gtk.FileDialog()
        dialog.set_title("Save New Budget As…")
        dialog.set_initial_name("budget.json")
        dialog.save(self, None, self._new_budget_chosen)

    def _new_budget_chosen(self, dialog, result):
        try:
            f = dialog.save_finish(result)
            if not f:
                return
            path = f.get_path()
            from kopilka.storage.json_io import set_budget_path, save_budget
            from kopilka.model.budget import Budget
            set_budget_path(path)
            self._budget_path = path
            self.budget = Budget()
            self.budget.couple = [self._current_user, "Partner"]
            save_budget(self.budget)
            self._load_mtime = __import__("kopilka.logic.sync", fromlist=["SyncManager"]).SyncManager.get_file_mtime(path)
            self._refresh_all_views()
            toast = Adw.Toast()
            toast.set_title(f"New budget created: {__import__('pathlib').Path(path).name}")
            self._toast_overlay.add_toast(toast)
        except Exception:
            pass

    def _on_open_budget(self, _action, _param):
        dialog = Gtk.FileDialog()
        dialog.set_title("Open Budget File")
        f = Gio.File.new_for_path(__import__("os").path.dirname(self._budget_path))
        dialog.set_initial_folder(f)
        dialog.open(self, None, self._open_budget_chosen)

    def _open_budget_chosen(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            if not f:
                return
            path = f.get_path()
            from kopilka.storage.json_io import set_budget_path, load_budget
            from kopilka.logic.sync import SyncManager
            set_budget_path(path)
            self._budget_path = path
            self.budget, _ = load_budget()
            self._load_mtime = SyncManager.get_file_mtime(path)
            self._current_user = self.budget.couple[0] if self.budget.couple else "User 1"
            cfg = load_config()
            self._webdav = build_from_config(cfg)
            self._refresh_all_views()
            toast = Adw.Toast()
            toast.set_title(f"Opened: {__import__('pathlib').Path(path).name}")
            self._toast_overlay.add_toast(toast)
        except Exception:
            pass

    def _shortcut_log_purchase(self, _widget, _args):
        from kopilka.ui.forms import LogSpendingDialog
        self._nav_listbox.select_row(self._nav_rows["log"])
        LogSpendingDialog(self.budget, on_saved=self._on_budget_change).present(self)
        return True

    def _on_font_toggled(self, switch, _param):
        display = self.get_display()
        if switch.get_active():
            Gtk.StyleContext.add_provider_for_display(
                display, self._gost_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_USER,
            )
        else:
            Gtk.StyleContext.remove_provider_for_display(
                display, self._gost_provider,
            )

    def _on_simple_toggled(self, switch, _param):
        self.dashboard.set_simple_mode(switch.get_active())

    def add_toast(self, toast):
        self._toast_overlay.add_toast(toast)
