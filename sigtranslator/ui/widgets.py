"""Small shared Qt widgets/helpers for the views."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def card(title: str | None = None):
    """Return (frame, layout) for a styled card; add your widgets to `layout`."""
    frame = QFrame()
    frame.setObjectName("Card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 16, 16, 16)
    lay.setSpacing(10)
    if title:
        h = QLabel(title)
        h.setObjectName("H2")
        lay.addWidget(h)
    return frame, lay


class SegmentToggle(QWidget):
    """Two-sided segmented toggle: each state is a labelled, clickable half.

    Left = False, right = True. The active side is filled with the accent color,
    so the current state (and what the other state would be) is always readable.
    """

    toggled = Signal(bool)

    def __init__(self, left: str, right: str, value: bool = False,
                 left_tip: str = "", right_tip: str = "") -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self._left = QPushButton(left)
        self._left.setObjectName("SegLeft")
        self._right = QPushButton(right)
        self._right.setObjectName("SegRight")
        for b in (self._left, self._right):
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        if left_tip:
            self._left.setToolTip(left_tip)
        if right_tip:
            self._right.setToolTip(right_tip)
        (self._right if value else self._left).setChecked(True)
        self._left.clicked.connect(lambda: self.toggled.emit(False))
        self._right.clicked.connect(lambda: self.toggled.emit(True))

    def value(self) -> bool:
        return self._right.isChecked()

    def set_value(self, right_active: bool) -> None:
        b = self._right if right_active else self._left
        b.blockSignals(True)
        b.setChecked(True)
        b.blockSignals(False)


class LinesView(QWidget):
    """Renders a list of (text, '#color') lines as a vertical stack of colored labels."""

    def __init__(self, placeholder: str = "—") -> None:
        super().__init__()
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(2)
        self._placeholder = placeholder
        self._font = None  # optional (family, size) to render lines like the overlay
        self.set_lines([])

    def set_font_spec(self, family: str, size: int) -> None:
        self._font = (family, size)

    def set_lines(self, lines) -> None:
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if not lines:
            lbl = QLabel(self._placeholder)
            lbl.setObjectName("Muted")
            self._lay.addWidget(lbl)
            return
        for text, color in lines:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color}; background: transparent;")
            if self._font:
                fnt = QFont(self._font[0], self._font[1])
                fnt.setBold(True)
                lbl.setFont(fnt)
            self._lay.addWidget(lbl)
