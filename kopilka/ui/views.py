"""List views for Income, Expense, Debt, and Category."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw

from kopilka.logic.calculations import BudgetCalculator
from kopilka.ui.forms import AddIncomeDialog, AddExpenseDialog, AddDebtDialog, AddCategoryDialog
from datetime import date, timedelta


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _num_lbl(text, css=""):
    lbl = Gtk.Label(label=text)
    lbl.add_css_class("numeric")
    if css:
        lbl.add_css_class(css)
    lbl.set_valign(Gtk.Align.CENTER)
    return lbl


def _clear_box(box):
    child = box.get_first_child()
    while child:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def _add_button(icon_name, label):
    """Button with icon + label using Adw.ButtonContent."""
    content = Adw.ButtonContent()
    content.set_icon_name(icon_name)
    content.set_label(label)
    btn = Gtk.Button()
    btn.set_child(content)
    btn.add_css_class("suggested-action")
    btn.add_css_class("pill")
    return btn


def _icon_button(icon_name, tooltip, css_class=None):
    btn = Gtk.Button()
    btn.set_icon_name(icon_name)
    btn.set_tooltip_text(tooltip)
    btn.add_css_class("flat")
    btn.add_css_class("circular")
    btn.set_valign(Gtk.Align.CENTER)
    if css_class:
        btn.add_css_class(css_class)
    return btn


def _list_header(title, add_btn):
    """A clamp-wrapped header row with title + add button."""
    clamp = Adw.Clamp()
    clamp.set_maximum_size(860)
    clamp.set_margin_start(16)
    clamp.set_margin_end(16)
    clamp.set_margin_top(20)
    clamp.set_margin_bottom(12)

    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    clamp.set_child(box)
    return clamp, box


def _list_view_skeleton(title, icon_name, add_label, on_add):
    """Return (outer_box, content_box) for a standard list view."""
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    outer.set_hexpand(True)
    outer.set_vexpand(True)

    # Header inside a clamp
    clamp_header = Adw.Clamp()
    clamp_header.set_maximum_size(860)
    clamp_header.set_margin_start(16)
    clamp_header.set_margin_end(16)
    clamp_header.set_margin_top(20)
    clamp_header.set_margin_bottom(8)

    header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    clamp_header.set_child(header_box)

    icon = Gtk.Image.new_from_icon_name(icon_name)
    icon.set_icon_size(Gtk.IconSize.LARGE)
    icon.add_css_class("dim-label")
    header_box.append(icon)

    lbl = Gtk.Label(label=title)
    lbl.add_css_class("title-2")
    lbl.set_hexpand(True)
    lbl.set_xalign(0)
    header_box.append(lbl)

    add_btn = _add_button("list-add-symbolic", add_label)
    add_btn.connect("clicked", on_add)
    header_box.append(add_btn)

    outer.append(clamp_header)

    # Scrollable content
    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_hexpand(True)

    content = Adw.Clamp()
    content.set_maximum_size(860)
    content.set_margin_start(16)
    content.set_margin_end(16)
    content.set_margin_bottom(24)

    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    content.set_child(inner)
    scroll.set_child(content)
    outer.append(scroll)

    return outer, inner


def _make_listbox():
    lb = Gtk.ListBox()
    lb.add_css_class("boxed-list")
    lb.set_selection_mode(Gtk.SelectionMode.NONE)
    return lb


def _confirm_delete(heading: str, body: str, parent, on_confirm) -> None:
    """Show a destructive-action confirmation dialog; call on_confirm() if the user confirms."""
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


# ---------------------------------------------------------------------------
# Income View
# ---------------------------------------------------------------------------

class IncomeView(Gtk.Box):
    def __init__(self, budget, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.budget = budget
        self.on_change = on_change

        self.outer, self.content = _list_view_skeleton(
            "Income Sources", "value-increase-symbolic", "Add Income", self._on_add
        )
        self.append(self.outer)
        self.refresh()

    def refresh(self):
        _clear_box(self.content)

        if not self.budget.income:
            sp = Adw.StatusPage()
            sp.set_title("No Income Sources")
            sp.set_description("Add your income to see budget calculations")
            sp.set_icon_name("value-increase-symbolic")
            self.content.append(sp)
            return

        lb = _make_listbox()
        self.content.append(lb)

        for inc in self.budget.income:
            row = Adw.ActionRow()
            row.set_title(inc.name)
            parts = [inc.owner, inc.frequency]
            if inc.frequency == "biweekly":
                payday = BudgetCalculator.next_biweekly_payday(getattr(inc, "next_payday", ""))
                if payday:
                    days = (payday - date.today()).days
                    if days == 0:
                        parts.append("payday today")
                    elif days == 1:
                        parts.append("payday tomorrow")
                    else:
                        parts.append(f"payday {payday.strftime('%-d %b')} ({days}d)")
            if not inc.active:
                parts.append("inactive")
            row.set_subtitle("  ·  ".join(parts))

            amt = Gtk.Label(label=f"${inc.amount:,.2f}")
            amt.add_css_class("numeric")
            amt.set_valign(Gtk.Align.CENTER)
            row.add_suffix(amt)

            edit_btn = _icon_button("document-edit-symbolic", "Edit")
            edit_btn.connect("clicked", self._on_edit, inc)
            row.add_suffix(edit_btn)

            del_btn = _icon_button("edit-delete-symbolic", "Delete", "destructive-action")
            del_btn.connect("clicked", self._on_delete, inc)
            row.add_suffix(del_btn)

            lb.append(row)

        # Summary row
        gross = BudgetCalculator.monthly_gross_income(self.budget)
        summary = Adw.ActionRow()
        summary.set_title("Total Monthly Gross")
        total_lbl = Gtk.Label(label=f"${gross:,.2f}")
        total_lbl.add_css_class("numeric")
        total_lbl.add_css_class("accent")
        total_lbl.set_valign(Gtk.Align.CENTER)
        summary.add_suffix(total_lbl)
        lb.append(summary)

    def _on_add(self, _btn):
        AddIncomeDialog(self.budget, on_saved=self._saved).present(self.get_root())

    def _on_edit(self, _btn, inc):
        AddIncomeDialog(self.budget, on_saved=self._saved, existing=inc).present(self.get_root())

    def _on_delete(self, _btn, inc):
        def _do():
            self.budget.income.remove(inc)
            self.on_change()
            self.refresh()
        _confirm_delete("Remove Income Source?", f'"{inc.name}" will be permanently removed.', self.get_root(), _do)

    def _saved(self, _item):
        self.on_change()
        self.refresh()


# ---------------------------------------------------------------------------
# Expense View
# ---------------------------------------------------------------------------

class ExpenseView(Gtk.Box):
    def __init__(self, budget, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.budget = budget
        self.on_change = on_change

        self.outer, self.content = _list_view_skeleton(
            "Fixed Expenses", "value-decrease-symbolic", "Add Expense", self._on_add
        )
        self.append(self.outer)
        self.refresh()

    def refresh(self):
        _clear_box(self.content)

        if not self.budget.expenses_fixed:
            sp = Adw.StatusPage()
            sp.set_title("No Fixed Expenses")
            sp.set_description("Add rent, subscriptions, and other recurring bills")
            sp.set_icon_name("value-decrease-symbolic")
            self.content.append(sp)
            return

        lb = _make_listbox()
        self.content.append(lb)

        for exp in self.budget.expenses_fixed:
            row = Adw.ActionRow()
            row.set_title(exp.name)
            parts = [exp.frequency]
            # Human-readable due date hint
            freq = exp.frequency
            due_day     = getattr(exp, "due_day",     0)
            due_weekday = getattr(exp, "due_weekday", -1)
            due_doy     = getattr(exp, "due_doy",     0)
            _WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            if freq == "weekly" and due_weekday >= 0:
                parts.append(f"due {_WEEKDAY_NAMES[due_weekday]}s")
            elif freq == "yearly" and due_doy > 0:
                import datetime as _dt
                _d = _dt.date(2024, 1, 1) + _dt.timedelta(days=due_doy - 1)
                parts.append(f"due {_d.strftime('%-d %b')}")
            elif due_day > 0:
                parts.append(f"due {due_day}{_ordinal(due_day)}")
            if not exp.active:
                parts.append("inactive")
            if exp.notes:
                parts.append(exp.notes)
            row.set_subtitle("  ·  ".join(parts))

            amt = Gtk.Label(label=f"${exp.amount:,.2f}")
            amt.add_css_class("numeric")
            amt.set_valign(Gtk.Align.CENTER)
            row.add_suffix(amt)

            edit_btn = _icon_button("document-edit-symbolic", "Edit")
            edit_btn.connect("clicked", self._on_edit, exp)
            row.add_suffix(edit_btn)

            del_btn = _icon_button("edit-delete-symbolic", "Delete", "destructive-action")
            del_btn.connect("clicked", self._on_delete, exp)
            row.add_suffix(del_btn)

            lb.append(row)

        total = BudgetCalculator.monthly_fixed_costs(self.budget)
        summary = Adw.ActionRow()
        summary.set_title("Total Monthly Fixed Costs")
        total_lbl = Gtk.Label(label=f"${total:,.2f}")
        total_lbl.add_css_class("numeric")
        total_lbl.add_css_class("accent")
        total_lbl.set_valign(Gtk.Align.CENTER)
        summary.add_suffix(total_lbl)
        lb.append(summary)

    def _on_add(self, _btn):
        AddExpenseDialog(self.budget, on_saved=self._saved).present(self.get_root())

    def _on_edit(self, _btn, exp):
        AddExpenseDialog(self.budget, on_saved=self._saved, existing=exp).present(self.get_root())

    def _on_delete(self, _btn, exp):
        def _do():
            self.budget.expenses_fixed.remove(exp)
            self.on_change()
            self.refresh()
        _confirm_delete("Remove Expense?", f'"{exp.name}" will be permanently removed.', self.get_root(), _do)

    def _saved(self, _item):
        self.on_change()
        self.refresh()


# ---------------------------------------------------------------------------
# Debt View
# ---------------------------------------------------------------------------

class DebtView(Gtk.Box):
    def __init__(self, budget, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.budget = budget
        self.on_change = on_change
        self._whatif_extra = 0.0

        self.outer, self.content = _list_view_skeleton(
            "Debt", "alarm-symbolic", "Add Debt", self._on_add
        )
        self.append(self.outer)
        self.refresh()

    def refresh(self):
        _clear_box(self.content)

        if not self.budget.debt:
            sp = Adw.StatusPage()
            sp.set_title("No Debt Entries")
            sp.set_description("Track loans, credit cards, and student debt")
            sp.set_icon_name("alarm-symbolic")
            self.content.append(sp)
            return

        lb = _make_listbox()
        self.content.append(lb)

        for debt in self.budget.debt:
            payoff  = BudgetCalculator.debt_payoff(debt)
            monthly = BudgetCalculator._to_monthly(debt.payment, debt.frequency)

            row = Adw.ExpanderRow()
            row.set_title(debt.name)
            row.set_subtitle(
                f"${debt.balance:,.2f} balance  ·  "
                f"{debt.rate:.2f}% APR  ·  "
                f"${monthly:,.2f}/mo"
            )

            upd_btn = _icon_button("document-edit-symbolic", "Update Balance")
            upd_btn.connect("clicked", self._on_update_balance, debt)
            row.add_suffix(upd_btn)

            edit_btn = _icon_button("document-properties-symbolic", "Edit Terms")
            edit_btn.connect("clicked", self._on_edit, debt)
            row.add_suffix(edit_btn)

            del_btn = _icon_button("edit-delete-symbolic", "Delete", "destructive-action")
            del_btn.connect("clicked", self._on_delete, debt)
            row.add_suffix(del_btn)

            if payoff["warning"]:
                wr = Adw.ActionRow()
                wr.set_title(payoff["warning"])
                wr.add_css_class("error")
                row.add_row(wr)
            else:
                months = payoff["months"]
                y, m   = months // 12, months % 12
                dur    = " ".join(filter(None, [f"{y} yr" if y else "", f"{m} mo" if m else ""])) or "< 1 mo"

                r1 = Adw.ActionRow()
                r1.set_title("Paid off")
                r1.add_suffix(_num_lbl(f"{payoff['payoff_date'].strftime('%B %Y')}  ({dur})"))
                row.add_row(r1)

                r2 = Adw.ActionRow()
                r2.set_title("Total interest")
                r2.add_suffix(_num_lbl(f"${payoff['total_interest']:,.2f}", "warning"))
                row.add_row(r2)

                r3 = Adw.ActionRow()
                r3.set_title("Total cost (principal + interest)")
                r3.add_suffix(_num_lbl(f"${debt.balance + payoff['total_interest']:,.2f}"))
                row.add_row(r3)

            # Balance history (last 3 entries)
            history = getattr(debt, "balance_history", [])
            if history:
                h_header = Adw.ActionRow()
                h_header.set_title("Balance history")
                h_header.add_css_class("dim-label")
                row.add_row(h_header)
                for entry in reversed(history[-3:]):
                    hr = Adw.ActionRow()
                    hr.set_title(entry.get("date", ""))
                    note = entry.get("note", "")
                    if note:
                        hr.set_subtitle(note)
                    hr.add_suffix(_num_lbl(f"${entry.get('balance', 0):,.2f}", "dim-label"))
                    row.add_row(hr)

            lb.append(row)

        total = BudgetCalculator.monthly_debt_payments(self.budget)
        summary = Adw.ActionRow()
        summary.set_title("Total Monthly Payments")
        summary.add_suffix(_num_lbl(f"${total:,.2f}", "accent"))
        lb.append(summary)

        # Avalanche / snowball strategy comparison
        if len(self.budget.debt) > 1:
            self._build_strategy_section()

        self._build_whatif_section()

    def _build_strategy_section(self):
        group = Adw.PreferencesGroup()
        group.set_title("Payoff Strategies")
        group.set_description("Compare interest saved by payoff order")
        self.content.append(group)

        try:
            av_list, av_total = BudgetCalculator.debt_avalanche(self.budget)
            sb_list, sb_total = BudgetCalculator.debt_snowball(self.budget)
        except Exception:
            return

        lb = _make_listbox()
        group.add(lb)

        for label, strategy, total_int in [
            ("Avalanche (highest APR first)", av_list, av_total),
            ("Snowball (lowest balance first)", sb_list, sb_total),
        ]:
            row = Adw.ExpanderRow()
            row.set_title(label)
            row.set_subtitle(f"Total interest: ${total_int:,.2f}")
            row.add_suffix(_num_lbl(f"${total_int:,.2f}", "warning"))

            for entry in strategy:
                d = entry["debt"]
                child = Adw.ActionRow()
                child.set_title(f"{entry['order']}. {d.name}")
                if entry["warning"]:
                    child.set_subtitle(entry["warning"])
                elif entry["payoff_date"]:
                    child.set_subtitle(f"paid off {entry['payoff_date'].strftime('%b %Y')}")
                if entry["total_interest"] is not None:
                    child.add_suffix(_num_lbl(f"+${entry['total_interest']:,.2f} interest", "dim-label"))
                row.add_row(child)

            lb.append(row)

    def _build_whatif_section(self):
        if not self.budget.debt:
            return
        import types
        group = Adw.PreferencesGroup()
        group.set_title("What If?")
        group.set_description("Extra monthly payment applied to every debt")
        self.content.append(group)

        extra_row = Adw.SpinRow.new_with_range(0, 5_000, 25)
        extra_row.set_title("Extra Payment / Month ($)")
        extra_row.set_digits(0)
        extra_row.set_value(self._whatif_extra)
        extra_row.set_tooltip_text(
            "Extra amount added to every debt's minimum payment. "
            "Results update live below."
        )
        group.add(extra_row)

        results_lb = Gtk.ListBox()
        results_lb.add_css_class("boxed-list")
        results_lb.set_selection_mode(Gtk.SelectionMode.NONE)
        group.add(results_lb)

        def _update(spin, _param=None):
            self._whatif_extra = spin.get_value()
            child = results_lb.get_first_child()
            while child:
                nxt = child.get_next_sibling()
                results_lb.remove(child)
                child = nxt

            if self._whatif_extra <= 0:
                ph = Adw.ActionRow()
                ph.set_title("Set an extra payment above to see the impact")
                ph.add_css_class("dim-label")
                results_lb.append(ph)
                return

            total_saved = 0.0
            for debt in self.budget.debt:
                monthly = BudgetCalculator._to_monthly(debt.payment, debt.frequency)
                payoff  = BudgetCalculator.debt_payoff(debt)
                mock = types.SimpleNamespace(
                    balance=debt.balance, rate=debt.rate,
                    payment=monthly + self._whatif_extra, frequency="monthly",
                )
                new_payoff = BudgetCalculator.debt_payoff(mock)

                r = Adw.ActionRow()
                r.set_title(debt.name)
                if payoff["warning"] or new_payoff["warning"]:
                    r.set_subtitle(new_payoff["warning"] or payoff["warning"] or "")
                else:
                    months_saved = (payoff["months"] or 0) - (new_payoff["months"] or 0)
                    int_saved    = (payoff["total_interest"] or 0.0) - (new_payoff["total_interest"] or 0.0)
                    total_saved += int_saved
                    r.set_subtitle(
                        f"Paid off {new_payoff['payoff_date'].strftime('%b %Y')}  ·  "
                        f"{months_saved} mo sooner"
                    )
                    r.add_suffix(_num_lbl(f"-${int_saved:,.2f}", "success"))
                    r.add_css_class("success")
                results_lb.append(r)

            if len(self.budget.debt) > 1 and total_saved > 0:
                tot = Adw.ActionRow()
                tot.set_title("Total interest saved")
                tot.add_suffix(_num_lbl(f"${total_saved:,.2f}", "success"))
                results_lb.append(tot)

        extra_row.connect("notify::value", _update)
        _update(extra_row)

    def _on_add(self, _btn):
        AddDebtDialog(self.budget, on_saved=self._saved).present(self.get_root())

    def _on_edit(self, _btn, debt):
        AddDebtDialog(self.budget, on_saved=self._saved, existing=debt).present(self.get_root())

    def _on_update_balance(self, _btn, debt):
        from kopilka.ui.savings import _DebtBalanceDialog
        _DebtBalanceDialog(debt, self._saved).present(self.get_root())

    def _on_delete(self, _btn, debt):
        def _do():
            self.budget.debt.remove(debt)
            self.on_change()
            self.refresh()
        _confirm_delete("Remove Debt?", f'"{debt.name}" will be permanently removed.', self.get_root(), _do)

    def _saved(self, _item):
        self.on_change()
        self.refresh()


# ---------------------------------------------------------------------------
# Category View
# ---------------------------------------------------------------------------

class CategoryView(Gtk.Box):
    def __init__(self, budget, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.budget = budget
        self.on_change = on_change

        self.outer, self.content = _list_view_skeleton(
            "Spending Categories", "tag-symbolic", "Add Category", self._on_add
        )
        self.append(self.outer)
        self.refresh()

    def refresh(self):
        _clear_box(self.content)

        if not self.budget.categories:
            sp = Adw.StatusPage()
            sp.set_title("No Categories")
            sp.set_description("Create categories to plan your discretionary spending")
            sp.set_icon_name("tag-symbolic")
            self.content.append(sp)
            return

        lb = _make_listbox()
        self.content.append(lb)

        today = date.today()
        week_start  = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        sem_start   = date(today.year, 1, 1) if today.month <= 6 else date(today.year, 7, 1)
        year_start  = date(today.year, 1, 1)

        for cat in self.budget.categories:
            effective = BudgetCalculator.category_effective_budget(cat, self.budget.spending, today)

            if cat.budget_period == "weekly":
                period_start = week_start
                period_label = "wk"
            elif cat.budget_period == "semesterly":
                period_start = sem_start
                period_label = "sem"
            elif cat.budget_period == "yearly":
                period_start = year_start
                period_label = "yr"
            else:
                period_start = month_start
                period_label = "mo"

            period_spent = sum(
                e.amount for e in self.budget.spending
                if e.category_id == cat.id and e.date >= period_start.isoformat()
            )

            row = Adw.ActionRow()
            row.set_title(cat.name)
            shared = "Shared" if cat.shared else "Personal"
            this_month = cat.budget_for_month(today.month)
            subtitle = f"{shared}  ·  ${cat.budget_amount:,.2f}/{cat.budget_period}  ·  ${period_spent:,.2f} of ${effective:,.2f}/{period_label}"
            if abs(this_month - cat.budget_monthly) > 0.01:
                subtitle += f"  ·  ${this_month:,.2f}/mo this month"
            row.set_subtitle(subtitle)

            if effective > 0:
                pct = min(period_spent / effective, 1.0)
                bar = Gtk.ProgressBar()
                bar.set_fraction(pct)
                bar.set_valign(Gtk.Align.CENTER)
                bar.set_size_request(90, -1)
                bar.set_tooltip_text(f"${period_spent:,.2f} of ${effective:,.2f} — {pct*100:.0f}%")
                bar.update_property(
                    [Gtk.AccessibleProperty.LABEL],
                    [f"{cat.name}: {pct*100:.0f}% of {period_label} budget used"],
                )
                for cls in ("error", "warning"):
                    bar.remove_css_class(cls)
                if pct >= 1.0:
                    bar.add_css_class("error")
                elif pct >= 0.8:
                    bar.add_css_class("warning")
                row.add_suffix(bar)

            edit_btn = _icon_button("document-edit-symbolic", "Edit")
            edit_btn.connect("clicked", self._on_edit, cat)
            row.add_suffix(edit_btn)

            del_btn = _icon_button("edit-delete-symbolic", "Delete", "destructive-action")
            del_btn.connect("clicked", self._on_delete, cat)
            row.add_suffix(del_btn)

            lb.append(row)

        # Allocation summary — use current month so overrides are reflected
        allocated = BudgetCalculator.monthly_category_budgets(self.budget)
        unallocated = BudgetCalculator.unallocated_discretionary(self.budget)

        summary = Adw.ActionRow()
        summary.set_title("Allocated this month")
        alloc_lbl = Gtk.Label(label=f"${allocated:,.2f}/month")
        alloc_lbl.add_css_class("numeric")
        alloc_lbl.set_valign(Gtk.Align.CENTER)
        summary.add_suffix(alloc_lbl)
        lb.append(summary)

        unalloc = Adw.ActionRow()
        unalloc.set_title("Unallocated this month")
        unalloc_lbl = Gtk.Label(label=f"${unallocated:,.2f}/month")
        unalloc_lbl.add_css_class("numeric")
        unalloc_lbl.add_css_class("success" if unallocated >= 0 else "error")
        unalloc_lbl.set_valign(Gtk.Align.CENTER)
        unalloc.add_suffix(unalloc_lbl)
        lb.append(unalloc)

    def _on_add(self, _btn):
        AddCategoryDialog(self.budget, on_saved=self._saved).present(self.get_root())

    def _on_edit(self, _btn, cat):
        AddCategoryDialog(self.budget, on_saved=self._saved, existing=cat).present(self.get_root())

    def _on_delete(self, _btn, cat):
        def _do():
            self.budget.categories.remove(cat)
            self.on_change()
            self.refresh()
        _confirm_delete("Remove Category?", f'"{cat.name}" and all its budget settings will be permanently removed.', self.get_root(), _do)

    def _saved(self, _item):
        self.on_change()
        self.refresh()
