# Changelog

All notable changes to Kopilka are documented here.

## [0.3.0] — 2026-06-02

### Added

**One-time purchase pool**
- New `ONE_TIME_CATEGORY_ID` sentinel lets spending entries be logged against an annual discretionary pool rather than a rolling category
- Dashboard shows YTD one-time spend and annual pool remaining (coloured green/red)
- `BudgetCalculator.yearly_one_time_spending()` sums entries under the sentinel for the current year

**Recurring entries**
- New `RecurringEntry` dataclass — a spending template with name, category, amount, frequency (weekly / biweekly / monthly), and next-due date
- Stored in `Budget.recurring`; auto-inserted into the spending log when `next_date` is reached

**Category colours**
- `SpendingCategory.color` stores a hex colour string
- 12 preset colours in `CATEGORY_COLORS` (blue, green, yellow, orange, red, purple, brown, teal, pink, indigo, forest, slate)
- Category dialog now shows a colour-swatch picker with active-ring highlight

**Bill reminders — weekly and yearly support**
- `FixedExpense.due_weekday` (0=Mon…6=Sun) for weekly bills
- `FixedExpense.due_doy` (1–366 day-of-year) for yearly bills
- `BudgetCalculator.bills_due_soon()` now correctly handles all four frequency families (weekly, monthly/biweekly/semesterly, yearly, once)
- Expense dialog shows the appropriate due-date field per frequency: weekday picker for weekly, month + day pickers for yearly, day-of-month spinner otherwise

**Configurable bills lookahead**
- `Budget.bills_look_ahead_days` (default 7) sets the bills-due-soon window
- Settings view exposes the field; dashboard "No bills due" message reflects the configured value

**Biweekly payday alignment**
- `IncomeSource.next_payday` stores a reference ISO date for biweekly sources
- `BudgetCalculator.next_biweekly_payday()` advances the reference by 14-day intervals to find the next upcoming payday
- Income dialog shows the reference payday field when frequency is biweekly

**Asset interest rate**
- `Asset.interest_rate` (annual %) added to the model and savings dialogs

**Gost Type B font**
- `gosttypeb.ttf` bundled in `kopilka/data/fonts/` — no system font installation required
- Font loaded at startup via `PangoCairo.FontMap.get_default().add_font_file()`
- Sidebar toggle renamed "Gost Type B" with subtitle "Technical drafting typeface"

**Quick-log shortcut**
- `Ctrl+Shift+L` opens the log-purchase dialog from anywhere in the app

### Fixed

- `UnboundLocalError: cannot access local variable 'BudgetCalculator'` crash in `CategoryView.refresh()` caused by a shadowing local import inside the method body
- Bills-due-soon calculation skipped weekly and yearly expenses entirely (only day-of-month was checked); weekly bills now use `due_weekday`, yearly bills use `due_doy`

### Changed

- `pyproject.toml` version bumped to 0.3.0
- `kopilka/data/` and `kopilka/data/fonts/` added as proper Python subpackages (with `__init__.py`) so `importlib.resources` can resolve bundled assets

---

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
