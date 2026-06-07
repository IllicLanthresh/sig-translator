"""Setup view: hotkey, scan FPS, update check, about."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from .widgets import card


class SetupView(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        cfg = ctx.config
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        title = QLabel("Setup")
        title.setObjectName("H1")
        root.addWidget(title)

        c, lay = card("General")
        hrow = QHBoxLayout()
        hrow.addWidget(QLabel("Toggle hotkey"))
        self.hotkey = QLineEdit(cfg.hotkey)
        self.hotkey.setFixedWidth(160)
        self.hotkey.editingFinished.connect(self._hotkey)
        hrow.addWidget(self.hotkey)
        hrow.addStretch(1)
        lay.addLayout(hrow)

        frow = QHBoxLayout()
        frow.addWidget(QLabel("Scan FPS"))
        self.fps = QSlider(Qt.Horizontal)
        self.fps.setRange(1, 20)  # tenths-of-... no: 1..20 fps mapped directly via /2
        self.fps.setRange(1, 20)
        self.fps.setValue(int(cfg.scan_fps * 2))  # 0.5 steps
        self.fps.valueChanged.connect(self._fps)
        frow.addWidget(self.fps, 1)
        self.fps_lbl = QLabel(f"{cfg.scan_fps:.1f}")
        frow.addWidget(self.fps_lbl)
        lay.addLayout(frow)

        self.updates = QCheckBox("Check for updates on startup")
        self.updates.setChecked(cfg.check_updates)
        self.updates.toggled.connect(self._updates)
        lay.addWidget(self.updates)
        root.addWidget(c)

        ac, alay = card("About")
        alay.addWidget(QLabel(f"sig-translator  v{__version__}"))
        sub = QLabel("Read-only signature + mining overlay for Star Citizen. Settings saved to "
                     "%APPDATA%\\sig-translator\\config.json.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        alay.addWidget(sub)
        root.addWidget(ac)
        root.addStretch(1)

    def _hotkey(self):
        new = self.hotkey.text().strip()
        if new and new != self.ctx.config.hotkey:
            self.ctx.config.hotkey = new
            self.ctx.config.save()
            self.ctx.register_hotkey()

    def _fps(self, v):
        fps = max(0.5, v / 2)
        self.ctx.config.scan_fps = fps
        self.fps_lbl.setText(f"{fps:.1f}")
        self.ctx.config.save()

    def _updates(self, on):
        self.ctx.config.check_updates = bool(on)
        self.ctx.config.save()
