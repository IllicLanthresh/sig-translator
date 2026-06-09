"""Qt app: single window (Home / Sigs / Mine / Look / Setup) + the two overlays.

This is the controller. It owns the config, the capture/OCR worker (a background thread
that emits Qt signals), the two click-through overlays, and the views. Worker results
fan out to the overlays (when enabled) and the Home live panels.
"""

from __future__ import annotations

import sys
import threading

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from .. import __version__
from ..config import Config
from . import format as fmt
from . import theme
from .breakability_overlay import BreakabilityOverlay
from .home import HomeView
from .mine import MineView
from .overlay import Overlay
from .settings import SettingsView
from .sigs import SigsView
from .worker import Worker

_NAV = ["◉  Control", "⌖  Sigs", "⛏  Loadouts", "⚙  Settings"]


class MainWindow(QMainWindow):
    hotkey_fired = Signal()
    update_found = Signal(str)

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.setWindowTitle(f"sig-translator  v{__version__}")
        self.resize(880, 600)

        self.sig_overlay = Overlay(config.font_family, config.font_size)
        self.mining_overlay = BreakabilityOverlay(config)

        self.home = HomeView(self)
        self.sigs = SigsView(self)
        self.mine = MineView(self)
        self.settings = SettingsView(self)

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
        for v in (self.home, self.sigs, self.mine, self.settings):
            self.stack.addWidget(v)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        row.addWidget(self.nav)
        row.addWidget(self.stack, 1)

        self.mining_overlay.plan_changed.connect(self._on_plan)

        self.worker = Worker(config)
        self.worker.signals.sig.connect(self._on_sig)
        self.worker.signals.mining.connect(self._on_mining)
        self.worker.signals.status.connect(self.home.set_status)
        self.worker.start()

        self.hotkey_fired.connect(lambda: self.set_capture(not self.config.enabled))
        self.update_found.connect(self.home.set_update)
        self.register_hotkey()
        self.mining_overlay.install_hook()
        self._start_update_check()

    # ---- worker slots ----
    def _on_sig(self, matches, number) -> None:
        lines = fmt.sig_lines(matches, number, self.config)
        self.home.live_sig.set_lines(lines)
        if self.config.show_sig_overlay and self.config.calibrated and lines:
            r = self.config.region
            self._style(self.sig_overlay)
            self.sig_overlay.set_lines(lines, anchor=(r.x + r.width // 2, r.y + r.height + 4))
        else:
            self.sig_overlay.hide()

    def _on_mining(self, rock) -> None:
        # Feed the scanned rock to the overlay; it evaluates the user's live config and
        # echoes the resulting Plan back via plan_changed (-> Home + nothing else here).
        if self.config.show_mining_overlay and self.config.rock_calibrated:
            r = self.config.rock_region
            self.mining_overlay.set_rock(rock, self.config, (r.x + r.width // 2, r.y - 4))
        else:
            self.mining_overlay.hide()
            self.home.live_mine.set_lines(fmt.mining_lines(None, self.config))

    def _on_plan(self, plan) -> None:
        self.home.live_mine.set_lines(fmt.mining_lines(plan, self.config))

    def _style(self, overlay: Overlay) -> None:
        overlay._family = self.config.font_family
        overlay._size = self.config.font_size

    # ---- ctx API used by the views ----
    def set_capture(self, on: bool) -> None:
        self.config.enabled = bool(on)
        self.config.save()
        self.home.set_capture(on)

    def open_calibration(self) -> None:
        from .calibrate import calibrate

        if calibrate(self.config, mining=self.config.mining_enabled):
            self.sigs.refresh()
            self.mine.refresh()

    def on_appearance_changed(self) -> None:
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.qss(self.config.accent_color))

    def loadouts_changed(self) -> None:
        self.home.refresh()
        self.mine.refresh()
        self.mining_overlay.reload_loadout()

    def open_releases(self) -> None:
        import webbrowser

        from ..update import RELEASES_URL

        webbrowser.open(RELEASES_URL)

    def register_hotkey(self) -> None:
        try:
            import keyboard
        except Exception:
            return
        try:
            keyboard.clear_all_hotkeys()
        except Exception:
            pass
        try:
            keyboard.add_hotkey(self.config.hotkey, self.hotkey_fired.emit)
        except Exception:
            pass

    def _start_update_check(self) -> None:
        if not self.config.check_updates:
            return

        def work():
            from ..update import check_for_update

            tag = check_for_update(__version__)
            if tag:
                self.update_found.emit(tag)

        threading.Thread(target=work, daemon=True).start()

    def closeEvent(self, event) -> None:
        self.worker.stop()
        self.mining_overlay.stop()
        try:
            import keyboard

            keyboard.clear_all_hotkeys()
        except Exception:
            pass
        super().closeEvent(event)


def run() -> int:
    config = Config.load()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(theme.qss(config.accent_color))
    win = MainWindow(config)
    win.show()
    return app.exec()
