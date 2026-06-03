"""User configuration: capture region, scan FPS, toggle hotkey, overlay style.

Stored as JSON next to the executable (``config.json``) so it survives restarts and
is easy to hand-edit. This is the app's *own* settings file -- not a data source --
so it has nothing to do with the "no external data dependency" rule.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _app_dir() -> Path:
    """Directory to store config next to the exe (or cwd when run from source)."""
    if getattr(sys, "frozen", False):  # PyInstaller bundle
        return Path(sys.executable).parent
    return Path.cwd()


CONFIG_PATH = _app_dir() / "config.json"


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
    # --- OCR performance knobs (keep the game smooth) ---
    # onnxruntime defaults to using every CPU core, which starves the game; cap it.
    ocr_threads: int = 1
    # False = recognition-only on the calibrated box (fast, no detection model).
    # True = full detect+recognize pipeline (slower, only if the box has clutter).
    ocr_detect: bool = False
    # Upscale tiny number crops so the recognizer reads them cleanly.
    ocr_upscale: float = 2.0
    # Skip OCR when the captured box hasn't changed (no signature on screen).
    skip_unchanged: bool = True

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            try:
                raw = json.loads(CONFIG_PATH.read_text())
                region = Region(**raw.pop("region", {}))
                return cls(region=region, **raw)
            except Exception as exc:  # corrupt config -> fall back to defaults
                print(f"[config] could not read {CONFIG_PATH}: {exc}; using defaults")
        cfg = cls()
        cfg.save()
        return cfg

    def save(self) -> None:
        data = asdict(self)
        CONFIG_PATH.write_text(json.dumps(data, indent=2))
