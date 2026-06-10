"""SC-style breakability overlay — passive readout that expands in place to an editor.

One overlay. Idle, it's a click-through HUD panel above the rock box: echoed stats, a
power gauge (your band vs the required-power tick + hold marker), a verdict pill, and a
row per firing head. HOLD the trigger key (default Caps Lock) and the SAME panel grows
compact inline controls — a dot to toggle each head, small chips to fire/cut each active
module — recomputing live against the scanned rock. Release snaps back to the game.

Focus handling briefly takes our own window to the foreground so the game releases the
mouse; it never reads or injects into the game. Needs the game in Borderless/Windowed.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QShortcut,
)
from PySide6.QtWidgets import QApplication, QWidget

from ..mining import LASERS_BY_KEY, MODULES_BY_KEY, Turret, difficulty, eval_config

PAD = 14
MINW = 300
MUTED = "#9aa4b0"
WHITE = "#e6edf3"
DIM = "#5e6770"
ON = "#33dd66"    # head on / module firing
OFF = "#ff5555"   # head off / module idle
PANEL_BG = QColor(10, 14, 20, 224)
_INF = float("inf")

IS_WIN = sys.platform == "win32"

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    _u32 = ctypes.windll.user32
    _k32 = ctypes.windll.kernel32
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_NOACTIVATE = 0x08000000
    SW_SHOW = 5
    SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001

    try:
        _get_long = _u32.GetWindowLongPtrW
        _set_long = _u32.SetWindowLongPtrW
    except AttributeError:
        _get_long = _u32.GetWindowLongW
        _set_long = _u32.SetWindowLongW
    _get_long.restype = ctypes.c_void_p
    _get_long.argtypes = [wintypes.HWND, ctypes.c_int]
    _set_long.restype = ctypes.c_void_p
    _set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    _u32.GetForegroundWindow.restype = ctypes.c_void_p
    _u32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    _u32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _u32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]

    def _get_foreground():
        return _u32.GetForegroundWindow()

    def _set_interactive(hwnd, on):
        ex = _get_long(hwnd, GWL_EXSTYLE) or 0
        if on:
            ex &= ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
        else:
            ex |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        _set_long(hwnd, GWL_EXSTYLE, ctypes.c_void_p(ex))

    def _force_foreground(hwnd):
        hwnd = ctypes.c_void_p(hwnd)
        fg = _u32.GetForegroundWindow()
        try:
            _u32.SystemParametersInfoW(SPI_SETFOREGROUNDLOCKTIMEOUT, 0, None, 0)
        except Exception:
            pass
        fg_thread = _u32.GetWindowThreadProcessId(fg, None) if fg else 0
        cur_thread = _k32.GetCurrentThreadId()
        attached = bool(fg_thread) and fg_thread != cur_thread
        if attached:
            _u32.AttachThreadInput(cur_thread, fg_thread, True)
        _u32.BringWindowToTop(hwnd)
        _u32.ShowWindow(hwnd, SW_SHOW)
        _u32.SetForegroundWindow(hwnd)
        _u32.SetActiveWindow(hwnd)
        _u32.SetFocus(hwnd)
        if attached:
            _u32.AttachThreadInput(cur_thread, fg_thread, False)

    def _restore_foreground(hwnd):
        if hwnd:
            _u32.SetForegroundWindow(ctypes.c_void_p(hwnd))
else:
    def _get_foreground():
        return None

    def _set_interactive(hwnd, on):
        pass

    def _force_foreground(hwnd):
        pass

    def _restore_foreground(hwnd):
        pass


def _fnum(x) -> str:
    return "∞" if x == _INF else f"{int(round(x)):,}"


class BreakabilityOverlay(QWidget):
    pressed = Signal()
    released = Signal()
    tap = Signal()
    plan_changed = Signal(object)  # latest Plan (or None) so the app can mirror to Home
    layout_changed = Signal()      # items rebuilt -> GUI mirror resizes/repaints

    HOLD_MS = 250

    def __init__(self, config=None, trigger: str = "caps lock") -> None:
        super().__init__(None)
        self._cfg = config
        self.trigger = trigger
        self.active = False           # editing (held) vs idle (readout)
        self.game_hwnd = None
        self._rock = None
        self._anchor = None           # (center_x, box_top)
        self._plan = None
        self._items = []
        self._w = self._h = 0
        self._caps_down = False
        self._engaged = False
        self._hold_timer = None
        self._hook = None
        self.heads = self._load_heads()

        # NB: no Qt.WindowTransparentForInput here — that Qt flag stops Qt from
        # delivering clicks to our hit-test even after we clear the native bit. Idle
        # click-through is done natively instead (set_interactive in showEvent/_leave).
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        # Window-local on purpose: fires while the overlay holds focus (hold-to-edit),
        # and never collides with the main window's own Esc (drawer close).
        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.activated.connect(self._leave)
        self.pressed.connect(self._enter)
        self.released.connect(self._leave)
        self.tap.connect(self._caps_tap_passthrough)

    # ---- loadout -> runtime head state ----
    def _load_heads(self) -> list:
        heads = []
        cfg = self._cfg
        turrets = cfg.active_turrets() if cfg else []
        for entry in turrets:
            laser = LASERS_BY_KEY.get((entry or {}).get("laser"))
            if not laser:
                continue
            passives, actives = [], []
            for k in entry.get("modules", []):
                m = MODULES_BY_KEY.get(k)
                if not m:
                    continue
                (actives if m.kind == "Active" else passives).append(m)
            heads.append({"laser": laser, "passives": passives, "actives": actives,
                          "on": True, "firing": set()})
        return heads

    def reload_loadout(self) -> None:
        self.heads = self._load_heads()
        self._refresh()

    def _active_turrets(self) -> list:
        out = []
        for h in self.heads:
            if not h["on"]:
                continue
            # `firing` holds active-module SLOT indices, so identical modules
            # (e.g. 3x Surge, same key) toggle independently.
            mods = list(h["passives"]) + [m for ai, m in enumerate(h["actives"])
                                          if ai in h["firing"]]
            out.append(Turret(h["laser"], mods))
        return out

    # ---- fed by the app each mining tick ----
    def set_rock(self, rock, config, anchor) -> None:
        self._cfg = config
        self._rock = rock
        self._anchor = anchor
        self._refresh()

    def _draw_enabled(self) -> bool:
        return bool(self._cfg and getattr(self._cfg, "show_mining_overlay", True))

    def _refresh(self) -> None:
        # Always compute + relayout (the GUI mirror stays live even when the in-game
        # panel is hidden); only DRAW the floating window when allowed.
        self._plan = (eval_config(self._rock, self._active_turrets())
                      if self._rock is not None else None)
        self.plan_changed.emit(self._plan)
        self._relayout()
        draw = self.active or (self._plan is not None and self._draw_enabled())
        if not draw:
            self.hide()
            return
        self._place()
        self.update()
        if not self.isVisible():
            self.show()

    # ---- fonts/sizes ----
    def _font(self, size: int, bold: bool = True) -> QFont:
        fam = self._cfg.font_family if self._cfg else "Bahnschrift"
        f = QFont(fam, size)
        f.setBold(bold)
        return f

    def _sizes(self):
        base = max(13, self._cfg.font_size if self._cfg else 14)
        return base, max(11, base - 3), max(9, base - 5)  # header, row, small

    # ---- layout (stored so paint and hit-testing agree) ----
    def _relayout(self) -> None:
        plan = self._plan
        hs, rs, ss = self._sizes()
        hfm, rfm, sfm = (QFontMetrics(self._font(hs)), QFontMetrics(self._font(rs)),
                         QFontMetrics(self._font(ss)))
        rh = rfm.height()

        if plan is not None:
            pill_text, pill_color = difficulty(plan)
            band = (_fnum(plan.power_max) if plan.power_min == plan.power_max
                    else f"{_fnum(plan.power_min)}–{_fnum(plan.power_max)}")
            hr = plan.headroom
            hr_color = "#33dd66" if hr >= 0 else "#ff5555"
            rock_rows = [("MASS", _fnum(plan.rock.mass), WHITE),
                         ("RESISTANCE", f"{plan.rock.resistance:.0f}%", WHITE)]
            metric_rows = [("REQUIRED", _fnum(plan.required), WHITE),
                           ("YOUR POWER", band, WHITE),
                           ("HEADROOM", f"{'+' if hr >= 0 else '−'}{_fnum(abs(hr))}", hr_color)]
            if plan.stable_pct is not None and plan.kind != "impossible":
                metric_rows.append(("HOLD AT", f"{plan.stable_pct:.0f}%", "#cfd3d6"))
            w_rows = max(rfm.horizontalAdvance(l) + 50 + rfm.horizontalAdvance(v)
                         for l, v, _ in rock_rows + metric_rows)
        else:  # summoned with no rock scanned yet
            pill_text, pill_color = "NO SCAN", MUTED
            rock_rows = metric_rows = []
            w_rows = rfm.horizontalAdvance("waiting for a rock scan…")

        # content width (heads + their module chips are shown in BOTH modes)
        w_header = hfm.horizontalAdvance("BREAKABILITY") + 14 + sfm.horizontalAdvance(pill_text) + 18
        w_body = 0
        for h in self.heads:
            w_head = 22 + rfm.horizontalAdvance(h["laser"].name) + 16 + \
                rfm.horizontalAdvance(_fnum(h["laser"].power_max))
            w_chips = 16 + sum(sfm.horizontalAdvance(m.name) + 14 for m in h["passives"]) \
                + sum(sfm.horizontalAdvance("▮ " + m.name) + 18 for m in h["actives"])
            w_body = max(w_body, w_head, w_chips)
        w_hint = sfm.horizontalAdvance(self._hint_text())
        cw = max(w_header, w_rows, w_body, w_hint, MINW - 2 * PAD)
        width = cw + 2 * PAD

        items = []
        y = PAD
        items.append(("header", y, pill_text, pill_color)); y += hfm.height()
        items.append(("hline", y + 2, cw)); y += 12
        if plan is not None:
            for l, v, vc in rock_rows:
                items.append(("row", y, l, v, vc)); y += rh
            y += 8
            items.append(("gauge", y, 14, cw)); y += 14 + 10
            for l, v, vc in metric_rows:
                items.append(("row", y, l, v, vc)); y += rh
            y += 6
        else:
            items.append(("hint", y, "waiting for a rock scan…")); y += sfm.height() + 4
        items.append(("hline", y, cw)); y += 8

        for idx, h in enumerate(self.heads):
            rect = QRectF(PAD - 4, y - 1, cw + 8, rh)
            items.append(("headrow", y, idx, h, rect)); y += rh
            if h["passives"] or h["actives"]:
                x = PAD + 18
                for m in h["passives"]:
                    items.append(("passchip", y, x, m.name)); x += sfm.horizontalAdvance(m.name) + 14
                for ai, m in enumerate(h["actives"]):
                    firing = ai in h["firing"]
                    cwid = sfm.horizontalAdvance("▮ " + m.name) + 10
                    rect = QRectF(x - 4, y - 1, cwid + 4, sfm.height() + 2)
                    items.append(("actchip", y, x, m.name, idx, ai, firing, rect))
                    x += cwid + 8
                y += sfm.height() + 4
        items.append(("hint", y + 2, self._hint_text())); y += sfm.height()

        self._items = items
        self._w, self._h = width, y + PAD
        self.layout_changed.emit()

    def _hint_text(self) -> str:
        if self.active:
            return "release to fly"
        return f"hold {self.trigger.title()} to edit"

    def _place(self) -> None:
        self.resize(self._w, self._h)
        if self._anchor is None:
            return
        cx, ey = self._anchor
        self.move(max(0, int(cx - self._w / 2)), max(0, int(ey - self._h)))

    # ---- paint (shared verbatim by the floating window and the GUI mirror) ----
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        self.paint_panel(p)
        p.end()

    def paint_panel(self, p: QPainter) -> None:
        if not self._items:
            return
        w, h = self._w, self._h
        accent = self._cfg.accent_color if self._cfg else "#29d3ff"
        hs, rs, ss = self._sizes()
        p.setRenderHint(QPainter.Antialiasing, True)

        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 8, 8)
        p.fillPath(path, PANEL_BG)
        edge = QColor(accent)
        edge.setAlpha(150 if self.active else 120)
        p.setPen(QPen(edge, 1))
        p.drawPath(path)
        p.fillRect(QRectF(8, 0, w - 16, 2), QColor(accent))

        for it in self._items:
            kind = it[0]
            if kind == "header":
                self._draw_header(p, it[1], it[2], it[3], w, accent, hs, ss)
            elif kind == "hline":
                _, y, cw = it
                c = QColor(accent); c.setAlpha(90)
                p.setPen(QPen(c, 1))
                p.drawLine(PAD, int(y), PAD + cw, int(y))
            elif kind == "row":
                _, y, label, value, vcolor = it
                f = self._font(rs); fm = QFontMetrics(f); p.setFont(f)
                base = y + fm.ascent()
                p.setPen(QColor(MUTED)); p.drawText(PAD, base, label)
                p.setPen(QColor(vcolor))
                p.drawText(int(w - PAD - fm.horizontalAdvance(value)), base, value)
            elif kind == "gauge":
                self._gauge(p, PAD, it[1], it[3], it[2], accent)
            elif kind == "headrow":
                self._draw_headrow(p, it, w, accent, rs)
            elif kind == "passchip":
                _, y, x, t = it
                f = self._font(ss, bold=False); fm = QFontMetrics(f); p.setFont(f)
                p.setPen(QColor(DIM)); p.drawText(int(x), int(y + fm.ascent()), t)
            elif kind == "actchip":
                self._draw_actchip(p, it, accent, ss)
            elif kind == "hint":
                _, y, t = it
                f = self._font(ss, bold=False); fm = QFontMetrics(f); p.setFont(f)
                p.setPen(QColor(MUTED)); p.drawText(PAD, int(y + fm.ascent()), t)

    def _draw_header(self, p, y, pill, pcol, w, accent, hs, ss) -> None:
        f = self._font(hs); fm = QFontMetrics(f); p.setFont(f)
        p.setPen(QColor(accent))
        p.drawText(PAD, y + fm.ascent(), "BREAKABILITY")
        sf = self._font(ss); sfm = QFontMetrics(sf)
        pw = sfm.horizontalAdvance(pill) + 16
        ph = sfm.height() + 4
        px = w - PAD - pw
        pill_path = QPainterPath()
        pill_path.addRoundedRect(QRectF(px, y, pw, ph), ph / 2, ph / 2)
        fill = QColor(pcol); fill.setAlpha(46)
        p.fillPath(pill_path, fill)
        p.setFont(sf); p.setPen(QColor(pcol))
        p.drawText(int(px + 8), int(y + sfm.ascent() + 2), pill)

    def _draw_headrow(self, p, it, w, accent, rs) -> None:
        _, y, idx, h, _rect = it
        f = self._font(rs); fm = QFontMetrics(f); p.setFont(f)
        base = y + fm.ascent()
        on = h["on"]
        col = ON if on else OFF
        dot = QRectF(PAD, y + fm.height() / 2 - 5, 10, 10)
        p.setBrush(QColor(col)); p.setPen(Qt.NoPen); p.drawEllipse(dot)
        p.setPen(QColor(WHITE if on else DIM))
        p.drawText(PAD + 22, base, h["laser"].name)
        pw = _fnum(h["laser"].power_max)
        p.setPen(QColor(MUTED if on else DIM))
        p.drawText(int(w - PAD - fm.horizontalAdvance(pw)), base, pw)

    def _draw_actchip(self, p, it, accent, ss) -> None:
        _, y, x, name, _idx, _ai, firing, _rect = it
        f = self._font(ss, bold=False); fm = QFontMetrics(f); p.setFont(f)
        base = y + fm.ascent()
        marker = "▮ " if firing else "▯ "
        p.setPen(QColor(ON if firing else OFF))
        p.drawText(int(x), int(base), marker)
        p.setPen(QColor(WHITE if firing else MUTED))
        p.drawText(int(x + fm.horizontalAdvance(marker)), int(base), name)

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
        c = QColor(vcol); c.setAlpha(160)
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
            p.setBrush(QColor(accent)); p.setPen(Qt.NoPen)
            p.drawPolygon(tri)

    # ---- interaction (shared hit-test: the in-game editor and the GUI mirror) ----
    def toggle_at(self, pos) -> bool:
        for it in self._items:
            if it[0] == "headrow" and it[4].contains(pos):
                self.heads[it[2]]["on"] = not self.heads[it[2]]["on"]
                self._after_toggle()
                return True
            if it[0] == "actchip" and it[7].contains(pos):
                idx, ai = it[4], it[5]
                fire = self.heads[idx]["firing"]
                fire.discard(ai) if ai in fire else fire.add(ai)
                self._after_toggle()
                return True
        return False

    def mousePressEvent(self, event) -> None:
        if self.active:
            self.toggle_at(event.position())

    def _after_toggle(self) -> None:
        if self._rock is not None:
            self._plan = eval_config(self._rock, self._active_turrets())
            self.plan_changed.emit(self._plan)
        self._relayout()
        self._place()
        self.update()

    # ---- key hook (caps hold-vs-tap; other keys = plain hold) ----
    def install_hook(self) -> None:
        try:
            import keyboard
        except Exception:
            return
        try:
            if self.trigger == "caps lock":
                self._hook = keyboard.hook_key("caps lock", self._on_caps, suppress=True)
            else:
                keyboard.on_press_key(self.trigger, lambda _e: self.pressed.emit(), suppress=False)
                keyboard.on_release_key(self.trigger, lambda _e: self.released.emit(), suppress=False)
        except Exception:
            pass

    def stop(self) -> None:
        try:
            import keyboard

            if self._hook is not None:
                keyboard.unhook(self._hook)
                self._hook = None
        except Exception:
            pass

    def set_trigger(self, key: str) -> None:
        """Rebind the hold-to-interact key at runtime. The caller must re-register any
        other global hotkeys afterwards (we clear ALL keyboard hooks to drop the old
        press/release handlers, which the keyboard lib gives us no handle for)."""
        key = (key or "caps lock").strip().lower()
        if key == self.trigger:
            return
        if self.active:
            self._leave()
        self._hook = None
        try:
            import keyboard

            keyboard.unhook_all()
        except Exception:
            pass
        self.trigger = key
        self._caps_down = False
        self._engaged = False
        self.install_hook()
        self._relayout()  # the idle hint names the key
        self.update()

    def _on_caps(self, event) -> None:
        import threading

        if event.event_type == "down":
            if self._caps_down:
                return
            self._caps_down = True
            self._hold_timer = threading.Timer(self.HOLD_MS / 1000, self._caps_held)
            self._hold_timer.start()
        elif event.event_type == "up":
            self._caps_down = False
            if self._hold_timer is not None:
                self._hold_timer.cancel()
                self._hold_timer = None
            if self._engaged:
                self._engaged = False
                self.released.emit()
            else:
                self.tap.emit()

    def _caps_held(self) -> None:
        if self._caps_down and not self._engaged:
            self._engaged = True
            self.pressed.emit()

    def _caps_tap_passthrough(self) -> None:
        import keyboard

        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
        keyboard.send("caps lock")
        self._hook = keyboard.hook_key("caps lock", self._on_caps, suppress=True)

    # ---- hold-to-interact focus swap ----
    def _enter(self) -> None:
        if self.active or not self._draw_enabled():  # overlay off -> hold does nothing
            return
        self.active = True
        self.game_hwnd = _get_foreground()
        if self._anchor is None:
            self._anchor = self._fallback_anchor()
        self._relayout()
        self._place()
        if not self.isVisible():
            self.show()
        hwnd = int(self.winId())
        _set_interactive(hwnd, True)
        self.update()
        _force_foreground(hwnd)

    def _leave(self) -> None:
        if not self.active:
            return
        self.active = False
        self._engaged = False
        hwnd = int(self.winId())
        _set_interactive(hwnd, False)
        _restore_foreground(self.game_hwnd)
        if self._plan is None:     # nothing to show when idle without a scan
            self.hide()
        else:
            self._relayout()
            self._place()
            self.update()

    def _fallback_anchor(self):
        """Where to put the panel when summoned with no live scan yet."""
        cfg = self._cfg
        if cfg is not None and getattr(cfg, "rock_calibrated", False):
            r = cfg.rock_region
            return (r.x + r.width // 2, r.y)
        scr = QApplication.primaryScreen().geometry()
        return (scr.width() // 2, scr.height() // 2 + 120)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self.active:
            _set_interactive(int(self.winId()), False)


class BreakabilityMirror(QWidget):
    """GUI twin of the breakability overlay — same items, same painter, same hit-test.

    The overlay object owns the state and layout; this widget just renders them in the
    dashboard and forwards clicks, so the in-game panel and the GUI can never drift.
    Clicks here toggle heads/modules even while the in-game panel is idle.
    """

    def __init__(self, overlay: BreakabilityOverlay) -> None:
        super().__init__()
        self._ov = overlay
        self.setMinimumSize(MINW, 64)
        overlay.layout_changed.connect(self._sync)
        self._sync()

    def _sync(self) -> None:
        ov = self._ov
        if ov._items:
            self.setFixedSize(ov._w, ov._h)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        ov = self._ov
        if not ov._items:
            f = QFont(ov._cfg.font_family if ov._cfg else "Bahnschrift", 11)
            p.setFont(f)
            p.setPen(QColor(MUTED))
            p.drawText(self.rect(), Qt.AlignCenter, "no scan")
        else:
            ov.paint_panel(p)
        p.end()

    def mousePressEvent(self, event) -> None:
        self._ov.toggle_at(event.position())
