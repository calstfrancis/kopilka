"""Spending log view."""

import csv
import io
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib, Gio
from datetime import date, timedelta
import calendar

from kopilka.model.budget import ONE_TIME_CATEGORY_ID
from kopilka.ui.forms import LogSpendingDialog, AddRecurringDialog


def _confirm_delete_log(heading: str, body: str, parent, on_confirm) -> None:
    dlg = Adw.AlertDialog()
    dlg.set_heading(heading)
    dlg.set_body(body)
    dlg.add_response("cancel", "Cancel")
    dlg.add_response("delete", "Delete")
    dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
    dlg.set_default_response("cancel")
    dlg.set_close_response("cancel")
    dlg.connect("response", lambda d, r: on_confirm() if r == "delete" else None)
    dlg.present(parent)


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


def _pill_fg(hex_color: str) -> str:
    """Return 'black' or 'white' for legible text on the given background."""
    try:
        r = int(hex_color[1:3], 16) / 255
        g = int(hex_color[3:5], 16) / 255
        b = int(hex_color[5:7], 16) / 255
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return "black" if luminance > 0.35 else "white"
    except (ValueError, IndexError):
        return "white"


def _colored_pill(text: str, hex_color: str) -> Gtk.Label:
    """Small label with an optional coloured background pill."""
    lbl = Gtk.Label(label=text)
    lbl.add_css_class("caption")
    lbl.set_valign(Gtk.Align.CENTER)
    if hex_color:
        fg = _pill_fg(hex_color)
        provider = Gtk.CssProvider()
        provider.load_from_string(
            f"label{{background:{hex_color};color:{fg};"
            f"border-radius:4px;padding:1px 6px;}}"
        )
        lbl.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    return lbl


def _apply_recurring(budget) -> bool:
    """Auto-insert any overdue recurring entries. Returns True if any were inserted."""
    today = date.today().isoformat()
    inserted = False
    from kopilka.model.budget import SpendingEntry
    for rec in budget.recurring:
        if not rec.active:
            continue
        iterations = 0
        while rec.next_date <= today and iterations < 730:
            iterations += 1
            entry = SpendingEntry(
                date=rec.next_date,
                category_id=rec.category_id,
                amount=rec.amount,
                description=rec.description or rec.name,
                user=rec.user,
            )
            budget.spending.append(entry)
            # Advance next_date by frequency
            d = date.fromisoformat(rec.next_date)
            if rec.frequency == "weekly":
                d += timedelta(days=7)
            elif rec.frequency == "biweekly":
                d += timedelta(days=14)
            else:  # monthly
                m = d.month + 1
                y = d.year + (m - 1) // 12
                m = (m - 1) % 12 + 1
                try:
                    d = d.replace(year=y, month=m)
                except ValueError:
                    d = d.replace(year=y, month=m, day=calendar.monthrange(y, m)[1])
            rec.next_date = d.isoformat()
            inserted = True
        if rec.next_date <= today:
            # next_date is still in the past after the iteration cap —
            # clamp forward so the loop doesn't re-trigger on next open
            rec.next_date = date.today().isoformat()
    return inserted


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

        # Export CSV button
        export_btn = Gtk.Button()
        export_btn.set_icon_name("document-save-symbolic")
        export_btn.set_tooltip_text("Export to CSV")
        export_btn.add_css_class("flat")
        export_btn.add_css_class("circular")
        export_btn.connect("clicked", self._on_export_csv)
        header_box.append(export_btn)

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

        cat_map   = {c.id: c for c in self.budget.categories}
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

        if not entries:
            sp = Adw.StatusPage()
            sp.set_title("No Purchases Logged")
            sp.set_description('Tap "Log Purchase" to track your spending')
            sp.set_icon_name("view-list-symbolic")
            self.list_box.append(sp)
            self._build_recurring_section()
            return

        # Group by date
        groups: dict[str, list] = {}
        for e in entries:
            groups.setdefault(e.date, []).append(e)

        for day in sorted(groups.keys(), reverse=True):
            try:
                d = date.fromisoformat(day)
                friendly = d.strftime("%A, %B ") + str(d.day)
                if d.year != date.today().year:
                    friendly += f", {d.year}"
            except ValueError:
                friendly = day
            day_lbl = Gtk.Label(label=friendly)
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

                # Category pill with colour
                if entry.category_id == ONE_TIME_CATEGORY_ID:
                    cat_name  = "One-time"
                    cat_color = ""
                else:
                    cat = cat_map.get(entry.category_id)
                    cat_name  = cat.name if cat else "Unknown"
                    cat_color = cat.color if cat else ""

                pill = _colored_pill(cat_name, cat_color)
                row.add_prefix(pill)

                row.set_subtitle(entry.user)

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

        self._build_recurring_section()

    def _build_recurring_section(self):
        """Append the recurring entries management section below the log."""
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hdr.set_margin_top(20)

        hdr_lbl = Gtk.Label(label="Recurring Entries")
        hdr_lbl.add_css_class("title-4")
        hdr_lbl.set_hexpand(True)
        hdr_lbl.set_xalign(0)
        hdr.append(hdr_lbl)

        add_rec_content = Adw.ButtonContent()
        add_rec_content.set_icon_name("list-add-symbolic")
        add_rec_content.set_label("Add Recurring")
        add_rec_btn = Gtk.Button()
        add_rec_btn.set_child(add_rec_content)
        add_rec_btn.add_css_class("pill")
        add_rec_btn.connect("clicked", self._on_add_recurring)
        hdr.append(add_rec_btn)

        self.list_box.append(hdr)

        if not self.budget.recurring:
            sp = Gtk.Label(label="No recurring entries")
            sp.add_css_class("dim-label")
            sp.add_css_class("caption")
            sp.set_xalign(0)
            sp.set_margin_bottom(8)
            self.list_box.append(sp)
            return

        lb = Gtk.ListBox()
        lb.add_css_class("boxed-list")
        lb.set_selection_mode(Gtk.SelectionMode.NONE)
        lb.set_margin_bottom(8)
        self.list_box.append(lb)

        cat_map = {c.id: c.name for c in self.budget.categories}

        for rec in self.budget.recurring:
            row = Adw.ActionRow()
            row.set_title(rec.name)
            cat_name = "One-time" if rec.category_id == ONE_TIME_CATEGORY_ID else cat_map.get(rec.category_id, "Unknown")
            status = "active" if rec.active else "paused"
            row.set_subtitle(f"${rec.amount:,.2f}  ·  {rec.frequency}  ·  {cat_name}  ·  next: {rec.next_date}  ·  {status}")

            edit_btn = Gtk.Button()
            edit_btn.set_icon_name("document-edit-symbolic")
            edit_btn.set_tooltip_text("Edit")
            edit_btn.add_css_class("flat")
            edit_btn.add_css_class("circular")
            edit_btn.set_valign(Gtk.Align.CENTER)
            edit_btn.connect("clicked", self._on_edit_recurring, rec)
            row.add_suffix(edit_btn)

            del_btn = Gtk.Button()
            del_btn.set_icon_name("edit-delete-symbolic")
            del_btn.set_tooltip_text("Delete")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("circular")
            del_btn.add_css_class("destructive-action")
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.connect("clicked", self._on_delete_recurring, rec)
            row.add_suffix(del_btn)

            lb.append(row)

    # ── Filter ────────────────────────────────────────────────────────────────

    def _on_filter_toggled(self, btn, days):
        if btn.get_active():
            self._filter_days = days
            for d, b in self._filter_btns.items():
                if d != days:
                    b.set_active(False)
            self.refresh()
        elif not any(b.get_active() for b in self._filter_btns.values()):
            btn.set_active(True)

    # ── Add / edit spending entries ───────────────────────────────────────────

    def _on_add(self, _btn):
        LogSpendingDialog(self.budget, on_saved=self._saved).present(self.get_root())

    def _on_edit(self, _btn, entry):
        LogSpendingDialog(self.budget, on_saved=self._saved, existing=entry).present(self.get_root())

    def _on_delete(self, _btn, entry):
        desc = entry.description or "(no description)"
        body = f'${entry.amount:,.2f} — {desc}'
        def _do():
            self.budget.spending.remove(entry)
            self.on_change()
            self.refresh()
        _confirm_delete_log("Delete Entry?", body, self.get_root(), _do)

    # ── Recurring ─────────────────────────────────────────────────────────────

    def _on_add_recurring(self, _btn):
        AddRecurringDialog(self.budget, on_saved=self._saved_recurring).present(self.get_root())

    def _on_edit_recurring(self, _btn, rec):
        AddRecurringDialog(self.budget, on_saved=self._saved_recurring, existing=rec).present(self.get_root())

    def _on_delete_recurring(self, _btn, rec):
        def _do():
            self.budget.recurring.remove(rec)
            self.on_change()
            self.refresh()
        _confirm_delete_log("Remove Recurring Entry?", f'"{rec.name}" will be permanently removed.', self.get_root(), _do)

    def _saved_recurring(self, _item):
        self.on_change()
        self.refresh()

    def _saved(self, _item):
        self.on_change()
        self.refresh()

    # ── Export CSV ────────────────────────────────────────────────────────────

    def _on_export_csv(self, _btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Export Spending Log")
        dialog.set_initial_name("spending_log.csv")
        dialog.save(self.get_root(), None, self._export_chosen)

    def _export_chosen(self, dialog, result):
        try:
            f = dialog.save_finish(result)
            if not f:
                return
            path = f.get_path()
        except Exception:
            return

        cat_map = {c.id: c.name for c in self.budget.categories}
        cutoff  = (date.today() - timedelta(days=self._filter_days)).isoformat()
        entries = sorted(
            [e for e in self.budget.spending if e.date >= cutoff],
            key=lambda e: e.date,
            reverse=True,
        )

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Date", "Category", "Amount", "Description", "Paid by"])
        for e in entries:
            if e.category_id == ONE_TIME_CATEGORY_ID:
                cat_name = "One-time Purchase"
            else:
                cat_name = cat_map.get(e.category_id, "Unknown")
            writer.writerow([e.date, cat_name, f"{e.amount:.2f}", e.description, e.user])

        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                fh.write(buf.getvalue())
        except OSError:
            return

        from gi.repository import Adw
        toast = Adw.Toast()
        toast.set_title(f"Exported {len(entries)} entries (last {self._filter_days} days)")
        root = self.get_root()
        if hasattr(root, "add_toast"):
            root.add_toast(toast)
