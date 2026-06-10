"""Control view: per-scanner on/off (+ its overlay), live readout, calibrate, loadout."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
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
        title = QLabel("Control")
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

        c, lay = card("Scanners")
        # Signatures scanner + its overlay
        self.sig_toggle = self._scanner_button()
        self.sig_toggle.clicked.connect(lambda: ctx.set_capture(self.sig_toggle.isChecked()))
        self.sig_ov = QCheckBox("overlay")
        self.sig_ov.setChecked(cfg.show_sig_overlay)
        self.sig_ov.toggled.connect(self._sig_ov)
        lay.addLayout(self._scanner_row(self.sig_toggle, self.sig_ov))
        # Mining scanner + its overlay
        self.mine_toggle = self._scanner_button()
        self.mine_toggle.clicked.connect(lambda: self._set_mining(self.mine_toggle.isChecked()))
        self.mine_ov = QCheckBox("overlay")
        self.mine_ov.setChecked(cfg.show_mining_overlay)
        self.mine_ov.toggled.connect(self._mine_ov)
        lay.addLayout(self._scanner_row(self.mine_toggle, self.mine_ov))

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

    # ---- builders ----
    @staticmethod
    def _scanner_button() -> QPushButton:
        b = QPushButton()
        b.setObjectName("Primary")
        b.setCheckable(True)
        b.setMinimumHeight(40)
        return b

    @staticmethod
    def _scanner_row(toggle: QPushButton, overlay_cb: QCheckBox) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(toggle, 1)
        row.addWidget(overlay_cb)
        return row

    @staticmethod
    def _btn_text(name: str, on: bool) -> str:
        return f"●  {name} — scanning" if on else f"○  {name} — off"

    # ---- refresh / external updates ----
    def refresh(self):
        cfg = self.ctx.config
        self.quick.blockSignals(True)
        self.quick.clear()
        self.quick.addItems([lo["name"] for lo in cfg.loadouts])
        if cfg.active_loadout:
            self.quick.setCurrentText(cfg.active_loadout)
        self.quick.blockSignals(False)
        self.set_capture(cfg.enabled)
        self._set_mining_ui(cfg.mining_enabled)

    def set_capture(self, on):
        self.sig_toggle.blockSignals(True)
        self.sig_toggle.setChecked(on)
        self.sig_toggle.setText(self._btn_text("Signatures", on))
        self.sig_toggle.blockSignals(False)

    def _set_mining_ui(self, on):
        self.mine_toggle.blockSignals(True)
        self.mine_toggle.setChecked(on)
        self.mine_toggle.setText(self._btn_text("Mining", on))
        self.mine_toggle.blockSignals(False)

    def set_status(self, text):
        self.status.setText(text)

    def set_update(self, tag):
        self.update_btn.setText(f"⬆ New version {tag} available — click to download")
        self.update_btn.show()

    # ---- events ----
    def _set_mining(self, on):
        self.ctx.config.mining_enabled = bool(on)
        self.ctx.config.save()
        self._set_mining_ui(on)

    def _sig_ov(self, on):
        self.ctx.config.show_sig_overlay = bool(on)
        self.ctx.config.save()

    def _mine_ov(self, on):
        self.ctx.config.show_mining_overlay = bool(on)
        self.ctx.config.save()

    def _quick(self, name):
        if name:
            self.ctx.config.active_loadout = name
            self.ctx.config.save()
            self.ctx.loadouts_changed()
