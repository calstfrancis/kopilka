# Kopilka — Developer Notes

## What it is

Couples budget planner built with GTK 4 / libadwaita. Designed for two-person households in
Nova Scotia, Canada. Tracks income, fixed expenses, debt, and discretionary spending across
shared categories. The budget lives in a single JSON file; sync happens via pCloud (shared
folder, passive conflict detection).

## Running

```sh
pip install -e .
kopilka
# or directly
python -m kopilka.kopilka
```

- Budget file: `~/.config/kopilka/budget.json`
- App config: `~/.config/kopilka/config.json` (user names, budget path, sync path)

## Version and release name

`kopilka/__init__.py` exports both `__version__` and `__release_name__`. Both must be kept
in sync when bumping for a release:

```python
__version__ = "0.5.5"
__release_name__ = "Level Ledger"
```

`app_window.py` imports `_RELEASE_NAME` and uses it in `set_version()` and
`set_release_notes()` of the `Adw.AboutDialog`. When releasing, update both symbols and
rewrite `set_release_notes()` with the new What's New text.

## Module map

| Path | Responsibility |
|---|---|
| `kopilka/kopilka.py` | Entry point — creates `Adw.Application`, calls `ensure_installed` |
| `kopilka/model/budget.py` | All dataclasses: `Budget`, `IncomeSource`, `FixedExpense`, `Debt`, `SpendingCategory`, `SpendingEntry`, `Asset`, `SavingsGoal` |
| `kopilka/logic/calculations.py` | Pure math on budget objects — income, tax deductions, debt payoff, category rollover, period conversions |
| `kopilka/logic/tax_calc.py` | Federal + Nova Scotia 2026 income tax, CPP tier 1+2, EI |
| `kopilka/logic/sync.py` | pCloud conflict detection; mtime-based external-change detection |
| `kopilka/storage/json_io.py` | Load/save `Budget` as JSON; config read/write |
| `kopilka/ui/app_window.py` | `AppWindow` — split view, sidebar nav, reload banner, Simple + Gost font toggles |
| `kopilka/ui/dashboard.py` | `Dashboard` — summary view with income, budget breakdown, bills, net worth, category bars, onboarding nudge banner |
| `kopilka/ui/views.py` | `IncomeView`, `ExpenseView`, `DebtView` (with what-if slider), `CategoryView` |
| `kopilka/ui/forms.py` | All add/edit dialogs: income, expense, debt, category, spending entry |
| `kopilka/ui/spending_log.py` | `SpendingLogView` — time-filtered log grouped by date |
| `kopilka/ui/reports.py` | `ReportsView` — donut charts, monthly bar chart, trend rows |
| `kopilka/ui/savings.py` | `SavingsView` — asset accounts with history, savings goals with contribution calc |
| `kopilka/ui/charts.py` | `DonutChart`, `BalanceLineChart`, `MonthlyBarChart` — Cairo/PangoCairo drawing widgets |
| `kopilka/ui/settings.py` | `SettingsView` — partner names, pCloud sync path, danger zone |
| `kopilka/ui/setup_wizard.py` | `SetupWizard` — first-launch onboarding |

## Data model key points

**Period units vs monthly units** — the subtlest part of the model:

- `SpendingCategory.budget_amount` is stored in **period units**: a weekly category of $200/wk
  stores `200.0`, not `866.0`.
- `SpendingCategory.budget_monthly` converts to monthly via `_PERIOD_TO_MONTHLY`
  (weekly × 4.33, semesterly × 2/12, etc.). Use this for allocation math
  (unallocated discretionary, monthly budget totals).
- `BudgetCalculator.category_effective_budget()` returns in **period units**
  (monthly base ÷ period_factor + rollover). Use this for per-period display.
- `budget_for_month(month_int)` always returns a **monthly** amount and applies
  seasonal overrides. It is not period-aware — do not compare it directly against
  weekly spending.
- `_PERIOD_TO_MONTHLY` in `model/budget.py` and `_PERIOD_FACTOR` in `calculations.py`
  are identical dicts. They exist in both modules to avoid a circular import.

**Rollover** — `category_effective_budget` = base + rollover. Rollover is computed from the
previous cycle's surplus/deficit according to `surplus_policy` / `deficit_policy`. All values
are in period units once the fix in `calculations.py` is applied.

**Spending entries** store ISO date strings (`"2026-06-01"`), not `date` objects. Compare
with `date.isoformat()`.

**Assets vs savings goals** — `Asset` represents a real account with balance history
(TFSA, chequing, brokerage…). `SavingsGoal` is a lightweight target tracker without
institution data. `BudgetCalculator.total_assets` prefers `budget.assets` if any exist,
falls back to `savings_goals.current` sum.

## Refresh pattern

All views receive `(budget, on_change)`. `on_change()` triggers:

```
save_budget → update mtime → _refresh_all_views
```

`_refresh_all_views` calls `view.refresh()` on every view. Do not call
`dashboard.refresh(budget)` directly without also persisting — the budget object in memory
may diverge from disk.

## Collapsible expanders in Dashboard

`Adw.ExpanderRow` children cannot be removed individually after being added via `add_row()`.
The whole expander is therefore removed from its container group and recreated on each
`refresh()`. Expanded state is preserved in `_bills_expanded` / `_nw_expanded` before
removal.

## What-if slider in DebtView

`DebtView._whatif_extra` (float, default 0) persists across `refresh()` calls so the extra-
payment value survives list rebuilds. The results listbox is updated live without a full
`refresh()` — only the results container is cleared and repopulated.

## Sync

pCloud sync is passive: the app monitors `budget.json`'s mtime when the window regains
focus. If the file changed externally, a reload banner appears. Conflicts (pCloud creates
`budget (... conflicted copy ...).json` siblings) are detected at startup and the user is
offered to delete them or open the folder.

## Tax calculation

Nova Scotia 2026 marginal rates. CPP uses tier 1 (YMPE $73 200) + tier 2 (YAMPE $81 900).
EI cap at $65 700 insurable earnings. The `cpp_ei_applicable` flag on `IncomeSource` lets
non-employment income (scholarships, investment income, pensions) skip CPP/EI.

## Accessibility conventions

- All icon-only buttons must carry `tooltip_text` — AT-SPI uses it as the accessible name.
- Cairo chart widgets set `Gtk.AccessibleProperty.LABEL` via `update_property` so screen
  readers announce the chart type and summary values.
- Progress bars carry `tooltip_text` with the numeric fraction (e.g. "$150 of $200 — 75%").
- Form rows use `set_tooltip_text` on `Adw.EntryRow`, `Adw.SpinRow`, and `Adw.ComboRow`
  to explain non-obvious fields.
