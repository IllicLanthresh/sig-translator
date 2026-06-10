"""Dashboard: one column per feature (Signature / Breakability), no tabs.

Each column is self-contained: scanner switch, in-game overlay visibility, a live
mirror of the actual overlay (same renderer — the breakability one is clickable),
a status line, and the feature's own controls. Subpages (Materials, Loadouts,
Settings) are reached via drill-in buttons handled by the main window.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .breakability_overlay import BreakabilityMirror
from .overlay import SigMirror
from .widgets import card


class HomeView(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        cfg = ctx.config
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        cols = QHBoxLayout()
        cols.setSpacing(14)
        cols.addWidget(self._sig_column(cfg), 1)
        cols.addWidget(self._mine_column(cfg), 1)
        root.addLayout(cols, 1)

        ctx.mining_overlay.plan_changed.connect(self._mine_status)
        self.refresh()

    # ---- column builders ----
    def _header_row(self, title: str, overlay_cb: QCheckBox) -> QHBoxLayout:
        row = QHBoxLayout()
        h = QLabel(title)
        h.setObjectName("H2")
        row.addWidget(h)
        row.addStretch(1)
        row.addWidget(overlay_cb)
        return row

    @staticmethod
    def _switch() -> QPushButton:
        b = QPushButton()
        b.setObjectName("Scanner")
        b.setCheckable(True)
        b.setMinimumHeight(40)
        return b

    @staticmethod
    def _centered(widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(widget)
        row.addStretch(1)
        return row

    def _sig_column(self, cfg) -> QWidget:
        c, lay = card()
        self.sig_ov = QCheckBox("in-game overlay")
        self.sig_ov.setChecked(cfg.show_sig_overlay)
        self.sig_ov.toggled.connect(self._sig_ov_toggle)
        lay.addLayout(self._header_row("SIGNATURE", self.sig_ov))

        self.sig_toggle = self._switch()
        self.sig_toggle.clicked.connect(lambda: self.ctx.set_capture(self.sig_toggle.isChecked()))
        lay.addWidget(self.sig_toggle)

        self.live_sig = SigMirror(cfg, placeholder="no signal")
        lay.addLayout(self._centered(self.live_sig))

        self.status = QLabel("starting…")
        self.status.setObjectName("Muted")
        lay.addWidget(self.status)

        lay.addStretch(1)
        ctr = QHBoxLayout()
        calb = QPushButton("Calibrate…")
        calb.clicked.connect(self.ctx.open_calibration)
        ctr.addWidget(calb)
        matb = QPushButton("Materials…")
        matb.clicked.connect(self.ctx.open_materials)
        ctr.addWidget(matb)
        ctr.addStretch(1)
        self.rarity = QCheckBox("show rarity")
        self.rarity.setChecked(cfg.show_rarity)
        self.rarity.toggled.connect(self._rarity_toggle)
        ctr.addWidget(self.rarity)
        lay.addLayout(ctr)
        return c

    def _mine_column(self, cfg) -> QWidget:
        c, lay = card()
        self.mine_ov = QCheckBox("in-game overlay")
        self.mine_ov.setChecked(cfg.show_mining_overlay)
        self.mine_ov.toggled.connect(self._mine_ov_toggle)
        lay.addLayout(self._header_row("BREAKABILITY", self.mine_ov))

        self.mine_toggle = self._switch()
        self.mine_toggle.clicked.connect(lambda: self._set_mining(self.mine_toggle.isChecked()))
        lay.addWidget(self.mine_toggle)

        self.live_mine = BreakabilityMirror(self.ctx.mining_overlay)
        lay.addLayout(self._centered(self.live_mine))

        self.mine_status = QLabel("scanner off")
        self.mine_status.setObjectName("Muted")
        lay.addWidget(self.mine_status)

        lay.addStretch(1)
        lrow = QHBoxLayout()
        lrow.addWidget(QLabel("Loadout"))
        self.quick = QComboBox()
        self.quick.currentTextChanged.connect(self._quick)
        lrow.addWidget(self.quick, 1)
        editb = QPushButton("Edit loadouts…")
        editb.clicked.connect(self.ctx.open_loadouts)
        lrow.addWidget(editb)
        lay.addLayout(lrow)

        krow = QHBoxLayout()
        calb = QPushButton("Calibrate…")
        calb.clicked.connect(self.ctx.open_calibration)
        krow.addWidget(calb)
        krow.addStretch(1)
        krow.addWidget(QLabel("Hold-to-edit key"))
        self.edit_key = QLineEdit(cfg.edit_hotkey)
        self.edit_key.setFixedWidth(110)
        self.edit_key.setAlignment(Qt.AlignCenter)
        self.edit_key.editingFinished.connect(self._edit_key)
        krow.addWidget(self.edit_key)
        lay.addLayout(krow)
        return c

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
        self.sig_toggle.setText("●  Scanning" if on else "○  Off")
        self.sig_toggle.blockSignals(False)

    def _set_mining_ui(self, on):
        self.mine_toggle.blockSignals(True)
        self.mine_toggle.setChecked(on)
        self.mine_toggle.setText("●  Scanning" if on else "○  Off")
        self.mine_toggle.blockSignals(False)

    def set_status(self, text):
        self.status.setText(text)

    def _mine_status(self, plan):
        if not self.ctx.config.mining_enabled:
            self.mine_status.setText("scanner off")
        elif plan is None:
            self.mine_status.setText("no rock in view")
        else:
            self.mine_status.setText("live")

    # ---- events ----
    def _set_mining(self, on):
        self.ctx.config.mining_enabled = bool(on)
        self.ctx.config.save()
        self._set_mining_ui(on)
        self._mine_status(None)

    def _sig_ov_toggle(self, on):
        self.ctx.config.show_sig_overlay = bool(on)
        self.ctx.config.save()

    def _mine_ov_toggle(self, on):
        self.ctx.config.show_mining_overlay = bool(on)
        self.ctx.config.save()
        self.ctx.mining_overlay._refresh()  # apply immediately, not on the next scan tick

    def _rarity_toggle(self, on):
        self.ctx.config.show_rarity = bool(on)
        self.ctx.config.save()

    def _edit_key(self):
        new = self.edit_key.text().strip().lower()
        if new and new != self.ctx.config.edit_hotkey:
            self.ctx.config.edit_hotkey = new
            self.ctx.config.save()
            self.ctx.register_edit_key()

    def _quick(self, name):
        if name:
            self.ctx.config.active_loadout = name
            self.ctx.config.save()
            self.ctx.loadouts_changed()
