"""Canadian tax estimation (Federal + Nova Scotia)."""


class TaxCalculator:
    """Calculate federal + NS taxes for 2026."""
    
    # 2026 Federal tax brackets (approximate)
    FEDERAL_BRACKETS = [
        (55867, 0.15),
        (111733, 0.205),
        (173205, 0.26),
        (246752, 0.29),
        (float('inf'), 0.33),
    ]
    
    # 2026 Nova Scotia tax brackets (approximate)
    NS_BRACKETS = [
        (50000, 0.0505),
        (100000, 0.1015),
        (165430, 0.1419),
        (235675, 0.1667),
        (float('inf'), 0.175),
    ]
    
    @classmethod
    def estimate_monthly_tax(cls, annual_income: float) -> float:
        """
        Estimate monthly combined federal + NS tax.
        
        Args:
            annual_income: Annual taxable income
            
        Returns:
            Monthly estimated tax
        """
        federal = cls._calculate_tax(annual_income, cls.FEDERAL_BRACKETS)
        ns = cls._calculate_tax(annual_income, cls.NS_BRACKETS)
        return (federal + ns) / 12
    
    @staticmethod
    def _calculate_tax(income: float, brackets: list) -> float:
        """Calculate tax using brackets."""
        tax = 0
        previous_limit = 0
        
        for limit, rate in brackets:
            if income <= previous_limit:
                break
            
            taxable_in_bracket = min(income, limit) - previous_limit
            tax += taxable_in_bracket * rate
            previous_limit = limit
        
        return tax
    
    @classmethod
    def estimate_annual_tax(cls, annual_income: float) -> float:
        """Estimate annual combined federal + NS tax."""
        federal = cls._calculate_tax(annual_income, cls.FEDERAL_BRACKETS)
        ns = cls._calculate_tax(annual_income, cls.NS_BRACKETS)
        return federal + ns
