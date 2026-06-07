"""Settings view: Appearance + General (merges the old Look and Setup)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from .widgets import LinesView, card

_FONTS = ["Bahnschrift", "Consolas", "Segoe UI", "Eurostile", "Orbitron"]


class SettingsView(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        cfg = ctx.config
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        title = QLabel("Settings")
        title.setObjectName("H1")
        root.addWidget(title)

        # --- Appearance ---
        ac, alay = card("Appearance")
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
        alay.addLayout(arow)

        srow = QHBoxLayout()
        srow.addWidget(QLabel("Label size"))
        self.size = QSlider(Qt.Horizontal)
        self.size.setRange(10, 40)
        self.size.setValue(cfg.font_size)
        self.size.valueChanged.connect(self._size)
        srow.addWidget(self.size, 1)
        self.size_lbl = QLabel(str(cfg.font_size))
        srow.addWidget(self.size_lbl)
        alay.addLayout(srow)

        frow = QHBoxLayout()
        frow.addWidget(QLabel("Font"))
        self.font = QComboBox()
        self.font.addItems(_FONTS)
        if cfg.font_family in _FONTS:
            self.font.setCurrentText(cfg.font_family)
        self.font.currentTextChanged.connect(self._font)
        frow.addWidget(self.font, 1)
        alay.addLayout(frow)

        self.rarity = QCheckBox("Show rarity in the label, e.g. (Epic)")
        self.rarity.setChecked(cfg.show_rarity)
        self.rarity.toggled.connect(self._rarity)
        alay.addWidget(self.rarity)
        self.sig_ov = QCheckBox("Signature overlay (in-game)")
        self.sig_ov.setChecked(cfg.show_sig_overlay)
        self.sig_ov.toggled.connect(self._sig_ov)
        alay.addWidget(self.sig_ov)
        self.mine_ov = QCheckBox("Breakability overlay (in-game)")
        self.mine_ov.setChecked(cfg.show_mining_overlay)
        self.mine_ov.toggled.connect(self._mine_ov)
        alay.addWidget(self.mine_ov)
        hint = QLabel("Turn both overlays off for a pure second-monitor setup — the readout "
                      "stays live on the Control page.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        alay.addWidget(hint)

        self.preview = LinesView()
        alay.addWidget(QLabel("Preview"))
        alay.addWidget(self.preview)
        self._refresh_preview()
        root.addWidget(ac)

        # --- General ---
        gc, glay = card("General")
        hrow = QHBoxLayout()
        hrow.addWidget(QLabel("Toggle hotkey"))
        self.hotkey = QLineEdit(cfg.hotkey)
        self.hotkey.setFixedWidth(160)
        self.hotkey.editingFinished.connect(self._hotkey)
        hrow.addWidget(self.hotkey)
        hrow.addStretch(1)
        glay.addLayout(hrow)
        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("Scan FPS"))
        self.fps = QSlider(Qt.Horizontal)
        self.fps.setRange(1, 20)
        self.fps.setValue(int(cfg.scan_fps * 2))
        self.fps.valueChanged.connect(self._fps)
        fps_row.addWidget(self.fps, 1)
        self.fps_lbl = QLabel(f"{cfg.scan_fps:.1f}")
        fps_row.addWidget(self.fps_lbl)
        glay.addLayout(fps_row)
        self.updates = QCheckBox("Check for updates on startup")
        self.updates.setChecked(cfg.check_updates)
        self.updates.toggled.connect(self._updates)
        glay.addWidget(self.updates)
        about = QLabel(f"sig-translator  v{__version__}  ·  read-only overlay for Star Citizen")
        about.setObjectName("Muted")
        glay.addWidget(about)
        root.addWidget(gc)
        root.addStretch(1)

    # ---- appearance ----
    def _set_swatch(self, color):
        self.swatch.setStyleSheet(f"background: {color}; border: 1px solid #2a323c; border-radius: 4px;")

    def _refresh_preview(self):
        cfg = self.ctx.config
        self.preview.set_font_spec(cfg.font_family, cfg.font_size)
        self.preview.set_lines([(f"[ 6,770 ]", cfg.accent_color), ("Riccite ×2  (Epic)", "#bf5bd6")])

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
        self._refresh_preview()
        self.ctx.on_appearance_changed()

    # ---- general ----
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
