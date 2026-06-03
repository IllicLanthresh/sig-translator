"""Control-panel window: on/off switch, scan FPS, calibrate button, hotkey, style.

This is the app's main window. It owns the single Tk root; the floating Overlay and
the calibrate picker are Toplevels of it. The capture/OCR worker runs on a background
thread and pushes label updates to the overlay.

Closing this window quits the app.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .config import Config
from .overlay import Overlay, calibrate_region


class ControlPanel:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._last_status = "starting…"

        self.root = tk.Tk()
        self.root.title("sig-translator")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.overlay = Overlay(self.root, config)
        self._build_widgets()
        self._register_hotkey()
        self._start_worker()
        self._poll_status()

    # ---------------------------------------------------------------- widgets
    def _build_widgets(self) -> None:
        pad = {"padx": 10, "pady": 6}
        frm = ttk.Frame(self.root, padding=12)
        frm.grid(sticky="nsew")

        row = 0
        ttk.Label(frm, text="sig-translator", font=("", 14, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad
        )

        # On/off switch
        row += 1
        self.enabled_var = tk.BooleanVar(value=self.config.enabled)
        sw = ttk.Checkbutton(
            frm,
            text="Overlay ON",
            variable=self.enabled_var,
            command=self._on_toggle,
        )
        sw.grid(row=row, column=0, columnspan=2, sticky="w", **pad)

        # Scan FPS
        row += 1
        ttk.Label(frm, text="Scan FPS").grid(row=row, column=0, sticky="w", **pad)
        self.fps_var = tk.DoubleVar(value=self.config.scan_fps)
        fps_box = ttk.Frame(frm)
        fps_box.grid(row=row, column=1, sticky="ew", **pad)
        self.fps_label = ttk.Label(fps_box, text=f"{self.config.scan_fps:.1f}", width=4)
        self.fps_label.pack(side="right")
        ttk.Scale(
            fps_box, from_=0.5, to=10.0, variable=self.fps_var,
            command=self._on_fps, orient="horizontal", length=140,
        ).pack(side="left", fill="x", expand=True)

        # Calibrate
        row += 1
        ttk.Button(frm, text="Calibrate box…", command=self._on_calibrate).grid(
            row=row, column=0, sticky="w", **pad
        )
        self.region_label = ttk.Label(frm, text=self._region_text())
        self.region_label.grid(row=row, column=1, sticky="w", **pad)

        # Hotkey
        row += 1
        ttk.Label(frm, text="Toggle hotkey").grid(row=row, column=0, sticky="w", **pad)
        self.hotkey_var = tk.StringVar(value=self.config.hotkey)
        hk = ttk.Entry(frm, textvariable=self.hotkey_var, width=16)
        hk.grid(row=row, column=1, sticky="w", **pad)
        hk.bind("<Return>", lambda _e: self._on_hotkey_change())
        hk.bind("<FocusOut>", lambda _e: self._on_hotkey_change())

        # Font size
        row += 1
        ttk.Label(frm, text="Label size").grid(row=row, column=0, sticky="w", **pad)
        self.font_var = tk.IntVar(value=self.config.font_size)
        ttk.Spinbox(
            frm, from_=8, to=48, textvariable=self.font_var, width=5,
            command=self._on_style,
        ).grid(row=row, column=1, sticky="w", **pad)

        # Status line
        row += 1
        self.status_var = tk.StringVar(value="starting…")
        ttk.Separator(frm, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        row += 1
        ttk.Label(frm, textvariable=self.status_var, foreground="#0a7").grid(
            row=row, column=0, columnspan=2, sticky="w", **pad
        )

    def _region_text(self) -> str:
        r = self.config.region
        return f"{r.width}×{r.height} @ ({r.x},{r.y})"

    # ----------------------------------------------------------------- events
    def _on_toggle(self) -> None:
        self.config.enabled = bool(self.enabled_var.get())
        self.config.save()
        if not self.config.enabled:
            self.overlay.update_async(None)

    def _on_fps(self, _value: str) -> None:
        self.config.scan_fps = round(float(self.fps_var.get()), 1)
        self.fps_label.configure(text=f"{self.config.scan_fps:.1f}")
        self.config.save()

    def _on_calibrate(self) -> None:
        self.root.withdraw()
        try:
            calibrate_region(self.root, self.config)
        finally:
            self.root.deiconify()
        self.region_label.configure(text=self._region_text())

    def _on_hotkey_change(self) -> None:
        new = self.hotkey_var.get().strip()
        if new and new != self.config.hotkey:
            self.config.hotkey = new
            self.config.save()
            self._register_hotkey()

    def _on_style(self) -> None:
        self.config.font_size = int(self.font_var.get())
        self.config.save()
        self.overlay.restyle()

    # ----------------------------------------------------------------- hotkey
    def _register_hotkey(self) -> None:
        try:
            import keyboard
        except Exception as exc:
            self._last_status = f"hotkey unavailable ({exc})"
            return
        try:
            keyboard.clear_all_hotkeys()
        except Exception:
            pass
        try:
            keyboard.add_hotkey(self.config.hotkey, self._hotkey_toggle)
        except Exception as exc:
            self._last_status = f"bad hotkey: {exc}"

    def _hotkey_toggle(self) -> None:
        # Called from the keyboard library's thread; bounce to the Tk thread.
        self.root.after(0, self._do_hotkey_toggle)

    def _do_hotkey_toggle(self) -> None:
        self.config.enabled = not self.config.enabled
        self.enabled_var.set(self.config.enabled)
        self.config.save()
        if not self.config.enabled:
            self.overlay.update_async(None)

    # ----------------------------------------------------------------- worker
    def _start_worker(self) -> None:
        self._worker = threading.Thread(target=self._run_loop, daemon=True)
        self._worker.start()

    def _run_loop(self) -> None:
        import time

        try:
            from .capture import Capture
            from .ocr import DigitOCR
            from .translate import translate
        except Exception as exc:
            self._last_status = f"capture/OCR import failed: {exc}"
            return

        try:
            capture = Capture()
            ocr = DigitOCR()
        except Exception as exc:
            self._last_status = f"init failed: {exc}"
            return
        self._last_status = "ready"

        while not self.stop_event.is_set():
            start = time.time()
            if self.config.enabled:
                try:
                    img = capture.grab(self.config.region)
                    number = ocr.read_number(img)
                    match = translate(number) if number else None
                    if match and match.confidence >= self.config.min_confidence:
                        self.overlay.update_async(match.label)
                        self._last_status = f"{number} → {match.label}"
                    else:
                        self.overlay.update_async(None)
                        self._last_status = f"{number or '—'} (no match)"
                except Exception as exc:
                    self._last_status = f"loop error: {exc}"
                    self.overlay.update_async(None)
            else:
                self._last_status = "overlay off"
            period = 1.0 / max(0.5, self.config.scan_fps)
            time.sleep(max(0.0, period - (time.time() - start)))

        capture.close()

    def _poll_status(self) -> None:
        self.status_var.set(self._last_status)
        self.root.after(250, self._poll_status)

    # ------------------------------------------------------------------ close
    def _on_close(self) -> None:
        self.stop_event.set()
        try:
            import keyboard

            keyboard.clear_all_hotkeys()
        except Exception:
            pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
