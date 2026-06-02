"""Assets, savings goals, and net worth view."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw
from datetime import date

from kopilka.model.budget import (
    Asset, SavingsGoal,
    ASSET_TYPES, ASSET_TYPE_LABELS, ASSET_TYPE_GROUPS,
)
from kopilka.logic.calculations import BudgetCalculator
from kopilka.ui.charts import BalanceLineChart, DonutChart


CHANGE_TYPES       = ["deposit", "withdrawal", "interest", "dividend",
                      "gain", "loss", "fee", "transfer", "other"]
CHANGE_TYPE_LABELS = ["Deposit", "Withdrawal", "Interest earned",
                      "Dividend received", "Market gain", "Market loss",
                      "Fee / charge", "Transfer", "Other"]

CHANGE_TYPE_CSS = {
    "deposit":    "success",
    "interest":   "success",
    "dividend":   "success",
    "gain":       "success",
    "withdrawal": "warning",
    "fee":        "error",
    "loss":       "error",
    "transfer":   "",
    "other":      "",
}


def _clear_box(box):
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def _num(text, css=""):
    lbl = Gtk.Label(label=text)
    lbl.add_css_class("numeric")
    if css:
        lbl.add_css_class(css)
    lbl.set_valign(Gtk.Align.CENTER)
    return lbl


def _icon_btn(icon, tooltip, css=None):
    btn = Gtk.Button()
    btn.set_icon_name(icon)
    btn.set_tooltip_text(tooltip)
    btn.add_css_class("flat")
    btn.add_css_class("circular")
    btn.set_valign(Gtk.Align.CENTER)
    if css:
        btn.add_css_class(css)
    return btn


# ---------------------------------------------------------------------------
# Asset dialog
# ---------------------------------------------------------------------------

class _AssetDialog(Adw.Dialog):
    def __init__(self, budget, on_saved, existing=None):
        super().__init__()
        self.budget   = budget
        self.on_saved = on_saved
        self.existing = existing
        self.set_title("Edit Account" if existing else "Add Account")
        self.set_content_width(460)

        tv = Adw.ToolbarView()
        self.set_child(tv)
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda b: self.close())
        hdr.pack_start(cancel)

        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        hdr.pack_end(save)

        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        tv.set_content(scroll)

        page  = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        scroll.set_child(page)

        self.name_row = Adw.EntryRow()
        self.name_row.set_title("Account Name")
        group.add(self.name_row)

        self.type_row = Adw.ComboRow()
        self.type_row.set_title("Account Type")
        type_model = Gtk.StringList()
        for t in ASSET_TYPES:
            type_model.append(ASSET_TYPE_LABELS[t])
        self.type_row.set_model(type_model)
        group.add(self.type_row)

        self.owner_row = Adw.ComboRow()
        self.owner_row.set_title("Owner")
        owner_model = Gtk.StringList()
        for p in budget.couple + ["Joint"]:
            owner_model.append(p)
        self.owner_row.set_model(owner_model)
        group.add(self.owner_row)

        self.institution_row = Adw.EntryRow()
        self.institution_row.set_title("Institution (optional)")
        group.add(self.institution_row)

        self.balance_row = Adw.SpinRow.new_with_range(0, 99_999_999, 100)
        self.balance_row.set_title("Current Balance / Value ($)")
        self.balance_row.set_digits(2)
        group.add(self.balance_row)

        self.rate_row = Adw.SpinRow.new_with_range(0, 100, 0.05)
        self.rate_row.set_title("Annual Interest / Return Rate (%)")
        self.rate_row.set_subtitle("Used for projected growth — 0 to skip")
        self.rate_row.set_digits(2)
        self.rate_row.set_tooltip_text(
            "Annual interest rate for savings accounts and GICs, "
            "or expected annual return for investment accounts. "
            "Leave at 0 if not applicable."
        )
        group.add(self.rate_row)

        self.notes_row = Adw.EntryRow()
        self.notes_row.set_title("Notes")
        group.add(self.notes_row)

        if existing:
            self.name_row.set_text(existing.name)
            if existing.asset_type in ASSET_TYPES:
                self.type_row.set_selected(ASSET_TYPES.index(existing.asset_type))
            owners = budget.couple + ["Joint"]
            if existing.owner in owners:
                self.owner_row.set_selected(owners.index(existing.owner))
            self.institution_row.set_text(existing.institution or "")
            self.balance_row.set_value(existing.balance)
            self.rate_row.set_value(getattr(existing, "interest_rate", 0.0))
            self.notes_row.set_text(existing.notes or "")

    def _save(self, _btn):
        name = self.name_row.get_text().strip()
        if not name:
            self.name_row.add_css_class("error")
            return
        self.name_row.remove_css_class("error")

        asset_type    = ASSET_TYPES[self.type_row.get_selected()]
        owners        = self.budget.couple + ["Joint"]
        owner         = owners[self.owner_row.get_selected()]
        institution   = self.institution_row.get_text().strip()
        balance       = self.balance_row.get_value()
        interest_rate = self.rate_row.get_value()
        notes         = self.notes_row.get_text().strip()

        if self.existing:
            if abs(balance - self.existing.balance) > 0.005:
                self.existing.balance_history.append({
                    "date":        date.today().isoformat(),
                    "balance":     balance,
                    "change":      balance - self.existing.balance,
                    "change_type": "other",
                    "note":        "Edited",
                })
            self.existing.name          = name
            self.existing.asset_type    = asset_type
            self.existing.owner         = owner
            self.existing.institution   = institution
            self.existing.balance       = balance
            self.existing.interest_rate = interest_rate
            self.existing.notes         = notes
            item = self.existing
        else:
            item = Asset(
                name=name, asset_type=asset_type, owner=owner,
                balance=balance, institution=institution,
                interest_rate=interest_rate, notes=notes,
            )
            self.budget.assets.append(item)

        if self.on_saved:
            self.on_saved(item)
        self.close()


# ---------------------------------------------------------------------------
# Balance update dialog
# ---------------------------------------------------------------------------

class _UpdateBalanceDialog(Adw.Dialog):
    def __init__(self, asset, on_saved):
        super().__init__()
        self.asset    = asset
        self.on_saved = on_saved
        self.set_title(f"Update {asset.name}")
        self.set_content_width(420)

        tv = Adw.ToolbarView()
        self.set_child(tv)
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda b: self.close())
        hdr.pack_start(cancel)

        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        hdr.pack_end(save)

        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        tv.set_content(scroll)

        page  = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        scroll.set_child(page)

        # Current balance (read-only display)
        cur = Adw.ActionRow()
        cur.set_title("Previous balance")
        cur.add_suffix(_num(f"${asset.balance:,.2f}", "dim-label"))
        group.add(cur)

        self.new_bal_row = Adw.SpinRow.new_with_range(0, 99_999_999, 100)
        self.new_bal_row.set_title("New Balance / Value ($)")
        self.new_bal_row.set_digits(2)
        self.new_bal_row.set_value(asset.balance)
        self.new_bal_row.connect("notify::value", self._on_value_changed)
        group.add(self.new_bal_row)

        # Live change preview
        self.change_row = Adw.ActionRow()
        self.change_row.set_title("Change")
        self._change_lbl = Gtk.Label(label="$0.00")
        self._change_lbl.add_css_class("numeric")
        self._change_lbl.set_valign(Gtk.Align.CENTER)
        self.change_row.add_suffix(self._change_lbl)
        group.add(self.change_row)

        self.type_row = Adw.ComboRow()
        self.type_row.set_title("Change Type")
        type_model = Gtk.StringList()
        for lbl in CHANGE_TYPE_LABELS:
            type_model.append(lbl)
        self.type_row.set_model(type_model)
        group.add(self.type_row)

        self.date_row = Adw.EntryRow()
        self.date_row.set_title("Date (YYYY-MM-DD)")
        self.date_row.set_text(date.today().isoformat())
        group.add(self.date_row)

        self.note_row = Adw.EntryRow()
        self.note_row.set_title("Note (optional)")
        group.add(self.note_row)

        self._on_value_changed()

    def _on_value_changed(self, *_):
        change = self.new_bal_row.get_value() - self.asset.balance
        sign   = "+" if change >= 0 else "−"
        css    = "success" if change > 0 else ("error" if change < 0 else "dim-label")
        self._change_lbl.set_text(f"{sign}${abs(change):,.2f}")
        for c in ("success", "error", "dim-label"):
            self._change_lbl.remove_css_class(c)
        self._change_lbl.add_css_class(css)

    def _save(self, _btn):
        new_bal     = self.new_bal_row.get_value()
        change      = new_bal - self.asset.balance
        change_type = CHANGE_TYPES[self.type_row.get_selected()]
        entry_date  = self.date_row.get_text().strip() or date.today().isoformat()
        note        = self.note_row.get_text().strip()

        self.asset.balance_history.append({
            "date":        entry_date,
            "balance":     new_bal,
            "change":      change,
            "change_type": change_type,
            "note":        note,
        })
        self.asset.balance = new_bal

        if self.on_saved:
            self.on_saved(self.asset)
        self.close()


# ---------------------------------------------------------------------------
# Savings goal dialogs  (carried over from previous version)
# ---------------------------------------------------------------------------

class _GoalDialog(Adw.Dialog):
    def __init__(self, budget, on_saved, existing=None):
        super().__init__()
        self.budget   = budget
        self.on_saved = on_saved
        self.existing = existing
        self.set_title("Edit Goal" if existing else "Add Savings Goal")
        self.set_content_width(440)

        tv = Adw.ToolbarView()
        self.set_child(tv)
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda b: self.close())
        hdr.pack_start(cancel)

        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        hdr.pack_end(save)

        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        tv.set_content(scroll)

        page  = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        scroll.set_child(page)

        self.name_row = Adw.EntryRow()
        self.name_row.set_title("Goal Name")
        group.add(self.name_row)

        self.target_row = Adw.SpinRow.new_with_range(0, 9_999_999, 100)
        self.target_row.set_title("Target ($)")
        self.target_row.set_digits(2)
        group.add(self.target_row)

        self.current_row = Adw.SpinRow.new_with_range(0, 9_999_999, 10)
        self.current_row.set_title("Current ($)")
        self.current_row.set_digits(2)
        group.add(self.current_row)

        self.date_row = Adw.EntryRow()
        self.date_row.set_title("Target Date (YYYY-MM-DD, optional)")
        group.add(self.date_row)

        self.notes_row = Adw.EntryRow()
        self.notes_row.set_title("Notes")
        group.add(self.notes_row)

        if existing:
            self.name_row.set_text(existing.name)
            self.target_row.set_value(existing.target)
            self.current_row.set_value(existing.current)
            self.date_row.set_text(existing.target_date or "")
            self.notes_row.set_text(existing.notes or "")

    def _save(self, _btn):
        name = self.name_row.get_text().strip()
        if not name:
            self.name_row.add_css_class("error")
            return
        self.name_row.remove_css_class("error")

        if self.existing:
            self.existing.name        = name
            self.existing.target      = self.target_row.get_value()
            self.existing.current     = self.current_row.get_value()
            self.existing.target_date = self.date_row.get_text().strip()
            self.existing.notes       = self.notes_row.get_text().strip()
            item = self.existing
        else:
            item = SavingsGoal(
                name=name,
                target=self.target_row.get_value(),
                current=self.current_row.get_value(),
                target_date=self.date_row.get_text().strip(),
                notes=self.notes_row.get_text().strip(),
            )
            self.budget.savings_goals.append(item)

        if self.on_saved:
            self.on_saved(item)
        self.close()


class _DepositDialog(Adw.Dialog):
    def __init__(self, goal, on_saved):
        super().__init__()
        self.goal     = goal
        self.on_saved = on_saved
        self.set_title(f"Add to {goal.name}")
        self.set_content_width(380)

        tv = Adw.ToolbarView()
        self.set_child(tv)
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda b: self.close())
        hdr.pack_start(cancel)

        save = Gtk.Button(label="Add")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        hdr.pack_end(save)

        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        tv.set_content(scroll)

        page  = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        scroll.set_child(page)

        cur = Adw.ActionRow()
        cur.set_title("Current")
        cur.add_suffix(_num(f"${goal.current:,.2f}", "dim-label"))
        group.add(cur)

        self.amount_row = Adw.SpinRow.new_with_range(-goal.target, 9_999_999, 10)
        self.amount_row.set_title("Amount to Add ($)")
        self.amount_row.set_subtitle("Negative to correct downward")
        self.amount_row.set_digits(2)
        group.add(self.amount_row)

    def _save(self, _btn):
        self.goal.current = max(0.0, self.goal.current + self.amount_row.get_value())
        if self.on_saved:
            self.on_saved(self.goal)
        self.close()


class _DebtBalanceDialog(Adw.Dialog):
    """Log a manual balance update for a debt."""
    def __init__(self, debt, on_saved):
        super().__init__()
        self.debt     = debt
        self.on_saved = on_saved
        self.set_title(f"Update {debt.name} Balance")
        self.set_content_width(380)

        tv = Adw.ToolbarView()
        self.set_child(tv)
        hdr = Adw.HeaderBar()
        tv.add_top_bar(hdr)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda b: self.close())
        hdr.pack_start(cancel)

        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        hdr.pack_end(save)

        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        tv.set_content(scroll)

        page  = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        scroll.set_child(page)

        old = Adw.ActionRow()
        old.set_title("Previous balance")
        old.add_suffix(_num(f"${debt.balance:,.2f}", "dim-label"))
        group.add(old)

        self.bal_row = Adw.SpinRow.new_with_range(0, 9_999_999, 100)
        self.bal_row.set_title("New Balance ($)")
        self.bal_row.set_digits(2)
        self.bal_row.set_value(debt.balance)
        group.add(self.bal_row)

        self.note_row = Adw.EntryRow()
        self.note_row.set_title("Note (optional)")
        group.add(self.note_row)

    def _save(self, _btn):
        new_bal = self.bal_row.get_value()
        self.debt.balance_history.append({
            "date":    date.today().isoformat(),
            "balance": self.debt.balance,
            "note":    self.note_row.get_text().strip(),
        })
        self.debt.balance = new_bal
        if self.on_saved:
            self.on_saved(self.debt)
        self.close()


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------

class SavingsView(Gtk.Box):
    def __init__(self, budget, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.budget    = budget
        self.on_change = on_change
        self.set_hexpand(True)
        self.set_vexpand(True)

        # ── Header ────────────────────────────────────────────────────────────
        clamp_hdr = Adw.Clamp()
        clamp_hdr.set_maximum_size(860)
        clamp_hdr.set_margin_start(16)
        clamp_hdr.set_margin_end(16)
        clamp_hdr.set_margin_top(20)
        clamp_hdr.set_margin_bottom(8)

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        clamp_hdr.set_child(hdr)

        icon = Gtk.Image.new_from_icon_name("starred-symbolic")
        icon.set_icon_size(Gtk.IconSize.LARGE)
        icon.add_css_class("dim-label")
        hdr.append(icon)

        lbl = Gtk.Label(label="Assets & Goals")
        lbl.add_css_class("title-2")
        lbl.set_hexpand(True)
        lbl.set_xalign(0)
        hdr.append(lbl)

        add_content = Adw.ButtonContent()
        add_content.set_icon_name("list-add-symbolic")
        add_content.set_label("Add Account")
        add_btn = Gtk.Button()
        add_btn.set_child(add_content)
        add_btn.add_css_class("suggested-action")
        add_btn.add_css_class("pill")
        add_btn.connect("clicked", self._on_add_asset)
        hdr.append(add_btn)

        self.append(clamp_hdr)

        # ── Scroll body ───────────────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(860)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)
        clamp.set_margin_bottom(24)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(self.content)
        scroll.set_child(clamp)
        self.append(scroll)

        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        _clear_box(self.content)

        self._build_net_worth()
        self._build_asset_chart()
        self._build_assets()
        self._build_goals()

    # ── Net worth summary ─────────────────────────────────────────────────────

    def _build_net_worth(self):
        group = Adw.PreferencesGroup()
        group.set_title("Net Worth")
        self.content.append(group)

        lb = Gtk.ListBox()
        lb.add_css_class("boxed-list")
        lb.set_selection_mode(Gtk.SelectionMode.NONE)
        group.add(lb)

        total_assets = BudgetCalculator.total_assets(self.budget)
        total_debt   = BudgetCalculator.total_debt_balance(self.budget)
        nw           = BudgetCalculator.net_worth(self.budget)
        est_interest = sum(
            a.balance * a.interest_rate / 100
            for a in self.budget.assets
            if getattr(a, "interest_rate", 0.0) > 0
        )

        for title, val, css in [
            ("Total Assets",  total_assets, "success"),
            ("Total Debt",    total_debt,   "error"),
            ("Net Worth",     nw,           "success" if nw >= 0 else "error"),
        ]:
            row = Adw.ActionRow()
            row.set_title(title)
            row.add_suffix(_num(f"${val:,.2f}", css))
            lb.append(row)

        if est_interest > 0:
            int_row = Adw.ActionRow()
            int_row.set_title("Est. Annual Interest Earnings")
            int_row.set_subtitle(f"${est_interest / 12:,.2f}/month")
            int_row.set_tooltip_text(
                "Simple interest estimate based on current balances and rates. "
                "Actual earnings may vary with compounding and balance changes."
            )
            int_row.add_suffix(_num(f"${est_interest:,.2f}/yr", "success"))
            lb.append(int_row)

    # ── Asset allocation donut ────────────────────────────────────────────────

    def _build_asset_chart(self):
        if not self.budget.assets:
            return

        group = Adw.PreferencesGroup()
        group.set_title("Allocation")
        self.content.append(group)

        # Group by type category
        by_group: dict[str, float] = {}
        for grp, types in ASSET_TYPE_GROUPS.items():
            total = sum(a.balance for a in self.budget.assets if a.asset_type in types)
            if total > 0:
                by_group[grp] = total

        if len(by_group) >= 2:
            chart_data = list(by_group.items())
            chart = DonutChart(chart_data, title="assets")
            group.add(chart)

    # ── Asset accounts ────────────────────────────────────────────────────────

    def _build_assets(self):
        if not self.budget.assets:
            sp = Adw.StatusPage()
            sp.set_title("No Accounts Yet")
            sp.set_description(
                "Add your chequing, savings, TFSA, RRSP, brokerage accounts…"
            )
            sp.set_icon_name("starred-symbolic")
            self.content.append(sp)
            return

        # Group by category
        for grp_name, types in ASSET_TYPE_GROUPS.items():
            grp_assets = [a for a in self.budget.assets if a.asset_type in types]
            if not grp_assets:
                continue

            group = Adw.PreferencesGroup()
            group.set_title(grp_name)
            self.content.append(group)

            lb = Gtk.ListBox()
            lb.add_css_class("boxed-list")
            lb.set_selection_mode(Gtk.SelectionMode.NONE)
            group.add(lb)

            for asset in grp_assets:
                row = Adw.ExpanderRow()
                title = asset.name
                if asset.institution:
                    title = f"{asset.institution}  –  {asset.name}"
                row.set_title(title)
                subtitle_parts = [
                    ASSET_TYPE_LABELS.get(asset.asset_type, asset.asset_type),
                    asset.owner,
                ]
                rate = getattr(asset, "interest_rate", 0.0)
                if rate > 0:
                    est_yr = asset.balance * rate / 100
                    subtitle_parts.append(f"{rate:.2f}%  ·  est. ${est_yr:,.0f}/yr")
                if asset.balance_history:
                    last = asset.balance_history[-1]
                    change = last.get("change", 0)
                    sign   = "+" if change >= 0 else "−"
                    ct     = last.get("change_type", "")
                    subtitle_parts.append(f"last: {sign}${abs(change):,.2f}")
                row.set_subtitle("  ·  ".join(subtitle_parts))

                row.add_suffix(_num(f"${asset.balance:,.2f}"))

                edit_btn = _icon_btn("document-edit-symbolic", "Edit")
                edit_btn.connect("clicked", self._on_edit_asset, asset)
                row.add_suffix(edit_btn)

                del_btn = _icon_btn("edit-delete-symbolic", "Delete", "destructive-action")
                del_btn.connect("clicked", self._on_delete_asset, asset)
                row.add_suffix(del_btn)

                # Inline quick-balance update child row
                row.add_row(_inline_balance_row(asset, self._saved))

                # Balance history child rows
                history = asset.balance_history
                if history:
                    # Line chart (if 2+ points)
                    chart_points = [(h["date"], h["balance"]) for h in history]
                    # Add current balance as last point if not already today
                    if history[-1]["date"] != date.today().isoformat():
                        chart_points.append((date.today().isoformat(), asset.balance))
                    if len(chart_points) >= 2:
                        chart = BalanceLineChart(chart_points)
                        row.add_row(_wrap_chart(chart))

                    # Recent history entries (last 5)
                    for entry in reversed(history[-5:]):
                        hrow = Adw.ActionRow()
                        hrow.set_title(entry.get("date", ""))
                        ct  = entry.get("change_type", "other")
                        lbl = CHANGE_TYPE_LABELS[CHANGE_TYPES.index(ct)] if ct in CHANGE_TYPES else ct
                        note = entry.get("note", "")
                        hrow.set_subtitle(lbl + (f"  ·  {note}" if note else ""))
                        change = entry.get("change", 0)
                        sign   = "+" if change >= 0 else "−"
                        css    = CHANGE_TYPE_CSS.get(ct, "")
                        hrow.add_suffix(_num(f"{sign}${abs(change):,.2f}", css))
                        hrow.add_suffix(_num(f"→ ${entry.get('balance', 0):,.2f}", "dim-label"))
                        row.add_row(hrow)
                else:
                    no_hist = Adw.ActionRow()
                    no_hist.set_title("No updates logged yet")
                    no_hist.add_css_class("dim-label")
                    row.add_row(no_hist)

                lb.append(row)

    # ── Savings goals ─────────────────────────────────────────────────────────

    def _build_goals(self):
        goal_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        goal_hdr.set_margin_top(8)

        goal_lbl = Gtk.Label(label="Savings Goals")
        goal_lbl.add_css_class("title-4")
        goal_lbl.set_hexpand(True)
        goal_lbl.set_xalign(0)
        goal_hdr.append(goal_lbl)

        add_goal_content = Adw.ButtonContent()
        add_goal_content.set_icon_name("list-add-symbolic")
        add_goal_content.set_label("Add Goal")
        add_goal_btn = Gtk.Button()
        add_goal_btn.set_child(add_goal_content)
        add_goal_btn.add_css_class("pill")
        add_goal_btn.connect("clicked", self._on_add_goal)
        goal_hdr.append(add_goal_btn)

        self.content.append(goal_hdr)

        if not self.budget.savings_goals:
            sp = Adw.StatusPage()
            sp.set_title("No Savings Goals")
            sp.set_description("Track emergency funds, vacations, down payments…")
            sp.set_icon_name("non-starred-symbolic")
            self.content.append(sp)
            return

        group = Adw.PreferencesGroup()
        self.content.append(group)

        lb = Gtk.ListBox()
        lb.add_css_class("boxed-list")
        lb.set_selection_mode(Gtk.SelectionMode.NONE)
        group.add(lb)

        for goal in self.budget.savings_goals:
            pct = goal.progress_pct
            row = Adw.ExpanderRow()
            row.set_title(goal.name)
            subtitle = f"${goal.current:,.2f} of ${goal.target:,.2f}  ({pct*100:.0f}%)"
            if goal.target_date:
                subtitle += f"  ·  target {goal.target_date}"
            row.set_subtitle(subtitle)

            bar = Gtk.ProgressBar()
            bar.set_fraction(pct)
            bar.set_valign(Gtk.Align.CENTER)
            bar.set_size_request(80, -1)
            if pct >= 1.0:
                bar.add_css_class("success")
            row.add_suffix(bar)

            dep_btn = _icon_btn("value-increase-symbolic", "Add Funds")
            dep_btn.connect("clicked", self._on_deposit, goal)
            row.add_suffix(dep_btn)

            edit_btn = _icon_btn("document-edit-symbolic", "Edit")
            edit_btn.connect("clicked", self._on_edit_goal, goal)
            row.add_suffix(edit_btn)

            del_btn = _icon_btn("edit-delete-symbolic", "Delete", "destructive-action")
            del_btn.connect("clicked", self._on_delete_goal, goal)
            row.add_suffix(del_btn)

            rem_row = Adw.ActionRow()
            rem_row.set_title("Still needed")
            rem_row.add_suffix(_num(f"${goal.remaining:,.2f}",
                                    "dim-label" if pct >= 1.0 else "warning"))
            row.add_row(rem_row)

            if goal.notes:
                note_row = Adw.ActionRow()
                note_row.set_title(goal.notes)
                note_row.add_css_class("dim-label")
                row.add_row(note_row)

            today = date.today()
            if goal.target_date and goal.remaining > 0:
                try:
                    td = date.fromisoformat(goal.target_date)
                    months_left = max(1, (td.year - today.year) * 12 + (td.month - today.month))
                    if td > today:
                        monthly_needed = goal.remaining / months_left
                        contrib_row = Adw.ActionRow()
                        contrib_row.set_title("Monthly contribution needed")
                        contrib_row.set_subtitle(f"{months_left} months to {td.strftime('%b %Y')}")
                        contrib_row.add_suffix(_num(f"${monthly_needed:,.2f}/mo", "accent"))

                        unallocated = BudgetCalculator.unallocated_discretionary(self.budget)
                        if unallocated >= monthly_needed:
                            contrib_row.set_subtitle(contrib_row.get_subtitle() + "  ·  affordable")
                        row.add_row(contrib_row)
                except (ValueError, TypeError):
                    pass

            lb.append(row)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_add_asset(self, _btn):
        _AssetDialog(self.budget, self._saved).present(self.get_root())

    def _on_edit_asset(self, _btn, asset):
        _AssetDialog(self.budget, self._saved, existing=asset).present(self.get_root())

    def _on_update(self, _btn, asset):
        _UpdateBalanceDialog(asset, self._saved).present(self.get_root())

    def _on_delete_asset(self, _btn, asset):
        self.budget.assets.remove(asset)
        self.on_change()
        self.refresh()

    def _on_add_goal(self, _btn):
        _GoalDialog(self.budget, self._saved).present(self.get_root())

    def _on_edit_goal(self, _btn, goal):
        _GoalDialog(self.budget, self._saved, existing=goal).present(self.get_root())

    def _on_deposit(self, _btn, goal):
        _DepositDialog(goal, self._saved).present(self.get_root())

    def _on_delete_goal(self, _btn, goal):
        self.budget.savings_goals.remove(goal)
        self.on_change()
        self.refresh()

    def _saved(self, _item):
        self.on_change()
        self.refresh()


# ---------------------------------------------------------------------------
# Helpers: wrap widgets into ExpanderRow children
# ---------------------------------------------------------------------------

def _inline_balance_row(asset, on_saved):
    """A child row with a SpinRow + Save button for fast balance updates."""
    spin = Adw.SpinRow.new_with_range(0, 99_999_999, 100)
    spin.set_title("Quick balance update")
    spin.set_subtitle(f"Current: ${asset.balance:,.2f}")
    spin.set_digits(2)
    spin.set_value(asset.balance)
    spin.set_tooltip_text("Enter the new balance and press Save. Logs with today's date and 'other' type.")

    save_btn = Gtk.Button(label="Save")
    save_btn.add_css_class("suggested-action")
    save_btn.set_valign(Gtk.Align.CENTER)

    def _do_save(_btn):
        new_bal = spin.get_value()
        change  = new_bal - asset.balance
        asset.balance_history.append({
            "date":        date.today().isoformat(),
            "balance":     new_bal,
            "change":      change,
            "change_type": "other",
            "note":        "Quick update",
        })
        asset.balance = new_bal
        if on_saved:
            on_saved(asset)

    save_btn.connect("clicked", _do_save)
    spin.add_suffix(save_btn)
    return spin


def _wrap_chart(widget):
    """Wrap a chart widget in a plain ListBoxRow for use as ExpanderRow child."""
    row = Gtk.ListBoxRow()
    row.set_selectable(False)
    row.set_activatable(False)
    widget.set_margin_start(12)
    widget.set_margin_end(12)
    row.set_child(widget)
    return row
