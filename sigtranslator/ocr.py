"""Digit OCR for the HUD signature number, via RapidOCR (bundled ONNX models).

Performance is critical: this runs while Star Citizen is also using the CPU heavily.
Two measures keep it from stalling the game (verified against rapidocr_onnxruntime
1.4.4 source):

* **Thread cap.** onnxruntime defaults to using every CPU core (config ships
  ``intra_op_num_threads: -1``). We pass an explicit small cap so an OCR pass can't
  saturate the cores and starve the game's render thread.
* **Recognition-only.** The user calibrates a tight box around the number, so we skip
  the heavyweight text-detection model (DBNet) and run recognition directly on the
  crop (``use_det=False``). That removes most of the per-frame cost.
"""

from __future__ import annotations

import re

import numpy as np

_DIGITS = re.compile(r"\d+")
# Thousands separators / spaces the HUD or OCR may put inside the number
# (e.g. "6,770", "16 900"). Stripped so the digits join into one value.
_SEPARATORS = re.compile(r"[,.\'\s\u00a0\u2009]")


def _extract_number(rows) -> int | None:
    """Pull the most likely signature integer out of a RapidOCR result.

    Handles both result shapes:
      * recognition-only: ``[[text, score], ...]``
      * full pipeline:    ``[[box, text, score], ...]``
    In both, the text is the second-to-last item and the score is the last.

    Thousands separators are removed first, so the in-game "6,770" reads as 6770
    instead of splitting into 6 and 770.
    """
    if not rows:
        return None
    candidates: list[int] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        text, score = str(row[-2]), row[-1]
        if isinstance(score, (int, float)) and score < 0.4:
            continue
        clean = _SEPARATORS.sub("", text)
        for chunk in _DIGITS.findall(clean):
            if 3 <= len(chunk) <= 6:  # signatures are 4-5 digits (2,000 .. ~64,500)
                candidates.append(int(chunk))
    if not candidates:
        return None
    # The signature is the largest number in the box (timers/percentages are smaller).
    return max(candidates)


class DigitOCR:
    def __init__(self, threads: int = 1) -> None:
        # Imported lazily so unit tests / non-Windows dev don't need the heavy dep.
        from rapidocr_onnxruntime import RapidOCR

        # Cap onnxruntime threads on every model so OCR can't peg all cores.
        self._engine = RapidOCR(
            intra_op_num_threads=threads,
            inter_op_num_threads=threads,
        )

    @staticmethod
    def _prepare(img: np.ndarray, upscale: float) -> np.ndarray:
        """Upscale small crops so the recognizer sees ~48px-tall glyphs."""
        if upscale and upscale > 1.0 and img.shape[0] < 60:
            try:
                from PIL import Image

                h, w = img.shape[:2]
                # Channel order is irrelevant to a resize; BGR in -> BGR out.
                resized = Image.fromarray(img).resize(
                    (int(w * upscale), int(h * upscale)), Image.BICUBIC
                )
                return np.asarray(resized)
            except Exception:
                return img
        return img

    def read_number(
        self, img: np.ndarray, detect: bool = True, upscale: float = 2.0
    ) -> int | None:
        """Return the most likely signature integer in the image, or None.

        ``detect=True`` (default) runs the full detect+recognize pipeline, which is what
        reliably finds the HUD digits. Recognition-only (``detect=False``) is faster but
        only works on a perfectly tight crop, so it's not used by default. onnxruntime
        threads are capped (see ``__init__``) so detection stays smooth alongside the game.
        """
        if not detect:
            img = self._prepare(img, upscale)
        result, _elapse = self._engine(
            img, use_det=detect, use_cls=False, use_rec=True
        )
        return _extract_number(result)

    def read_text(self, img: np.ndarray) -> str:
        """Full detect+recognize, returning all recognized text joined by spaces.

        Used for the multi-field rock scan panel (Mass / Resistance / Instability),
        which is then regex-parsed by sigtranslator.mining.parse_rock_stats.
        """
        result, _elapse = self._engine(img, use_det=True, use_cls=False, use_rec=True)
        if not result:
            return ""
        parts = []
        for row in result:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                parts.append(str(row[-2]))
        return " ".join(parts)
