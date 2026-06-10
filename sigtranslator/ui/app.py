"""Qt app: header bar + drill-in pages (Dashboard / Materials / Loadouts / Settings).

This is the controller. It owns the config, the capture/OCR worker (a background thread
that emits Qt signals), the two click-through overlays, and the pages. Worker results
fan out to the overlays (when enabled) and the dashboard mirrors. Navigation is
drill-in: the dashboard is home; subpages get a ← back button in the header.
"""

from __future__ import annotations

import sys
import threading

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
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


class MainWindow(QMainWindow):
    hotkey_fired = Signal()
    update_found = Signal(str)

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.setWindowTitle(f"sig-translator  v{__version__}")
        self.resize(900, 620)

        self.sig_overlay = Overlay(config.font_family, config.font_size)
        self.mining_overlay = BreakabilityOverlay(config, trigger=config.edit_hotkey)

        self.home = HomeView(self)
        self.sigs = SigsView(self)
        self.mine = MineView(self)
        self.settings = SettingsView(self)

        central = QWidget()
        self.setCentralWidget(central)
        col = QVBoxLayout(central)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._build_header())
        self.stack = QStackedWidget()
        for v in (self.home, self.sigs, self.mine, self.settings):
            self.stack.addWidget(v)
        self.stack.currentChanged.connect(
            lambda i: self.back_btn.setVisible(i != 0))
        col.addWidget(self.stack, 1)

        self.worker = Worker(config)
        self.worker.signals.sig.connect(self._on_sig)
        self.worker.signals.mining.connect(self._on_mining)
        self.worker.signals.status.connect(self.home.set_status)
        self.worker.start()

        self.hotkey_fired.connect(lambda: self.set_capture(not self.config.enabled))
        self.update_found.connect(self.set_update)
        self.register_hotkey()
        self.mining_overlay.install_hook()
        self._start_update_check()

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Header")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(10)
        self.back_btn = QPushButton("←  back")
        self.back_btn.setObjectName("Ghost")
        self.back_btn.clicked.connect(self.go_home)
        self.back_btn.setVisible(False)
        row.addWidget(self.back_btn)
        title = QLabel("SIG-TRANSLATOR")
        title.setObjectName("H2")
        row.addWidget(title)
        ver = QLabel(f"v{__version__}")
        ver.setObjectName("Muted")
        row.addWidget(ver)
        row.addStretch(1)
        self.update_btn = QPushButton()
        self.update_btn.setStyleSheet(
            "QPushButton { color: #ffcc44; font-weight: 700; background: transparent; "
            "border: none; padding: 0; }")
        self.update_btn.clicked.connect(self.open_releases)
        self.update_btn.hide()
        row.addWidget(self.update_btn)
        gear = QPushButton("⚙")
        gear.setObjectName("Ghost")
        gear.clicked.connect(self.open_settings)
        row.addWidget(gear)
        return bar

    # ---- navigation (drill-in) ----
    def go_home(self) -> None:
        self.stack.setCurrentWidget(self.home)

    def open_materials(self) -> None:
        self.stack.setCurrentWidget(self.sigs)

    def open_loadouts(self) -> None:
        self.stack.setCurrentWidget(self.mine)

    def open_settings(self) -> None:
        self.stack.setCurrentWidget(self.settings)

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
        # Feed the scanned rock to the overlay; it evaluates the user's live config,
        # mirrors itself onto the dashboard, and only draws in-game when allowed.
        anchor = None
        if self.config.rock_calibrated:
            r = self.config.rock_region
            anchor = (r.x + r.width // 2, r.y - 4)
        self.mining_overlay.set_rock(rock, self.config, anchor)

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

        if calibrate(self.config, mining=True):
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

    def set_update(self, tag: str) -> None:
        self.update_btn.setText(f"⬆ v{tag} available")
        self.update_btn.show()

    def register_edit_key(self) -> None:
        # set_trigger clears ALL keyboard hooks (lib limitation), so re-add the scan hotkey
        self.mining_overlay.set_trigger(self.config.edit_hotkey)
        self.register_hotkey()

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
