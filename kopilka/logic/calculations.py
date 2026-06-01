"""Budget calculations and aggregations."""

import math
from datetime import date, timedelta

from kopilka.logic.tax_calc import TaxCalculator

_PERIOD_FACTOR = {
    "weekly":     4.33,
    "monthly":    1.0,
    "semesterly": 2 / 12,
    "yearly":     1 / 12,
}


# ---------------------------------------------------------------------------
# Cycle helpers
# ---------------------------------------------------------------------------

def _prev_cycle(period: str, today: date | None = None) -> tuple[date, date]:
    """Return (start, end) of the cycle immediately before the one containing today."""
    if today is None:
        today = date.today()

    if period == "weekly":
        this_start = today - timedelta(days=today.weekday())
        prev_end   = this_start - timedelta(days=1)
        prev_start = prev_end   - timedelta(days=6)
        return prev_start, prev_end

    elif period == "monthly":
        this_start = today.replace(day=1)
        prev_end   = this_start - timedelta(days=1)
        return prev_end.replace(day=1), prev_end

    elif period == "semesterly":
        if today.month <= 6:
            return date(today.year - 1, 7, 1), date(today.year - 1, 12, 31)
        return date(today.year, 1, 1), date(today.year, 6, 30)

    else:  # yearly
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)


def _curr_cycle(period: str, today: date | None = None) -> tuple[date, date]:
    """Return (start, end) of the cycle currently in progress."""
    if today is None:
        today = date.today()

    if period == "weekly":
        start = today - timedelta(days=today.weekday())
        end   = start + timedelta(days=6)
        return start, end

    elif period == "monthly":
        start = today.replace(day=1)
        total = start.year * 12 + start.month
        end   = date(total // 12, total % 12 + 1, 1) - timedelta(days=1)
        return start, end

    elif period == "semesterly":
        if today.month <= 6:
            return date(today.year, 1, 1), date(today.year, 6, 30)
        return date(today.year, 7, 1), date(today.year, 12, 31)

    else:  # yearly
        return date(today.year, 1, 1), date(today.year, 12, 31)


# ---------------------------------------------------------------------------
# Main calculator
# ---------------------------------------------------------------------------

class BudgetCalculator:

    # ── Income / deductions ──────────────────────────────────────────────────

    @staticmethod
    def monthly_gross_income(budget) -> float:
        total = 0.0
        for inc in budget.income:
            if inc.active and inc.frequency != "once":
                total += BudgetCalculator._to_monthly(inc.amount, inc.frequency)
        return total

    @staticmethod
    def monthly_net_income(budget) -> float:
        annual_taxable = 0.0
        annual_cpp_ei  = 0.0
        for inc in budget.income:
            if not inc.active or not inc.is_taxed or inc.frequency == "once":
                continue
            annual = BudgetCalculator._to_annual(inc.amount, inc.frequency)
            annual_taxable += annual
            if getattr(inc, "cpp_ei_applicable", True):
                annual_cpp_ei += annual

        monthly_deductions = (
            TaxCalculator.estimate_monthly_income_tax(annual_taxable)
            + TaxCalculator.estimate_monthly_cpp(annual_cpp_ei)
            + TaxCalculator.estimate_monthly_ei(annual_cpp_ei)
        )
        return BudgetCalculator.monthly_gross_income(budget) - monthly_deductions

    # ── Fixed costs / debt ───────────────────────────────────────────────────

    @staticmethod
    def monthly_fixed_costs(budget) -> float:
        total = 0.0
        for exp in budget.expenses_fixed:
            if exp.active and exp.frequency != "once":
                total += BudgetCalculator._to_monthly(exp.amount, exp.frequency)
        return total

    @staticmethod
    def monthly_debt_payments(budget) -> float:
        total = 0.0
        for debt in budget.debt:
            total += BudgetCalculator._to_monthly(debt.payment, debt.frequency)
        return total

    @staticmethod
    def available_to_spend(budget) -> float:
        return (BudgetCalculator.monthly_net_income(budget)
                - BudgetCalculator.monthly_fixed_costs(budget)
                - BudgetCalculator.monthly_debt_payments(budget))

    @staticmethod
    def monthly_category_budgets(budget) -> float:
        return sum(c.budget_monthly for c in budget.categories)

    @staticmethod
    def unallocated_discretionary(budget) -> float:
        return (BudgetCalculator.available_to_spend(budget)
                - BudgetCalculator.monthly_category_budgets(budget))

    # ── One-time items ───────────────────────────────────────────────────────

    @staticmethod
    def one_time_income_in_period(budget, start: date, end: date) -> float:
        return sum(
            inc.amount for inc in budget.income
            if inc.frequency == "once" and inc.active and inc.date
            and start.isoformat() <= inc.date <= end.isoformat()
        )

    @staticmethod
    def one_time_expenses_in_period(budget, start: date, end: date) -> float:
        return sum(
            exp.amount for exp in budget.expenses_fixed
            if exp.frequency == "once" and exp.active and exp.date
            and start.isoformat() <= exp.date <= end.isoformat()
        )

    # ── Rollover ─────────────────────────────────────────────────────────────

    @staticmethod
    def category_prev_cycle_surplus(category, spending, today: date | None = None) -> float:
        """
        Surplus (positive) or deficit (negative) from the previous cycle
        of a spending category, expressed in period units.
        """
        prev_start, prev_end = _prev_cycle(category.budget_period, today)
        prev_spent = sum(
            e.amount for e in spending
            if e.category_id == category.id
            and prev_start.isoformat() <= e.date <= prev_end.isoformat()
        )
        prev_budget_monthly = category.budget_for_month(prev_start.month)
        prev_budget = prev_budget_monthly / _PERIOD_FACTOR.get(category.budget_period, 1.0)
        return prev_budget - prev_spent

    @staticmethod
    def category_rollover(category, spending, today: date | None = None) -> float:
        """
        Return the rollover adjustment (+ or −) to apply to the current cycle's budget.
        Positive = bonus budget from surplus; negative = reduction from deficit.
        """
        surplus = BudgetCalculator.category_prev_cycle_surplus(category, spending, today)

        if surplus > 0:
            if category.surplus_policy == "carry_forward":
                return surplus
            return 0.0  # ignore / to_debt / to_savings handled separately

        if surplus < 0:
            if category.deficit_policy == "deduct_next":
                return surplus
            if category.deficit_policy == "amortize":
                cycles = max(category.deficit_amortize_cycles, 1)
                return surplus / cycles
        return 0.0

    @staticmethod
    def category_effective_budget(category, spending, today: date | None = None) -> float:
        """Current cycle budget in period units + any rollover adjustment."""
        if today is None:
            today = date.today()
        base = category.budget_for_month(today.month) / _PERIOD_FACTOR.get(category.budget_period, 1.0)
        return base + BudgetCalculator.category_rollover(category, spending, today)

    # ── Savings / net worth ──────────────────────────────────────────────────

    @staticmethod
    def total_assets(budget) -> float:
        """Sum of all asset account balances. Falls back to savings goal totals if no assets defined."""
        assets = getattr(budget, "assets", [])
        if assets:
            return sum(a.balance for a in assets)
        return sum(g.current for g in budget.savings_goals)

    @staticmethod
    def total_savings(budget) -> float:
        return BudgetCalculator.total_assets(budget)

    @staticmethod
    def total_debt_balance(budget) -> float:
        return sum(d.balance for d in budget.debt)

    @staticmethod
    def net_worth(budget) -> float:
        return BudgetCalculator.total_assets(budget) - BudgetCalculator.total_debt_balance(budget)

    # ── Debt payoff ──────────────────────────────────────────────────────────

    @staticmethod
    def debt_payoff(debt) -> dict:
        monthly_payment = BudgetCalculator._to_monthly(debt.payment, debt.frequency)
        balance         = debt.balance
        monthly_rate    = debt.rate / 100 / 12

        if balance <= 0:
            return {"months": 0, "total_interest": 0.0,
                    "payoff_date": date.today(), "warning": None}
        if monthly_payment <= 0:
            return {"months": None, "total_interest": None,
                    "payoff_date": None, "warning": "No payment set"}

        interest_per_month = monthly_rate * balance
        if monthly_payment <= interest_per_month:
            return {
                "months": None, "total_interest": None, "payoff_date": None,
                "warning": f"Payment ${monthly_payment:,.2f} doesn't cover "
                           f"monthly interest ${interest_per_month:,.2f}",
            }

        months = math.ceil(
            -math.log(1 - (monthly_rate * balance) / monthly_payment)
            / math.log(1 + monthly_rate)
        ) if monthly_rate > 0 else math.ceil(balance / monthly_payment)

        total_interest = monthly_payment * months - balance
        today = date.today()
        m = today.month - 1 + months
        payoff_date = date(today.year + m // 12, m % 12 + 1, 1)

        return {"months": months, "total_interest": total_interest,
                "payoff_date": payoff_date, "warning": None}

    # ── Debt avalanche / snowball ────────────────────────────────────────────

    @staticmethod
    def debt_avalanche(budget) -> list[dict]:
        """
        Optimal payoff order (highest APR first).
        Returns list of dicts with order, debt, and total interest.
        """
        return BudgetCalculator._debt_payoff_strategy(budget, key=lambda d: -d.rate)

    @staticmethod
    def debt_snowball(budget) -> list[dict]:
        """Motivation-based payoff order (lowest balance first)."""
        return BudgetCalculator._debt_payoff_strategy(budget, key=lambda d: d.balance)

    @staticmethod
    def _debt_payoff_strategy(budget, key) -> list[dict]:
        debts = sorted(budget.debt, key=key)
        result = []
        for i, debt in enumerate(debts):
            p = BudgetCalculator.debt_payoff(debt)
            result.append({
                "order": i + 1,
                "debt":  debt,
                "months": p["months"],
                "total_interest": p["total_interest"],
                "payoff_date": p["payoff_date"],
                "warning": p["warning"],
            })
        # Total interest across all debts in this strategy
        total_interest = sum(
            r["total_interest"] for r in result if r["total_interest"] is not None
        )
        return result, total_interest

    # ── Bill reminders ───────────────────────────────────────────────────────

    @staticmethod
    def bills_due_soon(budget, days_ahead: int = 7) -> list:
        """Return FixedExpense items with due_day falling within the next N days."""
        today  = date.today()
        result = []
        for exp in budget.expenses_fixed:
            due = getattr(exp, "due_day", 0)
            if not exp.active or due == 0 or exp.frequency == "once":
                continue
            # Find the next occurrence this month or next
            try:
                due_date = today.replace(day=due)
            except ValueError:
                continue   # e.g. due_day=31 in February
            if due_date < today:
                total = today.year * 12 + today.month
                due_date = date(total // 12, total % 12 + 1, due)
            days_until = (due_date - today).days
            if 0 <= days_until <= days_ahead:
                result.append((exp, due_date, days_until))
        result.sort(key=lambda x: x[1])
        return result

    # ── Frequency conversion ─────────────────────────────────────────────────

    @staticmethod
    def _to_monthly(amount: float, frequency: str) -> float:
        freq_map = {
            "weekly":     lambda x: x * 4.33,
            "biweekly":   lambda x: x * 2.165,
            "monthly":    lambda x: x,
            "semesterly": lambda x: x * 2 / 12,
            "yearly":     lambda x: x / 12,
            "once":       lambda x: 0.0,
        }
        return freq_map.get(frequency, lambda x: x)(amount)

    @staticmethod
    def _to_annual(amount: float, frequency: str) -> float:
        return BudgetCalculator._to_monthly(amount, frequency) * 12

    @staticmethod
    def one_time_income_in_period(budget, start: date, end: date) -> float:
        return sum(
            i.amount for i in budget.income
            if i.frequency == "once" and i.active and i.date
            and start.isoformat() <= i.date <= end.isoformat()
        )

    @staticmethod
    def one_time_expenses_in_period(budget, start: date, end: date) -> float:
        return sum(
            e.amount for e in budget.expenses_fixed
            if e.frequency == "once" and e.active and e.date
            and start.isoformat() <= e.date <= end.isoformat()
        )
