"""Mining setup window: calibrate the rock scan panel + edit the laser/module loadout."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .config import Config
from .mining import LASERS, LASERS_BY_KEY, MODULES
from .overlay import calibrate_region

_NONE = "— none —"
_EMPTY = "— empty —"
_LASER_NAMES = [_NONE] + [l.name for l in LASERS]
_LASER_NAME_TO_KEY = {l.name: l.key for l in LASERS}
_LASER_KEY_TO_NAME = {l.key: l.name for l in LASERS}
_MODULE_NAMES = [_EMPTY] + [m.name for m in MODULES]
_MODULE_NAME_TO_KEY = {m.name: m.key for m in MODULES}
_MODULE_KEY_TO_NAME = {m.key: m.name for m in MODULES}

MAX_TURRETS = 3


class _TurretRow:
    def __init__(self, parent, config: Config, index: int, on_change) -> None:
        self.config = config
        self.index = index
        self.on_change = on_change

        self.frame = ttk.LabelFrame(parent, text=f"Turret {index + 1}", padding=6)
        self.frame.pack(fill="x", pady=4)
        top = ttk.Frame(self.frame)
        top.pack(fill="x")
        ttk.Label(top, text="Laser").pack(side="left")
        self.laser_var = tk.StringVar(value=_NONE)
        cb = ttk.Combobox(top, textvariable=self.laser_var, values=_LASER_NAMES,
                          state="readonly", width=16)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._on_laser())

        self.modules_frame = ttk.Frame(self.frame)
        self.modules_frame.pack(fill="x", pady=(4, 0))
        self.module_vars: list[tk.StringVar] = []
        self._load_existing()

    def _load_existing(self) -> None:
        loadout = self.config.loadout or []
        if self.index < len(loadout) and loadout[self.index]:
            entry = loadout[self.index]
            lk = entry.get("laser")
            if lk in _LASER_KEY_TO_NAME:
                self.laser_var.set(_LASER_KEY_TO_NAME[lk])
            self._rebuild_modules(preset=entry.get("modules", []))
        else:
            self._rebuild_modules()

    def _on_laser(self) -> None:
        self._rebuild_modules()
        self.on_change()

    def _rebuild_modules(self, preset=None) -> None:
        for w in self.modules_frame.winfo_children():
            w.destroy()
        self.module_vars = []
        name = self.laser_var.get()
        if name == _NONE:
            return
        laser = LASERS_BY_KEY[_LASER_NAME_TO_KEY[name]]
        preset = preset or []
        ttk.Label(self.modules_frame, text="Modules").pack(side="left", padx=(0, 4))
        for s in range(laser.slots or 0):
            var = tk.StringVar(value=_EMPTY)
            if s < len(preset) and preset[s] in _MODULE_KEY_TO_NAME:
                var.set(_MODULE_KEY_TO_NAME[preset[s]])
            cb = ttk.Combobox(self.modules_frame, textvariable=var, values=_MODULE_NAMES,
                              state="readonly", width=15)
            cb.pack(side="left", padx=3)
            cb.bind("<<ComboboxSelected>>", lambda _e: self.on_change())
            self.module_vars.append(var)

    def to_entry(self):
        name = self.laser_var.get()
        if name == _NONE:
            return None
        modules = [
            _MODULE_NAME_TO_KEY[v.get()] for v in self.module_vars if v.get() != _EMPTY
        ]
        return {"laser": _LASER_NAME_TO_KEY[name], "modules": modules}


class MiningSetupWindow:
    def __init__(self, master: tk.Misc, config: Config) -> None:
        self.master = master
        self.config = config

        self.top = tk.Toplevel(master)
        self.top.title("Mining setup")
        self.top.transient(master)
        frm = ttk.Frame(self.top, padding=12)
        frm.pack(fill="both", expand=True)

        cal = ttk.Frame(frm)
        cal.pack(fill="x", pady=(0, 8))
        ttk.Button(cal, text="Calibrate rock panel…", command=self._calibrate).pack(side="left")
        self.cal_label = ttk.Label(cal, text=self._cal_text())
        self.cal_label.pack(side="left", padx=8)

        ttk.Label(
            frm, text="Loadout — set the turrets you have (leave the rest as 'none')",
            font=("", 10, "bold"),
        ).pack(anchor="w", pady=(4, 2))
        self.rows = [_TurretRow(frm, config, i, self._save) for i in range(MAX_TURRETS)]

        ttk.Button(frm, text="Close", command=self.top.destroy).pack(pady=(8, 0))

    def _cal_text(self) -> str:
        r = self.config.rock_region
        return f"✓ {r.width}×{r.height}" if self.config.rock_calibrated else "not calibrated"

    def _calibrate(self) -> None:
        self.top.withdraw()
        try:
            calibrate_region(self.master, self.config, attr="rock_region",
                             calibrated_attr="rock_calibrated")
        finally:
            self.top.deiconify()
        self.cal_label.configure(text=self._cal_text())

    def _save(self) -> None:
        entries = [r.to_entry() for r in self.rows]
        self.config.loadout = [e for e in entries if e is not None]
        self.config.save()
