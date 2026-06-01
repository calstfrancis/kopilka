"""Spending log view."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw
from datetime import date, timedelta

from kopilka.ui.forms import LogSpendingDialog


def _clear_box(box):
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


FILTER_OPTIONS = [
    (7,   "7 days",  "Show purchases from the last 7 days"),
    (30,  "30 days", "Show purchases from the last 30 days"),
    (90,  "90 days", "Show purchases from the last 3 months"),
    (365, "1 year",  "Show purchases from the last 12 months"),
]


class SpendingLogView(Gtk.Box):
    def __init__(self, budget, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.budget = budget
        self.on_change = on_change
        self._filter_days = 30

        self.set_hexpand(True)
        self.set_vexpand(True)

        # ── Toolbar (clamp-wrapped) ───────────────────────────────────────────
        clamp_header = Adw.Clamp()
        clamp_header.set_maximum_size(860)
        clamp_header.set_margin_start(16)
        clamp_header.set_margin_end(16)
        clamp_header.set_margin_top(20)
        clamp_header.set_margin_bottom(8)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        clamp_header.set_child(header_box)

        icon = Gtk.Image.new_from_icon_name("view-list-symbolic")
        icon.set_icon_size(Gtk.IconSize.LARGE)
        icon.add_css_class("dim-label")
        header_box.append(icon)

        title_lbl = Gtk.Label(label="Spending Log")
        title_lbl.add_css_class("title-2")
        title_lbl.set_xalign(0)
        title_lbl.set_hexpand(True)
        header_box.append(title_lbl)

        # Segmented filter (linked buttons)
        filter_box = Gtk.Box(spacing=0)
        filter_box.add_css_class("linked")
        self._filter_btns = {}
        for days, label, tip in FILTER_OPTIONS:
            btn = Gtk.ToggleButton(label=label)
            btn.set_active(days == self._filter_days)
            btn.set_tooltip_text(tip)
            btn.connect("toggled", self._on_filter_toggled, days)
            filter_box.append(btn)
            self._filter_btns[days] = btn
        header_box.append(filter_box)

        add_content = Adw.ButtonContent()
        add_content.set_icon_name("list-add-symbolic")
        add_content.set_label("Log Purchase")
        add_btn = Gtk.Button()
        add_btn.set_child(add_content)
        add_btn.add_css_class("suggested-action")
        add_btn.add_css_class("pill")
        add_btn.connect("clicked", self._on_add)
        header_box.append(add_btn)

        self.append(clamp_header)

        # ── Scrollable list ───────────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)

        clamp_content = Adw.Clamp()
        clamp_content.set_maximum_size(860)
        clamp_content.set_margin_start(16)
        clamp_content.set_margin_end(16)
        clamp_content.set_margin_bottom(24)

        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        clamp_content.set_child(self.list_box)
        scroll.set_child(clamp_content)
        self.append(scroll)

        self.refresh()

    def refresh(self):
        _clear_box(self.list_box)

        cutoff = (date.today() - timedelta(days=self._filter_days)).isoformat()
        entries = sorted(
            [e for e in self.budget.spending if e.date >= cutoff],
            key=lambda e: e.date,
            reverse=True,
        )

        if not entries:
            sp = Adw.StatusPage()
            sp.set_title("No Purchases Logged")
            sp.set_description('Tap "Log Purchase" to track your spending')
            sp.set_icon_name("view-list-symbolic")
            self.list_box.append(sp)
            return

        cat_map = {c.id: c.name for c in self.budget.categories}
        total_period = sum(e.amount for e in entries)

        # Period total summary row
        summary_lb = Gtk.ListBox()
        summary_lb.add_css_class("boxed-list")
        summary_lb.set_selection_mode(Gtk.SelectionMode.NONE)
        summary_lb.set_margin_bottom(8)

        summary_row = Adw.ActionRow()
        summary_row.set_title(f"Total — last {self._filter_days} days")
        total_lbl = Gtk.Label(label=f"${total_period:,.2f}")
        total_lbl.add_css_class("numeric")
        total_lbl.add_css_class("accent")
        total_lbl.set_valign(Gtk.Align.CENTER)
        summary_row.add_suffix(total_lbl)
        summary_lb.append(summary_row)
        self.list_box.append(summary_lb)

        # Group by date
        groups: dict[str, list] = {}
        for e in entries:
            groups.setdefault(e.date, []).append(e)

        for day in sorted(groups.keys(), reverse=True):
            day_lbl = Gtk.Label(label=day)
            day_lbl.add_css_class("caption")
            day_lbl.add_css_class("dim-label")
            day_lbl.set_xalign(0)
            day_lbl.set_margin_top(12)
            day_lbl.set_margin_bottom(2)
            self.list_box.append(day_lbl)

            lb = Gtk.ListBox()
            lb.add_css_class("boxed-list")
            lb.set_selection_mode(Gtk.SelectionMode.NONE)
            self.list_box.append(lb)

            for entry in groups[day]:
                row = Adw.ActionRow()
                row.set_title(entry.description or "(no description)")
                cat_name = cat_map.get(entry.category_id, "Unknown")
                row.set_subtitle(f"{cat_name}  ·  {entry.user}")

                amt = Gtk.Label(label=f"${entry.amount:,.2f}")
                amt.add_css_class("numeric")
                amt.set_valign(Gtk.Align.CENTER)
                row.add_suffix(amt)

                edit_btn = Gtk.Button()
                edit_btn.set_icon_name("document-edit-symbolic")
                edit_btn.set_tooltip_text("Edit")
                edit_btn.add_css_class("flat")
                edit_btn.add_css_class("circular")
                edit_btn.set_valign(Gtk.Align.CENTER)
                edit_btn.connect("clicked", self._on_edit, entry)
                row.add_suffix(edit_btn)

                del_btn = Gtk.Button()
                del_btn.set_icon_name("edit-delete-symbolic")
                del_btn.set_tooltip_text("Delete")
                del_btn.add_css_class("flat")
                del_btn.add_css_class("circular")
                del_btn.add_css_class("destructive-action")
                del_btn.set_valign(Gtk.Align.CENTER)
                del_btn.connect("clicked", self._on_delete, entry)
                row.add_suffix(del_btn)

                lb.append(row)

    def _on_filter_toggled(self, btn, days):
        if btn.get_active():
            self._filter_days = days
            for d, b in self._filter_btns.items():
                if d != days:
                    b.set_active(False)
            self.refresh()
        elif not any(b.get_active() for b in self._filter_btns.values()):
            # Don't allow deselecting all — re-activate this one
            btn.set_active(True)

    def _on_add(self, _btn):
        if not self.budget.categories:
            dlg = Adw.AlertDialog()
            dlg.set_heading("No Categories")
            dlg.set_body("Create spending categories before logging purchases.")
            dlg.add_response("ok", "OK")
            dlg.present(self.get_root())
            return
        LogSpendingDialog(self.budget, on_saved=self._saved).present(self.get_root())

    def _on_edit(self, _btn, entry):
        LogSpendingDialog(self.budget, on_saved=self._saved, existing=entry).present(self.get_root())

    def _on_delete(self, _btn, entry):
        self.budget.spending.remove(entry)
        self.on_change()
        self.refresh()

    def _saved(self, _item):
        self.on_change()
        self.refresh()
