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
from .overlay import MiningOverlay, Overlay, calibrate_region


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
        self.mining_overlay = MiningOverlay(self.root, config)
        self._build_widgets()
        self._register_hotkey()
        self._start_worker()
        self._poll_status()
        self._start_update_check()

    # ---------------------------------------------------------------- widgets
    def _build_widgets(self) -> None:
        pad = {"padx": 10, "pady": 6}
        frm = ttk.Frame(self.root, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        row = 0
        ttk.Label(frm, text="sig-translator", font=("", 14, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad
        )

        # Update notice — hidden unless a newer release is found; click to open Releases.
        row += 1
        self.update_var = tk.StringVar(value="")
        self.update_lbl = tk.Label(
            frm, textvariable=self.update_var, fg="#ffcc44",
            cursor="hand2", font=("", 10, "bold"),
        )
        self.update_lbl.grid(row=row, column=0, columnspan=2, sticky="w", **pad)
        self.update_lbl.grid_remove()
        self.update_lbl.bind("<Button-1>", lambda _e: self._open_releases())

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

        # Customize sigs: slide-out panel to show/hide individual materials
        row += 1
        self.customize_btn = ttk.Button(
            frm, text="Customize sigs  ▸", command=self._toggle_side
        )
        self.customize_btn.grid(row=row, column=0, columnspan=2, sticky="w", **pad)

        # Mining breakability (separate capability)
        row += 1
        self.mining_var = tk.BooleanVar(value=self.config.mining_enabled)
        ttk.Checkbutton(
            frm, text="Mining mode (rock breakability)", variable=self.mining_var,
            command=self._on_mining,
        ).grid(row=row, column=0, sticky="w", **pad)
        ttk.Button(frm, text="Mining setup…", command=self._open_mining_setup).grid(
            row=row, column=1, sticky="w", **pad
        )

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

        # Accent color (match your ship manufacturer's HUD tint)
        row += 1
        ttk.Label(frm, text="Accent color").grid(row=row, column=0, sticky="w", **pad)
        accent_box = ttk.Frame(frm)
        accent_box.grid(row=row, column=1, sticky="w", **pad)
        self.accent_swatch = tk.Label(accent_box, bg=self.config.accent_color,
                                      width=3, relief="sunken")
        self.accent_swatch.pack(side="left", padx=(0, 6))
        ttk.Button(accent_box, text="Pick…", command=self._on_accent).pack(side="left")

        # Show the rarity tier text after the name, e.g. "(Epic)"
        row += 1
        self.rarity_var = tk.BooleanVar(value=self.config.show_rarity)
        ttk.Checkbutton(
            frm,
            text="Show rarity in the label, e.g. (Epic)",
            variable=self.rarity_var,
            command=self._on_rarity,
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

        self._build_side()

    def _region_text(self) -> str:
        r = self.config.region
        return f"{r.width}×{r.height} @ ({r.x},{r.y})"

    # ------------------------------------------------------- customize sigs panel
    def _build_side(self) -> None:
        """Collapsible side panel: a per-material show/hide checklist by tier."""
        from .materials import MATERIALS, TIER_COLORS

        self._side_open = False
        self.side = ttk.Frame(self.root, padding=(0, 12, 12, 12))
        self.side.grid(row=0, column=1, sticky="nsew")

        ttk.Label(self.side, text="Show / hide materials", font=("", 11, "bold")).pack(
            anchor="w"
        )
        btns = ttk.Frame(self.side)
        btns.pack(anchor="w", pady=(2, 6))
        ttk.Button(btns, text="Show all", width=10, command=self._reset_materials).pack(
            side="left"
        )
        ttk.Button(btns, text="Show none", width=10, command=self._hide_all_materials).pack(
            side="left", padx=(6, 0)
        )

        canvas = tk.Canvas(self.side, width=250, height=430, highlightthickness=0)
        scroll = ttk.Scrollbar(self.side, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._side_canvas = canvas
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", self._side_wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        disabled = set(self.config.disabled_materials)
        self.mat_vars: dict[str, tk.BooleanVar] = {}
        groups: dict[str, list] = {}
        for m in MATERIALS:
            groups.setdefault(m.tier, []).append(m)
        for tier, mats in groups.items():
            header = ttk.Frame(inner)
            header.pack(fill="x", pady=(8, 2))
            ttk.Label(header, text=tier, font=("", 9, "bold")).pack(side="left")
            ttk.Button(header, text="none", width=5,
                       command=lambda t=tier: self._set_tier(t, False)).pack(side="right")
            ttk.Button(header, text="all", width=4,
                       command=lambda t=tier: self._set_tier(t, True)).pack(side="right", padx=4)
            for m in mats:
                rowf = ttk.Frame(inner)
                rowf.pack(fill="x", anchor="w")
                tk.Label(rowf, bg=TIER_COLORS.get(m.tier, "#888888"), width=2).pack(
                    side="left", padx=(2, 6)
                )
                var = tk.BooleanVar(value=m.name not in disabled)  # checked = shown
                self.mat_vars[m.name] = var
                ttk.Checkbutton(rowf, text=m.name, variable=var,
                                command=self._save_materials).pack(side="left")

        self.side.grid_remove()  # hidden until "Customize sigs" is clicked

    def _toggle_side(self) -> None:
        if self._side_open:
            self.side.grid_remove()
            self.customize_btn.configure(text="Customize sigs  ▸")
        else:
            self.side.grid()
            self.customize_btn.configure(text="Customize sigs  ◂")
        self._side_open = not self._side_open

    def _side_wheel(self, event) -> None:
        self._side_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _set_tier(self, tier: str, value: bool) -> None:
        from .materials import MATERIALS

        for m in MATERIALS:
            if m.tier == tier:
                self.mat_vars[m.name].set(value)
        self._save_materials()

    def _reset_materials(self) -> None:
        for var in self.mat_vars.values():
            var.set(True)
        self._save_materials()

    def _hide_all_materials(self) -> None:
        for var in self.mat_vars.values():
            var.set(False)
        self._save_materials()

    def _save_materials(self) -> None:
        self.config.disabled_materials = [
            name for name, v in self.mat_vars.items() if not v.get()
        ]
        self.config.save()

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

    def _on_rarity(self) -> None:
        self.config.show_rarity = bool(self.rarity_var.get())
        self.config.save()

    def _on_mining(self) -> None:
        self.config.mining_enabled = bool(self.mining_var.get())
        self.config.save()
        if not self.config.mining_enabled:
            self.mining_overlay.update_async(None)

    def _open_mining_setup(self) -> None:
        from .mining_window import MiningSetupWindow

        MiningSetupWindow(self.root, self.config)

    def _on_accent(self) -> None:
        from tkinter import colorchooser

        _rgb, hex_color = colorchooser.askcolor(
            color=self.config.accent_color, title="Accent color"
        )
        if hex_color:
            self.config.accent_color = hex_color
            self.config.save()
            self.accent_swatch.configure(bg=hex_color)

    # ----------------------------------------------------------- update check
    def _start_update_check(self) -> None:
        if not self.config.check_updates:
            return

        def worker():
            from .update import check_for_update

            tag = check_for_update(__version__)
            if tag:
                self.root.after(0, lambda: self._set_update_available(tag))

        threading.Thread(target=worker, daemon=True).start()

    def _set_update_available(self, tag: str) -> None:
        self.update_var.set(f"⬆ New version {tag} available — click to download")
        self.update_lbl.grid()

    def _open_releases(self) -> None:
        import webbrowser

        from .update import RELEASES_URL

        webbrowser.open(RELEASES_URL)

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
            from .mining import analyze, parse_rock_stats, turrets_from_loadout
            from .ocr import DigitOCR
            from .translate import translate_matches
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
        last_rfp = None  # same, for the rock (mining) box
        was_enabled = self.config.enabled

        while not self.stop_event.is_set():
            start = time.time()
            if not self.config.calibrated:
                self._last_status = "⚠ calibrate the box to start"
                self.overlay.update_async(None)
            elif self.config.enabled:
                try:
                    # Force a fresh read right after re-enabling.
                    if not was_enabled:
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
                        number = ocr.read_number(img)  # detection always on
                        ocr_ms = (time.time() - t1) * 1000
                        matches = (
                            translate_matches(number, self.config.min_confidence)
                            if number else []
                        )
                        timing = f"(cap {cap_ms:.0f}ms, ocr {ocr_ms:.0f}ms)"
                        disabled = set(self.config.disabled_materials)
                        active = [m for m in matches if m.material.name not in disabled]
                        if not matches:
                            self.overlay.update_async(None)
                            self._last_status = f"{number or '—'} (no match)  {timing}"
                        elif active:
                            self.overlay.update_async(active, number)
                            shown = " / ".join(f"{m.material.name}×{m.count}" for m in active)
                            self._last_status = f"{number} → {shown}  {timing}"
                        else:
                            self.overlay.update_async([], number, sig_only=True)
                            self._last_status = f"{number} (hidden)  {timing}"
                except Exception as exc:
                    self._last_status = f"loop error: {exc}"
                    self.overlay.update_async(None)
            else:
                self._last_status = "overlay off"
            was_enabled = self.config.enabled

            # --- mining breakability (independent of the signature loop) ---
            if (self.config.mining_enabled and self.config.rock_calibrated
                    and self.config.loadout):
                try:
                    rimg = capture.grab(self.config.rock_region)
                    rfp = self._frame_fingerprint(rimg)
                    if (self.config.skip_unchanged and last_rfp is not None
                            and last_rfp.shape == rfp.shape
                            and float(np.abs(rfp - last_rfp).mean()) < 2.0):
                        pass  # rock panel unchanged -> keep the current readout
                    else:
                        last_rfp = rfp
                        rock = parse_rock_stats(ocr.read_text(rimg))
                        if rock:
                            turrets = turrets_from_loadout(self.config.loadout)
                            analysis = analyze(rock, turrets)
                            self.mining_overlay.update_async(self._mining_lines(analysis))
                        else:
                            self.mining_overlay.update_async(None)
                except Exception as exc:
                    self.mining_overlay.update_async(None)
                    print(f"[mining] loop error: {exc}")
            else:
                self.mining_overlay.update_async(None)
                last_rfp = None

            period = 1.0 / max(0.5, self.config.scan_fps)
            time.sleep(max(0.0, period - (time.time() - start)))

        capture.close()

    def _mining_lines(self, analysis):
        rock = analysis.rock
        acc = self.config.accent_color
        lines = [(f"[ {int(round(rock.mass))} m · {rock.resistance:.0f}% ]", acc)]
        colors = {"ok": "#33dd66", "overpower": "#ffcc44", "cant": "#ff5555"}
        labels = {"ok": "controllable", "overpower": "too much power", "cant": "can't break"}
        for v in analysis.verdicts:
            lines.append((f"{v.name} — {labels[v.state]}", colors.get(v.state, "#ffffff")))
        lines.append((f"→ {analysis.recommendation}", "#e8e8e8"))
        return lines

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
