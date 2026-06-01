# Changelog

All notable changes to Kopilka are documented here.

## [0.2.0] — 2026-06-01

### Added

**Assets & savings goals**
- New `Asset` model: real accounts (TFSA, RRSP, chequing, FHSA, brokerage, GIC, cash, other) with typed balance history entries (deposit, withdrawal, interest, dividend, gain/loss, fee, transfer)
- New `SavingsGoal` model: lightweight target tracker with target amount, current balance, and monthly contribution
- `SavingsView` with per-account balance line charts, history log, add/edit/delete dialogs, and savings goal contribution calculator
- `BudgetCalculator.total_assets` prefers `budget.assets` when present, falls back to savings-goal sum

**Reports**
- `ReportsView` with period filter (week / month / 3 months / year)
- Spending donut chart broken down by category
- Monthly bar chart showing income vs spending for the trailing 6 months
- Per-category trend rows with period totals and budget comparison

**Charts**
- `DonutChart` — Cairo-drawn donut with legend, accessible label
- `BalanceLineChart` — account balance over time with hover crosshair
- `MonthlyBarChart` — grouped income/spending bars

**Settings view**
- Partner name editing
- pCloud sync path configuration
- Budget file relocation (open / new)
- Danger zone: reset budget

**Setup wizard**
- First-launch onboarding: partner names → income → first expense → first category

**Sidebar navigation**
- Split view with icon + label nav rows for Dashboard, Income, Expenses, Debt, Spending, Reports, Savings, Settings
- Active-section subtitle in sidebar header
- Simple mode toggle (hides tax/debt detail)
- Gost font toggle

**Sync improvements**
- mtime-based external-change detection on window focus; reload banner
- Conflict-file detection at startup (pCloud `conflicted copy` siblings) with delete or open-folder options

**Tax calculation**
- CPP tier 2 (YAMPE $81 900) added alongside tier 1 (YMPE $73 200)
- `cpp_ei_applicable` flag on `IncomeSource` skips CPP/EI for scholarships, investment income, pensions

**Data model**
- `SpendingCategory`: `surplus_policy` / `deficit_policy` fields for rollover behaviour
- `SpendingCategory.budget_monthly` property for period-to-monthly conversion
- `BudgetCalculator.category_effective_budget()` returns period-unit base + rollover
- `budget_for_month(month_int)` with seasonal override support
- Unified `_PERIOD_TO_MONTHLY` / `_PERIOD_FACTOR` dicts (weekly × 4.33, semesterly × 2/12, etc.)

**Spending log**
- Time-range filter (this week / this month / last 30 days / this year / all)
- Entries grouped by date with daily subtotals
- Inline delete with undo toast

**Dashboard**
- Bills section with next-due dates and calendar-style ordering
- Net worth expander with asset breakdown
- Onboarding nudge banner when budget is empty
- Collapsible expander rows (`Adw.ExpanderRow`) with preserved expanded state across refreshes

**Forms**
- Spending entry dialog with date picker and category selector
- Asset add/edit and history entry dialogs
- Savings goal add/edit dialogs

**AppImage**
- GitHub Actions release workflow: builds `Kopilka-x86_64.AppImage` on every `v*` tag push and attaches it to the GitHub Release

### Changed

- `pyproject.toml` version bumped to 0.2.0
- `install.sh` updated to reference `kopilka` (was leftover `budgetapp` name)
- `.gitignore` expanded: AppImage artifacts, `.venv/`, pytest/mypy/ruff caches, `Thumbs.db`
- Desktop entry: `StartupNotify=true`, `X-GNOME-SingleWindow=true`

### Fixed

- Period-unit rollover bug: `category_effective_budget` now correctly stays in period units instead of mixing monthly and period amounts
- pCloud sync path was not persisted across restarts

---

## [0.1.0] — 2026-05-01

Initial release.

- Income tracking with Nova Scotia 2026 federal + provincial tax estimation
- Fixed expense tracking (monthly / weekly / annual)
- Debt tracking with minimum payment and payoff projection
- Discretionary spending categories with period budgets and spending entry log
- Dashboard summary
- pCloud shared-folder sync (manual reload)
- Budget stored as `~/.config/kopilka/budget.json`
