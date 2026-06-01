"""Cairo-based chart widgets for Kopilka."""

import math
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Pango, PangoCairo

# Visually distinct palette that works in both Adwaita light and dark
PALETTE = [
    (0.204, 0.741, 0.549),  # teal
    (0.259, 0.529, 0.961),  # blue
    (0.961, 0.573, 0.122),  # orange
    (0.694, 0.341, 0.855),  # purple
    (0.925, 0.322, 0.322),  # red
    (0.118, 0.733, 0.820),  # cyan
    (0.545, 0.796, 0.200),  # lime
    (0.957, 0.412, 0.545),  # pink
]


class _Swatch(Gtk.DrawingArea):
    def __init__(self, color):
        super().__init__()
        self._color = color
        self.set_size_request(10, 10)
        self.set_valign(Gtk.Align.CENTER)
        self.set_draw_func(self._draw, None)

    def _draw(self, _area, cr, w, h, _):
        r, g, b = self._color
        cr.set_source_rgb(r, g, b)
        cr.arc(w / 2, h / 2, min(w, h) / 2, 0, 2 * math.pi)
        cr.fill()


class DonutChart(Gtk.Box):
    """
    Donut (ring) chart with a legend.

    data  — list of (label: str, value: float)
    title — short label shown in the donut centre (e.g. "Spent")
    """

    def __init__(self, data: list[tuple[str, float]], title: str = ""):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        self.set_margin_top(8)
        self.set_margin_bottom(8)

        non_zero = [(l, v) for l, v in data if v > 0]
        self._data = non_zero
        self._title = title
        self._total = sum(v for _, v in non_zero)

        # ── Donut canvas ──────────────────────────────────────────────────────
        self._canvas = Gtk.DrawingArea()
        self._canvas.set_size_request(170, 170)
        self._canvas.set_valign(Gtk.Align.CENTER)
        self._canvas.set_halign(Gtk.Align.CENTER)
        self._canvas.set_draw_func(self._draw_donut, None)
        self.append(self._canvas)

        # Accessible label summarises top items for screen readers
        if non_zero:
            top = ", ".join(f"{l} ${v:,.0f}" for l, v in non_zero[:3])
            self.update_property([Gtk.AccessibleProperty.LABEL],
                                 [f"Donut chart — {title}: {top}"])

        # ── Legend ────────────────────────────────────────────────────────────
        legend = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        legend.set_valign(Gtk.Align.CENTER)
        legend.set_hexpand(True)
        self.append(legend)

        for i, (label, value) in enumerate(non_zero):
            color = PALETTE[i % len(PALETTE)]
            pct = value / self._total * 100 if self._total else 0

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
            legend.append(row)

            row.append(_Swatch(color))

            text = Gtk.Label()
            text.set_markup(
                f"{label}  "
                f'<span alpha="65%">${value:,.2f} · {pct:.0f}%</span>'
            )
            text.set_xalign(0)
            text.set_ellipsize(Pango.EllipsizeMode.END)
            text.set_max_width_chars(28)
            row.append(text)

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _draw_donut(self, area, cr, width, height, _):
        if not self._data or self._total == 0:
            return

        cx, cy = width / 2, height / 2
        r_out = min(cx, cy) - 6
        r_in  = r_out * 0.54      # thickness of the ring
        gap   = 0.018             # radians between slices

        start = -math.pi / 2
        for i, (_, value) in enumerate(self._data):
            sweep = 2 * math.pi * value / self._total
            color = PALETTE[i % len(PALETTE)]

            a0 = start + gap / 2
            a1 = start + sweep - gap / 2

            cr.new_sub_path()
            cr.arc(cx, cy, r_out, a0, a1)
            cr.arc_negative(cx, cy, r_in, a1, a0)
            cr.close_path()
            cr.set_source_rgb(*color)
            cr.fill()

            start += sweep

        # ── Centre text ───────────────────────────────────────────────────────
        sc  = area.get_style_context()
        fg  = sc.get_color()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, fg.alpha)

        # Amount line
        layout = PangoCairo.create_layout(cr)
        layout.set_text(f"${self._total:,.0f}")
        layout.set_font_description(Pango.FontDescription.from_string("Sans Bold 13"))
        tw, th = layout.get_pixel_size()
        cr.move_to(cx - tw / 2, cy - th / 2 - 6)
        PangoCairo.show_layout(cr, layout)

        # Label line
        if self._title:
            cr.set_source_rgba(fg.red, fg.green, fg.blue, fg.alpha * 0.6)
            sub = PangoCairo.create_layout(cr)
            sub.set_text(self._title)
            sub.set_font_description(Pango.FontDescription.from_string("Sans 9"))
            sw, sh = sub.get_pixel_size()
            cr.move_to(cx - sw / 2, cy + th / 2 - 2)
            PangoCairo.show_layout(cr, sub)


# ---------------------------------------------------------------------------
# Balance line chart
# ---------------------------------------------------------------------------

_LINE_COLOR = (0.204, 0.741, 0.549)   # teal — matches PALETTE[0]


class BalanceLineChart(Gtk.DrawingArea):
    """
    Sparkline-style chart for an asset's balance history.

    points — list of (iso_date_str, balance_float), oldest first.
    """

    def __init__(self, points: list[tuple[str, float]]):
        super().__init__()
        self._points = sorted(points, key=lambda p: p[0])
        self.set_size_request(-1, 110)
        self.set_hexpand(True)
        self.set_margin_top(4)
        self.set_margin_bottom(8)
        self.set_margin_start(4)
        self.set_margin_end(4)
        self.set_draw_func(self._draw, None)
        if self._points:
            first, last = self._points[0][1], self._points[-1][1]
            self.update_property([Gtk.AccessibleProperty.LABEL],
                                 [f"Balance history chart: ${first:,.0f} → ${last:,.0f}"])

    def _draw(self, area, cr, width, height, _):
        if len(self._points) < 2:
            return

        values = [v for _, v in self._points]
        min_v  = min(values)
        max_v  = max(values)
        if max_v == min_v:
            max_v = min_v + 1.0

        pad_l, pad_r, pad_t, pad_b = 56, 10, 10, 24
        cw = width  - pad_l - pad_r
        ch = height - pad_t - pad_b
        n  = len(self._points)

        def px(i, v):
            x = pad_l + (i / (n - 1)) * cw
            y = pad_t + (1 - (v - min_v) / (max_v - min_v)) * ch
            return x, y

        coords = [px(i, v) for i, (_, v) in enumerate(self._points)]
        r, g, b = _LINE_COLOR

        # Filled area under line
        cr.new_path()
        cr.move_to(coords[0][0], pad_t + ch)
        for x, y in coords:
            cr.line_to(x, y)
        cr.line_to(coords[-1][0], pad_t + ch)
        cr.close_path()
        cr.set_source_rgba(r, g, b, 0.15)
        cr.fill()

        # Line
        cr.new_path()
        cr.move_to(*coords[0])
        for x, y in coords[1:]:
            cr.line_to(x, y)
        cr.set_source_rgb(r, g, b)
        cr.set_line_width(1.8)
        cr.stroke()

        # Dots
        for x, y in coords:
            cr.arc(x, y, 2.5, 0, 2 * math.pi)
            cr.set_source_rgb(r, g, b)
            cr.fill()

        # Axis labels (min, max, dates)
        sc = area.get_style_context()
        fg = sc.get_color()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, fg.alpha * 0.55)

        font = Pango.FontDescription.from_string("Sans 7.5")

        def draw_text(text, tx, ty, align_right=False):
            layout = PangoCairo.create_layout(cr)
            layout.set_text(text)
            layout.set_font_description(font)
            tw, th = layout.get_pixel_size()
            if align_right:
                tx -= tw
            cr.move_to(tx, ty - th / 2)
            PangoCairo.show_layout(cr, layout)

        # Y labels
        draw_text(f"${max_v:,.0f}", pad_l - 4, pad_t, align_right=True)
        draw_text(f"${min_v:,.0f}", pad_l - 4, pad_t + ch, align_right=True)

        # X labels: first and last date (abbreviated)
        def short_date(iso):
            try:
                from datetime import date
                d = date.fromisoformat(iso)
                return d.strftime("%b %Y")
            except Exception:
                return iso[:7]

        first_x, _ = coords[0]
        last_x,  _ = coords[-1]
        draw_text(short_date(self._points[0][0]),  first_x, pad_t + ch + 14)
        draw_text(short_date(self._points[-1][0]), last_x,  pad_t + ch + 14, align_right=True)


# ---------------------------------------------------------------------------
# Monthly bar chart
# ---------------------------------------------------------------------------

_TEAL_COLOR = (0.204, 0.741, 0.549)   # under budget
_RED_COLOR  = (0.925, 0.322, 0.322)   # over budget


class MonthlyBarChart(Gtk.DrawingArea):
    """
    Vertical bar chart for monthly spending vs budget.

    months — list of (label: str, spent: float, budget: float), oldest first.
    """

    def __init__(self, months: list[tuple[str, float, float]]):
        super().__init__()
        self._months = months
        self.set_size_request(-1, 160)
        self.set_hexpand(True)
        self.set_margin_top(4)
        self.set_margin_bottom(8)
        self.set_margin_start(4)
        self.set_margin_end(4)
        self.set_draw_func(self._draw, None)
        if months:
            summary = ", ".join(
                f"{lbl} ${spent:,.0f}" for lbl, spent, _ in months if spent > 0
            ) or "no spending recorded"
            self.update_property([Gtk.AccessibleProperty.LABEL],
                                 [f"Monthly spending bar chart — {summary}"])

    def _draw(self, area, cr, width, height, _):
        if not self._months:
            return

        labels  = [m[0] for m in self._months]
        spents  = [m[1] for m in self._months]
        budgets = [m[2] for m in self._months]

        max_val = max(max(spents), max(budgets), 1.0)

        pad_l, pad_r, pad_t, pad_b = 52, 10, 10, 22
        cw = width  - pad_l - pad_r
        ch = height - pad_t - pad_b
        n  = len(self._months)

        bar_w    = max(4, cw / n * 0.55)
        slot_w   = cw / n

        def bar_height(v):
            return ch * v / max_val

        sc = area.get_style_context()
        fg = sc.get_color()

        font = Pango.FontDescription.from_string("Sans 7.5")

        def draw_text(text, tx, ty, align_right=False, align_center=False):
            layout = PangoCairo.create_layout(cr)
            layout.set_text(text)
            layout.set_font_description(font)
            tw, th = layout.get_pixel_size()
            if align_right:
                tx -= tw
            elif align_center:
                tx -= tw / 2
            cr.move_to(tx, ty - th / 2)
            PangoCairo.show_layout(cr, layout)

        # Budget reference line (dashed)
        if max(budgets) > 0:
            budget_y = pad_t + ch - bar_height(budgets[0])  # use first budget
            # average budget for the line
            avg_budget = sum(b for b in budgets if b > 0)
            count_b = sum(1 for b in budgets if b > 0)
            if count_b:
                avg_budget /= count_b
                budget_y = pad_t + ch - bar_height(avg_budget)
                cr.set_source_rgba(fg.red, fg.green, fg.blue, fg.alpha * 0.35)
                cr.set_line_width(1.0)
                cr.set_dash([4.0, 3.0], 0)
                cr.move_to(pad_l, budget_y)
                cr.line_to(pad_l + cw, budget_y)
                cr.stroke()
                cr.set_dash([], 0)

        # Draw bars
        for i, (label, spent, budget) in enumerate(self._months):
            cx = pad_l + slot_w * i + slot_w / 2
            bx = cx - bar_w / 2
            bh = bar_height(spent)
            by = pad_t + ch - bh

            if budget > 0 and spent > budget:
                r, g, b = _RED_COLOR
            else:
                r, g, b = _TEAL_COLOR

            cr.set_source_rgba(r, g, b, 0.85)
            cr.rectangle(bx, by, bar_w, bh)
            cr.fill()

        # Y labels ($0 and max)
        cr.set_source_rgba(fg.red, fg.green, fg.blue, fg.alpha * 0.55)
        draw_text(f"${max_val:,.0f}", pad_l - 4, pad_t, align_right=True)
        draw_text("$0", pad_l - 4, pad_t + ch, align_right=True)

        # X labels (month abbreviations)
        for i, label in enumerate(labels):
            cx = pad_l + slot_w * i + slot_w / 2
            draw_text(label, cx, pad_t + ch + 14, align_center=True)
