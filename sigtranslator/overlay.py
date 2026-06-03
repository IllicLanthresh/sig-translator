"""Transparent, top-most, click-through label drawn near the in-game number.

Implemented as a borderless Tkinter window. On Windows we add the layered +
transparent extended styles so mouse clicks pass straight through to the game --
the overlay is a separate top-most window and never hooks the game's renderer,
which is the EAC-safe approach.

Also hosts the one-time region calibration picker (``calibrate_region``).
"""

from __future__ import annotations

import sys
import tkinter as tk

from .config import Config, Region

# Color treated as fully transparent by the window (must not appear in the text).
_TRANSPARENT_KEY = "#010203"


def _make_click_through(root: tk.Tk) -> None:
    """Apply Windows layered + transparent + tool-window styles (no-op elsewhere)."""
    if sys.platform != "win32":
        return
    try:
        import win32con
        import win32gui

        hwnd = win32gui.GetParent(root.winfo_id()) or root.winfo_id()
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
    """A single floating label positioned just below the capture region."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", _TRANSPARENT_KEY)
        except tk.TclError:
            pass  # non-Windows: transparentcolor unsupported, still usable for dev
        self.root.configure(bg=_TRANSPARENT_KEY)

        self._text = tk.StringVar(value="")
        self._label = tk.Label(
            self.root,
            textvariable=self._text,
            fg=config.text_color,
            bg=_TRANSPARENT_KEY,
            font=("Consolas", config.font_size, "bold"),
        )
        self._label.pack()
        self.root.withdraw()
        self.root.update_idletasks()
        _make_click_through(self.root)

    def _position(self) -> tuple[int, int]:
        r = self.config.region
        x = r.x + r.width // 2
        y = r.y + r.height + 4
        return x, y

    def show(self, text: str) -> None:
        self._text.set(text)
        x, y = self._position()
        self.root.deiconify()
        self.root.update_idletasks()
        w = self.root.winfo_width()
        self.root.geometry(f"+{max(0, x - w // 2)}+{y}")
        self.root.lift()

    def hide(self) -> None:
        self.root.withdraw()

    # The capture/OCR thread pushes updates here; Tk only touches widgets on its
    # own thread, so we schedule via after().
    def update_async(self, text: str | None) -> None:
        if text:
            self.root.after(0, lambda: self.show(text))
        else:
            self.root.after(0, self.hide)

    def run(self) -> None:
        self.root.mainloop()

    def stop(self) -> None:
        try:
            self.root.after(0, self.root.quit)
        except Exception:
            pass


def calibrate_region(config: Config) -> Region:
    """Fullscreen drag-to-select. Returns the chosen region and saves it to config."""
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.3)
    except tk.TclError:
        pass
    root.configure(bg="black", cursor="cross")

    canvas = tk.Canvas(root, highlightthickness=0, bg="black")
    canvas.pack(fill="both", expand=True)
    canvas.create_text(
        root.winfo_screenwidth() // 2,
        40,
        fill="#00ff88",
        font=("Consolas", 16, "bold"),
        text="Drag a box over the in-game SIGNATURE number, then release.  Esc to cancel.",
    )

    state = {"x0": 0, "y0": 0, "rect": None, "result": None}

    def on_press(e):
        state["x0"], state["y0"] = e.x, e.y
        state["rect"] = canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="#00ff88", width=2)

    def on_drag(e):
        if state["rect"] is not None:
            canvas.coords(state["rect"], state["x0"], state["y0"], e.x, e.y)

    def on_release(e):
        x0, y0 = state["x0"], state["y0"]
        x1, y1 = e.x, e.y
        state["result"] = Region(
            x=min(x0, x1), y=min(y0, y1), width=abs(x1 - x0), height=abs(y1 - y0)
        )
        root.destroy()

    def on_cancel(_e):
        root.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>", on_cancel)
    root.mainloop()

    if state["result"] and state["result"].width > 10 and state["result"].height > 10:
        config.region = state["result"]
        config.save()
        print(f"[calibrate] saved region: {config.region}")
        return config.region
    print("[calibrate] cancelled; region unchanged")
    return config.region
