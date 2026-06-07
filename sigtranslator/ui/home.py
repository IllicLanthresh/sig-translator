"""Home view: capture on/off, live readout (mirrors the overlays), quick loadout."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .widgets import LinesView, card


class HomeView(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        cfg = ctx.config
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        title = QLabel("Home")
        title.setObjectName("H1")
        root.addWidget(title)

        self.update_btn = QPushButton()
        self.update_btn.setStyleSheet(
            "QPushButton { color: #ffcc44; font-weight: 700; text-align: left; "
            "background: transparent; border: none; padding: 0; }"
        )
        self.update_btn.clicked.connect(ctx.open_releases)
        self.update_btn.hide()
        root.addWidget(self.update_btn)

        c, lay = card()
        self.toggle = QPushButton()
        self.toggle.setObjectName("Primary")
        self.toggle.setCheckable(True)
        self.toggle.setChecked(cfg.enabled)
        self.toggle.setMinimumHeight(42)
        self.toggle.clicked.connect(lambda: ctx.set_capture(self.toggle.isChecked()))
        lay.addWidget(self.toggle)
        brow = QHBoxLayout()
        calb = QPushButton("Calibrate…")
        calb.clicked.connect(ctx.open_calibration)
        brow.addWidget(calb)
        brow.addStretch(1)
        brow.addWidget(QLabel("Loadout"))
        self.quick = QComboBox()
        self.quick.setMinimumWidth(160)
        self.quick.currentTextChanged.connect(self._quick)
        brow.addWidget(self.quick)
        lay.addLayout(brow)
        self.status = QLabel("starting…")
        self.status.setObjectName("Muted")
        lay.addWidget(self.status)
        root.addWidget(c)

        live = QHBoxLayout()
        sc, slay = card("Signature")
        self.live_sig = LinesView("no signal")
        slay.addWidget(self.live_sig)
        live.addWidget(sc, 1)
        mc, mlay = card("Mining")
        self.live_mine = LinesView("no rock")
        mlay.addWidget(self.live_mine)
        live.addWidget(mc, 1)
        root.addLayout(live)
        root.addStretch(1)

        self.refresh()

    def refresh(self):
        cfg = self.ctx.config
        self.quick.blockSignals(True)
        self.quick.clear()
        self.quick.addItems([lo["name"] for lo in cfg.loadouts])
        if cfg.active_loadout:
            self.quick.setCurrentText(cfg.active_loadout)
        self.quick.blockSignals(False)
        self.set_capture(cfg.enabled)

    def set_capture(self, on):
        self.toggle.blockSignals(True)
        self.toggle.setChecked(on)
        self.toggle.setText("● Capturing — click to pause" if on else "○ Paused — click to start")
        self.toggle.blockSignals(False)

    def set_status(self, text):
        self.status.setText(text)

    def set_update(self, tag):
        self.update_btn.setText(f"⬆ New version {tag} available — click to download")
        self.update_btn.show()

    def _quick(self, name):
        if name:
            self.ctx.config.active_loadout = name
            self.ctx.config.save()
            self.ctx.loadouts_changed()
