"""Budget data model."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime
import uuid


@dataclass
class IncomeSource:
    """Income source item."""
    name: str
    owner: str
    amount: float
    frequency: str  # monthly, weekly, semesterly, yearly, custom
    is_taxed: bool = True
    notes: str = ""
    active: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class FixedExpense:
    """Fixed expense item."""
    name: str
    amount: float
    frequency: str  # monthly, weekly, etc.
    notes: str = ""
    active: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Debt:
    """Debt item."""
    name: str
    balance: float
    rate: float
    payment: float
    frequency: str
    notes: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class SpendingCategory:
    """Spending category."""
    name: str
    budget_weekly: float
    shared: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    @property
    def budget_monthly(self) -> float:
        """Calculate monthly budget from weekly."""
        return self.budget_weekly * 4.33


@dataclass
class SpendingEntry:
    """Individual spending entry."""
    date: str  # ISO format
    category_id: str
    amount: float
    description: str
    user: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Budget:
    """Main budget container."""
    version: str = "0.1.0"
    couple: List[str] = field(default_factory=lambda: ["User 1", "User 2"])
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified_by: str = "User 1"
    currency: str = "CAD"
    tax_year: int = 2026
    province: str = "Nova Scotia"
    sync_path: str = ""
    
    income: List[IncomeSource] = field(default_factory=list)
    expenses_fixed: List[FixedExpense] = field(default_factory=list)
    debt: List[Debt] = field(default_factory=list)
    categories: List[SpendingCategory] = field(default_factory=list)
    spending: List[SpendingEntry] = field(default_factory=list)
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
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
            },
            "income": [asdict(i) for i in self.income],
            "expenses_fixed": [asdict(e) for e in self.expenses_fixed],
            "debt": [asdict(d) for d in self.debt],
            "categories": [asdict(c) for c in self.categories],
            "spending": [asdict(s) for s in self.spending],
        }
    
    @staticmethod
    def from_dict(data: dict) -> "Budget":
        """Create Budget from dictionary."""
        budget = Budget()
        
        if "metadata" in data:
            budget.couple = data["metadata"].get("couple", ["User 1", "User 2"])
            budget.created = data["metadata"].get("created", "")
            budget.last_modified = data["metadata"].get("last_modified", "")
            budget.last_modified_by = data["metadata"].get("last_modified_by", "")
        
        if "config" in data:
            budget.currency = data["config"].get("currency", "CAD")
            budget.tax_year = data["config"].get("tax_year", 2026)
            budget.province = data["config"].get("province", "Nova Scotia")
            budget.sync_path = data["config"].get("sync_path", "")
        
        # TODO: Load income, expenses, debt, categories, spending
        
        return budget
