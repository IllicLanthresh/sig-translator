"""Mining view: toggle, calibrate, saved loadouts (CRUD) + turret cards."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..mining import LASERS, LASERS_BY_KEY, MODULES
from .widgets import card

_NONE = "— none —"
_EMPTY = "— empty —"
_LASER_NAMES = [_NONE] + [l.name for l in LASERS]
_L_N2K = {l.name: l.key for l in LASERS}
_L_K2N = {l.key: l.name for l in LASERS}
_MODULE_NAMES = [_EMPTY] + [m.name for m in MODULES]
_M_N2K = {m.name: m.key for m in MODULES}
_M_K2N = {m.key: m.name for m in MODULES}


class TurretCard(QFrame):
    def __init__(self, index, on_change) -> None:
        super().__init__()
        self.setObjectName("Card")
        self.index = index
        self.on_change = on_change
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)
        h = QLabel(f"Turret {index + 1}")
        h.setObjectName("H2")
        lay.addWidget(h)
        self.laser = QComboBox()
        self.laser.addItems(_LASER_NAMES)
        self.laser.currentTextChanged.connect(self._on_laser)
        lay.addWidget(self.laser)
        self.modules_box = QWidget()
        self.modules_lay = QVBoxLayout(self.modules_box)
        self.modules_lay.setContentsMargins(0, 0, 0, 0)
        self.modules_lay.setSpacing(4)
        lay.addWidget(self.modules_box)
        self.module_combos: list[QComboBox] = []

    def load(self, entry) -> None:
        self.laser.blockSignals(True)
        lk = (entry or {}).get("laser")
        self.laser.setCurrentText(_L_K2N.get(lk, _NONE))
        self.laser.blockSignals(False)
        self._rebuild((entry or {}).get("modules", []))

    def _on_laser(self, _name) -> None:
        self._rebuild([])
        self.on_change()

    def _rebuild(self, preset) -> None:
        while self.modules_lay.count():
            it = self.modules_lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self.module_combos = []
        name = self.laser.currentText()
        if name == _NONE:
            return
        laser = LASERS_BY_KEY[_L_N2K[name]]
        preset = preset or []
        for s in range(laser.slots or 0):
            cb = QComboBox()
            cb.addItems(_MODULE_NAMES)
            if s < len(preset) and preset[s] in _M_K2N:
                cb.blockSignals(True)
                cb.setCurrentText(_M_K2N[preset[s]])
                cb.blockSignals(False)
            cb.currentTextChanged.connect(lambda _t: self.on_change())
            self.modules_lay.addWidget(cb)
            self.module_combos.append(cb)

    def entry(self):
        name = self.laser.currentText()
        if name == _NONE:
            return None
        mods = [_M_N2K[c.currentText()] for c in self.module_combos if c.currentText() != _EMPTY]
        return {"laser": _L_N2K[name], "modules": mods}


class MineView(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        cfg = ctx.config
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        title = QLabel("Loadouts")
        title.setObjectName("H1")
        root.addWidget(title)

        c, lay = card("Breakability")
        trow = QHBoxLayout()
        self.toggle = QCheckBox("Mining mode")
        self.toggle.setChecked(cfg.mining_enabled)
        self.toggle.toggled.connect(self._toggle)
        trow.addWidget(self.toggle)
        self.cal_lbl = QLabel()
        self.cal_lbl.setObjectName("Muted")
        trow.addWidget(self.cal_lbl)
        trow.addStretch(1)
        lay.addLayout(trow)
        root.addWidget(c)

        lc, llay = card("Loadout")
        srow = QHBoxLayout()
        self.switch = QComboBox()
        self.switch.currentTextChanged.connect(self._switch)
        srow.addWidget(self.switch, 1)
        for text, fn in (("New", self._new), ("Rename", self._rename),
                         ("Duplicate", self._dup), ("Delete", self._delete)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            srow.addWidget(b)
        llay.addLayout(srow)
        cards_row = QHBoxLayout()
        self.cards = [TurretCard(i, self._save_turrets) for i in range(3)]
        for tc in self.cards:
            cards_row.addWidget(tc)
        llay.addLayout(cards_row)
        root.addWidget(lc)
        root.addStretch(1)

        self.refresh()

    # ---- data ----
    def _active(self):
        for lo in self.ctx.config.loadouts:
            if lo.get("name") == self.ctx.config.active_loadout:
                return lo
        return self.ctx.config.loadouts[0] if self.ctx.config.loadouts else None

    def refresh(self):
        cfg = self.ctx.config
        r = cfg.rock_region
        self.cal_lbl.setText(f"{r.width}×{r.height}" if cfg.rock_calibrated else "not calibrated")
        self.switch.blockSignals(True)
        self.switch.clear()
        self.switch.addItems([lo["name"] for lo in cfg.loadouts])
        if cfg.active_loadout:
            self.switch.setCurrentText(cfg.active_loadout)
        self.switch.blockSignals(False)
        self._load_cards()

    def _load_cards(self):
        active = self._active()
        turrets = active.get("turrets", []) if active else []
        for i, tc in enumerate(self.cards):
            tc.load(turrets[i] if i < len(turrets) else None)

    # ---- events ----
    def _toggle(self, on):
        self.ctx.config.mining_enabled = bool(on)
        self.ctx.config.save()

    def _switch(self, name):
        if name:
            self.ctx.config.active_loadout = name
            self.ctx.config.save()
            self._load_cards()
            self.ctx.loadouts_changed()

    def _save_turrets(self):
        active = self._active()
        if active is None:
            return
        active["turrets"] = [e for e in (tc.entry() for tc in self.cards) if e is not None]
        self.ctx.config.save()

    def _new(self):
        name, ok = QInputDialog.getText(self, "New loadout", "Name:")
        name = name.strip()
        if ok and name:
            self.ctx.config.loadouts.append({"name": name, "turrets": []})
            self.ctx.config.active_loadout = name
            self.ctx.config.save()
            self.refresh()
            self.ctx.loadouts_changed()

    def _rename(self):
        active = self._active()
        if not active:
            return
        name, ok = QInputDialog.getText(self, "Rename loadout", "Name:", text=active["name"])
        name = name.strip()
        if ok and name:
            active["name"] = name
            self.ctx.config.active_loadout = name
            self.ctx.config.save()
            self.refresh()
            self.ctx.loadouts_changed()

    def _dup(self):
        active = self._active()
        if not active:
            return
        new = {"name": active["name"] + " copy",
               "turrets": [dict(t) for t in active.get("turrets", [])]}
        self.ctx.config.loadouts.append(new)
        self.ctx.config.active_loadout = new["name"]
        self.ctx.config.save()
        self.refresh()
        self.ctx.loadouts_changed()

    def _delete(self):
        cfg = self.ctx.config
        if len(cfg.loadouts) <= 1:
            return
        cfg.loadouts = [lo for lo in cfg.loadouts if lo.get("name") != cfg.active_loadout]
        cfg.active_loadout = cfg.loadouts[0]["name"]
        cfg.save()
        self.refresh()
        self.ctx.loadouts_changed()
