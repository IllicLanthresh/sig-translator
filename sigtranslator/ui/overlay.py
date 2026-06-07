"""Frameless, translucent, always-on-top, click-through HUD overlay (Qt).

`Qt.WindowTransparentForInput` makes the whole window pass mouse/keyboard straight
through to whatever is underneath (the game), which is what keeps it EAC-safe and
non-intrusive. Content is drawn with QPainter as a rounded translucent chip.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class Overlay(QWidget):
    def __init__(self, font_family: str = "Bahnschrift", font_size: int = 18) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._lines: list[tuple[str, str]] = []
        self._family = font_family
        self._size = font_size
        self._pad = 12
        self._gap = 4

    def _font(self) -> QFont:
        f = QFont(self._family, self._size)
        f.setBold(True)
        return f

    def set_lines(self, lines, anchor=None, above: bool = False) -> None:
        """lines: list of (text, '#hex'). anchor: (center_x, edge_y) in screen px;
        with above=True the chip's bottom sits at edge_y, else its top sits there."""
        self._lines = list(lines or [])
        if not self._lines:
            self.hide()
            return
        fm = QFontMetrics(self._font())
        w = max(fm.horizontalAdvance(t) for t, _ in self._lines) + self._pad * 2
        h = fm.height() * len(self._lines) + self._gap * (len(self._lines) - 1) + self._pad * 2
        self.resize(int(w), int(h))
        if anchor is not None:
            cx, ey = anchor
            x = int(cx - w / 2)
            y = int(ey - h) if above else int(ey)
            self.move(max(0, x), max(0, y))
        self.update()
        if not self.isVisible():
            self.show()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 10, 10)
        p.fillPath(path, QColor(8, 12, 18, 170))
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        p.drawPath(path)

        f = self._font()
        p.setFont(f)
        fm = QFontMetrics(f)
        y = self._pad
        for text, color in self._lines:
            p.setPen(QColor(0, 14, 20, 200))           # soft shadow
            p.drawText(self._pad + 1, y + fm.ascent() + 1, text)
            p.setPen(QColor(color))                    # colored text
            p.drawText(self._pad, y + fm.ascent(), text)
            y += fm.height() + self._gap
        p.end()
