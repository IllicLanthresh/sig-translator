"""Dashboard: command rail (left) + live-mirror stages (right).

The rail holds every control, grouped per feature; the stages give the two overlay
mirrors a dark canvas at native scale. Overlay visibility is toggled by the
IN GAME · SHOWN/HIDDEN pill that sits on each stage — the control lives on the thing
it controls. Submenus (Materials / Loadouts / Settings) open as drawers (main window).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..mining import difficulty
from .breakability_overlay import BreakabilityMirror
from .overlay import SigMirror
from .widgets import card

MUTED = "#9aa4b0"
DIM = "#5e6770"
WHITE = "#e6edf3"


class HomeView(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        cfg = ctx.config
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)
        root.addWidget(self._rail(cfg))
        root.addLayout(self._stages(cfg), 1)

        ctx.mining_overlay.plan_changed.connect(self._mine_status)
        ctx.mining_overlay.layout_changed.connect(self._sync_turrets)
        self.refresh()

    # ================= rail =================
    def _rail(self, cfg) -> QWidget:
        rail = QFrame()
        rail.setObjectName("Card")
        rail.setFixedWidth(330)
        lay = QVBoxLayout(rail)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        # ---- SIGNATURE ----
        lay.addWidget(self._h2("SIGNATURE"))
        self.sig_toggle = self._switch()
        self.sig_toggle.clicked.connect(lambda: self.ctx.set_capture(self.sig_toggle.isChecked()))
        lay.addWidget(self.sig_toggle)
        self.status = QLabel("starting…")
        self.status.setObjectName("Muted")
        lay.addWidget(self.status)
        srow = QHBoxLayout()
        srow.setSpacing(8)
        srow.addWidget(self._btn("Calibrate box…", self.ctx.open_calibration))
        srow.addWidget(self._btn("Materials…", self.ctx.open_materials))
        srow.addStretch(1)
        lay.addLayout(srow)
        self.rarity = QCheckBox("Show rarity in label")
        self.rarity.setChecked(cfg.show_rarity)
        self.rarity.toggled.connect(self._rarity_toggle)
        lay.addWidget(self.rarity)

        lay.addWidget(self._divider())

        # ---- BREAKABILITY ----
        lay.addWidget(self._h2("BREAKABILITY"))
        self.mine_toggle = self._switch()
        self.mine_toggle.clicked.connect(lambda: self._set_mining(self.mine_toggle.isChecked()))
        lay.addWidget(self.mine_toggle)
        self.mine_status = QLabel("scanner off")
        self.mine_status.setObjectName("Muted")
        lay.addWidget(self.mine_status)

        lrow = QHBoxLayout()
        lrow.addWidget(QLabel("Loadout"))
        self.quick = QComboBox()
        self.quick.currentTextChanged.connect(self._quick)
        lrow.addWidget(self.quick, 1)
        lay.addLayout(lrow)

        self._turret_box = QVBoxLayout()
        self._turret_box.setSpacing(0)
        lay.addLayout(self._turret_box)
        self._turret_rows: list[QPushButton] = []

        brow = QHBoxLayout()
        brow.setSpacing(8)
        brow.addWidget(self._btn("Edit loadouts…", self.ctx.open_loadouts))
        brow.addWidget(self._btn("Calibrate box…", self.ctx.open_calibration))
        brow.addStretch(1)
        lay.addLayout(brow)

        krow = QHBoxLayout()
        krow.addWidget(QLabel("Hold-to-edit"))
        self.edit_key = QLineEdit(cfg.edit_hotkey)
        self.edit_key.setFixedWidth(110)
        self.edit_key.setAlignment(Qt.AlignCenter)
        self.edit_key.editingFinished.connect(self._edit_key)
        krow.addWidget(self.edit_key)
        krow.addStretch(1)
        lay.addLayout(krow)

        lay.addStretch(1)

        # ---- footer chips (app-level quick info; click -> settings) ----
        foot = QHBoxLayout()
        foot.setSpacing(8)
        self.hotkey_chip = self._chip()
        foot.addWidget(self.hotkey_chip)
        self.fps_chip = self._chip()
        foot.addWidget(self.fps_chip)
        foot.addStretch(1)
        lay.addLayout(foot)
        return rail

    # ================= stages =================
    def _stages(self, cfg) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(14)

        self.sig_pill = self._pill(cfg.show_sig_overlay)
        self.sig_pill.clicked.connect(self._sig_ov_toggle)
        self.live_sig = SigMirror(cfg, placeholder="no signal")
        col.addWidget(self._stage("SIGNATURE · LIVE MIRROR", self.sig_pill, self.live_sig), 2)

        self.mine_pill = self._pill(cfg.show_mining_overlay)
        self.mine_pill.clicked.connect(self._mine_ov_toggle)
        self.live_mine = BreakabilityMirror(self.ctx.mining_overlay)
        col.addWidget(self._stage("BREAKABILITY · LIVE MIRROR", self.mine_pill, self.live_mine), 3)
        return col

    def _stage(self, title: str, pill: QPushButton, mirror: QWidget) -> QWidget:
        c, lay = card()
        head = QHBoxLayout()
        t = QLabel(title)
        t.setObjectName("Muted")
        head.addWidget(t)
        head.addStretch(1)
        head.addWidget(pill)
        lay.addLayout(head)
        stage = QFrame()
        stage.setObjectName("Stage")
        s = QVBoxLayout(stage)
        s.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(mirror)
        row.addStretch(1)
        s.addLayout(row)
        s.addStretch(1)
        lay.addWidget(stage, 1)
        return c

    # ================= small builders =================
    @staticmethod
    def _h2(text: str) -> QLabel:
        h = QLabel(text)
        h.setObjectName("H2")
        return h

    @staticmethod
    def _divider() -> QFrame:
        d = QFrame()
        d.setFrameShape(QFrame.HLine)
        d.setStyleSheet("color: #2a323c; margin: 6px 0;")
        return d

    @staticmethod
    def _switch() -> QPushButton:
        b = QPushButton()
        b.setObjectName("Scanner")
        b.setCheckable(True)
        b.setMinimumHeight(40)
        return b

    @staticmethod
    def _btn(text: str, slot) -> QPushButton:
        b = QPushButton(text)
        b.clicked.connect(slot)
        return b

    def _chip(self) -> QPushButton:
        b = QPushButton()
        b.setObjectName("Chip")
        b.clicked.connect(self.ctx.open_settings)
        return b

    @staticmethod
    def _pill(shown: bool) -> QPushButton:
        b = QPushButton()
        b.setObjectName("Pill")
        b.setCheckable(True)
        b.setChecked(shown)
        b.setToolTip("Whether the overlay is also drawn over the game.\n"
                     "Hidden: the scanner keeps running and the mirror here stays live.")
        return b

    @staticmethod
    def _pill_text(b: QPushButton) -> None:
        b.setText("IN GAME · SHOWN" if b.isChecked() else "IN GAME · HIDDEN")

    # ================= refresh / external updates =================
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
        for b, v in ((self.sig_pill, cfg.show_sig_overlay), (self.mine_pill, cfg.show_mining_overlay)):
            b.blockSignals(True)
            b.setChecked(v)
            self._pill_text(b)
            b.blockSignals(False)
        self.hotkey_chip.setText(f"SCAN  {cfg.hotkey}")
        self.fps_chip.setText(f"{cfg.scan_fps:.1f} FPS")
        self.edit_key.setText(cfg.edit_hotkey)
        self._sync_turrets()

    def _sync_turrets(self):
        heads = self.ctx.mining_overlay.heads
        while len(self._turret_rows) < len(heads):
            i = len(self._turret_rows)
            b = QPushButton()
            b.setObjectName("TurretRow")
            b.setToolTip("Click to toggle this head on/off")
            b.clicked.connect(lambda _=False, idx=i: self._toggle_head(idx))
            self._turret_box.addWidget(b)
            self._turret_rows.append(b)
        for i, b in enumerate(self._turret_rows):
            if i >= len(heads):
                b.hide()
                continue
            h = heads[i]
            mods = {}
            for m in h["passives"] + h["actives"]:
                mods[m.name] = mods.get(m.name, 0) + 1
            summary = " · ".join(f"{n} ×{c}" if c > 1 else n for n, c in mods.items())
            b.setText(f"T{i + 1}   {h['laser'].name}     {summary}")
            b.setStyleSheet(f"color: {WHITE if h['on'] else DIM};")
            b.show()

    def _toggle_head(self, i: int):
        ov = self.ctx.mining_overlay
        if i < len(ov.heads):
            ov.heads[i]["on"] = not ov.heads[i]["on"]
            ov._after_toggle()

    def set_capture(self, on):
        self.sig_toggle.blockSignals(True)
        self.sig_toggle.setChecked(on)
        self.sig_toggle.setText("●  SCANNING" if on else "○  OFF")
        self.sig_toggle.blockSignals(False)

    def _set_mining_ui(self, on):
        self.mine_toggle.blockSignals(True)
        self.mine_toggle.setChecked(on)
        self.mine_toggle.setText("●  SCANNING" if on else "○  OFF")
        self.mine_toggle.blockSignals(False)

    def set_status(self, text):
        self.status.setText(text)

    def _mine_status(self, plan):
        if not self.ctx.config.mining_enabled:
            self.mine_status.setText("scanner off")
        elif plan is None:
            self.mine_status.setText("no rock in view")
        else:
            label, _c = difficulty(plan)
            txt = f"rock {int(plan.rock.mass):,} · {label.lower()}"
            if plan.stable_pct is not None and plan.kind != "impossible":
                txt += f" · hold {plan.stable_pct:.0f}%"
            self.mine_status.setText(txt)

    # ================= events =================
    def _set_mining(self, on):
        self.ctx.config.mining_enabled = bool(on)
        self.ctx.config.save()
        self._set_mining_ui(on)
        self._mine_status(None)

    def _sig_ov_toggle(self):
        self.ctx.config.show_sig_overlay = self.sig_pill.isChecked()
        self.ctx.config.save()
        self._pill_text(self.sig_pill)

    def _mine_ov_toggle(self):
        self.ctx.config.show_mining_overlay = self.mine_pill.isChecked()
        self.ctx.config.save()
        self._pill_text(self.mine_pill)
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
