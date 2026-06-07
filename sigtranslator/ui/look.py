"""Appearance view: accent color, label size, font, rarity, overlay toggles, preview."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from .widgets import LinesView, card

_FONTS = ["Bahnschrift", "Consolas", "Segoe UI", "Eurostile", "Orbitron"]


class LookView(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        cfg = ctx.config
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        title = QLabel("Look")
        title.setObjectName("H1")
        root.addWidget(title)

        c, lay = card("Overlay")
        # accent
        arow = QHBoxLayout()
        arow.addWidget(QLabel("Accent color"))
        self.swatch = QLabel()
        self.swatch.setFixedSize(28, 20)
        self._set_swatch(cfg.accent_color)
        arow.addWidget(self.swatch)
        pick = QPushButton("Pick…")
        pick.clicked.connect(self._pick_accent)
        arow.addWidget(pick)
        arow.addStretch(1)
        lay.addLayout(arow)
        # size
        srow = QHBoxLayout()
        srow.addWidget(QLabel("Label size"))
        self.size = QSlider(Qt.Horizontal)
        self.size.setRange(10, 40)
        self.size.setValue(cfg.font_size)
        self.size.valueChanged.connect(self._size)
        srow.addWidget(self.size, 1)
        self.size_lbl = QLabel(str(cfg.font_size))
        srow.addWidget(self.size_lbl)
        lay.addLayout(srow)
        # font
        frow = QHBoxLayout()
        frow.addWidget(QLabel("Font"))
        self.font = QComboBox()
        self.font.addItems(_FONTS)
        if cfg.font_family in _FONTS:
            self.font.setCurrentText(cfg.font_family)
        self.font.currentTextChanged.connect(self._font)
        frow.addWidget(self.font, 1)
        lay.addLayout(frow)
        # toggles
        self.rarity = QCheckBox("Show rarity in the label, e.g. (Epic)")
        self.rarity.setChecked(cfg.show_rarity)
        self.rarity.toggled.connect(self._rarity)
        lay.addWidget(self.rarity)
        self.sig_ov = QCheckBox("In-game signature overlay")
        self.sig_ov.setChecked(cfg.show_sig_overlay)
        self.sig_ov.toggled.connect(self._sig_ov)
        lay.addWidget(self.sig_ov)
        self.mine_ov = QCheckBox("In-game mining overlay")
        self.mine_ov.setChecked(cfg.show_mining_overlay)
        self.mine_ov.toggled.connect(self._mine_ov)
        lay.addWidget(self.mine_ov)
        hint = QLabel("Turn both overlays off for a pure second-monitor setup — the readout "
                      "stays live on the Home page.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        root.addWidget(c)

        pc, play = card("Preview")
        self.preview = LinesView()
        self.preview.set_lines([
            (f"[ 6,770 ]", cfg.accent_color),
            ("Riccite ×2  (Epic)", "#bf5bd6"),
        ])
        play.addWidget(self.preview)
        root.addWidget(pc)
        root.addStretch(1)

    def _set_swatch(self, color):
        self.swatch.setStyleSheet(f"background: {color}; border: 1px solid #2a323c; border-radius: 4px;")

    def _pick_accent(self):
        col = QColorDialog.getColor()
        if col.isValid():
            self.ctx.config.accent_color = col.name()
            self._set_swatch(col.name())
            self._changed()

    def _size(self, v):
        self.ctx.config.font_size = int(v)
        self.size_lbl.setText(str(int(v)))
        self._changed()

    def _font(self, name):
        self.ctx.config.font_family = name
        self._changed()

    def _rarity(self, on):
        self.ctx.config.show_rarity = bool(on)
        self._changed()

    def _sig_ov(self, on):
        self.ctx.config.show_sig_overlay = bool(on)
        self._changed()

    def _mine_ov(self, on):
        self.ctx.config.show_mining_overlay = bool(on)
        self._changed()

    def _changed(self):
        self.ctx.config.save()
        cfg = self.ctx.config
        self.preview.set_lines([(f"[ 6,770 ]", cfg.accent_color), ("Riccite ×2  (Epic)", "#bf5bd6")])
        self.ctx.on_appearance_changed()
