"""SC-style breakability panel overlay — a designed, click-through HUD panel.

Draws a translucent panel (thin accent border + top strip) with echoed stats, a
power gauge (your throttle band vs the required-power tick + a 'hold' marker), a
verdict pill, and role-colored per-laser rows. Fed a mining Plan.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QWidget

from ..mining import difficulty

PAD = 14
MINW = 300
MUTED = "#9aa4b0"
WHITE = "#e6edf3"
PANEL_BG = QColor(10, 14, 20, 214)
_INF = float("inf")


def _fnum(x) -> str:
    return "∞" if x == _INF else f"{int(round(x)):,}"


class BreakabilityOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._plan = None
        self._cfg = None

    def _font(self, size: int, bold: bool = True) -> QFont:
        fam = self._cfg.font_family if self._cfg else "Bahnschrift"
        f = QFont(fam, size)
        f.setBold(bold)
        return f

    def _sizes(self):
        base = max(13, self._cfg.font_size)
        return base, max(11, base - 3), max(9, base - 5)  # header, row, small

    def set_plan(self, plan, config, anchor) -> None:
        if plan is None:
            self.hide()
            return
        self._plan = plan
        self._cfg = config
        w, h, _ = self._layout()
        self.resize(w, h)
        cx, ey = anchor
        self.move(max(0, int(cx - w / 2)), max(0, int(ey - h)))  # panel sits ABOVE the box
        self.update()
        if not self.isVisible():
            self.show()

    # ---- layout (measured once, used by sizing and painting) ----
    def _layout(self):
        plan = self._plan
        hs, rs, ss = self._sizes()
        hfm, rfm, sfm = (QFontMetrics(self._font(hs)), QFontMetrics(self._font(rs)),
                         QFontMetrics(self._font(ss)))
        pill_text, pill_color = difficulty(plan)

        stats = [("MASS", _fnum(plan.rock.mass)),
                 ("RESISTANCE", f"{plan.rock.resistance:.0f}%")]
        band = (_fnum(plan.power_max) if plan.power_min == plan.power_max
                else f"{_fnum(plan.power_min)}–{_fnum(plan.power_max)}")
        hr = plan.headroom
        sign = "+" if hr >= 0 else "−"
        metrics = f"req {_fnum(plan.required)} · {band} · {sign}{_fnum(abs(hr))}"
        if plan.stable_pct is not None and plan.kind != "impossible":
            metrics += f" · hold {plan.stable_pct:.0f}%"
        lasers = [(r.color, r.name, _fnum(r.power_max), r.role) for r in plan.roles]

        w_header = hfm.horizontalAdvance("BREAKABILITY") + 14 + sfm.horizontalAdvance(pill_text) + 18
        w_stats = max(rfm.horizontalAdvance(l) + 50 + rfm.horizontalAdvance(v) for l, v in stats)
        w_metrics = sfm.horizontalAdvance(metrics)
        w_lasers = max((rfm.horizontalAdvance(n) + 24 + rfm.horizontalAdvance(p) + 18
                        + rfm.horizontalAdvance(ro)) for _c, n, p, ro in lasers) if lasers else 0
        cw = max(w_header, w_stats, w_metrics, w_lasers, MINW - 2 * PAD)
        width = cw + 2 * PAD

        items = []
        y = PAD
        items.append(("header", y, pill_text, pill_color)); y += hfm.height()
        items.append(("hline", y + 2, cw)); y += 12
        for l, v in stats:
            items.append(("row", y, l, v)); y += rfm.height()
        y += 8
        items.append(("gauge", y, 14, cw)); y += 14 + 7
        items.append(("metrics", y, metrics)); y += sfm.height() + 7
        for c, n, p, ro in lasers:
            items.append(("laser", y, c, n, p, ro)); y += rfm.height()
        height = y + PAD
        return width, height, items

    # ---- paint ----
    def paintEvent(self, _e) -> None:
        if not self._plan:
            return
        w, h, items = self._layout()
        accent = self._cfg.accent_color
        hs, rs, ss = self._sizes()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 8, 8)
        p.fillPath(path, PANEL_BG)
        edge = QColor(accent)
        edge.setAlpha(120)
        p.setPen(QPen(edge, 1))
        p.drawPath(path)
        p.fillRect(QRectF(8, 0, w - 16, 2), QColor(accent))  # top accent strip

        for it in items:
            kind = it[0]
            if kind == "header":
                _, y, pill, pcol = it
                f = self._font(hs)
                fm = QFontMetrics(f)
                p.setFont(f)
                p.setPen(QColor(accent))
                p.drawText(PAD, y + fm.ascent(), "BREAKABILITY")
                sf = self._font(ss)
                sfm = QFontMetrics(sf)
                pw = sfm.horizontalAdvance(pill) + 16
                ph = sfm.height() + 4
                px = w - PAD - pw
                pill_path = QPainterPath()
                pill_path.addRoundedRect(QRectF(px, y, pw, ph), ph / 2, ph / 2)
                fill = QColor(pcol)
                fill.setAlpha(46)
                p.fillPath(pill_path, fill)
                p.setFont(sf)
                p.setPen(QColor(pcol))
                p.drawText(int(px + 8), int(y + sfm.ascent() + 2), pill)
            elif kind == "hline":
                _, y, cw = it
                c = QColor(accent)
                c.setAlpha(90)
                p.setPen(QPen(c, 1))
                p.drawLine(PAD, int(y), PAD + cw, int(y))
            elif kind == "row":
                _, y, label, value = it
                f = self._font(rs)
                fm = QFontMetrics(f)
                p.setFont(f)
                base = y + fm.ascent()
                p.setPen(QColor(MUTED))
                p.drawText(PAD, base, label)
                p.setPen(QColor(WHITE))
                p.drawText(int(w - PAD - fm.horizontalAdvance(value)), base, value)
            elif kind == "gauge":
                _, y, gh, cw = it
                self._gauge(p, PAD, y, cw, gh, accent)
            elif kind == "metrics":
                _, y, text = it
                f = self._font(ss, bold=False)
                fm = QFontMetrics(f)
                p.setFont(f)
                p.setPen(QColor("#cfd3d6"))
                p.drawText(PAD, y + fm.ascent(), text)
            elif kind == "laser":
                _, y, color, name, power, role = it
                f = self._font(rs)
                fm = QFontMetrics(f)
                p.setFont(f)
                base = y + fm.ascent()
                p.setBrush(QColor(color))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QRectF(PAD, y + fm.height() / 2 - 4, 8, 8))
                p.setPen(QColor(WHITE))
                p.drawText(PAD + 16, base, name)
                p.setPen(QColor(MUTED))
                p.drawText(int(PAD + 16 + fm.horizontalAdvance(name) + 12), base, power)
                p.setPen(QColor(color))
                p.drawText(int(w - PAD - fm.horizontalAdvance(role)), base, role)
        p.end()

    def _gauge(self, p, gx, gy, gw, gh, accent) -> None:
        plan = self._plan
        req = plan.required
        scale = max(plan.power_max, req if req != _INF else plan.power_max, 1)

        def px(v):
            return gx + gw * min(1.0, v / scale)

        track = QPainterPath()
        track.addRoundedRect(QRectF(gx, gy, gw, gh), gh / 2, gh / 2)
        p.fillPath(track, QColor(255, 255, 255, 20))

        _label, vcol = difficulty(plan)
        bx0, bx1 = px(plan.power_min), px(plan.power_max)
        band = QPainterPath()
        band.addRoundedRect(QRectF(bx0, gy, max(2, bx1 - bx0), gh), gh / 2, gh / 2)
        c = QColor(vcol)
        c.setAlpha(160)
        p.fillPath(band, c)

        if req != _INF:
            rx = px(req)
            p.setPen(QPen(QColor(WHITE), 2))
            p.drawLine(int(rx), int(gy - 3), int(rx), int(gy + gh + 3))
        else:
            p.setPen(QPen(QColor("#ff5555"), 2))
            p.drawLine(int(gx + gw), int(gy - 3), int(gx + gw), int(gy + gh + 3))

        if req != _INF and plan.kind in ("single", "combo"):
            hold = max(plan.power_min, min(plan.power_max, req))
            hx = px(hold)
            tri = QPolygonF([QPointF(hx - 4, gy - 6), QPointF(hx + 4, gy - 6), QPointF(hx, gy - 1)])
            p.setBrush(QColor(accent))
            p.setPen(Qt.NoPen)
            p.drawPolygon(tri)
