"""Forms for adding and editing budget items."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw
from datetime import date

from kopilka.model.budget import IncomeSource, FixedExpense, Debt, SpendingCategory, SpendingEntry
from kopilka.logic.calculations import BudgetCalculator


FREQUENCIES       = ["weekly", "biweekly", "monthly", "semesterly", "yearly", "once"]
FREQUENCY_LABELS  = ["Weekly", "Bi-weekly", "Monthly", "Semesterly (2×/yr)", "Yearly", "One-time"]
CATEGORY_PERIODS  = ["weekly", "monthly", "semesterly", "yearly"]
CATEGORY_PERIOD_LABELS = ["Weekly", "Monthly", "Semesterly", "Yearly"]


def _freq_list():
    sl = Gtk.StringList()
    for label in FREQUENCY_LABELS:
        sl.append(label)
    return sl


def _build_toolbar_view(title, on_save):
    """Return (toolbar_view, header) wired with Cancel/Save buttons."""
    toolbar_view = Adw.ToolbarView()
    header = Adw.HeaderBar()

    cancel_btn = Gtk.Button(label="Cancel")
    cancel_btn.connect("clicked", lambda b: b.get_root().close())
    header.pack_start(cancel_btn)

    save_btn = Gtk.Button(label="Save")
    save_btn.add_css_class("suggested-action")
    save_btn.connect("clicked", on_save)
    header.pack_end(save_btn)

    toolbar_view.add_top_bar(header)
    return toolbar_view


# ---------------------------------------------------------------------------
# Income
# ---------------------------------------------------------------------------

class AddIncomeDialog(Adw.Dialog):
    def __init__(self, budget, on_saved=None, existing=None):
        super().__init__()
        self.budget = budget
        self.on_saved = on_saved
        self.existing = existing

        self.set_title("Edit Income" if existing else "Add Income")
        self.set_content_width(440)

        toolbar_view = _build_toolbar_view(self.get_title(), self._on_save)
        self.set_child(toolbar_view)

        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        toolbar_view.set_content(scroll)

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        scroll.set_child(page)

        self.name_row = Adw.EntryRow()
        self.name_row.set_title("Name")
        group.add(self.name_row)

        self.owner_row = Adw.ComboRow()
        self.owner_row.set_title("Owner")
        owners = Gtk.StringList()
        for o in budget.couple + ["Shared"]:
            owners.append(o)
        self.owner_row.set_model(owners)
        group.add(self.owner_row)

        self.amount_row = Adw.SpinRow.new_with_range(0, 9_999_999, 1)
        self.amount_row.set_title("Amount ($)")
        self.amount_row.set_digits(2)
        self.amount_row.set_tooltip_text("Amount received per pay period")
        group.add(self.amount_row)

        self.freq_row = Adw.ComboRow()
        self.freq_row.set_title("Frequency")
        self.freq_row.set_model(_freq_list())
        self.freq_row.set_selected(2)  # monthly default
        self.freq_row.set_tooltip_text("How often you receive this payment")
        group.add(self.freq_row)

        self.date_row = Adw.EntryRow()
        self.date_row.set_title("Date (YYYY-MM-DD)")
        self.date_row.set_text(__import__("datetime").date.today().isoformat())
        self.date_row.set_visible(False)
        self.date_row.set_tooltip_text("Date the one-time payment was received")
        group.add(self.date_row)

        self.freq_row.connect("notify::selected", self._on_freq_changed_income)

        self.taxed_row = Adw.SwitchRow()
        self.taxed_row.set_title("Taxable Income")
        self.taxed_row.set_tooltip_text("Include this income in the tax and deduction estimate")
        self.taxed_row.set_active(True)
        group.add(self.taxed_row)

        self.cpp_ei_row = Adw.SwitchRow()
        self.cpp_ei_row.set_title("Subject to CPP & EI")
        self.cpp_ei_row.set_subtitle("Disable for scholarships, investments, pensions…")
        self.cpp_ei_row.set_tooltip_text(
            "CPP and EI apply to employment income. Disable for non-employment sources."
        )
        self.cpp_ei_row.set_active(True)
        group.add(self.cpp_ei_row)

        # Hide CPP/EI toggle when income is non-taxable
        self.taxed_row.connect("notify::active", self._on_taxed_toggled)

        self.active_row = Adw.SwitchRow()
        self.active_row.set_title("Active")
        self.active_row.set_tooltip_text("Inactive sources are excluded from all calculations")
        self.active_row.set_active(True)
        group.add(self.active_row)

        self.notes_row = Adw.EntryRow()
        self.notes_row.set_title("Notes")
        group.add(self.notes_row)

        if existing:
            self.name_row.set_text(existing.name)
            owners_list = budget.couple + ["Shared"]
            if existing.owner in owners_list:
                self.owner_row.set_selected(owners_list.index(existing.owner))
            self.amount_row.set_value(existing.amount)
            if existing.frequency in FREQUENCIES:
                idx = FREQUENCIES.index(existing.frequency)
                self.freq_row.set_selected(idx)
            if existing.date:
                self.date_row.set_text(existing.date)
            self.taxed_row.set_active(existing.is_taxed)
            self.cpp_ei_row.set_active(getattr(existing, "cpp_ei_applicable", True))
            self.active_row.set_active(existing.active)
            self.notes_row.set_text(existing.notes or "")

        self._on_taxed_toggled()
        self._on_freq_changed_income()

    def _on_freq_changed_income(self, *_args):
        is_once = FREQUENCIES[self.freq_row.get_selected()] == "once"
        self.date_row.set_visible(is_once)
        self.cpp_ei_row.set_sensitive(self.taxed_row.get_active() and not is_once)
        if is_once:
            self.cpp_ei_row.set_active(False)

    def _on_taxed_toggled(self, *_args):
        taxed = self.taxed_row.get_active()
        self.cpp_ei_row.set_sensitive(taxed)
        if not taxed:
            self.cpp_ei_row.set_active(False)

    def _on_save(self, _btn):
        name = self.name_row.get_text().strip()
        if not name:
            self.name_row.add_css_class("error")
            return
        self.name_row.remove_css_class("error")

        owners = self.budget.couple + ["Shared"]
        owner = owners[self.owner_row.get_selected()]
        amount = self.amount_row.get_value()
        frequency = FREQUENCIES[self.freq_row.get_selected()]
        is_taxed = self.taxed_row.get_active()
        cpp_ei = self.cpp_ei_row.get_active()

        item_date = self.date_row.get_text().strip() if frequency == "once" else ""

        if self.existing:
            self.existing.name = name
            self.existing.owner = owner
            self.existing.amount = amount
            self.existing.frequency = frequency
            self.existing.is_taxed = is_taxed
            self.existing.cpp_ei_applicable = cpp_ei
            self.existing.active = self.active_row.get_active()
            self.existing.notes = self.notes_row.get_text().strip()
            self.existing.date = item_date
            item = self.existing
        else:
            item = IncomeSource(
                name=name,
                owner=owner,
                amount=amount,
                frequency=frequency,
                is_taxed=is_taxed,
                cpp_ei_applicable=cpp_ei,
                active=self.active_row.get_active(),
                notes=self.notes_row.get_text().strip(),
                date=item_date,
            )
            self.budget.income.append(item)

        if self.on_saved:
            self.on_saved(item)
        self.close()


# ---------------------------------------------------------------------------
# Expense
# ---------------------------------------------------------------------------

class AddExpenseDialog(Adw.Dialog):
    def __init__(self, budget, on_saved=None, existing=None):
        super().__init__()
        self.budget = budget
        self.on_saved = on_saved
        self.existing = existing

        self.set_title("Edit Expense" if existing else "Add Expense")
        self.set_content_width(440)

        toolbar_view = _build_toolbar_view(self.get_title(), self._on_save)
        self.set_child(toolbar_view)

        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        toolbar_view.set_content(scroll)

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        scroll.set_child(page)

        self.name_row = Adw.EntryRow()
        self.name_row.set_title("Name")
        group.add(self.name_row)

        self.amount_row = Adw.SpinRow.new_with_range(0, 9_999_999, 1)
        self.amount_row.set_title("Amount ($)")
        self.amount_row.set_digits(2)
        group.add(self.amount_row)

        self.freq_row = Adw.ComboRow()
        self.freq_row.set_title("Frequency")
        self.freq_row.set_model(_freq_list())
        self.freq_row.set_selected(2)
        group.add(self.freq_row)

        self.exp_date_row = Adw.EntryRow()
        self.exp_date_row.set_title("Date (YYYY-MM-DD)")
        self.exp_date_row.set_text(__import__("datetime").date.today().isoformat())
        self.exp_date_row.set_visible(False)
        group.add(self.exp_date_row)

        self.freq_row.connect("notify::selected", self._on_freq_changed_exp)

        self.active_row = Adw.SwitchRow()
        self.active_row.set_title("Active")
        self.active_row.set_active(True)
        group.add(self.active_row)

        self.notes_row = Adw.EntryRow()
        self.notes_row.set_title("Notes")
        group.add(self.notes_row)

        if existing:
            self.name_row.set_text(existing.name)
            self.amount_row.set_value(existing.amount)
            if existing.frequency in FREQUENCIES:
                self.freq_row.set_selected(FREQUENCIES.index(existing.frequency))
            if existing.date:
                self.exp_date_row.set_text(existing.date)
            self.active_row.set_active(existing.active)
            self.notes_row.set_text(existing.notes or "")

        self._on_freq_changed_exp()

    def _on_freq_changed_exp(self, *_args):
        is_once = FREQUENCIES[self.freq_row.get_selected()] == "once"
        self.exp_date_row.set_visible(is_once)

    def _on_save(self, _btn):
        name = self.name_row.get_text().strip()
        if not name:
            self.name_row.add_css_class("error")
            return
        self.name_row.remove_css_class("error")

        amount = self.amount_row.get_value()
        frequency = FREQUENCIES[self.freq_row.get_selected()]
        item_date = self.exp_date_row.get_text().strip() if frequency == "once" else ""

        if self.existing:
            self.existing.name = name
            self.existing.amount = amount
            self.existing.frequency = frequency
            self.existing.active = self.active_row.get_active()
            self.existing.notes = self.notes_row.get_text().strip()
            self.existing.date = item_date
            item = self.existing
        else:
            item = FixedExpense(
                name=name,
                amount=amount,
                frequency=frequency,
                active=self.active_row.get_active(),
                notes=self.notes_row.get_text().strip(),
                date=item_date,
            )
            self.budget.expenses_fixed.append(item)

        if self.on_saved:
            self.on_saved(item)
        self.close()


# ---------------------------------------------------------------------------
# Debt
# ---------------------------------------------------------------------------

class AddDebtDialog(Adw.Dialog):
    def __init__(self, budget, on_saved=None, existing=None):
        super().__init__()
        self.budget = budget
        self.on_saved = on_saved
        self.existing = existing

        self.set_title("Edit Debt" if existing else "Add Debt")
        self.set_content_width(440)

        toolbar_view = _build_toolbar_view(self.get_title(), self._on_save)
        self.set_child(toolbar_view)

        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        toolbar_view.set_content(scroll)

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        scroll.set_child(page)

        self.name_row = Adw.EntryRow()
        self.name_row.set_title("Name")
        group.add(self.name_row)

        self.balance_row = Adw.SpinRow.new_with_range(0, 9_999_999, 1)
        self.balance_row.set_title("Balance ($)")
        self.balance_row.set_digits(2)
        group.add(self.balance_row)

        self.rate_row = Adw.SpinRow.new_with_range(0, 100, 0.1)
        self.rate_row.set_title("Interest Rate (%)")
        self.rate_row.set_digits(2)
        group.add(self.rate_row)

        self.payment_row = Adw.SpinRow.new_with_range(0, 9_999_999, 1)
        self.payment_row.set_title("Minimum Payment ($)")
        self.payment_row.set_digits(2)
        group.add(self.payment_row)

        self.freq_row = Adw.ComboRow()
        self.freq_row.set_title("Payment Frequency")
        self.freq_row.set_model(_freq_list())
        self.freq_row.set_selected(2)
        group.add(self.freq_row)

        self.notes_row = Adw.EntryRow()
        self.notes_row.set_title("Notes")
        group.add(self.notes_row)

        if existing:
            self.name_row.set_text(existing.name)
            self.balance_row.set_value(existing.balance)
            self.rate_row.set_value(existing.rate)
            self.payment_row.set_value(existing.payment)
            if existing.frequency in FREQUENCIES:
                self.freq_row.set_selected(FREQUENCIES.index(existing.frequency))
            self.notes_row.set_text(existing.notes or "")

    def _on_save(self, _btn):
        name = self.name_row.get_text().strip()
        if not name:
            self.name_row.add_css_class("error")
            return
        self.name_row.remove_css_class("error")

        if self.existing:
            self.existing.name = name
            self.existing.balance = self.balance_row.get_value()
            self.existing.rate = self.rate_row.get_value()
            self.existing.payment = self.payment_row.get_value()
            self.existing.frequency = FREQUENCIES[self.freq_row.get_selected()]
            self.existing.notes = self.notes_row.get_text().strip()
            item = self.existing
        else:
            item = Debt(
                name=name,
                balance=self.balance_row.get_value(),
                rate=self.rate_row.get_value(),
                payment=self.payment_row.get_value(),
                frequency=FREQUENCIES[self.freq_row.get_selected()],
                notes=self.notes_row.get_text().strip(),
            )
            self.budget.debt.append(item)

        if self.on_saved:
            self.on_saved(item)
        self.close()


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class AddCategoryDialog(Adw.Dialog):
    def __init__(self, budget, on_saved=None, existing=None):
        super().__init__()
        self.budget = budget
        self.on_saved = on_saved
        self.existing = existing

        self.set_title("Edit Category" if existing else "Add Category")
        self.set_content_width(440)

        toolbar_view = _build_toolbar_view(self.get_title(), self._on_save)
        self.set_child(toolbar_view)

        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        toolbar_view.set_content(scroll)

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        scroll.set_child(page)

        self.name_row = Adw.EntryRow()
        self.name_row.set_title("Category Name")
        group.add(self.name_row)

        self.budget_row = Adw.SpinRow.new_with_range(0, 99_999, 1)
        self.budget_row.set_title("Budget Amount ($)")
        self.budget_row.set_digits(2)
        self.budget_row.set_tooltip_text(
            "How much to budget per period. Stored in period units — "
            "a weekly value is multiplied by 4.33 to reach the monthly equivalent."
        )
        group.add(self.budget_row)

        self.period_row = Adw.ComboRow()
        self.period_row.set_title("Per")
        period_model = Gtk.StringList()
        for lbl in CATEGORY_PERIOD_LABELS:
            period_model.append(lbl)
        self.period_row.set_model(period_model)
        self.period_row.set_tooltip_text(
            "How often this budget resets. Weekly resets every Monday; "
            "monthly resets on the 1st."
        )
        group.add(self.period_row)

        self.shared_row = Adw.SwitchRow()
        self.shared_row.set_title("Shared Category")
        self.shared_row.set_tooltip_text(
            "Shared categories count spending from both partners. "
            "Personal categories are tracked individually."
        )
        self.shared_row.set_active(True)
        group.add(self.shared_row)

        # Live remaining-to-allocate indicator
        other_cats_monthly = sum(
            c.budget_monthly for c in budget.categories
            if c is not existing
        )
        self._base_unallocated = BudgetCalculator.available_to_spend(budget) - other_cats_monthly

        remaining_group = Adw.PreferencesGroup()
        remaining_group.set_title("Budget Impact")
        page.add(remaining_group)

        self.remaining_row = Adw.ActionRow()
        self.remaining_row.set_title("Remaining to allocate")
        self._remaining_label = Gtk.Label()
        self._remaining_label.add_css_class("numeric")
        self._remaining_label.set_valign(Gtk.Align.CENTER)
        self.remaining_row.add_suffix(self._remaining_label)
        remaining_group.add(self.remaining_row)

        self.budget_row.connect("notify::value", self._update_remaining)
        self.period_row.connect("notify::selected", self._update_remaining)

        # ── Rollover policies ─────────────────────────────────────────────────
        rollover_group = Adw.PreferencesGroup()
        rollover_group.set_title("Cycle Rollover")
        rollover_group.set_description(
            "What to do with unspent or overspent funds at the end of each cycle"
        )
        page.add(rollover_group)

        SURPLUS_POLICIES  = ["ignore", "carry_forward", "to_debt", "to_savings"]
        SURPLUS_LABELS    = ["Ignore", "Carry forward", "Apply to debt", "Move to savings"]
        DEFICIT_POLICIES  = ["ignore", "deduct_next", "amortize"]
        DEFICIT_LABELS    = ["Ignore", "Deduct next cycle", "Amortize over cycles"]

        self.surplus_row = Adw.ComboRow()
        self.surplus_row.set_title("Surplus (unspent)")
        self.surplus_row.set_tooltip_text(
            "What happens when you spend less than the budget this cycle. "
            "'Carry forward' adds the leftover to next cycle's budget."
        )
        s_model = Gtk.StringList()
        for lbl in SURPLUS_LABELS:
            s_model.append(lbl)
        self.surplus_row.set_model(s_model)
        rollover_group.add(self.surplus_row)

        self.deficit_row = Adw.ComboRow()
        self.deficit_row.set_title("Deficit (overspent)")
        self.deficit_row.set_tooltip_text(
            "What happens when you overspend this cycle. "
            "'Deduct next cycle' reduces next cycle's budget by the overage."
        )
        d_model = Gtk.StringList()
        for lbl in DEFICIT_LABELS:
            d_model.append(lbl)
        self.deficit_row.set_model(d_model)
        rollover_group.add(self.deficit_row)

        self.amortize_row = Adw.SpinRow.new_with_range(2, 12, 1)
        self.amortize_row.set_title("Amortize over (cycles)")
        self.amortize_row.set_tooltip_text(
            "Spread the deficit repayment across this many future cycles "
            "instead of deducting it all at once."
        )
        self.amortize_row.set_value(3)
        self.amortize_row.set_visible(False)
        rollover_group.add(self.amortize_row)

        self.deficit_row.connect(
            "notify::selected",
            lambda r, _: self.amortize_row.set_visible(
                DEFICIT_POLICIES[r.get_selected()] == "amortize"
            ),
        )

        # ── Seasonal overrides ────────────────────────────────────────────────
        seasonal_group = Adw.PreferencesGroup()
        seasonal_group.set_title("Seasonal Overrides")
        seasonal_group.set_description("Override the budget for specific months (0 = use default)")
        page.add(seasonal_group)

        MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        self._override_rows: list[Adw.SpinRow] = []
        for i, month_name in enumerate(MONTHS):
            row = Adw.SpinRow.new_with_range(0, 99_999, 10)
            row.set_title(month_name)
            row.set_digits(2)
            seasonal_group.add(row)
            self._override_rows.append(row)

        # ── Populate existing values ──────────────────────────────────────────
        if existing:
            self.name_row.set_text(existing.name)
            self.budget_row.set_value(existing.budget_amount)
            if existing.budget_period in CATEGORY_PERIODS:
                self.period_row.set_selected(CATEGORY_PERIODS.index(existing.budget_period))
            self.shared_row.set_active(existing.shared)
            sp = getattr(existing, "surplus_policy", "ignore")
            dp = getattr(existing, "deficit_policy", "ignore")
            if sp in SURPLUS_POLICIES:
                self.surplus_row.set_selected(SURPLUS_POLICIES.index(sp))
            if dp in DEFICIT_POLICIES:
                self.deficit_row.set_selected(DEFICIT_POLICIES.index(dp))
            self.amortize_row.set_value(getattr(existing, "deficit_amortize_cycles", 3))
            overrides = getattr(existing, "monthly_overrides", {})
            for i, spin in enumerate(self._override_rows):
                spin.set_value(overrides.get(i + 1, 0.0))
        else:
            for spin in self._override_rows:
                spin.set_value(0.0)

        self._SURPLUS_POLICIES = SURPLUS_POLICIES
        self._DEFICIT_POLICIES = DEFICIT_POLICIES
        self._update_remaining()

    def _update_remaining(self, *_args):
        from kopilka.model.budget import _PERIOD_TO_MONTHLY
        period = CATEGORY_PERIODS[self.period_row.get_selected()]
        monthly = self.budget_row.get_value() * _PERIOD_TO_MONTHLY.get(period, 1.0)
        remaining = self._base_unallocated - monthly
        weekly_remaining = remaining / 4.33

        self._remaining_label.set_text(
            f"${remaining:,.2f}/mo  (${weekly_remaining:,.2f}/wk)"
        )
        for cls in ("success", "warning", "error"):
            self.remaining_row.remove_css_class(cls)
        if remaining < 0:
            self.remaining_row.add_css_class("error")
        elif remaining < 50:
            self.remaining_row.add_css_class("warning")
        else:
            self.remaining_row.add_css_class("success")

    def _on_save(self, _btn):
        name = self.name_row.get_text().strip()
        if not name:
            self.name_row.add_css_class("error")
            return
        self.name_row.remove_css_class("error")

        period          = CATEGORY_PERIODS[self.period_row.get_selected()]
        surplus_policy  = self._SURPLUS_POLICIES[self.surplus_row.get_selected()]
        deficit_policy  = self._DEFICIT_POLICIES[self.deficit_row.get_selected()]
        amortize_cycles = int(self.amortize_row.get_value())
        overrides       = {
            i + 1: spin.get_value()
            for i, spin in enumerate(self._override_rows)
            if spin.get_value() > 0
        }

        if self.existing:
            self.existing.name = name
            self.existing.budget_amount = self.budget_row.get_value()
            self.existing.budget_period = period
            self.existing.shared = self.shared_row.get_active()
            self.existing.surplus_policy = surplus_policy
            self.existing.deficit_policy = deficit_policy
            self.existing.deficit_amortize_cycles = amortize_cycles
            self.existing.monthly_overrides = overrides
            item = self.existing
        else:
            item = SpendingCategory(
                name=name,
                budget_amount=self.budget_row.get_value(),
                budget_period=period,
                shared=self.shared_row.get_active(),
                surplus_policy=surplus_policy,
                deficit_policy=deficit_policy,
                deficit_amortize_cycles=amortize_cycles,
                monthly_overrides=overrides,
            )
            self.budget.categories.append(item)

        if self.on_saved:
            self.on_saved(item)
        self.close()


# ---------------------------------------------------------------------------
# Log Spending
# ---------------------------------------------------------------------------

class LogSpendingDialog(Adw.Dialog):
    def __init__(self, budget, on_saved=None, existing=None, preset_user=None):
        super().__init__()
        self.budget = budget
        self.on_saved = on_saved
        self.existing = existing

        self.set_title("Edit Entry" if existing else "Log Purchase")
        self.set_content_width(440)

        toolbar_view = _build_toolbar_view(self.get_title(), self._on_save)
        self.set_child(toolbar_view)

        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        toolbar_view.set_content(scroll)

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        scroll.set_child(page)

        self.date_row = Adw.EntryRow()
        self.date_row.set_title("Date (YYYY-MM-DD)")
        self.date_row.set_text(existing.date if existing else date.today().isoformat())
        group.add(self.date_row)

        self.cat_row = Adw.ComboRow()
        self.cat_row.set_title("Category")
        cat_model = Gtk.StringList()
        self._cat_ids = []
        for c in budget.categories:
            cat_model.append(c.name)
            self._cat_ids.append(c.id)
        self.cat_row.set_model(cat_model)
        group.add(self.cat_row)

        if existing and existing.category_id in self._cat_ids:
            self.cat_row.set_selected(self._cat_ids.index(existing.category_id))

        self.amount_row = Adw.SpinRow.new_with_range(0, 9_999_999, 0.01)
        self.amount_row.set_title("Amount ($)")
        self.amount_row.set_digits(2)
        if existing:
            self.amount_row.set_value(existing.amount)
        group.add(self.amount_row)

        self.desc_row = Adw.EntryRow()
        self.desc_row.set_title("Description")
        if existing:
            self.desc_row.set_text(existing.description or "")
        group.add(self.desc_row)

        self.user_row = Adw.ComboRow()
        self.user_row.set_title("Who paid?")
        user_model = Gtk.StringList()
        for u in budget.couple:
            user_model.append(u)
        self.user_row.set_model(user_model)
        if existing and existing.user in budget.couple:
            self.user_row.set_selected(budget.couple.index(existing.user))
        elif preset_user and preset_user in budget.couple:
            self.user_row.set_selected(budget.couple.index(preset_user))
        group.add(self.user_row)

    def _on_save(self, _btn):
        date_str = self.date_row.get_text().strip()
        if not date_str:
            self.date_row.add_css_class("error")
            return
        self.date_row.remove_css_class("error")

        if not self._cat_ids:
            return

        cat_id = self._cat_ids[self.cat_row.get_selected()]
        amount = self.amount_row.get_value()
        description = self.desc_row.get_text().strip()
        user = self.budget.couple[self.user_row.get_selected()]

        if self.existing:
            self.existing.date = date_str
            self.existing.category_id = cat_id
            self.existing.amount = amount
            self.existing.description = description
            self.existing.user = user
            item = self.existing
        else:
            item = SpendingEntry(
                date=date_str,
                category_id=cat_id,
                amount=amount,
                description=description,
                user=user,
            )
            self.budget.spending.append(item)

        if self.on_saved:
            self.on_saved(item)
        self.close()
