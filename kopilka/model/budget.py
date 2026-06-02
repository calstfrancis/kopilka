"""Budget data model."""

from dataclasses import dataclass, field, asdict
from typing import List
from datetime import datetime
import uuid


# Sentinel category_id for one-time / irregular purchases
ONE_TIME_CATEGORY_ID = "__one_time__"

# Preset palette for category colour pills
CATEGORY_COLORS = [
    "#3584e4",  # blue
    "#33d17a",  # green
    "#f6d32d",  # yellow
    "#ff7800",  # orange
    "#e01b24",  # red
    "#9141ac",  # purple
    "#986a44",  # brown
    "#1c787e",  # teal
    "#e61a80",  # pink
    "#1a5fb4",  # indigo
    "#26a269",  # forest
    "#5c5c5c",  # slate
]


@dataclass
class IncomeSource:
    name: str
    owner: str
    amount: float
    frequency: str          # weekly | biweekly | monthly | semesterly | yearly | once
    is_taxed: bool = True
    cpp_ei_applicable: bool = True
    notes: str = ""
    active: bool = True
    date: str = ""          # ISO date for one-time items
    next_payday: str = ""   # ISO date reference for biweekly pay alignment
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class FixedExpense:
    name: str
    amount: float
    frequency: str
    notes: str = ""
    active: bool = True
    date: str = ""          # ISO date for one-time items
    due_day: int = 0        # day-of-month (1-31) for monthly/biweekly/semesterly; 0 = no reminder
    due_weekday: int = -1   # 0=Mon…6=Sun for weekly frequency; -1 = not set
    due_doy: int = 0        # 1-366 day-of-year for yearly frequency; 0 = not set
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Debt:
    name: str
    balance: float
    rate: float
    payment: float
    frequency: str
    notes: str = ""
    balance_history: list = field(default_factory=list)  # [{date, balance, note}]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


ASSET_TYPES = [
    "chequing", "savings", "tfsa", "rrsp", "fhsa",
    "resp", "brokerage", "crypto", "gic", "other",
]
ASSET_TYPE_LABELS = {
    "chequing":  "Chequing",
    "savings":   "Savings / HYSA",
    "tfsa":      "TFSA",
    "rrsp":      "RRSP",
    "fhsa":      "FHSA",
    "resp":      "RESP",
    "brokerage": "Non-reg. Brokerage",
    "crypto":    "Crypto",
    "gic":       "GIC / Bond",
    "other":     "Other",
}
ASSET_TYPE_GROUPS = {
    "Bank":       ["chequing", "savings"],
    "Registered": ["tfsa", "rrsp", "fhsa", "resp"],
    "Investments":["brokerage", "crypto", "gic"],
    "Other":      ["other"],
}


@dataclass
class Asset:
    """A financial account or holding."""
    name: str
    asset_type: str         # one of ASSET_TYPES
    owner: str
    balance: float          # current market value / balance
    institution: str = ""   # TD, RBC, Questrade, Wealthsimple…
    interest_rate: float = 0.0  # annual interest / dividend rate (%)
    notes: str = ""
    # Each entry: {date, balance, change, change_type, note}
    # change_type: deposit | withdrawal | interest | dividend | gain | loss | fee | transfer | other
    balance_history: list = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class SavingsGoal:
    name: str
    target: float
    current: float = 0.0
    target_date: str = ""   # ISO date
    notes: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def progress_pct(self) -> float:
        return min(self.current / self.target, 1.0) if self.target > 0 else 0.0

    @property
    def remaining(self) -> float:
        return max(self.target - self.current, 0.0)


_PERIOD_TO_MONTHLY = {
    "weekly":     4.33,
    "monthly":    1.0,
    "semesterly": 2 / 12,
    "yearly":     1 / 12,
}


@dataclass
class SpendingCategory:
    name: str
    budget_amount: float
    budget_period: str = "weekly"
    shared: bool = True
    # Rollover policies
    surplus_policy: str = "ignore"        # ignore | carry_forward | to_debt | to_savings
    deficit_policy: str = "ignore"        # ignore | deduct_next | amortize
    deficit_amortize_cycles: int = 3
    # Monthly budget overrides  {month_int: amount}  e.g. {12: 400.0}
    monthly_overrides: dict = field(default_factory=dict)
    color: str = ""         # hex colour for pill labels e.g. "#3584e4"; "" = no colour
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def budget_monthly(self) -> float:
        return self.budget_amount * _PERIOD_TO_MONTHLY.get(self.budget_period, 1.0)

    @property
    def budget_weekly(self) -> float:
        return self.budget_monthly / 4.33

    def budget_for_month(self, month: int) -> float:
        """Monthly budget, applying seasonal override if set."""
        return self.monthly_overrides.get(month, self.budget_monthly)


@dataclass
class SpendingEntry:
    date: str               # ISO format
    category_id: str        # SpendingCategory.id or ONE_TIME_CATEGORY_ID
    amount: float
    description: str
    user: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class RecurringEntry:
    """A template that auto-inserts a SpendingEntry when next_date is reached."""
    name: str
    category_id: str        # SpendingCategory.id or ONE_TIME_CATEGORY_ID
    amount: float
    description: str
    user: str
    frequency: str          # weekly | biweekly | monthly
    next_date: str          # ISO date — when to next insert
    active: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Budget:
    version: str = "0.1.0"
    couple: List[str] = field(default_factory=lambda: ["User 1", "User 2"])
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified_by: str = "User 1"
    currency: str = "CAD"
    tax_year: int = 2026
    province: str = "Nova Scotia"
    sync_path: str = ""
    bills_look_ahead_days: int = 7

    income: List[IncomeSource] = field(default_factory=list)
    expenses_fixed: List[FixedExpense] = field(default_factory=list)
    debt: List[Debt] = field(default_factory=list)
    categories: List[SpendingCategory] = field(default_factory=list)
    spending: List[SpendingEntry] = field(default_factory=list)
    savings_goals: List[SavingsGoal] = field(default_factory=list)
    assets: List[Asset] = field(default_factory=list)
    recurring: List[RecurringEntry] = field(default_factory=list)

    def to_dict(self):
        return {
            "version": self.version,
            "metadata": {
                "couple": self.couple,
                "created": self.created,
                "last_modified": self.last_modified,
                "last_modified_by": self.last_modified_by,
            },
            "config": {
                "currency": self.currency,
                "tax_year": self.tax_year,
                "province": self.province,
                "sync_path": self.sync_path,
                "bills_look_ahead_days": self.bills_look_ahead_days,
            },
            "income":          [asdict(i) for i in self.income],
            "expenses_fixed":  [asdict(e) for e in self.expenses_fixed],
            "debt":            [asdict(d) for d in self.debt],
            "categories": [
                {
                    "id": c.id, "name": c.name,
                    "budget_amount": c.budget_amount, "budget_period": c.budget_period,
                    "shared": c.shared,
                    "surplus_policy": c.surplus_policy,
                    "deficit_policy": c.deficit_policy,
                    "deficit_amortize_cycles": c.deficit_amortize_cycles,
                    "monthly_overrides": {str(k): v for k, v in c.monthly_overrides.items()},
                    "color": c.color,
                }
                for c in self.categories
            ],
            "spending":        [asdict(s) for s in self.spending],
            "savings_goals":   [asdict(g) for g in self.savings_goals],
            "assets":          [asdict(a) for a in self.assets],
            "recurring":       [asdict(r) for r in self.recurring],
        }

    @staticmethod
    def from_dict(data: dict) -> "Budget":
        budget = Budget()

        if "metadata" in data:
            m = data["metadata"]
            budget.couple           = m.get("couple", ["User 1", "User 2"])
            budget.created          = m.get("created", "")
            budget.last_modified    = m.get("last_modified", "")
            budget.last_modified_by = m.get("last_modified_by", "")

        if "config" in data:
            c = data["config"]
            budget.currency              = c.get("currency", "CAD")
            budget.tax_year              = c.get("tax_year", 2026)
            budget.province              = c.get("province", "Nova Scotia")
            budget.sync_path             = c.get("sync_path", "")
            budget.bills_look_ahead_days = c.get("bills_look_ahead_days", 7)

        for i in data.get("income", []):
            try:
                budget.income.append(IncomeSource(**i))
            except TypeError:
                pass

        for e in data.get("expenses_fixed", []):
            try:
                budget.expenses_fixed.append(FixedExpense(**e))
            except TypeError:
                pass

        for d in data.get("debt", []):
            try:
                budget.debt.append(Debt(**d))
            except TypeError:
                pass

        for c in data.get("categories", []):
            try:
                cat = dict(c)
                if "budget_weekly" in cat and "budget_amount" not in cat:
                    cat["budget_amount"] = cat.pop("budget_weekly")
                    cat.setdefault("budget_period", "weekly")
                # Convert monthly_overrides string keys → int
                raw_ov = cat.pop("monthly_overrides", {})
                cat["monthly_overrides"] = {int(k): float(v) for k, v in raw_ov.items()}
                budget.categories.append(SpendingCategory(**cat))
            except TypeError:
                pass

        for s in data.get("spending", []):
            try:
                budget.spending.append(SpendingEntry(**s))
            except TypeError:
                pass

        for g in data.get("savings_goals", []):
            try:
                budget.savings_goals.append(SavingsGoal(**g))
            except TypeError:
                pass

        for a in data.get("assets", []):
            try:
                budget.assets.append(Asset(**a))
            except TypeError:
                pass

        for r in data.get("recurring", []):
            try:
                budget.recurring.append(RecurringEntry(**r))
            except TypeError:
                pass

        return budget
