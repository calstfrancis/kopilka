"""Budget calculations and aggregations."""

from kopilka.logic.tax_calc import TaxCalculator


class BudgetCalculator:
    """Calculate budget metrics."""
    
    @staticmethod
    def monthly_gross_income(budget) -> float:
        """Calculate total monthly gross income (scaled)."""
        total = 0
        for income in budget.income:
            if not income.active:
                continue
            
            monthly = BudgetCalculator._to_monthly(income.amount, income.frequency)
            total += monthly
        
        return total
    
    @staticmethod
    def monthly_net_income(budget) -> float:
        """Calculate total monthly net income after taxes."""
        # Calculate annual taxable income
        annual_taxable = 0
        for income in budget.income:
            if not income.active or not income.is_taxed:
                continue
            
            annual = BudgetCalculator._to_annual(income.amount, income.frequency)
            annual_taxable += annual
        
        # Estimate tax
        monthly_tax = TaxCalculator.estimate_monthly_tax(annual_taxable)
        
        # Return gross - tax
        return BudgetCalculator.monthly_gross_income(budget) - monthly_tax
    
    @staticmethod
    def monthly_fixed_costs(budget) -> float:
        """Calculate total monthly fixed expenses."""
        total = 0
        for expense in budget.expenses_fixed:
            if not expense.active:
                continue
            
            monthly = BudgetCalculator._to_monthly(expense.amount, expense.frequency)
            total += monthly
        
        return total
    
    @staticmethod
    def monthly_debt_payments(budget) -> float:
        """Calculate total monthly debt payments."""
        total = 0
        for debt in budget.debt:
            monthly = BudgetCalculator._to_monthly(debt.payment, debt.frequency)
            total += monthly
        
        return total
    
    @staticmethod
    def available_to_spend(budget) -> float:
        """Calculate available to spend (net - fixed - debt)."""
        net = BudgetCalculator.monthly_net_income(budget)
        fixed = BudgetCalculator.monthly_fixed_costs(budget)
        debt = BudgetCalculator.monthly_debt_payments(budget)
        
        return net - fixed - debt
    
    @staticmethod
    def _to_monthly(amount: float, frequency: str) -> float:
        """Convert amount to monthly equivalent."""
        freq_map = {
            "weekly": lambda x: x * 4.33,
            "biweekly": lambda x: x * 2.165,
            "monthly": lambda x: x,
            "semesterly": lambda x: x * 2 / 12,
            "yearly": lambda x: x / 12,
        }
        
        converter = freq_map.get(frequency, lambda x: x)
        return converter(amount)
    
    @staticmethod
    def _to_annual(amount: float, frequency: str) -> float:
        """Convert amount to annual equivalent."""
        monthly = BudgetCalculator._to_monthly(amount, frequency)
        return monthly * 12
