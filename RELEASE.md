# Release Notes

## [0.5.5] "Level Ledger" — math corrections, crash fixes, and UX clarity improvements

### Fixed

- **Annual one-time purchase pool overstated** — the pool was calculated as `available_to_spend × 12`, which includes money already allocated to spending categories. Now uses `unallocated_discretionary × 12` so the figure reflects genuinely free funds.
- **Debt avalanche / snowball were not cascaded** — each debt was evaluated in isolation. Both strategies now run a month-by-month simulation where freed payments from a paid-off debt roll into the next priority debt, producing accurate interest-saved figures.
- **Recurring entries could crash the app at startup** — `_apply_recurring` fired inside `SpendingLogView.refresh()` during `__init__`, before `reports_view`, `savings_view`, and `settings_view` existed. `_refresh_all_views()` then crashed accessing those missing attributes. Processing now runs in `AppWindow._on_startup()` (after all views are created) and on `_on_focus_changed()`.
- **Recurring entries now fire on window focus** — entries due while the app was in the background now insert immediately when the window regains focus, not only after the next manual edit.
- **Non-atomic budget save** — `save_budget()` wrote directly to `budget.json`; a crash mid-write left a truncated, unrecoverable file. Now uses a temp-file + `os.replace()` pattern.
- **Color pills unreadable on light category colors** — all category pills used `color:white`, which was invisible on yellow (`#f6d32d`) and stone (`#9a9996`). Foreground is now chosen by computing relative luminance.
- **CSV export ignored the active filter** — the export button exported full spending history regardless of the 7/30/90/365-day view. Now exports only the visible window.
- **Date fields unvalidated in income/expense forms** — one-time date entries were not parsed before saving; malformed ISO strings were silently persisted. Both forms now reject invalid dates on save.
- **Monthly Reports ignored seasonal budget overrides** — the "This Month" summary compared spending against `budget_monthly` (base), ignoring per-month overrides. Now uses `budget_for_month(current_month)`.
- **Monthly trend chart conflated one-time fixed expenses with category spending** — a month with annual insurance appeared over-budget even if all category spending was fine. Bars now show category spending only; one-time fixed expenses are annotated in the text rows.

### Improved

- **Dashboard category rows now show the time window** — e.g. "week of 16 Jun: $45 of $150/wk", making mixed weekly/monthly category rows unambiguous at a glance.
- **Bill reminders show frequency and per-period unit** — subtitle now includes the billing frequency; the amount label shows the unit (e.g. `$18.99/mo`, `$1,200/yr`).
- **Income rows now display the per-period unit** — e.g. `$3,500/2wk` instead of `$3,500`.
- **Income form prompts for take-home pay** — the amount field subtitle now reads "Enter your take-home (after-tax) amount".
- **About dialog shows release name** — version now appears as `0.5.5 "Level Ledger"` in the About dialog and What's New panel.
