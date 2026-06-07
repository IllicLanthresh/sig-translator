"""User configuration: capture region, scan FPS, toggle hotkey, overlay style.

Stored as JSON in the standard per-user config location (``%APPDATA%\\sig-translator``
on Windows, ``~/Library/Application Support/sig-translator`` on macOS), so it persists
across updates and doesn't clutter wherever the exe happens to live. This is the app's
*own* settings file -- not a data source -- so it has nothing to do with the "no
external data dependency" rule.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


def _config_dir() -> Path:
    """Standard per-user directory for this app's config."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "sig-translator"


CONFIG_PATH = _config_dir() / "config.json"


@dataclass
class Region:
    x: int = 0
    y: int = 0
    width: int = 600
    height: int = 120

    def as_mss(self) -> dict:
        return {"left": self.x, "top": self.y, "width": self.width, "height": self.height}


@dataclass
class Config:
    region: Region = field(default_factory=Region)
    scan_fps: float = 3.0
    hotkey: str = "ctrl+alt+s"
    enabled: bool = True
    min_confidence: float = 0.985  # below this we show nothing (likely no signature)
    font_size: int = 18
    text_color: str = "#00ff88"
    outline: bool = True
    # Star-Citizen-ish HUD font (ships on Windows 10/11); Tk substitutes if missing.
    font_family: str = "Bahnschrift"
    # Accent tint for the signature line — match your ship manufacturer's HUD color.
    accent_color: str = "#7fdfff"
    # --- OCR performance knobs (keep the game smooth) ---
    # onnxruntime defaults to using every CPU core, which starves the game; cap it.
    ocr_threads: int = 1
    # Skip OCR when the captured box hasn't changed (no signature on screen).
    skip_unchanged: bool = True
    # Show the rarity tier in parentheses after the name, e.g. "Riccite ×2 (Epic)".
    show_rarity: bool = True
    # Set once the user has calibrated the capture box. Until then the app insists on
    # calibration and won't scan a meaningless default region.
    calibrated: bool = False
    # Check GitHub for a newer release on startup (the app's only network call).
    check_updates: bool = True
    # Every material is shown by default. Names listed here are "disabled": when one of
    # them is scanned the overlay shows only the signature readback (no material name),
    # so you can focus on what you actually want to mine.
    disabled_materials: list[str] = field(default_factory=list)
    # --- Mining breakability (separate capability) ---
    mining_enabled: bool = False
    rock_region: Region = field(default_factory=Region)  # 2nd capture box, the scan panel
    rock_calibrated: bool = False
    # Loadout: up to 3 turrets, each {"laser": <key>, "modules": [<key>, ...]}.
    loadout: list = field(default_factory=list)

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            try:
                raw = json.loads(CONFIG_PATH.read_text())
                region_fields = {f.name for f in fields(Region)}

                def _region(key):
                    return Region(**{k: v for k, v in raw.pop(key, {}).items()
                                     if k in region_fields})

                region = _region("region")
                rock_region = _region("rock_region")
                # Ignore unknown/removed keys so old config files keep loading.
                known = {f.name for f in fields(cls)} - {"region", "rock_region"}
                raw = {k: v for k, v in raw.items() if k in known}
                return cls(region=region, rock_region=rock_region, **raw)
            except Exception as exc:  # corrupt config -> fall back to defaults
                print(f"[config] could not read {CONFIG_PATH}: {exc}; using defaults")
        cfg = cls()
        cfg.save()
        return cfg

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        CONFIG_PATH.write_text(json.dumps(data, indent=2))
