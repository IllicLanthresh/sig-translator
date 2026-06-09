"""THROWAWAY prototype: hold-to-interact overlay (Path A, focus-swap).

Goal: confirm Star Citizen (borderless) releases the mouse the instant our overlay
takes focus, lets you click the panel, and snaps back cleanly on release. This is a
spike to de-risk the real design — it is NOT wired into the app architecture and
should be deleted once we've validated the behaviour.

Run it, get into a ship in SC (borderless windowed), then:
  * HOLD  Caps Lock  -> screen dims, cursor appears, the dummy panel is clickable
  * click the buttons -> the click counter goes up (proves mouse works over us)
  * RELEASE Caps Lock -> dim + cursor vanish, focus snaps back to the game
  * QUIT: click "Quit prototype" on the panel, or press Esc while holding.

Caps Lock's normal toggle is suppressed while running, so your caps state never
flips. Everything you need to watch is drawn on the panel (the exe has no console).
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config import Config
from .mining import (
    LASERS_BY_KEY,
    MODULES_BY_KEY,
    Turret,
    difficulty,
    eval_config,
    parse_rock_stats,
)

# Until live OCR feeds the spike, evaluate against a fixed rock so the panel reacts.
SAMPLE_ROCK = parse_rock_stats("MASS 8600 RESISTANCE 19%")

IS_WIN = sys.platform == "win32"

# ---- Win32 plumbing (only used on Windows) ----------------------------------
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
    except AttributeError:  # 32-bit Python
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

    def get_foreground():
        return _u32.GetForegroundWindow()

    def set_interactive(hwnd, on: bool):
        """on=True -> window receives mouse + can be activated; on=False -> click-through."""
        ex = _get_long(hwnd, GWL_EXSTYLE) or 0
        if on:
            ex &= ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
        else:
            ex |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        _set_long(hwnd, GWL_EXSTYLE, ctypes.c_void_p(ex))

    def force_foreground(hwnd):
        """Steal foreground reliably past Windows' foreground-lock protection."""
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

    def set_foreground(hwnd):
        if hwnd:
            _u32.SetForegroundWindow(ctypes.c_void_p(hwnd))
else:  # non-Windows: no-ops so the script at least launches for a visual check
    def get_foreground():
        return None

    def set_interactive(hwnd, on: bool):
        pass

    def force_foreground(hwnd):
        pass

    def set_foreground(hwnd):
        pass


class ProtoOverlay(QWidget):
    pressed = Signal()
    released = Signal()
    tap = Signal()

    HOLD_MS = 250  # press shorter than this = a normal Caps tap; longer = open the overlay

    def __init__(self, config: Config, trigger: str = "caps lock") -> None:
        super().__init__(None)
        self.config = config
        self.trigger = trigger
        self.active = False
        self.game_hwnd = None
        self._caps_down = False
        self._engaged = False
        self._hold_timer = None
        self._hook = None
        # runtime config state (per session): which heads on + which actives firing
        self.heads = self._load_heads()  # [{laser, passives[], actives[], on, firing:set}]

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setGeometry(QApplication.primaryScreen().geometry())

        self._build_panel()

        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.setContext(Qt.ApplicationShortcut)
        esc.activated.connect(QApplication.quit)

        self.pressed.connect(self._enter)
        self.released.connect(self._leave)
        self.tap.connect(self._caps_tap_passthrough)
        self._recompute()

    # ---- loadout -> runtime head state ----
    def _load_heads(self) -> list:
        heads = []
        for entry in self.config.active_turrets():
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

    def _active_turrets(self) -> list:
        turrets = []
        for h in self.heads:
            if not h["on"]:
                continue
            mods = list(h["passives"]) + [m for m in h["actives"] if m.key in h["firing"]]
            turrets.append(Turret(h["laser"], mods))
        return turrets

    # ---- panel ----
    def _build_panel(self) -> None:
        self.panel = QWidget(self)
        self.panel.setObjectName("Panel")
        self.panel.setStyleSheet(
            "#Panel{background:rgba(12,16,22,235);border:1px solid #29d3ff;border-radius:10px;}"
            "QLabel{color:#e6edf3;background:transparent;}"
            "QLabel#Muted{color:#9aa4b0;}"
            "QPushButton{color:#e6edf3;background:#16222e;border:1px solid #2a3b4a;"
            "border-radius:6px;padding:6px 10px;}"
            "QPushButton:hover{background:#1f3344;}"
            "QPushButton:checked{background:#13402a;border-color:#33dd66;color:#bdfcd2;}"
            "QPushButton#Head:checked{background:#10324a;border-color:#29d3ff;color:#cdeffc;}"
            "QPushButton#Quit{border-color:#5a2530;color:#ff9a9a;}"
        )
        root = QVBoxLayout(self.panel)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        title = QLabel("BREAKABILITY")
        title.setFont(QFont("Bahnschrift", 15, QFont.Bold))
        title.setStyleSheet("color:#29d3ff;")
        self.pill = QLabel("")
        self.pill.setFont(QFont("Bahnschrift", 11, QFont.Bold))
        top = QHBoxLayout()
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.pill)
        root.addLayout(top)

        if not self.heads:
            root.addWidget(QLabel("No loadout configured — set one in the app first."))
        for i, h in enumerate(self.heads):
            root.addWidget(self._head_row(i, h))

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#29d3ff;")
        root.addWidget(line)
        self.verdict = QLabel("")
        self.verdict.setFont(QFont("Bahnschrift", 11))
        root.addWidget(self.verdict)
        note = QLabel("sample rock (live scan next)   ·   hold to edit, release to fly")
        note.setObjectName("Muted")
        note.setFont(QFont("Bahnschrift", 9))
        root.addWidget(note)

        quit_btn = QPushButton("Quit")
        quit_btn.setObjectName("Quit")
        quit_btn.clicked.connect(QApplication.quit)
        root.addWidget(quit_btn, alignment=Qt.AlignRight)

        self.panel.adjustSize()
        self._center_panel()
        self.panel.hide()

    def _head_row(self, i: int, h: dict) -> QWidget:
        box = QWidget()
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)
        head = QPushButton(f"{h['laser'].name}   {int(h['laser'].power_max):,}")
        head.setObjectName("Head")
        head.setCheckable(True)
        head.setChecked(h["on"])
        head.toggled.connect(lambda on, idx=i: self._set_head(idx, on))
        col.addWidget(head)

        chips = QHBoxLayout()
        chips.setContentsMargins(16, 0, 0, 0)
        chips.setSpacing(6)
        for m in h["passives"]:
            lab = QLabel(f"{m.name}")
            lab.setObjectName("Muted")
            lab.setFont(QFont("Bahnschrift", 9))
            lab.setToolTip("passive — always on")
            chips.addWidget(lab)
        for m in h["actives"]:
            chip = QPushButton(m.name)
            chip.setCheckable(True)
            chip.setFont(QFont("Bahnschrift", 9))
            chip.toggled.connect(lambda on, idx=i, key=m.key: self._set_active(idx, key, on))
            chips.addWidget(chip)
        chips.addStretch(1)
        col.addLayout(chips)
        return box

    def _set_head(self, i: int, on: bool) -> None:
        self.heads[i]["on"] = on
        self._recompute()

    def _set_active(self, i: int, key: str, on: bool) -> None:
        fire = self.heads[i]["firing"]
        fire.add(key) if on else fire.discard(key)
        self._recompute()

    def _recompute(self) -> None:
        plan = eval_config(SAMPLE_ROCK, self._active_turrets())
        label, color = difficulty(plan)
        self.pill.setText(label)
        self.pill.setStyleSheet(f"color:{color};")
        f = lambda x: "∞" if x == float("inf") else f"{int(round(x)):,}"
        hr = plan.headroom
        sign = "+" if hr >= 0 else "−"
        band = f(plan.power_max) if plan.power_min == plan.power_max else f"{f(plan.power_min)}–{f(plan.power_max)}"
        txt = f"req {f(plan.required)}   ·   you {band}   ·   {sign}{f(abs(hr))}"
        if plan.stable_pct is not None and plan.kind != "impossible":
            txt += f"   ·   hold {plan.stable_pct:.0f}%"
        self.verdict.setText(txt)
        self.verdict.setStyleSheet(f"color:{color};")

    # ---- key hook bridges to the GUI thread via signals ----
    def install_hook(self) -> None:
        import keyboard

        if self.trigger == "caps lock":
            # Suppress raw Caps so its toggle never fires unexpectedly; we decide:
            # a quick TAP -> re-send Caps (normal toggle for typing); a HOLD -> overlay.
            self._hook = keyboard.hook_key("caps lock", self._on_caps, suppress=True)
        else:
            # any other key: plain hold = press enters, release leaves
            keyboard.on_press_key(self.trigger, lambda _e: self.pressed.emit(), suppress=False)
            keyboard.on_release_key(self.trigger, lambda _e: self.released.emit(), suppress=False)

    def _on_caps(self, event) -> None:
        import threading

        if event.event_type == "down":
            if self._caps_down:
                return  # ignore key-repeat while held
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
                self.tap.emit()  # was a quick tap -> let it toggle caps as normal

    def _caps_held(self) -> None:
        if self._caps_down and not self._engaged:
            self._engaged = True
            self.pressed.emit()

    def _caps_tap_passthrough(self) -> None:
        """A genuine Caps tap was suppressed; re-issue one toggle so typing-caps works."""
        import keyboard

        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
        keyboard.send("caps lock")
        self._hook = keyboard.hook_key("caps lock", self._on_caps, suppress=True)

    def _center_panel(self) -> None:
        g = self.geometry()
        self.panel.move((g.width() - self.panel.width()) // 2,
                        (g.height() - self.panel.height()) // 2)

    def _enter(self) -> None:
        if self.active:
            return
        self.active = True
        self.game_hwnd = get_foreground()  # remember the game so we can hand it back
        hwnd = int(self.winId())
        set_interactive(hwnd, True)        # become clickable + activatable
        self.panel.show()
        self.update()
        force_foreground(hwnd)             # take focus -> game releases the mouse

    def _leave(self) -> None:
        if not self.active:
            return
        self.active = False
        hwnd = int(self.winId())
        self.panel.hide()
        self.update()
        set_interactive(hwnd, False)       # back to click-through
        set_foreground(self.game_hwnd)     # hand focus back to the game

    def paintEvent(self, _e) -> None:
        if not self.active:
            return
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))  # the Alt+Z-style dim
        p.end()


def run(trigger: str = "caps lock") -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    ov = ProtoOverlay(Config.load(), trigger)
    ov.show()
    try:
        ov.install_hook()
    except Exception:  # noqa: BLE001
        pass  # no global hook (e.g. not Windows / no perms) — panel still works on click
    return app.exec()


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "caps lock"
    sys.exit(run(key))
