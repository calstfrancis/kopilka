"""Canadian tax + payroll deduction estimation (Federal + Nova Scotia, 2026)."""


class TaxCalculator:
    """Estimate federal + NS income tax plus CPP and EI for 2026."""

    # ── Income tax brackets ────────────────────────────────────────────────────
    # Federal 2026 (approximate — CRA adjusts annually for inflation)
    FEDERAL_BRACKETS = [
        (55_867,        0.150),
        (111_733,       0.205),
        (173_205,       0.260),
        (246_752,       0.290),
        (float("inf"),  0.330),
    ]

    # Nova Scotia 2026 (approximate)
    NS_BRACKETS = [
        (50_000,        0.0505),
        (100_000,       0.1015),
        (165_430,       0.1419),
        (235_675,       0.1667),
        (float("inf"),  0.1750),
    ]

    # ── CPP (Canada Pension Plan) ──────────────────────────────────────────────
    # Employee rates — 2025 actuals used as 2026 estimate
    CPP_RATE          = 0.0595     # employee share, tier 1
    CPP_EXEMPTION     = 3_500      # basic annual exemption (unchanged since 2019)
    CPP_YMPE          = 73_200     # Year's Maximum Pensionable Earnings, tier 1
    CPP2_RATE         = 0.04       # employee share, tier 2 (added 2024)
    CPP2_YAMPE        = 81_900     # Year's Additional Maximum Pensionable Earnings

    # ── EI (Employment Insurance) ─────────────────────────────────────────────
    # Employee premium rate — 2025 actuals used as 2026 estimate
    EI_RATE           = 0.0166
    EI_MAX_INSURABLE  = 65_700     # maximum annual insurable earnings

    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def estimate_monthly_income_tax(cls, annual_income: float) -> float:
        """Federal + NS income tax only (no CPP/EI)."""
        federal = cls._calculate_tax(annual_income, cls.FEDERAL_BRACKETS)
        ns      = cls._calculate_tax(annual_income, cls.NS_BRACKETS)
        return (federal + ns) / 12

    @classmethod
    def estimate_monthly_tax(cls, annual_income: float) -> float:
        """
        Total monthly employee deductions:
        federal + NS income tax + CPP (tier 1 + 2) + EI.
        Uses the same income base for all three (convenience / backward compat).
        """
        return (
            cls.estimate_monthly_income_tax(annual_income)
            + cls.estimate_monthly_cpp(annual_income)
            + cls.estimate_monthly_ei(annual_income)
        )

    @classmethod
    def estimate_monthly_cpp(cls, annual_income: float) -> float:
        """Monthly employee CPP1 + CPP2 contributions."""
        cpp1 = max(0.0, min(annual_income, cls.CPP_YMPE) - cls.CPP_EXEMPTION) * cls.CPP_RATE
        cpp2 = max(0.0, min(annual_income, cls.CPP2_YAMPE) - cls.CPP_YMPE) * cls.CPP2_RATE
        return (cpp1 + cpp2) / 12

    @classmethod
    def estimate_monthly_ei(cls, annual_income: float) -> float:
        """Monthly employee EI premium."""
        return min(annual_income, cls.EI_MAX_INSURABLE) * cls.EI_RATE / 12

    @classmethod
    def estimate_annual_tax(cls, annual_income: float) -> float:
        return cls.estimate_monthly_tax(annual_income) * 12

    @staticmethod
    def _calculate_tax(income: float, brackets: list) -> float:
        tax, prev = 0.0, 0.0
        for limit, rate in brackets:
            if income <= prev:
                break
            tax += (min(income, limit) - prev) * rate
            prev = limit
        return tax
