# Changelog

All notable changes to Kopilka are documented here.

## [0.5.5] "Level Ledger" — math, crash, and UX fixes

### Fixed
- **Annual one-time pool was wildly overstated** — the pool was calculated as `available_to_spend × 12` which includes money already allocated to spending categories; now uses `unallocated_discretionary × 12` so the pool reflects only genuinely free funds
- **Debt avalanche / snowball now model payment cascade** — previously each debt was evaluated in isolation; freed payments from a paid-off debt now roll into the next priority debt, giving accurate "true avalanche" interest savings
- **Recurring entries could crash app at startup** — `_apply_recurring` was called inside `SpendingLogView.refresh()` which fired during `__init__`, before later views (Reports, Savings, Settings) existed; `_refresh_all_views()` then referenced those missing attributes. Recurring processing is now owned by `AppWindow._on_startup()` and `_on_focus_changed()` instead
- **Recurring entries now fire on window focus** — previously entries due while the app was in the background would not fire until any budget change was made; the focus-change handler now triggers them immediately
- **`save_budget` was not atomic** — a crash during write left a truncated `budget.json`; now uses a temp-file + `os.replace()` pattern
- **Color pills unreadable on light category colors** — hardcoded `color:white` text was invisible on yellow (#f6d32d) and stone (#9a9996); pill foreground is now chosen by luminance
- **CSV export ignored the active time filter** — exported all spending history regardless of the 7/30/90/365-day view; now exports only the visible window
- **Date fields in income/expense forms had no validation** — malformed dates on one-time items were silently saved; both forms now reject invalid ISO dates on save
- **Monthly Reports used base budget, not seasonal overrides** — "This Month" summary compared spending against `budget_monthly`, ignoring per-month overrides; now uses `budget_for_month(current_month)`
- **Monthly trend chart folded fixed one-time expenses into category spending bars** — a month with annual insurance appeared over-budget even if all category spending was fine; the bar now shows category spending only, with fixed one-time expenses annotated as text

### Improved
- **Dashboard category rows now show the time window** — e.g. "week of 16 Jun: $45 of $150/wk" instead of just "$45 of $150/wk", making mixed weekly/monthly categories unambiguous
- **Bill reminders show frequency** — subtitle now includes the billing frequency; amount label includes the per-period unit (e.g. "$18.99/mo")
- **Income list shows per-period unit** — each income row now displays "$3,500/2wk" instead of "$3,500", avoiding ambiguity between pay frequencies
- **Income form prompts for take-home pay** — subtitle on the amount field now reads "Enter your take-home (after-tax) amount"

---

## [0.5.4] — 2026-06-10

### Fixed
- **Biweekly income/expense factor corrected** — was `× 2.165`, now `× 26/12` (≈ 2.1667); affects monthly totals, debt payoff projections, and unallocated amounts
- **Recurring entry loop bomb** — if a recurring entry's `next_date` was set far in the past, the app would insert hundreds of entries and freeze; capped at 730 insertions, then clamps `next_date` to today
- **Biweekly payday O(1) calculation** — `next_biweekly_payday()` used an unbounded while-loop; replaced with direct arithmetic
- **Monthly budget override silently lost on load** — `{str → int}` key conversion failure would drop the entire category; bad overrides now fall back to `{}` instead of losing the category
- **Save failure now shown to user** — `save_budget()` returning `False` previously went unnoticed; a persistent toast is now shown
- **Silent item discard on load now logged** — corrupted JSON items are printed to stderr instead of disappearing silently
- **Delete category warns about orphaned spending** — confirmation dialog now shows how many spending entries will show as "Unknown category"
- **"Who paid?" crash on empty couple list** — guarded against a budget file with an empty couple array
- **Version string unified** — status bar and About dialog now read from `__version__`; `__init__.py` was stale at `0.1.0`

---

## [0.5.3] — 2026-06-10

### Fixed
- **App would not open from GNOME launcher or Discover** — a background test process was holding the D-Bus name, but the underlying issue was that `on_activate` always created a new window instead of raising the existing one on repeated launches. Subsequent launcher clicks now bring the existing window to the front.
- **"Savings & Investments" label caused a GTK markup warning** — `Adw.ActionRow.set_title()` parses Pango markup, so the bare `&` was rejected; escaped to `&amp;`.

## [0.5.2] — 2026-06-09

### Added
- **Status bar** — new bottom bar with SIMPLE and GOST toggle buttons (replaces the sidebar switches), matching the layout in Rubric and Zerkalo. Active toggles appear bold; inactive toggles are dimmed.
- **About / changelog dialog** — version chip `v0.5.2` on the right of the status bar opens the standard GNOME About dialog with release notes.

## [0.5.1] — 2026-06-09

### Fixed
- **App would not open on most systems** — the flatpak was built against GNOME Platform 50, which is not yet available on most Linux distributions. Downgraded to Platform 48 (matching Zerkalo and Rubric).
- **GNOME taskbar icon mismatch** — the installed desktop file was missing `StartupWMClass`, causing the launcher icon and running window to appear as separate items in the dock/taskbar.
- **Desktop integration ran inside Flatpak** — `ensure_installed()` (the bare-Python icon installer) was running even inside the Flatpak sandbox, where it is pointless and was writing a redundant `.desktop` file to `~/.local/share/applications/`.
- **Recurring entry insertion caused double-render of the spending log** — inserting due recurring entries on `refresh()` triggered `on_change()` → `_refresh_all_views()` → `refresh()` a second time, rendering the list twice.
- **Settings view showed stale values after budget reload** — partner names and bills look-ahead setting were not updated when the budget was reloaded from sync.
- **Budget open/create errors were silently swallowed** — file permission errors, malformed JSON, and similar failures when opening or creating a budget file now show a persistent toast message.
- **`_curr_cycle` monthly end-date formula** — replaced an implicit year-overflow trick with an explicit December check; same fix applied to `bills_due_soon`.
- **Bare `except:` in `json_io.py`** — was catching `SystemExit` and `KeyboardInterrupt`; changed to `except Exception:`.

## [0.5.0] — 2026-06-06

### Added

**Delete confirmation dialogs**
- Every destructive remove action (income source, expense, debt, category, spending entry, recurring entry, asset account, savings goal) now shows an `Adw.AlertDialog` before committing the deletion — no more accidental data loss

**"Today" button on all date fields**
- All date entry rows (spending log, income, expense, recurring entry, asset balance update) now have a jump-to-today icon button so the date can be reset in one click without retyping

**Friendly date headers in spending log**
- Date group separators now read "Saturday, June 6" instead of the raw ISO string "2026-06-06". The year is appended ("Saturday, June 6, 2025") when the entry is from a previous year

**Budget load error notification**
- If the budget JSON file is malformed or unreadable at startup, a persistent toast notification is now shown instead of silently starting with an empty budget

### Fixed

- **Debt balance history** (`savings.py`): `_DebtBalanceDialog` was recording the _old_ balance in the history entry instead of the new one — the history table now shows the correct balance for each logged date
- **Dashboard crash** (`dashboard.py`): `date.fromisoformat()` called on the last spending entry's date without a guard — a malformed date string would crash the dashboard refresh; now wrapped in try/except
- **End-of-month banner** (`dashboard.py`): the "month ends in N days" over/under calculation incorrectly included one-time purchase entries in the spending sum while comparing against category-only budgets; one-time entries are now excluded from that sum
- **Spending date validation** (`forms.py`): the Log Spending dialog accepted any non-empty string as a date; it now validates with `date.fromisoformat()` and highlights the field red on invalid input
- **Spending amount validation** (`forms.py`): the Log Spending dialog now rejects $0.00 entries and highlights the amount field red

### Changed

- `pyproject.toml` version bumped to 0.5.0

---

## [0.4.0-beta1] — 2026-06-03

WebDAV sync overhaul and income model simplification.

- WebDAV sync replaces pCloud-specific file-watching (`webdav_sync.py`)
- Nova Scotia tax estimation removed — income is now entered as a gross amount
- Conflict detection ported to work with WebDAV ETag comparison

---

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
