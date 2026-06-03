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

from . import __version__
from .config import Config
from .overlay import Overlay, calibrate_region


class ControlPanel:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._last_status = "starting…"

        self.root = tk.Tk()
        self.root.title(f"sig-translator v{__version__}")
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

        # On/off button (big, color-coded; mirrors the global hotkey)
        row += 1
        self.toggle_btn = tk.Button(
            frm,
            text="",
            width=28,
            font=("", 11, "bold"),
            cursor="hand2",
            command=self._toggle_capture,
        )
        self.toggle_btn.grid(row=row, column=0, columnspan=2, sticky="ew", **pad)
        self._refresh_toggle()

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

        # OCR mode: recognition-only (fast) vs full detect+recognize (slower)
        row += 1
        self.detect_var = tk.BooleanVar(value=self.config.ocr_detect)
        ttk.Checkbutton(
            frm,
            text="Accurate OCR (slower) — try if it misreads",
            variable=self.detect_var,
            command=self._on_detect,
        ).grid(row=row, column=0, columnspan=2, sticky="w", **pad)

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
    def _refresh_toggle(self) -> None:
        """Sync the toggle button's look to the current enabled state."""
        on = self.config.enabled
        self.toggle_btn.configure(
            text=("●  Capturing  —  click to PAUSE" if on else "○  Paused  —  click to START"),
            bg=("#1f9d55" if on else "#555555"),
            fg="white",
            activebackground=("#188048" if on else "#666666"),
            activeforeground="white",
        )

    def _toggle_capture(self) -> None:
        self.config.enabled = not self.config.enabled
        self.config.save()
        if not self.config.enabled:
            self.overlay.update_async(None)
        self._refresh_toggle()

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

    def _on_detect(self) -> None:
        self.config.ocr_detect = bool(self.detect_var.get())
        self.config.save()

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
        self.config.save()
        if not self.config.enabled:
            self.overlay.update_async(None)
        self._refresh_toggle()

    # ----------------------------------------------------------------- worker
    def _start_worker(self) -> None:
        self._worker = threading.Thread(target=self._run_loop, daemon=True)
        self._worker.start()

    @staticmethod
    def _frame_fingerprint(img):
        """Cheap downsampled-grayscale fingerprint for change detection."""
        import numpy as np

        small = img[::8, ::8]
        return small.mean(axis=2) if small.ndim == 3 else small.astype("float32")

    def _run_loop(self) -> None:
        import time

        import numpy as np

        try:
            from .capture import Capture
            from .ocr import DigitOCR
            from .translate import translate
        except Exception as exc:
            self._last_status = f"capture/OCR import failed: {exc}"
            return

        try:
            capture = Capture()
            ocr = DigitOCR(threads=self.config.ocr_threads)
        except Exception as exc:
            self._last_status = f"init failed: {exc}"
            return
        self._last_status = "ready"

        last_fp = None  # fingerprint of the last frame we actually OCR'd
        was_enabled = self.config.enabled
        was_detect = self.config.ocr_detect

        while not self.stop_event.is_set():
            start = time.time()
            if self.config.enabled:
                try:
                    # Force a fresh read after re-enabling or flipping OCR mode.
                    if not was_enabled or self.config.ocr_detect != was_detect:
                        last_fp = None
                    t0 = time.time()
                    img = capture.grab(self.config.region)
                    cap_ms = (time.time() - t0) * 1000

                    # Skip OCR entirely when the box hasn't changed (no new signature).
                    fp = self._frame_fingerprint(img)
                    if (
                        self.config.skip_unchanged
                        and last_fp is not None
                        and last_fp.shape == fp.shape
                        and float(np.abs(fp - last_fp).mean()) < 2.0
                    ):
                        self._last_status = f"idle (cap {cap_ms:.0f}ms, ocr skipped)"
                    else:
                        last_fp = fp
                        t1 = time.time()
                        number = ocr.read_number(
                            img,
                            detect=self.config.ocr_detect,
                            upscale=self.config.ocr_upscale,
                        )
                        ocr_ms = (time.time() - t1) * 1000
                        match = translate(number) if number else None
                        if match and match.confidence >= self.config.min_confidence:
                            self.overlay.update_async(match.label)
                            self._last_status = (
                                f"{number} → {match.label}  "
                                f"(cap {cap_ms:.0f}ms, ocr {ocr_ms:.0f}ms)"
                            )
                        else:
                            self.overlay.update_async(None)
                            self._last_status = (
                                f"{number or '—'} (no match)  "
                                f"(cap {cap_ms:.0f}ms, ocr {ocr_ms:.0f}ms)"
                            )
                except Exception as exc:
                    self._last_status = f"loop error: {exc}"
                    self.overlay.update_async(None)
            else:
                self._last_status = "overlay off"
            was_enabled = self.config.enabled
            was_detect = self.config.ocr_detect

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
