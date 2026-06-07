"""The floating in-game label and the drag-to-calibrate picker.

The label is a borderless Toplevel pinned top-most over the game. On Windows we add
the layered + transparent extended styles so clicks pass straight through -- the
overlay is a separate top-most window and never hooks the game's renderer, which is
the EAC-safe approach.

Both the label and the calibrate picker are Toplevels of a shared Tk root (owned by
the control-panel GUI), so the whole app is a single Tk application.
"""

from __future__ import annotations

import sys
import tkinter as tk

from .config import Config, Region
from .materials import RARITY_TIERS, TIER_COLORS

# Color treated as fully transparent by the window (must not appear in the text).
_TRANSPARENT_KEY = "#010203"


def _make_click_through(win: tk.Toplevel) -> None:
    """Apply Windows layered + transparent + tool-window styles (no-op elsewhere)."""
    if sys.platform != "win32":
        return
    try:
        import win32con
        import win32gui

        hwnd = win32gui.GetParent(win.winfo_id()) or win.winfo_id()
        styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        styles |= (
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_TOOLWINDOW
            | win32con.WS_EX_NOACTIVATE
        )
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)
    except Exception as exc:  # pragma: no cover - Windows-only path
        print(f"[overlay] click-through not applied: {exc}")


class Overlay:
    """Floating, SC-styled readout positioned just below the capture region.

    Drawn on a transparent canvas as outlined ("glowing") text -- one colored line
    per material match (name ×count, colored by rarity) plus a small cyan line echoing
    the scanned signature for cross-checking. The dark outline keeps it legible over
    both bright rock and dark space, blending with Star Citizen's HUD.
    """

    _SHADOW = "#001218"   # dark halo behind the text

    def __init__(self, master: tk.Misc, config: Config) -> None:
        self.config = config
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", _TRANSPARENT_KEY)
        except tk.TclError:
            pass  # non-Windows: transparentcolor unsupported, still usable for dev
        self.win.configure(bg=_TRANSPARENT_KEY)
        self.canvas = tk.Canvas(self.win, bg=_TRANSPARENT_KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self._fonts: list = []  # keep Font refs alive while drawn
        self.win.withdraw()
        self.win.update_idletasks()
        _make_click_through(self.win)

    def restyle(self) -> None:
        # Redrawn every scan, so font/size/color changes take effect on the next read.
        pass

    def _outlined(self, cx: int, y: int, text: str, color: str, font) -> None:
        c = self.canvas
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    c.create_text(cx + dx, y + dy, text=text, fill=self._SHADOW,
                                  font=font, anchor="n")
        c.create_text(cx, y, text=text, fill=color, font=font, anchor="n")

    def show_matches(self, matches, scanned: int, sig_only: bool = False) -> None:
        import tkinter.font as tkfont

        fam = self.config.font_family
        base = self.config.font_size
        # Recognized-signature readback first (top), bracketed so it clearly reads as
        # "this is the number I recognized — compare it to the game", in the accent color.
        lines: list[tuple[str, str, int]] = [
            (f"[ {scanned:,} ]", self.config.accent_color, base)
        ]
        if not sig_only:
            for m in matches:
                tier = m.material.tier
                suffix = f"  ({tier})" if (self.config.show_rarity and tier in RARITY_TIERS) else ""
                lines.append((f"{m.material.name} ×{m.count}{suffix}",
                              TIER_COLORS.get(tier, "#ffffff"), base))

        self._fonts = [tkfont.Font(family=fam, size=s, weight="bold") for (_, _, s) in lines]
        widths = [f.measure(t) for (t, _, _), f in zip(lines, self._fonts)]
        heights = [f.metrics("linespace") for f in self._fonts]
        pad = 6
        total_w = max(widths) + pad * 2 + 4
        total_h = sum(heights) + pad * 2 + (len(lines) - 1) * 2

        c = self.canvas
        c.delete("all")
        c.configure(width=total_w, height=total_h)
        cx = total_w // 2
        y = pad
        for (text, color, _), f, h in zip(lines, self._fonts, heights):
            self._outlined(cx, y, text, color, f)
            y += h + 2

        r = self.config.region
        x = r.x + r.width // 2
        wy = r.y + r.height + 4
        self.win.deiconify()
        self.win.update_idletasks()
        self.win.geometry(f"{total_w}x{total_h}+{max(0, x - total_w // 2)}+{wy}")
        self.win.lift()

    def hide(self) -> None:
        self.win.withdraw()

    def update_async(self, matches, scanned: int = 0, sig_only: bool = False) -> None:
        """Thread-safe: schedule a label update on the Tk thread.

        Shows the readout when there are matches, or when ``sig_only`` is set and a
        signature was read (scanned a material whose name display is disabled).
        """
        matches = matches or []
        if matches or (sig_only and scanned):
            self.win.after(0, lambda: self.show_matches(matches, scanned, sig_only))
        else:
            self.win.after(0, self.hide)


class MiningOverlay:
    """Floating breakability readout, anchored just ABOVE the rock-panel capture box.

    Rendered like the signature overlay (transparent, click-through, outlined text),
    but fed pre-formatted (text, color) lines by the worker so it stays dumb.
    """

    _SHADOW = "#001218"

    def __init__(self, master: tk.Misc, config: Config) -> None:
        self.config = config
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", _TRANSPARENT_KEY)
        except tk.TclError:
            pass
        self.win.configure(bg=_TRANSPARENT_KEY)
        self.canvas = tk.Canvas(self.win, bg=_TRANSPARENT_KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self._fonts: list = []
        self.win.withdraw()
        self.win.update_idletasks()
        _make_click_through(self.win)

    def _outlined(self, cx, y, text, color, font) -> None:
        c = self.canvas
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    c.create_text(cx + dx, y + dy, text=text, fill=self._SHADOW,
                                  font=font, anchor="n")
        c.create_text(cx, y, text=text, fill=color, font=font, anchor="n")

    def show_lines(self, lines: list[tuple[str, str]]) -> None:
        import tkinter.font as tkfont

        fam = self.config.font_family
        base = max(11, self.config.font_size - 2)
        self._fonts = [tkfont.Font(family=fam, size=base, weight="bold") for _ in lines]
        widths = [f.measure(t) for (t, _), f in zip(lines, self._fonts)]
        heights = [f.metrics("linespace") for f in self._fonts]
        pad = 6
        total_w = (max(widths) if widths else 10) + pad * 2 + 4
        total_h = sum(heights) + pad * 2 + (len(lines) - 1) * 2

        c = self.canvas
        c.delete("all")
        c.configure(width=total_w, height=total_h)
        cx = total_w // 2
        y = pad
        for (text, color), f, h in zip(lines, self._fonts, heights):
            self._outlined(cx, y, text, color, f)
            y += h + 2

        r = self.config.rock_region
        x = r.x + r.width // 2
        wy = r.y - total_h - 4  # ABOVE the rock box
        self.win.deiconify()
        self.win.update_idletasks()
        self.win.geometry(f"{total_w}x{total_h}+{max(0, x - total_w // 2)}+{max(0, wy)}")
        self.win.lift()

    def hide(self) -> None:
        self.win.withdraw()

    def update_async(self, lines) -> None:
        """Thread-safe: schedule a redraw (or hide if lines is falsy)."""
        if lines:
            self.win.after(0, lambda: self.show_lines(lines))
        else:
            self.win.after(0, self.hide)


# Resize-handle layout: handle name -> which box sides it moves.
_HANDLE_SIDES = {
    "nw": ("l", "t"), "n": ("t",), "ne": ("r", "t"),
    "w": ("l",), "e": ("r",),
    "sw": ("l", "b"), "s": ("b",), "se": ("r", "b"),
}
_HANDLE_CURSORS = {
    "nw": "sizing", "ne": "sizing", "sw": "sizing", "se": "sizing",
    "n": "sb_v_double_arrow", "s": "sb_v_double_arrow",
    "w": "sb_h_double_arrow", "e": "sb_h_double_arrow",
}
_MIN_SIZE = 24
_HANDLE_HIT = 11  # px tolerance for grabbing a handle


class _Calibrator:
    """Fullscreen movable/resizable selection box for choosing the capture region."""

    def __init__(self, master: tk.Misc, config: Config, initial: Region | None = None) -> None:
        self.config = config
        self.result: Region | None = None
        initial = initial if initial is not None else config.region

        self.top = tk.Toplevel(master)
        self.top.attributes("-topmost", True)
        try:
            self.top.attributes("-alpha", 0.4)  # dim the scene so the box stands out
        except tk.TclError:
            pass
        self.top.configure(bg="#0a0a0a")

        # Span the WHOLE virtual desktop (all monitors), in the same coordinate space
        # mss captures in. This is what fixes the multi-monitor cursor jump: the grab
        # now covers every screen, and the saved region maps 1:1 onto capture.
        self.ox, self.oy = 0, 0
        self.ui_cx = None  # primary-monitor center, for placing instructions
        self.ui_top = 0
        try:
            import mss

            with mss.mss() as sct:
                mons = sct.monitors
            vd = mons[0]  # union bounding box of all monitors
            primary = mons[1] if len(mons) > 1 else mons[0]
            self.ox, self.oy = int(vd["left"]), int(vd["top"])
            self.sw, self.sh = int(vd["width"]), int(vd["height"])
            self.ui_cx = int(primary["left"]) - self.ox + int(primary["width"]) // 2
            self.ui_top = int(primary["top"]) - self.oy
        except Exception:
            self.sw = self.top.winfo_screenwidth()
            self.sh = self.top.winfo_screenheight()
        if self.ui_cx is None:
            self.ui_cx = self.sw // 2
        self.top.overrideredirect(True)
        self.top.geometry(f"{self.sw}x{self.sh}+{self.ox}+{self.oy}")

        self.canvas = tk.Canvas(self.top, highlightthickness=0, bg="#0a0a0a")
        self.canvas.pack(fill="both", expand=True)

        # Start from the current region (converted to window-local coords), or a
        # sensible default centered on the desktop if never calibrated.
        r = initial
        if r.width < _MIN_SIZE or r.height < _MIN_SIZE or (r.x == 0 and r.y == 0):
            w, h = 420, 90
            cx = (self.sw - w) // 2
            cy = self.sh // 4
            self.box = {"l": cx, "t": cy, "r": cx + w, "b": cy + h}
        else:
            lx, ty = r.x - self.ox, r.y - self.oy
            self.box = {"l": lx, "t": ty, "r": lx + r.width, "b": ty + r.height}

        self._drag = None
        self._buttons: dict[str, tuple[int, int, int, int]] = {}

        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", lambda _e: self._accept())
        self.top.bind("<Escape>", lambda _e: self._cancel())
        self.top.bind("<Return>", lambda _e: self._accept())
        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            self.top.bind(f"<{key}>", lambda _e, dx=dx, dy=dy: self._nudge(dx, dy))
            self.top.bind(f"<Shift-{key}>", lambda _e, dx=dx, dy=dy: self._nudge(dx * 10, dy * 10))

        self.top.grab_set()
        self.top.focus_force()
        self._draw()

    def _handle_points(self) -> dict[str, tuple[int, int]]:
        b = self.box
        cx, cy = (b["l"] + b["r"]) // 2, (b["t"] + b["b"]) // 2
        return {
            "nw": (b["l"], b["t"]), "n": (cx, b["t"]), "ne": (b["r"], b["t"]),
            "w": (b["l"], cy), "e": (b["r"], cy),
            "sw": (b["l"], b["b"]), "s": (cx, b["b"]), "se": (b["r"], b["b"]),
        }

    def _hit_handle(self, x, y) -> str | None:
        for name, (hx, hy) in self._handle_points().items():
            if abs(x - hx) <= _HANDLE_HIT and abs(y - hy) <= _HANDLE_HIT:
                return name
        return None

    def _inside(self, x, y) -> bool:
        b = self.box
        return b["l"] <= x <= b["r"] and b["t"] <= y <= b["b"]

    def _draw(self) -> None:
        c = self.canvas
        c.delete("all")
        b = self.box
        # Faint green wash so the capture area reads clearly.
        c.create_rectangle(b["l"], b["t"], b["r"], b["b"], fill="#00ff88", stipple="gray12", outline="")
        # Double outline (dark backing + bright line) for contrast on any scene.
        c.create_rectangle(b["l"], b["t"], b["r"], b["b"], outline="#003322", width=5)
        c.create_rectangle(b["l"], b["t"], b["r"], b["b"], outline="#00ff88", width=2)
        for hx, hy in self._handle_points().values():
            c.create_rectangle(hx - 6, hy - 6, hx + 6, hy + 6, fill="white", outline="#003322")
        # Control strip anchored to the box, so it's always where you're working.
        w, h = b["r"] - b["l"], b["b"] - b["t"]
        bcx = max(170, min(self.sw - 170, (b["l"] + b["r"]) // 2))
        below = b["b"] + 56 <= self.sh
        sy = (b["b"] + 16) if below else (b["t"] - 52)
        c.create_text(bcx, sy, fill="#00ff88", font=("Consolas", 12, "bold"),
                      text=f"{w} × {h}")
        c.create_text(bcx, sy + 18, fill="#e8e8e8", font=("Consolas", 10),
                      text="drag = move  •  handles = resize  •  arrows = nudge  "
                           "•  double-click / Enter = SAVE  •  Esc = cancel")
        self._buttons.clear()
        self._draw_button("save", bcx - 124, sy + 30, "   ✓  Save   ", "#1f9d55")
        self._draw_button("cancel", bcx + 22, sy + 30, "   ✗  Cancel   ", "#aa3333")

    def _draw_button(self, name, x, y, label, color) -> None:
        t = self.canvas.create_text(x, y, anchor="nw", fill="white",
                                     font=("Consolas", 12, "bold"), text=label)
        x0, y0, x1, y1 = self.canvas.bbox(t)
        pad = 6
        x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
        rect = self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="white")
        self.canvas.tag_lower(rect, t)
        self._buttons[name] = (x0, y0, x1, y1)

    def _hit_button(self, x, y) -> str | None:
        for name, (x0, y0, x1, y1) in self._buttons.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return name
        return None

    def _on_motion(self, e) -> None:
        if self._hit_button(e.x, e.y):
            self.canvas.configure(cursor="hand2")
            return
        h = self._hit_handle(e.x, e.y)
        if h:
            self.canvas.configure(cursor=_HANDLE_CURSORS[h])
        elif self._inside(e.x, e.y):
            self.canvas.configure(cursor="fleur")
        else:
            self.canvas.configure(cursor="arrow")

    def _on_press(self, e) -> None:
        btn = self._hit_button(e.x, e.y)
        if btn == "save":
            self._accept()
            return
        if btn == "cancel":
            self._cancel()
            return
        h = self._hit_handle(e.x, e.y)
        if h:
            self._drag = ("resize", h)
        elif self._inside(e.x, e.y):
            self._drag = ("move", (e.x - self.box["l"], e.y - self.box["t"]))
        else:
            self._drag = None

    def _on_drag(self, e) -> None:
        if not self._drag:
            return
        kind, data = self._drag
        b = self.box
        if kind == "move":
            offx, offy = data
            w, h = b["r"] - b["l"], b["b"] - b["t"]
            b["l"] = max(0, min(self.sw - w, e.x - offx))
            b["t"] = max(0, min(self.sh - h, e.y - offy))
            b["r"], b["b"] = b["l"] + w, b["t"] + h
        else:  # resize
            for side in _HANDLE_SIDES[data]:
                if side == "l":
                    b["l"] = max(0, min(e.x, b["r"] - _MIN_SIZE))
                elif side == "r":
                    b["r"] = min(self.sw, max(e.x, b["l"] + _MIN_SIZE))
                elif side == "t":
                    b["t"] = max(0, min(e.y, b["b"] - _MIN_SIZE))
                elif side == "b":
                    b["b"] = min(self.sh, max(e.y, b["t"] + _MIN_SIZE))
        self._draw()

    def _on_release(self, _e) -> None:
        self._drag = None

    def _nudge(self, dx, dy) -> None:
        b = self.box
        w, h = b["r"] - b["l"], b["b"] - b["t"]
        b["l"] = max(0, min(self.sw - w, b["l"] + dx))
        b["t"] = max(0, min(self.sh - h, b["t"] + dy))
        b["r"], b["b"] = b["l"] + w, b["t"] + h
        self._draw()

    def _accept(self) -> None:
        b = self.box
        # Convert window-local coords back to virtual-desktop coords for capture.
        self.result = Region(
            x=b["l"] + self.ox, y=b["t"] + self.oy,
            width=b["r"] - b["l"], height=b["b"] - b["t"],
        )
        self.top.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.top.destroy()


def calibrate_region(
    master: tk.Misc, config: Config, attr: str = "region",
    calibrated_attr: str = "calibrated",
) -> Region:
    """Show a movable/resizable selection box; save the chosen region to config.

    `attr` chooses which config region to edit ("region" for the signature box,
    "rock_region" for the mining scan panel).
    """
    cal = _Calibrator(master, config, getattr(config, attr))
    master.wait_window(cal.top)
    if cal.result and cal.result.width >= _MIN_SIZE and cal.result.height >= _MIN_SIZE:
        setattr(config, attr, cal.result)
        setattr(config, calibrated_attr, True)
        config.save()
        print(f"[calibrate] saved {attr}: {getattr(config, attr)}")
    else:
        print("[calibrate] cancelled; region unchanged")
    return getattr(config, attr)
