"""Signatures view: calibrate + per-material show/hide grid (replaces the old side panel)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..materials import MATERIALS, TIER_COLORS
from .widgets import card


class SigsView(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        cfg = ctx.config
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        title = QLabel("Signatures")
        title.setObjectName("H1")
        root.addWidget(title)

        c, lay = card("Capture box")
        crow = QHBoxLayout()
        crow.addWidget(QLabel("Signature box:"))
        self.cal_lbl = QLabel()
        self.cal_lbl.setObjectName("Muted")
        crow.addWidget(self.cal_lbl)
        crow.addStretch(1)
        lay.addLayout(crow)
        root.addWidget(c)

        gc, glay = card("Show / hide materials")
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.textChanged.connect(self._filter)
        top.addWidget(self.search, 1)
        allb = QPushButton("Show all")
        allb.clicked.connect(lambda: self._bulk(True))
        noneb = QPushButton("Show none")
        noneb.clicked.connect(lambda: self._bulk(False))
        top.addWidget(allb)
        top.addWidget(noneb)
        glay.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        ilay = QVBoxLayout(inner)
        ilay.setContentsMargins(0, 0, 0, 0)
        ilay.setSpacing(2)
        disabled = set(cfg.disabled_materials)
        self.rows = []  # (name, row_widget, checkbox)
        seen_tier = set()
        for m in MATERIALS:
            if m.tier not in seen_tier:
                seen_tier.add(m.tier)
                h = QLabel(m.tier)
                h.setObjectName("Muted")
                h.setStyleSheet("margin-top: 8px; font-weight: 700;")
                ilay.addWidget(h)
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            chip = QLabel()
            chip.setFixedSize(12, 12)
            chip.setStyleSheet(f"background: {TIER_COLORS.get(m.tier, '#888')}; border-radius: 3px;")
            rl.addWidget(chip)
            cb = QCheckBox(m.name)
            cb.setChecked(m.name not in disabled)
            cb.toggled.connect(self._save)
            rl.addWidget(cb)
            rl.addStretch(1)
            ilay.addWidget(row)
            self.rows.append((m.name.lower(), row, cb))
        ilay.addStretch(1)
        scroll.setWidget(inner)
        glay.addWidget(scroll, 1)
        root.addWidget(gc, 1)
        self.refresh()

    def refresh(self):
        cfg = self.ctx.config
        r = cfg.region
        self.cal_lbl.setText(f"{r.width}×{r.height}" if cfg.calibrated else "not calibrated")

    def _filter(self, text):
        t = text.lower().strip()
        for name, row, _cb in self.rows:
            row.setVisible(t in name)

    def _bulk(self, show):
        for _n, _row, cb in self.rows:
            cb.blockSignals(True)
            cb.setChecked(show)
            cb.blockSignals(False)
        self._save()

    def _save(self):
        self.ctx.config.disabled_materials = [
            cb.text() for _n, _row, cb in self.rows if not cb.isChecked()
        ]
        self.ctx.config.save()
