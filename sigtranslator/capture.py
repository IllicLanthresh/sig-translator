"""Read-only screen capture of the configured region.

Uses ``mss`` (BitBlt under the hood on Windows) -- the same desktop-grab technique
screenshot/OBS tools use. We never touch the game process, so this stays clear of
EasyAntiCheat: no injection, no memory reads, just copying the desktop image.
"""

from __future__ import annotations

import numpy as np
import mss

from .config import Region


class Capture:
    def __init__(self) -> None:
        self._sct = mss.mss()

    def grab(self, region: Region) -> np.ndarray:
        """Return the region as a BGR uint8 array (H, W, 3)."""
        raw = self._sct.grab(region.as_mss())
        # mss returns BGRA; drop alpha.
        img = np.asarray(raw)[:, :, :3]
        return img

    def close(self) -> None:
        try:
            self._sct.close()
        except Exception:
            pass
