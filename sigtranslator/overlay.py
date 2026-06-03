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
    """A single floating label positioned just below the capture region."""

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

        self._text = tk.StringVar(value="")
        self._label = tk.Label(
            self.win,
            textvariable=self._text,
            fg=config.text_color,
            bg=_TRANSPARENT_KEY,
            font=("Consolas", config.font_size, "bold"),
        )
        self._label.pack()
        self.win.withdraw()
        self.win.update_idletasks()
        _make_click_through(self.win)

    def restyle(self) -> None:
        self._label.configure(
            fg=self.config.text_color,
            font=("Consolas", self.config.font_size, "bold"),
        )

    def _position(self) -> tuple[int, int]:
        r = self.config.region
        return r.x + r.width // 2, r.y + r.height + 4

    def show(self, text: str) -> None:
        self._text.set(text)
        x, y = self._position()
        self.win.deiconify()
        self.win.update_idletasks()
        w = self.win.winfo_width()
        self.win.geometry(f"+{max(0, x - w // 2)}+{y}")
        self.win.lift()

    def hide(self) -> None:
        self.win.withdraw()

    def update_async(self, text: str | None) -> None:
        """Thread-safe: schedule a label update on the Tk thread."""
        if text:
            self.win.after(0, lambda: self.show(text))
        else:
            self.win.after(0, self.hide)


def calibrate_region(master: tk.Misc, config: Config) -> Region:
    """Fullscreen drag-to-select. Saves the chosen region to config and returns it."""
    top = tk.Toplevel(master)
    top.attributes("-fullscreen", True)
    top.attributes("-topmost", True)
    try:
        top.attributes("-alpha", 0.3)
    except tk.TclError:
        pass
    top.configure(bg="black", cursor="cross")

    canvas = tk.Canvas(top, highlightthickness=0, bg="black")
    canvas.pack(fill="both", expand=True)
    canvas.create_text(
        top.winfo_screenwidth() // 2,
        40,
        fill="#00ff88",
        font=("Consolas", 16, "bold"),
        text="Drag a box over the in-game SIGNATURE number, then release.  Esc to cancel.",
    )

    state: dict = {"x0": 0, "y0": 0, "rect": None, "result": None}

    def on_press(e):
        state["x0"], state["y0"] = e.x, e.y
        state["rect"] = canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="#00ff88", width=2)

    def on_drag(e):
        if state["rect"] is not None:
            canvas.coords(state["rect"], state["x0"], state["y0"], e.x, e.y)

    def on_release(e):
        x0, y0, x1, y1 = state["x0"], state["y0"], e.x, e.y
        state["result"] = Region(
            x=min(x0, x1), y=min(y0, y1), width=abs(x1 - x0), height=abs(y1 - y0)
        )
        top.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    top.bind("<Escape>", lambda _e: top.destroy())
    top.grab_set()
    master.wait_window(top)

    res = state["result"]
    if res and res.width > 10 and res.height > 10:
        config.region = res
        config.save()
        print(f"[calibrate] saved region: {config.region}")
    else:
        print("[calibrate] cancelled; region unchanged")
    return config.region
