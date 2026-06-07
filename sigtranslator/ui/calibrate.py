"""Unified calibration: one fullscreen screen to place all capture boxes at once.

Spans the whole virtual desktop (multi-monitor safe). Each named box can be dragged
(move) or resized via 8 handles; arrow keys nudge the active box. Saves every box to
its config region in one pass. Coordinates are kept window-local and converted to
global (the mss/Qt virtual-desktop space) on save.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from ..config import Region

HANDLE = 8
MIN = 24
_SIDES = {
    "nw": ("l", "t"), "n": ("t",), "ne": ("r", "t"),
    "w": ("l",), "e": ("r",),
    "sw": ("l", "b"), "s": ("b",), "se": ("r", "b"),
}


class Calibrator(QWidget):
    def __init__(self, config, regions) -> None:
        """regions: list of (config_attr, calibrated_attr, label, '#color')."""
        super().__init__(None)
        self.config = config
        self.saved = False

        vg = QGuiApplication.primaryScreen().virtualGeometry()
        self.ox, self.oy = vg.x(), vg.y()
        self.setGeometry(vg)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # let the dim layer reveal the game
        self.setMouseTracking(True)

        self.boxes = []
        for attr, cal_attr, label, color in regions:
            r = getattr(config, attr)
            if r.width < MIN or r.height < MIN or (r.x == 0 and r.y == 0):
                w, h = 360, 90
                rect = QRect((vg.width() - w) // 2, vg.height() // 4, w, h)
            else:
                rect = QRect(r.x - self.ox, r.y - self.oy, r.width, r.height)
            self.boxes.append({"attr": attr, "cal": cal_attr, "label": label,
                               "color": color, "rect": rect})
        self.active = 0
        self._drag = None  # (mode, handle|offset)

        self.save_btn = QPushButton("Save  (Enter)", self)
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn = QPushButton("Cancel  (Esc)", self)
        self.cancel_btn.clicked.connect(self._cancel)
        cx = vg.width() // 2
        self.save_btn.setGeometry(cx - 150, 28, 140, 36)
        self.cancel_btn.setGeometry(cx + 10, 28, 140, 36)

    # ---- geometry helpers ----
    @staticmethod
    def _handle_points(r: QRect):
        cx, cy = r.center().x(), r.center().y()
        return {
            "nw": (r.left(), r.top()), "n": (cx, r.top()), "ne": (r.right(), r.top()),
            "w": (r.left(), cy), "e": (r.right(), cy),
            "sw": (r.left(), r.bottom()), "s": (cx, r.bottom()), "se": (r.right(), r.bottom()),
        }

    def _hit_handle(self, r: QRect, x, y):
        for name, (hx, hy) in self._handle_points(r).items():
            if abs(x - hx) <= HANDLE + 2 and abs(y - hy) <= HANDLE + 2:
                return name
        return None

    # ---- mouse ----
    def mousePressEvent(self, e):
        x, y = e.position().x(), e.position().y()
        for i, b in enumerate(self.boxes):
            r = b["rect"]
            h = self._hit_handle(r, x, y)
            if h:
                self.active = i
                self._drag = ("resize", h)
                return
            if r.contains(int(x), int(y)):
                self.active = i
                self._drag = ("move", (x - r.left(), y - r.top()))
                return
        self._drag = None

    def mouseMoveEvent(self, e):
        if not self._drag:
            return
        x, y = e.position().x(), e.position().y()
        r = self.boxes[self.active]["rect"]
        mode, data = self._drag
        if mode == "move":
            offx, offy = data
            r.moveTo(int(x - offx), int(y - offy))
        else:
            for side in _SIDES[data]:
                if side == "l":
                    r.setLeft(min(int(x), r.right() - MIN))
                elif side == "r":
                    r.setRight(max(int(x), r.left() + MIN))
                elif side == "t":
                    r.setTop(min(int(y), r.bottom() - MIN))
                elif side == "b":
                    r.setBottom(max(int(y), r.top() + MIN))
        self.update()

    def mouseReleaseEvent(self, _e):
        self._drag = None

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Return, Qt.Key_Enter):
            self._save()
        elif k == Qt.Key_Escape:
            self._cancel()
        elif k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = 10 if e.modifiers() & Qt.ShiftModifier else 1
            dx = (-step if k == Qt.Key_Left else step if k == Qt.Key_Right else 0)
            dy = (-step if k == Qt.Key_Up else step if k == Qt.Key_Down else 0)
            self.boxes[self.active]["rect"].translate(dx, dy)
            self.update()
        elif k == Qt.Key_Tab:
            self.active = (self.active + 1) % len(self.boxes)
            self.update()

    # ---- paint ----
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(8, 9, 12, 150))  # dim the scene
        for i, b in enumerate(self.boxes):
            r = b["rect"]
            col = QColor(b["color"])
            p.fillRect(r, QColor(col.red(), col.green(), col.blue(), 26))
            p.setPen(QPen(col, 2 if i == self.active else 1))
            p.drawRect(r)
            for hx, hy in self._handle_points(r).values():
                p.fillRect(hx - HANDLE // 2, hy - HANDLE // 2, HANDLE, HANDLE, QColor("#ffffff"))
            p.setFont(QFont("Bahnschrift", 11, QFont.Bold))
            p.setPen(col)
            ly = r.top() - 8 if r.top() > 24 else r.bottom() + 18
            p.drawText(r.left(), ly, f"{b['label']}   {r.width()}×{r.height()}")
        p.setFont(QFont("Bahnschrift", 12))
        p.setPen(QColor("#cfd3d6"))
        p.drawText(self.width() // 2 - 320, 86,
                   "drag = move · handles = resize · arrows = nudge (Shift ×10) · Tab = next box")
        p.end()

    # ---- commit ----
    def _save(self):
        for b in self.boxes:
            r = b["rect"].normalized()
            setattr(self.config, b["attr"],
                    Region(x=r.left() + self.ox, y=r.top() + self.oy,
                           width=r.width(), height=r.height()))
            setattr(self.config, b["cal"], True)
        self.config.save()
        self.saved = True
        self.close()

    def _cancel(self):
        self.close()


def calibrate(config, mining: bool = True) -> bool:
    """Open the unified calibrator modally-ish; returns True if saved."""
    from PySide6.QtCore import QEventLoop

    regions = [("region", "calibrated", "Signature", "#33dd66")]
    if mining:
        regions.append(("rock_region", "rock_calibrated", "Rock panel", "#7fdfff"))
    cal = Calibrator(config, regions)
    loop = QEventLoop()
    cal.destroyed.connect(loop.quit)
    cal.show()
    cal.activateWindow()
    cal.raise_()
    cal.setFocus()
    loop.exec()
    return cal.saved
