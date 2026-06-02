"""Dashboard view showing budget summary."""

import calendar
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw
from datetime import date, timedelta

from kopilka.logic.calculations import BudgetCalculator


def _amount_row(title, subtitle=None):
    """ActionRow with a right-aligned numeric label suffix. Returns (row, label)."""
    row = Adw.ActionRow()
    row.set_title(title)
    if subtitle:
        row.set_subtitle(subtitle)
    label = Gtk.Label()
    label.add_css_class("numeric")
    label.set_valign(Gtk.Align.CENTER)
    row.add_suffix(label)
    return row, label


def _make_amount_label(text, css=""):
    lbl = Gtk.Label(label=text)
    lbl.add_css_class("numeric")
    if css:
        lbl.add_css_class(css)
    lbl.set_valign(Gtk.Align.CENTER)
    return lbl


def _set_amount(label, amount, negative=False, color_class=None):
    sign = "−" if negative else ""
    label.set_text(f"{sign}${amount:,.2f}")
    for cls in ("success", "warning", "error", "accent", "dim-label"):
        label.remove_css_class(cls)
    if color_class:
        label.add_css_class(color_class)


class Dashboard(Gtk.Box):
    def __init__(self, budget, on_change=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.budget = budget
        self._on_change = on_change
        self.set_hexpand(True)
        self.set_vexpand(True)

        self._banner = Adw.Banner()
        self._banner.set_button_label("Dismiss")
        self._banner.connect("button-clicked", lambda b: b.set_revealed(False))
        self.append(self._banner)

        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        self.append(scroll)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(860)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)
        scroll.set_child(clamp)

        page = Adw.PreferencesPage()
        clamp.set_child(page)

        self._simple_mode = False

        # ── Income Summary ────────────────────────────────────────────────────
        income_group = Adw.PreferencesGroup()
        income_group.set_title("Income")
        page.add(income_group)

        self.gross_row, self.gross_lbl = _amount_row("Monthly Gross")
        income_group.add(self.gross_row)

        self.tax_row, self.tax_lbl = _amount_row(
            "Est. Deductions", "income tax + CPP + EI"
        )
        income_group.add(self.tax_row)

        self.net_row, self.net_lbl = _amount_row("Monthly Net")
        self.net_row.add_css_class("property")
        income_group.add(self.net_row)

        # ── Monthly Budget ────────────────────────────────────────────────────
        self._budget_group = Adw.PreferencesGroup()
        self._budget_group.set_title("Monthly Budget")
        page.add(self._budget_group)
        budget_group = self._budget_group

        self.fixed_row, self.fixed_lbl = _amount_row("Fixed Expenses")
        budget_group.add(self.fixed_row)

        self.debt_row, self.debt_lbl = _amount_row("Debt Payments")
        budget_group.add(self.debt_row)

        self.discretionary_row, self.disc_lbl = _amount_row(
            "Total Discretionary", "net income after fixed costs and debt"
        )
        budget_group.add(self.discretionary_row)

        self.cat_budget_row, self.cat_lbl = _amount_row("Allocated to Categories")
        budget_group.add(self.cat_budget_row)

        self.available_row, self.avail_lbl = _amount_row("Unallocated")
        budget_group.add(self.available_row)

        self.onetimey_row, self.onetimey_lbl = _amount_row(
            "One-time Purchases (YTD)",
            "logged against the annual discretionary pool"
        )
        budget_group.add(self.onetimey_row)

        self.onetimey_rem_row, self.onetimey_rem_lbl = _amount_row(
            "Annual Pool Remaining"
        )
        budget_group.add(self.onetimey_rem_row)

        # ── Bills & Reminders (collapsible) ───────────────────────────────────
        self._bills_container = Adw.PreferencesGroup()
        page.add(self._bills_container)
        self._bills_expander = None
        self._bills_expanded = True

        # ── Net Worth (collapsible) ───────────────────────────────────────────
        self._nw_container = Adw.PreferencesGroup()
        page.add(self._nw_container)
        self._nw_expander = None
        self._nw_expanded = False

        # ── Spending Budgets ──────────────────────────────────────────────────
        self.cat_group = Adw.PreferencesGroup()
        self.cat_group.set_title("Spending Budgets")
        self.cat_group.set_description("This period's spending vs. budget")
        page.add(self.cat_group)

        self._cat_rows = []

        self.refresh(self.budget)

    def set_simple_mode(self, active: bool):
        self._simple_mode = active
        self._budget_group.set_visible(not active)
        self._nw_container.set_visible(not active)
        self._bills_container.set_visible(not active)
        self.tax_row.set_visible(not active)

    def refresh(self, budget):
        self.budget = budget

        self._check_banner(budget)

        self._budget_group.set_visible(not self._simple_mode)
        self._nw_container.set_visible(not self._simple_mode)
        self._bills_container.set_visible(not self._simple_mode)
        self.tax_row.set_visible(not self._simple_mode)

        gross = BudgetCalculator.monthly_gross_income(budget)
        net = BudgetCalculator.monthly_net_income(budget)
        tax = gross - net
        fixed = BudgetCalculator.monthly_fixed_costs(budget)
        debt = BudgetCalculator.monthly_debt_payments(budget)
        discretionary = BudgetCalculator.available_to_spend(budget)
        cat_budgets = BudgetCalculator.monthly_category_budgets(budget)
        unallocated = BudgetCalculator.unallocated_discretionary(budget)

        _set_amount(self.gross_lbl, gross)
        _set_amount(self.tax_lbl, tax, negative=True, color_class="dim-label")
        _set_amount(self.net_lbl, net, color_class="accent")
        _set_amount(self.fixed_lbl, fixed, negative=True)
        _set_amount(self.debt_lbl, debt, negative=True)
        _set_amount(self.disc_lbl, discretionary)
        _set_amount(self.cat_lbl, cat_budgets, negative=True)

        if unallocated < 0:
            _set_amount(self.avail_lbl, abs(unallocated), negative=True, color_class="error")
        elif unallocated < 50:
            _set_amount(self.avail_lbl, unallocated, color_class="warning")
        else:
            _set_amount(self.avail_lbl, unallocated, color_class="success")

        ot_spent   = BudgetCalculator.yearly_one_time_spending(budget)
        annual_pool = max(0.0, BudgetCalculator.available_to_spend(budget)) * 12
        ot_remain  = annual_pool - ot_spent
        _set_amount(self.onetimey_lbl, ot_spent, negative=True,
                    color_class="dim-label" if ot_spent == 0 else "warning")
        if ot_remain < 0:
            _set_amount(self.onetimey_rem_lbl, abs(ot_remain), negative=True, color_class="error")
        else:
            _set_amount(self.onetimey_rem_lbl, ot_remain, color_class="success")

        # ── Bills (collapsible expander) ──────────────────────────────────────
        if self._bills_expander:
            self._bills_expanded = self._bills_expander.get_expanded()
            self._bills_container.remove(self._bills_expander)

        bills_exp = Adw.ExpanderRow()
        bills_exp.set_title("Upcoming Bills")
        bills_exp.set_expanded(self._bills_expanded)

        if self._on_change:
            add_btn = Gtk.Button()
            add_btn.set_icon_name("list-add-symbolic")
            add_btn.add_css_class("flat")
            add_btn.add_css_class("circular")
            add_btn.set_valign(Gtk.Align.CENTER)
            add_btn.set_tooltip_text("Add bill")
            add_btn.connect("clicked", self._on_add_bill)
            bills_exp.add_suffix(add_btn)

        look_ahead = getattr(budget, "bills_look_ahead_days", 7)
        upcoming = BudgetCalculator.bills_due_soon(budget, days_ahead=look_ahead)
        if not upcoming:
            row = Adw.ActionRow()
            row.set_title(f"No bills due in the next {look_ahead} days")
            row.set_sensitive(False)
            bills_exp.add_row(row)
        else:
            for exp, due_date, days_until in upcoming:
                row = Adw.ActionRow()
                row.set_title(exp.name)
                if days_until == 0:
                    row.set_subtitle("Due today")
                    row.add_css_class("error")
                elif days_until == 1:
                    row.set_subtitle("Due tomorrow")
                    row.add_css_class("warning")
                else:
                    row.set_subtitle(f"Due in {days_until} days  ({due_date.strftime('%b %-d')})")
                row.add_suffix(_make_amount_label(f"${exp.amount:,.2f}"))
                bills_exp.add_row(row)

        self._bills_container.add(bills_exp)
        self._bills_expander = bills_exp

        # ── Net Worth (collapsible expander) ──────────────────────────────────
        if self._nw_expander:
            self._nw_expanded = self._nw_expander.get_expanded()
            self._nw_container.remove(self._nw_expander)

        total_sav  = BudgetCalculator.total_savings(budget)
        total_debt = BudgetCalculator.total_debt_balance(budget)
        nw         = BudgetCalculator.net_worth(budget)

        nw_exp = Adw.ExpanderRow()
        nw_exp.set_title("Net Worth")
        nw_sign = "" if nw >= 0 else "−"
        nw_exp.set_subtitle(f"{nw_sign}${abs(nw):,.2f}")
        nw_exp.set_expanded(self._nw_expanded)

        sav_row = Adw.ActionRow()
        sav_row.set_title("Savings & Investments")
        sav_row.add_suffix(_make_amount_label(f"${total_sav:,.2f}", "success"))
        nw_exp.add_row(sav_row)

        debt_bal_row = Adw.ActionRow()
        debt_bal_row.set_title("Total Debt")
        debt_bal_row.add_suffix(_make_amount_label(f"−${total_debt:,.2f}"))
        nw_exp.add_row(debt_bal_row)

        self._nw_container.add(nw_exp)
        self._nw_expander = nw_exp

        # ── Rebuild category rows ─────────────────────────────────────────────
        for row in self._cat_rows:
            self.cat_group.remove(row)
        self._cat_rows.clear()

        if not budget.categories:
            row = Adw.ActionRow()
            row.set_title("No spending categories yet")
            row.set_subtitle("Add categories in the sidebar")
            img = Gtk.Image.new_from_icon_name("tag-symbolic")
            img.set_icon_size(Gtk.IconSize.NORMAL)
            img.add_css_class("dim-label")
            row.add_prefix(img)
            self.cat_group.add(row)
            self._cat_rows.append(row)
            return

        today = date.today()
        week_start  = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        sem_start   = date(today.year, 1, 1) if today.month <= 6 else date(today.year, 7, 1)
        year_start  = date(today.year, 1, 1)

        for cat in budget.categories:
            effective = BudgetCalculator.category_effective_budget(cat, budget.spending, today)
            rollover  = BudgetCalculator.category_rollover(cat, budget.spending, today)

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
                e.amount for e in budget.spending
                if e.category_id == cat.id and e.date >= period_start.isoformat()
            )
            period_budget = effective

            row = Adw.ActionRow()
            row.set_title(cat.name)
            subtitle = f"${period_spent:,.2f} of ${period_budget:,.2f}/{period_label}"
            if abs(rollover) > 0.01:
                sign = "+" if rollover > 0 else "−"
                subtitle += f"  ·  rollover {sign}${abs(rollover):,.2f}"
            row.set_subtitle(subtitle)

            if period_budget > 0:
                pct = min(period_spent / period_budget, 1.0)
                bar = Gtk.ProgressBar()
                bar.set_fraction(pct)
                bar.set_valign(Gtk.Align.CENTER)
                bar.set_size_request(100, -1)
                bar.set_tooltip_text(
                    f"${period_spent:,.2f} of ${period_budget:,.2f} — {pct*100:.0f}%"
                )
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

            row.add_suffix(_make_amount_label(f"${period_spent:,.2f}", "caption"))

            self.cat_group.add(row)
            self._cat_rows.append(row)

    def _check_banner(self, budget):
        today = date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]
        days_left = last_day - today.day

        if days_left <= 2 and budget.categories:
            month_start = today.replace(day=1)
            spent = sum(e.amount for e in budget.spending if e.date >= month_start.isoformat())
            monthly_budget = BudgetCalculator.monthly_category_budgets(budget)
            if monthly_budget > 0:
                diff = monthly_budget - spent
                day_str = "today" if days_left == 0 else f"in {days_left} day{'s' if days_left != 1 else ''}"
                sign = "over" if diff < 0 else "under"
                self._banner.set_title(f"Month ends {day_str} — ${abs(diff):,.0f} {sign} budget")
                self._banner.set_revealed(True)
                return
        elif budget.income and not budget.categories:
            self._banner.set_title("Add spending categories to start tracking your budget")
            self._banner.set_revealed(True)
            return
        elif budget.categories and budget.spending:
            last = max(budget.spending, key=lambda e: e.date)
            days_since = (today - date.fromisoformat(last.date)).days
            if days_since >= 14:
                self._banner.set_title(f"No spending logged in {days_since} days — keeping up?")
                self._banner.set_revealed(True)
                return
        self._banner.set_revealed(False)

    def _on_add_bill(self, _btn):
        from kopilka.ui.forms import AddExpenseDialog
        AddExpenseDialog(
            self.budget,
            on_saved=lambda _: self._on_change() if self._on_change else None,
        ).present(self.get_root())
