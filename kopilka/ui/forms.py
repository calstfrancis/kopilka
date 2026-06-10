"""Forms for adding and editing budget items."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw
from datetime import date

from kopilka.model.budget import (
    IncomeSource, FixedExpense, Debt, SpendingCategory, SpendingEntry,
    RecurringEntry, ONE_TIME_CATEGORY_ID, CATEGORY_COLORS,
)
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


def _add_today_btn(row: "Adw.EntryRow") -> None:
    """Append a 'reset to today' icon button to a date EntryRow."""
    btn = Gtk.Button()
    btn.set_icon_name("go-jump-symbolic")
    btn.set_tooltip_text("Set to today")
    btn.add_css_class("flat")
    btn.add_css_class("circular")
    btn.set_valign(Gtk.Align.CENTER)
    btn.connect("clicked", lambda _: row.set_text(date.today().isoformat()))
    row.add_suffix(btn)


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
        self.date_row.set_text(date.today().isoformat())
        self.date_row.set_visible(False)
        self.date_row.set_tooltip_text("Date the one-time payment was received")
        _add_today_btn(self.date_row)
        group.add(self.date_row)

        self.payday_row = Adw.EntryRow()
        self.payday_row.set_title("Reference Payday (YYYY-MM-DD)")
        self.payday_row.set_tooltip_text(
            "Enter any date when you were paid. The app uses this to compute "
            "the next upcoming payday by adding 14-day intervals."
        )
        self.payday_row.set_visible(False)
        group.add(self.payday_row)

        self.freq_row.connect("notify::selected", self._on_freq_changed_income)

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
            if getattr(existing, "next_payday", ""):
                self.payday_row.set_text(existing.next_payday)
            self.active_row.set_active(existing.active)
            self.notes_row.set_text(existing.notes or "")

        self._on_freq_changed_income()

    def _on_freq_changed_income(self, *_args):
        freq = FREQUENCIES[self.freq_row.get_selected()]
        self.date_row.set_visible(freq == "once")
        self.payday_row.set_visible(freq == "biweekly")

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
        item_date = self.date_row.get_text().strip() if frequency == "once" else ""
        next_payday = self.payday_row.get_text().strip() if frequency == "biweekly" else ""

        if self.existing:
            self.existing.name = name
            self.existing.owner = owner
            self.existing.amount = amount
            self.existing.frequency = frequency
            self.existing.active = self.active_row.get_active()
            self.existing.notes = self.notes_row.get_text().strip()
            self.existing.date = item_date
            self.existing.next_payday = next_payday
            item = self.existing
        else:
            item = IncomeSource(
                name=name,
                owner=owner,
                amount=amount,
                frequency=frequency,
                active=self.active_row.get_active(),
                notes=self.notes_row.get_text().strip(),
                date=item_date,
                next_payday=next_payday,
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
        self.set_content_width(480)
        self.set_content_height(560)

        toolbar_view = _build_toolbar_view(self.get_title(), self._on_save)
        self.set_child(toolbar_view)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
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
        self.exp_date_row.set_text(date.today().isoformat())
        self.exp_date_row.set_visible(False)
        _add_today_btn(self.exp_date_row)
        group.add(self.exp_date_row)

        # Due-date rows — only one is shown at a time depending on frequency
        self.due_day_row = Adw.SpinRow.new_with_range(0, 31, 1)
        self.due_day_row.set_title("Due on day of month")
        self.due_day_row.set_subtitle("0 = no reminder")
        self.due_day_row.set_tooltip_text(
            "Day of the month this bill is due (e.g. 15 for the 15th). "
            "Set to 0 to skip the upcoming-bills reminder."
        )
        self.due_day_row.set_digits(0)
        group.add(self.due_day_row)

        self.due_weekday_row = Adw.ComboRow()
        self.due_weekday_row.set_title("Due on day of week")
        self.due_weekday_row.set_tooltip_text(
            "Which day of the week this bill is due. "
            "Used for the upcoming-bills reminder."
        )
        wd_model = Gtk.StringList()
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            wd_model.append(day)
        self.due_weekday_row.set_model(wd_model)
        self.due_weekday_row.set_visible(False)
        group.add(self.due_weekday_row)

        self.due_doy_month_row = Adw.ComboRow()
        self.due_doy_month_row.set_title("Due month")
        self.due_doy_month_row.set_tooltip_text("Month the yearly bill falls in")
        doy_month_model = Gtk.StringList()
        for m in ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]:
            doy_month_model.append(m)
        self.due_doy_month_row.set_model(doy_month_model)
        self.due_doy_month_row.set_visible(False)
        group.add(self.due_doy_month_row)

        self.due_doy_day_row = Adw.SpinRow.new_with_range(0, 31, 1)
        self.due_doy_day_row.set_title("Due day of month (yearly)")
        self.due_doy_day_row.set_subtitle("0 = no reminder")
        self.due_doy_day_row.set_tooltip_text(
            "Day within the selected month this yearly bill is due. "
            "Set to 0 to skip the upcoming-bills reminder."
        )
        self.due_doy_day_row.set_digits(0)
        self.due_doy_day_row.set_visible(False)
        group.add(self.due_doy_day_row)

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
            self.due_day_row.set_value(getattr(existing, "due_day", 0))
            wd = getattr(existing, "due_weekday", -1)
            self.due_weekday_row.set_selected(wd if wd >= 0 else 0)
            doy = getattr(existing, "due_doy", 0)
            if doy > 0:
                import datetime
                try:
                    d = datetime.date(2024, 1, 1) + datetime.timedelta(days=doy - 1)
                    self.due_doy_month_row.set_selected(d.month - 1)
                    self.due_doy_day_row.set_value(d.day)
                except Exception:
                    pass
            self.active_row.set_active(existing.active)
            self.notes_row.set_text(existing.notes or "")

        self._on_freq_changed_exp()

    def _on_freq_changed_exp(self, *_args):
        freq = FREQUENCIES[self.freq_row.get_selected()]
        is_once   = freq == "once"
        is_weekly = freq == "weekly"
        is_yearly = freq == "yearly"
        self.exp_date_row.set_visible(is_once)
        self.due_weekday_row.set_visible(is_weekly and not is_once)
        self.due_doy_month_row.set_visible(is_yearly)
        self.due_doy_day_row.set_visible(is_yearly)
        self.due_day_row.set_visible(not is_once and not is_weekly and not is_yearly)

    def _on_save(self, _btn):
        name = self.name_row.get_text().strip()
        if not name:
            self.name_row.add_css_class("error")
            return
        self.name_row.remove_css_class("error")

        amount = self.amount_row.get_value()
        frequency = FREQUENCIES[self.freq_row.get_selected()]
        item_date = self.exp_date_row.get_text().strip() if frequency == "once" else ""

        due_day = 0
        due_weekday = -1
        due_doy = 0
        if frequency == "weekly":
            due_weekday = self.due_weekday_row.get_selected()  # 0=Mon…6=Sun
        elif frequency == "yearly":
            import datetime, calendar
            month = self.due_doy_month_row.get_selected() + 1  # 1-12
            day   = int(self.due_doy_day_row.get_value())
            if day > 0:
                max_day = calendar.monthrange(2024, month)[1]
                day = min(day, max_day)
                due_doy = (datetime.date(2024, month, day) - datetime.date(2024, 1, 1)).days + 1
        elif frequency != "once":
            due_day = int(self.due_day_row.get_value())

        if self.existing:
            self.existing.name = name
            self.existing.amount = amount
            self.existing.frequency = frequency
            self.existing.active = self.active_row.get_active()
            self.existing.notes = self.notes_row.get_text().strip()
            self.existing.date = item_date
            self.existing.due_day = due_day
            self.existing.due_weekday = due_weekday
            self.existing.due_doy = due_doy
            item = self.existing
        else:
            item = FixedExpense(
                name=name,
                amount=amount,
                frequency=frequency,
                active=self.active_row.get_active(),
                notes=self.notes_row.get_text().strip(),
                date=item_date,
                due_day=due_day,
                due_weekday=due_weekday,
                due_doy=due_doy,
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
        self.set_content_width(690)
        self.set_content_height(660)

        toolbar_view = _build_toolbar_view(self.get_title(), self._on_save)
        self.set_child(toolbar_view)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
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

        # ── Colour picker ─────────────────────────────────────────────────────
        color_group = Adw.PreferencesGroup()
        color_group.set_title("Category Colour")
        page.add(color_group)

        self._selected_color = existing.color if existing else ""
        self._color_btns: dict[str, Gtk.ToggleButton] = {}

        # Build colour swatches in a single row (none + 13 colours)
        all_colors = [("", "No colour")] + [(c, c) for c in CATEGORY_COLORS]
        row_box = Gtk.Box(spacing=4, margin_top=8, margin_bottom=8,
                          margin_start=12, margin_end=12)
        for hex_c, tip in all_colors:
            btn = Gtk.ToggleButton()
            btn.set_size_request(32, 32)
            btn.set_tooltip_text(tip)
            btn.set_active(hex_c == self._selected_color or
                           (hex_c == "" and not self._selected_color))
            bg = hex_c if hex_c else "@card_shade_color"
            ring = hex_c if hex_c else "@card_fg_color"
            _prov = Gtk.CssProvider()
            _prov.load_from_string(
                f"button{{background:{bg};min-width:26px;min-height:26px;"
                f"border-radius:4px;padding:0;font-size:14px;}}"
                f"button:checked{{box-shadow:0 0 0 2px @window_bg_color,0 0 0 4px {ring};}}"
            )
            btn.get_style_context().add_provider(_prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            if hex_c == "":
                btn.set_label("—")
            row_box.append(btn)
            self._color_btns[hex_c] = btn
        color_vbox = row_box

        def _on_color_toggled(btn, color):
            if btn.get_active():
                self._selected_color = color
                for c, b in self._color_btns.items():
                    if b is not btn:
                        b.set_active(False)
            elif not any(b.get_active() for b in self._color_btns.values()):
                btn.set_active(True)

        for color, btn in self._color_btns.items():
            btn.connect("toggled", _on_color_toggled, color)

        color_group.add(color_vbox)

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

        _MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        self._override_spins: dict[int, Gtk.SpinButton] = {}

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(6)
        grid.set_margin_top(10)
        grid.set_margin_bottom(10)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        for i, name in enumerate(_MONTHS):
            row_i = i // 2
            col_i = (i % 2) * 2
            lbl = Gtk.Label(label=name)
            lbl.set_xalign(1.0)
            lbl.add_css_class("dim-label")
            lbl.set_size_request(32, -1)
            adj = Gtk.Adjustment(value=0.0, lower=0.0, upper=99_999.0, step_increment=10.0)
            spin = Gtk.SpinButton(adjustment=adj, digits=2)
            spin.set_hexpand(True)
            spin.set_tooltip_text(f"Budget override for {name} (0 = use default)")
            grid.attach(lbl,  col_i,     row_i, 1, 1)
            grid.attach(spin, col_i + 1, row_i, 1, 1)
            self._override_spins[i + 1] = spin
        seasonal_group.add(grid)

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
            for month_num, spin in self._override_spins.items():
                spin.set_value(overrides.get(month_num, 0.0))
        else:
            for spin in self._override_spins.values():
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
            m: spin.get_value()
            for m, spin in self._override_spins.items()
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
            self.existing.color = self._selected_color
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
                color=self._selected_color,
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
        _add_today_btn(self.date_row)
        group.add(self.date_row)

        self.cat_row = Adw.ComboRow()
        self.cat_row.set_title("Category")
        cat_model = Gtk.StringList()
        self._cat_ids = []
        # One-time purchase is always the first option
        cat_model.append("One-time Purchase (annual pool)")
        self._cat_ids.append(ONE_TIME_CATEGORY_ID)
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
        _couple = budget.couple or ["User 1"]
        user_model = Gtk.StringList()
        for u in _couple:
            user_model.append(u)
        self.user_row.set_model(user_model)
        if existing and existing.user in _couple:
            self.user_row.set_selected(_couple.index(existing.user))
        elif preset_user and preset_user in _couple:
            self.user_row.set_selected(_couple.index(preset_user))
        group.add(self.user_row)

    def _on_save(self, _btn):
        date_str = self.date_row.get_text().strip()
        try:
            date.fromisoformat(date_str)
            self.date_row.remove_css_class("error")
        except ValueError:
            self.date_row.add_css_class("error")
            return

        if not self._cat_ids:
            return

        cat_id = self._cat_ids[self.cat_row.get_selected()]
        amount = self.amount_row.get_value()
        if amount <= 0:
            self.amount_row.add_css_class("error")
            return
        self.amount_row.remove_css_class("error")
        description = self.desc_row.get_text().strip()
        _couple = self.budget.couple or ["User 1"]
        user = _couple[min(self.user_row.get_selected(), len(_couple) - 1)]

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


# ---------------------------------------------------------------------------
# Recurring Entry
# ---------------------------------------------------------------------------

RECURRING_FREQS       = ["weekly", "biweekly", "monthly"]
RECURRING_FREQ_LABELS = ["Weekly", "Bi-weekly", "Monthly"]


class AddRecurringDialog(Adw.Dialog):
    def __init__(self, budget, on_saved=None, existing=None):
        super().__init__()
        self.budget   = budget
        self.on_saved = on_saved
        self.existing = existing

        self.set_title("Edit Recurring" if existing else "Add Recurring Entry")
        self.set_content_width(440)

        toolbar_view = _build_toolbar_view(self.get_title(), self._on_save)
        self.set_child(toolbar_view)

        scroll = Gtk.ScrolledWindow()
        scroll.set_propagate_natural_height(True)
        toolbar_view.set_content(scroll)

        page  = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        scroll.set_child(page)

        self.name_row = Adw.EntryRow()
        self.name_row.set_title("Name")
        self.name_row.set_tooltip_text("Label shown before the entry is inserted")
        group.add(self.name_row)

        self.cat_row = Adw.ComboRow()
        self.cat_row.set_title("Category")
        cat_model = Gtk.StringList()
        self._cat_ids = [ONE_TIME_CATEGORY_ID]
        cat_model.append("One-time Purchase (annual pool)")
        for c in budget.categories:
            cat_model.append(c.name)
            self._cat_ids.append(c.id)
        self.cat_row.set_model(cat_model)
        group.add(self.cat_row)

        self.amount_row = Adw.SpinRow.new_with_range(0, 9_999_999, 0.01)
        self.amount_row.set_title("Amount ($)")
        self.amount_row.set_digits(2)
        group.add(self.amount_row)

        self.desc_row = Adw.EntryRow()
        self.desc_row.set_title("Description")
        group.add(self.desc_row)

        self.user_row = Adw.ComboRow()
        self.user_row.set_title("Who paid?")
        user_model = Gtk.StringList()
        for u in budget.couple:
            user_model.append(u)
        self.user_row.set_model(user_model)
        group.add(self.user_row)

        self.freq_row = Adw.ComboRow()
        self.freq_row.set_title("Frequency")
        freq_model = Gtk.StringList()
        for lbl in RECURRING_FREQ_LABELS:
            freq_model.append(lbl)
        self.freq_row.set_model(freq_model)
        self.freq_row.set_selected(2)  # monthly default
        group.add(self.freq_row)

        self.next_date_row = Adw.EntryRow()
        self.next_date_row.set_title("Next insertion date (YYYY-MM-DD)")
        self.next_date_row.set_text(date.today().isoformat())
        self.next_date_row.set_tooltip_text(
            "The entry will be auto-inserted on or after this date when you open the spending log."
        )
        _add_today_btn(self.next_date_row)
        group.add(self.next_date_row)

        self.active_row = Adw.SwitchRow()
        self.active_row.set_title("Active")
        self.active_row.set_active(True)
        group.add(self.active_row)

        if existing:
            self.name_row.set_text(existing.name)
            if existing.category_id in self._cat_ids:
                self.cat_row.set_selected(self._cat_ids.index(existing.category_id))
            self.amount_row.set_value(existing.amount)
            self.desc_row.set_text(existing.description or "")
            if existing.user in budget.couple:
                self.user_row.set_selected(budget.couple.index(existing.user))
            if existing.frequency in RECURRING_FREQS:
                self.freq_row.set_selected(RECURRING_FREQS.index(existing.frequency))
            self.next_date_row.set_text(existing.next_date)
            self.active_row.set_active(existing.active)

    def _on_save(self, _btn):
        name = self.name_row.get_text().strip()
        if not name:
            self.name_row.add_css_class("error")
            return
        self.name_row.remove_css_class("error")

        cat_id      = self._cat_ids[self.cat_row.get_selected()]
        amount      = self.amount_row.get_value()
        description = self.desc_row.get_text().strip()
        user        = self.budget.couple[self.user_row.get_selected()]
        frequency   = RECURRING_FREQS[self.freq_row.get_selected()]
        next_date   = self.next_date_row.get_text().strip() or date.today().isoformat()
        active      = self.active_row.get_active()

        if self.existing:
            self.existing.name        = name
            self.existing.category_id = cat_id
            self.existing.amount      = amount
            self.existing.description = description
            self.existing.user        = user
            self.existing.frequency   = frequency
            self.existing.next_date   = next_date
            self.existing.active      = active
            item = self.existing
        else:
            item = RecurringEntry(
                name=name, category_id=cat_id, amount=amount,
                description=description, user=user,
                frequency=frequency, next_date=next_date, active=active,
            )
            self.budget.recurring.append(item)

        if self.on_saved:
            self.on_saved(item)
        self.close()
