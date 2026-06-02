# Kopilka

A couples budget planner built with GTK 4 and libadwaita. Designed for two-person households in Nova Scotia, Canada — tracks income, taxes, fixed expenses, debt, discretionary spending, assets, and savings goals in a single shared JSON file synced via pCloud.

## Features

- **Dashboard** — income breakdown, net budget, bills calendar, net worth summary, spending category bars
- **Income tracking** — multiple sources per person with Nova Scotia 2026 tax estimation (federal + provincial + CPP tier 1 & 2 + EI)
- **Fixed expenses** — monthly/weekly/annual bills with calendar view and next-due dates (configurable lookahead window)
- **Debt management** — payoff projections with what-if extra payment slider
- **Discretionary spending** — per-category budgets with weekly/monthly/bi-weekly/semi-annual periods, rollover support, seasonal overrides, and colour-coded category pills
- **One-time purchase pool** — log irregular purchases against an annual discretionary pool; dashboard tracks YTD spend and remaining allowance
- **Recurring entries** — spending templates (weekly/biweekly/monthly) that auto-insert into the log
- **Spending log** — date-filtered entry log grouped by date with category tagging
- **Reports** — donut charts, monthly bar charts, per-category trend rows, filterable by week / month / quarter / year
- **Assets & savings goals** — TFSA, RRSP, chequing, and brokerage accounts with balance history and line charts; lightweight savings goal tracker
- **Settings** — partner names, pCloud sync path, budget file location
- **pCloud sync** — passive mtime-based external-change detection with reload banner; conflict-file detection on startup
- **Setup wizard** — first-launch onboarding flow

## Requirements

- Python 3.10+
- GTK 4.0 + libadwaita 1.x (system packages)
- PyGObject 3.46+

### Install system dependencies

**openSUSE Tumbleweed**
```sh
sudo zypper install python3-gobject typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0
```

**Ubuntu 22.04+**
```sh
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
```

**Fedora 38+**
```sh
sudo dnf install python3-gobject gtk4 libadwaita
```

## Installation

### AppImage (recommended for end users)

Download the latest `Kopilka-x86_64.AppImage` from the [Releases](https://github.com/calstfrancis/kopilka/releases) page, make it executable, and run it:

```sh
chmod +x Kopilka-x86_64.AppImage
./Kopilka-x86_64.AppImage
```

### From source

```sh
pip install --user -e .
kopilka
```

Or with [pipx](https://pipx.pypa.io/) (recommended for isolation):

```sh
pipx install --system-site-packages .
kopilka
```

### Desktop entry

```sh
python -m kopilka.desktop_install
```

This installs the `.desktop` file and icon to `~/.local/share/`.

## Data & config

| Path | Contents |
|---|---|
| `~/.config/kopilka/budget.json` | All budget data |
| `~/.config/kopilka/config.json` | User names, budget path, pCloud sync path |

Budget data is a plain JSON file — back it up or sync it via pCloud (shared folder). The app detects external changes on window focus and offers a one-click reload.

## Running from source

```sh
python -m kopilka.kopilka
# or after pip install -e .
kopilka
```

## Project structure

```
kopilka/
  kopilka.py          Entry point
  model/budget.py     Dataclasses: Budget, IncomeSource, Debt, Asset, SavingsGoal, RecurringEntry, …
  logic/
    calculations.py   Pure math — income, tax deductions, debt payoff, rollover
    tax_calc.py       Federal + NS 2026 marginal tax, CPP tier 1+2, EI
    sync.py           pCloud conflict detection, mtime monitoring
  storage/json_io.py  Load/save JSON, config read/write
  ui/
    app_window.py     Main window, sidebar nav, reload banner
    dashboard.py      Summary view
    views.py          Income, expense, and debt views
    forms.py          Add/edit dialogs
    spending_log.py   Time-filtered spending log
    reports.py        Donut + bar chart reports
    savings.py        Assets and savings goals
    charts.py         Cairo drawing widgets (donut, line, bar)
    settings.py       Settings view
    setup_wizard.py   First-launch wizard
```

## License

GPL-3.0 — see [LICENSE](LICENSE) if present, or the SPDX identifier in `pyproject.toml`.
