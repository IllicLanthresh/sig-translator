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


def _extract_number(rows) -> int | None:
    """Pull the most likely signature integer out of a RapidOCR result.

    Handles both result shapes:
      * recognition-only: ``[[text, score], ...]``
      * full pipeline:    ``[[box, text, score], ...]``
    In both, the text is the second-to-last item and the score is the last.
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
        for chunk in _DIGITS.findall(text.replace(" ", "")):
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
        self, img: np.ndarray, detect: bool = False, upscale: float = 2.0
    ) -> int | None:
        """Return the most likely signature integer in the image, or None.

        ``detect=False`` (default) runs recognition-only on the crop -- fast, assumes a
        tight calibration box. ``detect=True`` runs the full detect+recognize pipeline.
        """
        if not detect:
            img = self._prepare(img, upscale)
        result, _elapse = self._engine(
            img, use_det=detect, use_cls=False, use_rec=True
        )
        return _extract_number(result)
