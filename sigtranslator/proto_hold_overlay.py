"""THROWAWAY prototype: hold-to-interact overlay (Path A, focus-swap).

Goal: confirm Star Citizen (borderless) releases the mouse the instant our overlay
takes focus, lets you click the panel, and snaps back cleanly on release. This is a
spike to de-risk the real design — it is NOT wired into the app architecture and
should be deleted once we've validated the behaviour.

Run it, get into a ship in SC (borderless windowed), then:
  * HOLD  Scroll Lock  -> screen dims, cursor appears, the dummy panel is clickable
  * click the buttons  -> the click counter goes up (proves mouse works over us)
  * RELEASE Scroll Lock -> dim + cursor vanish, focus snaps back to the game

Everything you need to watch is drawn on the panel (the exe has no console).
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

IS_WIN = sys.platform == "win32"

# ---- Win32 plumbing (only used on Windows) ----------------------------------
if IS_WIN:
    import ctypes
    from ctypes import wintypes

    _u32 = ctypes.windll.user32
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020

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

    def get_foreground():
        return _u32.GetForegroundWindow()

    def set_foreground(hwnd):
        if hwnd:
            _u32.SetForegroundWindow(ctypes.c_void_p(hwnd))

    def set_click_through(hwnd, on: bool):
        ex = _get_long(hwnd, GWL_EXSTYLE) or 0
        ex = (ex | WS_EX_TRANSPARENT) if on else (ex & ~WS_EX_TRANSPARENT)
        _set_long(hwnd, GWL_EXSTYLE, ex)
else:  # non-Windows: no-ops so the script at least launches for a visual check
    def get_foreground():
        return None

    def set_foreground(hwnd):
        pass

    def set_click_through(hwnd, on: bool):
        pass


class ProtoOverlay(QWidget):
    pressed = Signal()
    released = Signal()

    def __init__(self, trigger: str = "scroll lock") -> None:
        super().__init__(None)
        self.trigger = trigger
        self.active = False
        self.game_hwnd = None
        self.clicks = 0

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
        self.panel.adjustSize()
        self._center_panel()
        self.panel.hide()

        self.pressed.connect(self._enter)
        self.released.connect(self._leave)
        self._refresh_info()

    # ---- key hook bridges to the GUI thread via signals ----
    def install_hook(self) -> None:
        import keyboard

        keyboard.on_press_key(self.trigger, lambda _e: self.pressed.emit(), suppress=False)
        keyboard.on_release_key(self.trigger, lambda _e: self.released.emit(), suppress=False)

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
        set_click_through(hwnd, False)     # become clickable
        self.panel.show()
        self.update()
        self.raise_()
        self.activateWindow()
        set_foreground(hwnd)               # steal focus -> game releases the mouse

    def _leave(self) -> None:
        if not self.active:
            return
        self.active = False
        hwnd = int(self.winId())
        self.panel.hide()
        self.update()
        set_click_through(hwnd, True)      # back to click-through
        set_foreground(self.game_hwnd)     # hand focus back to the game

    def paintEvent(self, _e) -> None:
        if not self.active:
            return
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))  # the Alt+Z-style dim
        p.end()


def run(trigger: str = "scroll lock") -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    ov = ProtoOverlay(trigger)
    ov.show()
    try:
        ov.install_hook()
    except Exception as exc:  # noqa: BLE001
        ov.info.setText(f"keyboard hook failed: {exc}")
    return app.exec()


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "scroll lock"
    sys.exit(run(key))
