"""Small shared Qt widgets/helpers for the views."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


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


class LinesView(QWidget):
    """Renders a list of (text, '#color') lines as a vertical stack of colored labels."""

    def __init__(self, placeholder: str = "—") -> None:
        super().__init__()
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(2)
        self._placeholder = placeholder
        self.set_lines([])

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
            self._lay.addWidget(lbl)
