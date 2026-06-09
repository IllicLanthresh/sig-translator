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
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

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

    def __init__(self, trigger: str = "caps lock") -> None:
        super().__init__(None)
        self.trigger = trigger
        self.active = False
        self.game_hwnd = None
        self.clicks = 0
        self._caps_down = False
        self._engaged = False
        self._hold_timer = None
        self._hook = None

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setGeometry(QApplication.primaryScreen().geometry())

        # dummy panel (hidden until you hold the key)
        self.panel = QWidget(self)
        self.panel.setObjectName("Panel")
        self.panel.setStyleSheet(
            "#Panel{background:rgba(12,16,22,230);border:1px solid #29d3ff;border-radius:10px;}"
            "QLabel{color:#e6edf3;background:transparent;}"
            "QPushButton{color:#e6edf3;background:#1b2a36;border:1px solid #29d3ff;"
            "border-radius:6px;padding:10px 16px;}"
            "QPushButton:hover{background:#26415a;}"
        )
        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        self.title = QLabel("HOLD-TO-INTERACT PROTOTYPE")
        self.title.setFont(QFont("Bahnschrift", 16, QFont.Bold))
        self.info = QLabel()
        for b in ("Toggle A", "Toggle B", "Toggle C"):
            btn = QPushButton(b)
            btn.clicked.connect(self._bump)
            lay.addWidget(btn)
        lay.insertWidget(0, self.title)
        lay.addWidget(self.info)
        quit_btn = QPushButton("Quit prototype")
        quit_btn.setStyleSheet("border-color:#ff5555;color:#ff9a9a;")
        quit_btn.clicked.connect(QApplication.quit)
        lay.addWidget(quit_btn)
        self.panel.adjustSize()
        self._center_panel()
        self.panel.hide()

        # Esc closes it too (works while we hold focus during interact)
        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.setContext(Qt.ApplicationShortcut)
        esc.activated.connect(QApplication.quit)

        self.pressed.connect(self._enter)
        self.released.connect(self._leave)
        self.tap.connect(self._caps_tap_passthrough)
        self._refresh_info()

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

    def _bump(self) -> None:
        self.clicks += 1
        self._refresh_info()

    def _refresh_info(self) -> None:
        hwnd = f"0x{self.game_hwnd:x}" if self.game_hwnd else "—"
        self.info.setText(f"clicks: {self.clicks}    last game window: {hwnd}\n"
                          f"release [{self.trigger}] to return to the game")

    def _enter(self) -> None:
        if self.active:
            return
        self.active = True
        self.game_hwnd = get_foreground()  # remember the game so we can hand it back
        self._refresh_info()
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
    ov = ProtoOverlay(trigger)
    ov.show()
    try:
        ov.install_hook()
    except Exception as exc:  # noqa: BLE001
        ov.info.setText(f"keyboard hook failed: {exc}")
    return app.exec()


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "caps lock"
    sys.exit(run(key))
