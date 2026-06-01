"""Spending reports view."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw
from datetime import date, timedelta

from kopilka.logic.calculations import BudgetCalculator
from kopilka.ui.charts import DonutChart, MonthlyBarChart


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _month_start(months_back: int) -> date:
    today = date.today()
    total = today.year * 12 + (today.month - 1) - months_back
    return date(total // 12, total % 12 + 1, 1)


def _next_month(d: date) -> date:
    total = d.year * 12 + d.month
    return date(total // 12, total % 12 + 1, 1)


def _period_range(period: str) -> tuple[date, date]:
    today = date.today()
    if period == "week":
        return today - timedelta(days=today.weekday()), today
    elif period == "month":
        return today.replace(day=1), today
    elif period == "3months":
        return _month_start(2), today
    else:
        return today.replace(month=1, day=1), today


def _period_months(period: str) -> float:
    return {"week": 7 / 30.44, "month": 1.0, "3months": 3.0, "year": 12.0}[period]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_listbox():
    lb = Gtk.ListBox()
    lb.add_css_class("boxed-list")
    lb.set_selection_mode(Gtk.SelectionMode.NONE)
    return lb


def _amount_lbl(text, css=""):
    lbl = Gtk.Label(label=text)
    lbl.add_css_class("numeric")
    if css:
        lbl.add_css_class(css)
    lbl.set_valign(Gtk.Align.CENTER)
    return lbl


PERIOD_OPTS = [
    ("week",    "This Week",  "Spending since Monday"),
    ("month",   "This Month", "Spending since the 1st of this month"),
    ("3months", "3 Months",   "Spending over the last 3 months"),
    ("year",    "This Year",  "Spending since January 1st"),
]


# ---------------------------------------------------------------------------
# Reports view
# ---------------------------------------------------------------------------

class ReportsView(Gtk.Box):
    def __init__(self, budget, _on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.budget = budget
        self._period = "month"
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

        icon = Gtk.Image.new_from_icon_name("view-sort-descending-symbolic")
        icon.set_icon_size(Gtk.IconSize.LARGE)
        icon.add_css_class("dim-label")
        hdr.append(icon)

        title = Gtk.Label(label="Reports")
        title.add_css_class("title-2")
        title.set_xalign(0)
        title.set_hexpand(True)
        hdr.append(title)

        seg = Gtk.Box(spacing=0)
        seg.add_css_class("linked")
        self._period_btns: dict[str, Gtk.ToggleButton] = {}
        for key, label, tip in PERIOD_OPTS:
            btn = Gtk.ToggleButton(label=label)
            btn.set_active(key == self._period)
            btn.set_tooltip_text(tip)
            btn.connect("toggled", self._on_period_toggled, key)
            seg.append(btn)
            self._period_btns[key] = btn
        hdr.append(seg)

        print_btn = Gtk.Button()
        print_btn.set_icon_name("document-print-symbolic")
        print_btn.set_tooltip_text("Print budget sheet")
        print_btn.connect("clicked", self._on_print)
        hdr.append(print_btn)

        self.append(clamp_hdr)

        # ── Scrollable body ───────────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)

        clamp_body = Adw.Clamp()
        clamp_body.set_maximum_size(860)
        clamp_body.set_margin_start(16)
        clamp_body.set_margin_end(16)
        clamp_body.set_margin_bottom(24)

        self._body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        clamp_body.set_child(self._body)
        scroll.set_child(clamp_body)
        self.append(scroll)

        self.refresh()

    # ── Print ─────────────────────────────────────────────────────────────────

    def _on_print(self, _btn):
        from kopilka.logic.print_sheet import show_preview
        show_preview(self.budget, self.get_root())

    # ── Period toggle ─────────────────────────────────────────────────────────

    def _on_period_toggled(self, btn, key):
        if btn.get_active():
            self._period = key
            for k, b in self._period_btns.items():
                if k != key:
                    b.set_active(False)
            self.refresh()
        elif not any(b.get_active() for b in self._period_btns.values()):
            btn.set_active(True)

    # ── Rebuild ───────────────────────────────────────────────────────────────

    def refresh(self):
        child = self._body.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._body.remove(child)
            child = nxt

        if not self.budget.spending and not self.budget.income and not self.budget.expenses_fixed:
            sp = Adw.StatusPage()
            sp.set_title("No Data Yet")
            sp.set_description("Add income, log spending, and reports will appear here")
            sp.set_icon_name("view-sort-descending-symbolic")
            self._body.append(sp)
            return

        start, end = _period_range(self._period)
        months = _period_months(self._period)

        entries = [
            e for e in self.budget.spending
            if start.isoformat() <= e.date <= end.isoformat()
        ]
        cat_map = {c.id: c for c in self.budget.categories}

        self._build_summary(entries, months, start, end)
        self._build_by_category_chart(entries, cat_map, months)
        self._build_by_person_chart(entries)
        self._build_monthly_trend()

    # ── Summary ───────────────────────────────────────────────────────────────

    def _build_summary(self, entries, months, start, end):
        group = Adw.PreferencesGroup()
        group.set_title("Summary")
        self._body.append(group)

        spent = sum(e.amount for e in entries)
        one_time_inc  = BudgetCalculator.one_time_income_in_period(self.budget, start, end)
        one_time_exp  = BudgetCalculator.one_time_expenses_in_period(self.budget, start, end)
        total_budget  = sum(c.budget_monthly for c in self.budget.categories) * months
        diff = total_budget - spent

        lb = _make_listbox()
        group.add(lb)

        def _row(title, value, css=""):
            r = Adw.ActionRow()
            r.set_title(title)
            r.add_suffix(_amount_lbl(value, css))
            lb.append(r)

        _row("Spending", f"${spent:,.2f}")
        _row("Category Budget", f"${total_budget:,.2f}", "dim-label")

        diff_css = "error" if diff < 0 else "success"
        sign = "Over" if diff < 0 else "Under"
        _row(f"{sign} Budget", f"${abs(diff):,.2f}", diff_css)

        if one_time_inc > 0:
            _row("One-time Income", f"+${one_time_inc:,.2f}", "success")
        if one_time_exp > 0:
            _row("One-time Expenses", f"−${one_time_exp:,.2f}", "warning")

        if total_budget > 0:
            pct = min(spent / total_budget, 1.0)
            bar = Gtk.ProgressBar()
            bar.set_fraction(pct)
            bar.set_show_text(True)
            bar.set_text(f"{pct * 100:.0f}% of budget used")
            bar.set_margin_start(8)
            bar.set_margin_end(8)
            bar.set_margin_bottom(8)
            if pct >= 1.0:
                bar.add_css_class("error")
            elif pct >= 0.8:
                bar.add_css_class("warning")
            group.add(bar)

    # ── By category — donut chart ─────────────────────────────────────────────

    def _build_by_category_chart(self, entries, cat_map, months):
        group = Adw.PreferencesGroup()
        group.set_title("Spending by Category")
        self._body.append(group)

        cat_spent: dict[str, float] = {}
        uncategorised = 0.0
        for e in entries:
            if e.category_id in cat_map:
                cat_spent[e.category_id] = cat_spent.get(e.category_id, 0.0) + e.amount
            else:
                uncategorised += e.amount

        if not cat_spent and uncategorised == 0:
            row = Adw.ActionRow()
            row.set_title("No spending in this period")
            group.add(row)
            return

        chart_data = [
            (cat_map[cid].name, amt)
            for cid, amt in sorted(cat_spent.items(), key=lambda x: -x[1])
            if cid in cat_map
        ]
        if uncategorised > 0:
            chart_data.append(("Other", uncategorised))

        chart = DonutChart(chart_data, title="spent")
        group.add(chart)

        # Detail rows below the chart
        lb = _make_listbox()
        group.add(lb)

        for cat in sorted(self.budget.categories, key=lambda c: cat_spent.get(c.id, 0), reverse=True):
            spent_amt = cat_spent.get(cat.id, 0.0)
            budget_amt = cat.budget_monthly * months
            pct = spent_amt / budget_amt if budget_amt > 0 else 0

            row = Adw.ExpanderRow()
            row.set_title(cat.name)
            css = "error" if pct >= 1.0 else ("warning" if pct >= 0.8 else "")
            row.set_subtitle(f"${spent_amt:,.2f} of ${budget_amt:,.2f}  ({pct*100:.0f}%)")

            bar = Gtk.ProgressBar()
            bar.set_fraction(min(pct, 1.0))
            bar.set_valign(Gtk.Align.CENTER)
            bar.set_size_request(80, -1)
            if css:
                bar.add_css_class(css)
            row.add_suffix(bar)

            remaining = budget_amt - spent_amt
            rem_row = Adw.ActionRow()
            rem_row.set_title("Under budget" if remaining >= 0 else "Over budget")
            rem_row.add_suffix(_amount_lbl(f"${abs(remaining):,.2f}",
                                           "success" if remaining >= 0 else "error"))
            row.add_row(rem_row)
            lb.append(row)

        if uncategorised > 0:
            unc = Adw.ActionRow()
            unc.set_title("Uncategorised spending")
            unc.add_suffix(_amount_lbl(f"${uncategorised:,.2f}", "warning"))
            lb.append(unc)

    # ── By person — donut chart ───────────────────────────────────────────────

    def _build_by_person_chart(self, entries):
        if len(self.budget.couple) < 2 or not entries:
            return

        group = Adw.PreferencesGroup()
        group.set_title("Spending by Person")
        self._body.append(group)

        totals: dict[str, float] = {}
        for e in entries:
            totals[e.user] = totals.get(e.user, 0.0) + e.amount

        chart_data = [
            (person, totals.get(person, 0.0))
            for person in self.budget.couple
        ]
        others = [(u, v) for u, v in totals.items() if u not in self.budget.couple]
        if others:
            chart_data.append(("Other", sum(v for _, v in others)))

        chart = DonutChart(chart_data, title="total")
        group.add(chart)

    # ── Monthly trend ─────────────────────────────────────────────────────────

    def _build_monthly_trend(self):
        group = Adw.PreferencesGroup()
        group.set_title("Monthly Trend")
        group.set_description("Last 6 months — spending vs category budgets")
        self._body.append(group)

        monthly_budget = sum(c.budget_monthly for c in self.budget.categories)
        has_data = False

        chart_data = []
        row_data = []  # (m_start, total_out, one_exp) for text rows

        for i in range(5, -1, -1):
            m_start = _month_start(i)
            m_end   = _next_month(m_start)

            month_entries = [
                e for e in self.budget.spending
                if m_start.isoformat() <= e.date < m_end.isoformat()
            ]
            spent = sum(e.amount for e in month_entries)
            one_exp = BudgetCalculator.one_time_expenses_in_period(
                self.budget, m_start, m_end
            )
            total_out = spent + one_exp

            label = m_start.strftime("%b")
            chart_data.append((label, total_out, monthly_budget))

            if total_out == 0 and not month_entries:
                row_data.append((m_start, total_out, one_exp, False))
                continue
            has_data = True
            row_data.append((m_start, total_out, one_exp, True))

        chart = MonthlyBarChart(chart_data)
        group.add(chart)

        lb = _make_listbox()
        group.add(lb)

        for m_start, total_out, one_exp, include in row_data:
            if not include:
                continue
            diff = monthly_budget - total_out
            row = Adw.ActionRow()
            row.set_title(m_start.strftime("%B %Y"))

            if monthly_budget > 0:
                sign = "−$" if diff < 0 else "+$"
                css  = "error" if diff < 0 else "success"
                row.set_subtitle(f"{sign}{abs(diff):,.2f} vs budget")

            extra = f"  +${one_exp:,.2f} one-time" if one_exp > 0 else ""
            row.add_suffix(_amount_lbl(f"${total_out:,.2f}{extra}"))
            lb.append(row)

        if not has_data:
            row = Adw.ActionRow()
            row.set_title("No spending recorded yet")
            lb.append(row)
