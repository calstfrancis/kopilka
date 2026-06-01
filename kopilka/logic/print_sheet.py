"""In-app printable budget sheet — Cairo/Pango renderer + GTK PrintOperation."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Gtk, Adw, Pango, PangoCairo
from datetime import date

from kopilka.logic.calculations import BudgetCalculator

# ── Page geometry  (landscape letter, 72 pt/inch) ────────────────────────────

PAGE_W  = 792
PAGE_H  = 612
MARGIN  = 34
HDR_H   = 46
SUM_H   = 50
SUM_Y   = PAGE_H - MARGIN - SUM_H   # top of summary strip
LEFT_W  = 210
GAP     = 16
RIGHT_X = MARGIN + LEFT_W + GAP
RIGHT_W = PAGE_W - MARGIN - RIGHT_X
BODY_Y  = HDR_H + 10
ROW_H   = 14

# ── Fonts (Pango description strings) ────────────────────────────────────────

F_TITLE   = "Sans Bold 16"
F_MONTH   = "Sans 9.5"
F_SEC     = "Sans Bold 6.5"
F_BODY    = "Sans 8.5"
F_BOLD    = "Sans Bold 8.5"
F_PERIOD  = "Sans Bold 11"    # the hero number — per-period amount
F_MONTHLY = "Sans 8"
F_SUMVAL  = "Sans Bold 10.5"
F_UNALLOC = "Sans Bold 13"
F_FOOT    = "Sans 5.5"

# ── Colors ────────────────────────────────────────────────────────────────────

C_INK    = (0.07, 0.07, 0.07)
C_DIM    = (0.52, 0.52, 0.52)
C_HAIR   = (0.78, 0.78, 0.78)
C_ALT    = (0.955, 0.955, 0.955)
C_HDR_BG = (0.11, 0.17, 0.27)
C_HDR_FG = (1.0,  1.0,  1.0)
C_HDR_DIM= (0.70, 0.76, 0.88)
C_SUM_BG = (0.90, 0.90, 0.90)
C_ACCENT = (0.14, 0.41, 0.76)
C_POS    = (0.08, 0.50, 0.18)
C_NEG    = (0.72, 0.09, 0.09)

_PERIOD_LABEL = {
    "weekly":     "/wk",
    "monthly":    "/mo",
    "semesterly": "/6mo",
    "yearly":     "/yr",
}
_FREQ_LABEL = {
    "weekly":     "/wk",
    "biweekly":   "/2wk",
    "monthly":    "/mo",
    "semesterly": "/6mo",
    "yearly":     "/yr",
}


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _fmt(v: float) -> str:
    return f"${v:,.0f}"


# ── Drawing primitives ────────────────────────────────────────────────────────

def _txt(cr, x, y, text, font, rgb=C_INK, align="left", box_w=None):
    """Render text; return pixel (width, height)."""
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription(font))
    layout.set_text(text, -1)
    if box_w is not None:
        layout.set_width(int(box_w * Pango.SCALE))
        layout.set_alignment(
            Pango.Alignment.RIGHT if align == "right" else Pango.Alignment.LEFT
        )
    cr.set_source_rgb(*rgb)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)
    _, lr = layout.get_pixel_extents()
    return lr.width, lr.height


def _hline(cr, x0, x1, y, rgb=C_HAIR, lw=0.5):
    cr.set_source_rgb(*rgb)
    cr.set_line_width(lw)
    cr.move_to(x0, y)
    cr.line_to(x1, y)
    cr.stroke()


def _vline(cr, x, y0, y1, rgb=C_HAIR, lw=0.5):
    cr.set_source_rgb(*rgb)
    cr.set_line_width(lw)
    cr.move_to(x, y0)
    cr.line_to(x, y1)
    cr.stroke()


def _sec_title(cr, x, y, w, title):
    """Draw section title + rule; return y after."""
    _, th = _txt(cr, x, y, title.upper(), F_SEC, C_DIM)
    _hline(cr, x, x + w, y + th + 2)
    return y + th + 6


# ── Left column sections ──────────────────────────────────────────────────────

def _draw_income(cr, x, y, w, budget, gross, net):
    y = _sec_title(cr, x, y, w, "Income")
    for inc in budget.income:
        if not inc.active or inc.frequency == "once":
            continue
        monthly = BudgetCalculator._to_monthly(inc.amount, inc.frequency)
        _txt(cr, x, y, inc.name, F_BODY, C_INK)
        _txt(cr, x, y, _fmt(monthly) + "/mo", F_BODY, C_DIM, align="right", box_w=w)
        y += ROW_H
    _hline(cr, x, x + w, y + 1)
    y += 5
    _txt(cr, x, y, "Net take-home", F_BOLD, C_INK)
    _txt(cr, x, y, _fmt(net) + "/mo", F_BOLD, C_INK, align="right", box_w=w)
    return y + ROW_H


def _draw_bills(cr, x, y, w, budget, total):
    y = _sec_title(cr, x, y, w, "Fixed Bills")
    bills = [e for e in budget.expenses_fixed if e.active and e.frequency != "once"]
    bills.sort(key=lambda e: e.due_day or 99)
    for exp in bills:
        monthly = BudgetCalculator._to_monthly(exp.amount, exp.frequency)
        due     = f"  {exp.due_day}{_ordinal(exp.due_day)}" if exp.due_day else ""
        _txt(cr, x, y, f"☐  {exp.name}{due}", F_BODY, C_INK)
        _txt(cr, x, y, _fmt(monthly) + "/mo", F_BODY, C_DIM, align="right", box_w=w)
        y += ROW_H
    _hline(cr, x, x + w, y + 1)
    y += 5
    _txt(cr, x, y, "Total", F_BOLD, C_INK)
    _txt(cr, x, y, _fmt(total) + "/mo", F_BOLD, C_INK, align="right", box_w=w)
    return y + ROW_H


def _draw_debt(cr, x, y, w, budget, total):
    y = _sec_title(cr, x, y, w, "Debt Payments")
    for d in budget.debt:
        monthly = BudgetCalculator._to_monthly(d.payment, d.frequency)
        _txt(cr, x, y, f"{d.name}  {d.rate:.1f}%", F_BODY, C_INK)
        _txt(cr, x, y, _fmt(monthly) + "/mo", F_BODY, C_DIM, align="right", box_w=w)
        y += ROW_H
    _hline(cr, x, x + w, y + 1)
    y += 5
    _txt(cr, x, y, "Total", F_BOLD, C_INK)
    _txt(cr, x, y, _fmt(total) + "/mo", F_BOLD, C_INK, align="right", box_w=w)
    return y + ROW_H


# ── Right column: categories (the centrepiece) ────────────────────────────────

def _draw_categories(cr, x, y_top, w, max_h, budget, total_monthly):
    y = _sec_title(cr, x, y_top, w, "Spending Categories")

    name_w   = w * 0.46
    period_w = w * 0.30
    month_w  = w - name_w - period_w

    # Sub-column headers
    _txt(cr, x + name_w, y, "per period", F_SEC, C_DIM, align="right", box_w=period_w)
    _txt(cr, x + name_w + period_w, y, "per month", F_SEC, C_DIM, align="right", box_w=month_w)
    y += 10
    _hline(cr, x, x + w, y)
    y += 5

    row_h = 17
    for i, cat in enumerate(budget.categories):
        if y + row_h > y_top + max_h:
            break
        # Alternating row bg
        if i % 2 == 1:
            cr.set_source_rgb(*C_ALT)
            cr.rectangle(x - 3, y - 1, w + 6, row_h)
            cr.fill()

        plabel = _PERIOD_LABEL.get(cat.budget_period, "")
        _txt(cr, x + 3, y + 3, cat.name, F_BODY, C_INK)

        # Per-period: big, blue, the focus of attention
        _txt(cr, x + name_w, y,
             f"{_fmt(cat.budget_amount)}{plabel}", F_PERIOD, C_ACCENT,
             align="right", box_w=period_w)

        # Per-month: small, gray, context only
        _txt(cr, x + name_w + period_w, y + 5,
             f"{_fmt(cat.budget_monthly)}/mo", F_MONTHLY, C_DIM,
             align="right", box_w=month_w)

        y += row_h

    # Total row
    y += 3
    _hline(cr, x, x + w, y, lw=0.8)
    y += 5
    _txt(cr, x + 3, y, "Total", F_BOLD, C_INK)
    _txt(cr, x + name_w + period_w, y,
         _fmt(total_monthly) + "/mo", F_BOLD, C_INK,
         align="right", box_w=month_w)


# ── Summary strip ─────────────────────────────────────────────────────────────

def _draw_summary(cr, x, y, w, net, fixed, debt_m, cats_m, unalloc):
    items = [("Net take-home", _fmt(net) + "/mo"), ("Fixed bills", "−" + _fmt(fixed))]
    if debt_m > 0:
        items.append(("Debt", "−" + _fmt(debt_m)))
    items.append(("Categories", "−" + _fmt(cats_m)))

    col_w = (w - 185) / len(items)
    for i, (label, val) in enumerate(items):
        cx = x + i * col_w
        _txt(cr, cx, y, label, F_SEC, C_DIM)
        _txt(cr, cx, y + 12, val, F_SUMVAL, C_INK)

    # Unallocated — highlighted on the right
    ux   = x + w - 180
    col  = C_POS if unalloc >= 0 else C_NEG
    sign = "surplus" if unalloc >= 0 else "deficit"
    _txt(cr, ux, y, "Unallocated", F_SEC, C_DIM)
    _txt(cr, ux, y + 9, f"{_fmt(abs(unalloc))}  {sign}", F_UNALLOC, col)


# ── Main draw function (PAGE_W × PAGE_H coordinate space) ────────────────────

def draw_page(cr, budget):
    """Render the full budget sheet. Caller scales cr to PAGE_W × PAGE_H."""
    today  = date.today()
    couple = " & ".join(budget.couple) if budget.couple else "Budget"
    month  = today.strftime("%B %Y")

    net     = BudgetCalculator.monthly_net_income(budget)
    gross   = BudgetCalculator.monthly_gross_income(budget)
    fixed   = BudgetCalculator.monthly_fixed_costs(budget)
    debt_m  = BudgetCalculator.monthly_debt_payments(budget)
    cats_m  = BudgetCalculator.monthly_category_budgets(budget)
    unalloc = BudgetCalculator.unallocated_discretionary(budget)

    # White background
    cr.set_source_rgb(1, 1, 1)
    cr.paint()

    # ── Header ────────────────────────────────────────────────────────────────
    cr.set_source_rgb(*C_HDR_BG)
    cr.rectangle(0, 0, PAGE_W, HDR_H)
    cr.fill()
    _txt(cr, MARGIN, 12, couple, F_TITLE, C_HDR_FG)
    _txt(cr, RIGHT_X, 16, f"{month}  ·  Monthly Budget",
         F_MONTH, C_HDR_DIM, align="right", box_w=RIGHT_W)

    # ── Left column ───────────────────────────────────────────────────────────
    y = _draw_income(cr, MARGIN, BODY_Y, LEFT_W, budget, gross, net)
    y += 8
    y = _draw_bills(cr, MARGIN, y, LEFT_W, budget, fixed)
    if budget.debt:
        y += 8
        _draw_debt(cr, MARGIN, y, LEFT_W, budget, debt_m)

    # Column divider
    _vline(cr, RIGHT_X - GAP // 2, BODY_Y, SUM_Y - 6)

    # ── Right column ──────────────────────────────────────────────────────────
    _draw_categories(cr, RIGHT_X, BODY_Y, RIGHT_W,
                     SUM_Y - BODY_Y - 10, budget, cats_m)

    # ── Summary strip ─────────────────────────────────────────────────────────
    cr.set_source_rgb(*C_SUM_BG)
    cr.rectangle(0, SUM_Y, PAGE_W, PAGE_H - SUM_Y)
    cr.fill()
    _draw_summary(cr, MARGIN, SUM_Y + 10, PAGE_W - 2 * MARGIN,
                  net, fixed, debt_m, cats_m, unalloc)

    # Footer
    _txt(cr, PAGE_W - MARGIN, PAGE_H - 9,
         f"Kopilka  ·  {today.strftime('%Y-%m-%d')}",
         F_FOOT, C_HAIR, align="right", box_w=200)


# ── In-app preview dialog ─────────────────────────────────────────────────────

class PrintPreviewDialog(Adw.Dialog):
    def __init__(self, budget):
        super().__init__()
        self.budget = budget
        self.set_title("Budget Sheet")
        self.set_content_width(820)
        self.set_content_height(660)

        toolbar = Adw.ToolbarView()
        self.set_child(toolbar)

        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        print_btn = Gtk.Button(label="Print…")
        print_btn.add_css_class("suggested-action")
        print_btn.set_tooltip_text("Open print dialog")
        print_btn.connect("clicked", self._on_print)
        header.pack_end(print_btn)

        canvas = Gtk.DrawingArea()
        canvas.set_hexpand(True)
        canvas.set_vexpand(True)
        canvas.set_size_request(760, int(760 * PAGE_H / PAGE_W))
        canvas.set_draw_func(self._draw, None)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(canvas)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        toolbar.set_content(scroll)

    def _draw(self, _area, cr, w, h, _):
        # Gray canvas around the page
        cr.set_source_rgb(0.80, 0.80, 0.80)
        cr.paint()

        pad   = 14
        scale = min((w - pad * 2) / PAGE_W, (h - pad * 2) / PAGE_H)
        off_x = (w - PAGE_W * scale) / 2
        off_y = (h - PAGE_H * scale) / 2

        # Drop shadow
        cr.set_source_rgba(0, 0, 0, 0.20)
        cr.rectangle(off_x + 3, off_y + 3, PAGE_W * scale, PAGE_H * scale)
        cr.fill()

        cr.save()
        cr.translate(off_x, off_y)
        cr.scale(scale, scale)
        draw_page(cr, self.budget)
        cr.restore()

        # Thin page border
        cr.set_source_rgba(0, 0, 0, 0.10)
        cr.set_line_width(1)
        cr.rectangle(off_x, off_y, PAGE_W * scale, PAGE_H * scale)
        cr.stroke()

    def _on_print(self, _btn):
        import cairo
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(
            suffix=".pdf", prefix="kopilka_budget_", delete=False
        ) as f:
            path = f.name

        # Letter landscape in points (72 pt/inch): 11" × 8.5"
        surface = cairo.PDFSurface(path, PAGE_W, PAGE_H)
        cr = cairo.Context(surface)
        draw_page(cr, self.budget)
        surface.finish()

        subprocess.Popen(["xdg-open", path])


def show_preview(budget, parent):
    PrintPreviewDialog(budget).present(parent)
