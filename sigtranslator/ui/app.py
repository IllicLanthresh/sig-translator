"""Qt app shell — single window with sidebar nav (Slice 1: shell + overlay spike).

This is the de-risk slice: a themed window and a click-through overlay, so the
transparent/always-on-top/click-through behaviour can be validated over Star Citizen
before the full views are built. Logic modules are not wired in yet.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from . import theme
from .overlay import Overlay

_NAV = ["◉  Home", "⌖  Sigs", "⛏  Mine", "✦  Look", "⚙  Setup"]


def _page(title: str, body: str) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(24, 24, 24, 24)
    lay.setSpacing(12)
    h = QLabel(title)
    h.setObjectName("H1")
    lay.addWidget(h)
    b = QLabel(body)
    b.setObjectName("Muted")
    b.setWordWrap(True)
    lay.addWidget(b)
    lay.addStretch(1)
    return w


class MainWindow(QMainWindow):
    def __init__(self, overlay: Overlay) -> None:
        super().__init__()
        self.overlay = overlay
        self.setWindowTitle(f"sig-translator  v{__version__}")
        self.resize(840, 560)

        central = QWidget()
        self.setCentralWidget(central)
        row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        self.nav.setFixedWidth(150)
        for n in _NAV:
            self.nav.addItem(n)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._home_page())
        self.stack.addWidget(_page("Signatures", "Signature box calibration + the material "
                                   "show/hide grid will live here."))
        self.stack.addWidget(_page("Mining", "Saved loadouts + turret cards + rock-panel "
                                   "calibration will live here."))
        self.stack.addWidget(_page("Look", "Accent color, label size, overlays on/off, and a "
                                   "live preview will live here."))
        self.stack.addWidget(_page("Setup", "Hotkey, scan FPS, update check, about."))
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        row.addWidget(self.nav)
        row.addWidget(self.stack, 1)

    def _home_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)
        h = QLabel("Home")
        h.setObjectName("H1")
        lay.addWidget(h)
        msg = QLabel(
            "Qt shell + overlay spike. Toggle the test overlay below, then confirm over "
            "Star Citizen that it floats on top AND that your clicks pass through to the game."
        )
        msg.setObjectName("Muted")
        msg.setWordWrap(True)
        lay.addWidget(msg)
        self.cb = QCheckBox("Show test overlay")
        self.cb.setChecked(True)
        self.cb.toggled.connect(self._toggle)
        lay.addWidget(self.cb)
        lay.addStretch(1)
        return w

    def _toggle(self, on: bool) -> None:
        if on:
            self.show_sample()
        else:
            self.overlay.hide()

    def show_sample(self) -> None:
        geo = self.screen().geometry()
        anchor = (geo.center().x(), int(geo.y() + geo.height() * 0.2))
        self.overlay.set_lines(
            [
                ("[ 18,000 m · 19% ]", "#7fdfff"),
                ("req 1,984 · power 4,080 · +2,096", "#cfd3d6"),
                ("Helix S2  4,080  use  (+2,096)", "#33dd66"),
                ("OVERLAY TEST — clicks should pass through", "#ffcc44"),
            ],
            anchor=anchor,
        )


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(theme.qss())
    overlay = Overlay()
    win = MainWindow(overlay)
    win.show()
    win.show_sample()
    return app.exec()
