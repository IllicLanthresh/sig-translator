"""The 'Targets' window: pick which materials the overlay flags as wanted.

A scrollable checklist grouped by rarity tier, with per-tier select/clear shortcuts.
Toggling any box updates ``config.targets`` and saves immediately.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .config import Config
from .materials import MATERIALS, TIER_COLORS


def _grouped() -> dict[str, list]:
    """Materials grouped by tier, preserving table order."""
    groups: dict[str, list] = {}
    for m in MATERIALS:
        groups.setdefault(m.tier, []).append(m)
    return groups


class TargetsWindow:
    def __init__(self, master: tk.Misc, config: Config) -> None:
        self.config = config
        self.vars: dict[str, tk.BooleanVar] = {}

        self.top = tk.Toplevel(master)
        self.top.title("Targets")
        self.top.resizable(False, True)
        self.top.transient(master)
        self.top.protocol("WM_DELETE_WINDOW", self._close)

        outer = ttk.Frame(self.top, padding=8)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, width=300, height=480, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._canvas = canvas
        canvas.bind_all("<MouseWheel>", self._on_wheel)

        wanted = set(config.targets)
        for tier, mats in _grouped().items():
            header = ttk.Frame(inner)
            header.pack(fill="x", pady=(8, 2))
            ttk.Label(header, text=tier, font=("", 10, "bold")).pack(side="left")
            ttk.Button(header, text="none", width=5,
                       command=lambda t=tier: self._set_tier(t, False)).pack(side="right")
            ttk.Button(header, text="all", width=4,
                       command=lambda t=tier: self._set_tier(t, True)).pack(side="right", padx=4)
            for m in mats:
                row = ttk.Frame(inner)
                row.pack(fill="x", anchor="w")
                tk.Label(row, bg=TIER_COLORS.get(m.tier, "#888888"), width=2).pack(
                    side="left", padx=(6, 6)
                )
                var = tk.BooleanVar(value=m.name in wanted)
                self.vars[m.name] = var
                ttk.Checkbutton(row, text=m.name, variable=var, command=self._save).pack(
                    side="left"
                )

        ttk.Button(self.top, text="Close", command=self._close).pack(pady=6)

    def _on_wheel(self, event) -> None:
        self._canvas.yview_scroll(int(-event.delta / 120), "units")

    def _set_tier(self, tier: str, value: bool) -> None:
        for m in MATERIALS:
            if m.tier == tier:
                self.vars[m.name].set(value)
        self._save()

    def _save(self) -> None:
        self.config.targets = [name for name, v in self.vars.items() if v.get()]
        self.config.save()

    def _close(self) -> None:
        try:
            self._canvas.unbind_all("<MouseWheel>")
        except Exception:
            pass
        self.top.destroy()
