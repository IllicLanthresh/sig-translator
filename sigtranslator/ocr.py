"""Digit OCR for the HUD signature number, via RapidOCR (bundled ONNX models).

RapidOCR ships its own models in the pip package, so there is no separate install
and no network access at runtime. We keep only digits and pick the largest plausible
number found in the region (the signature is the dominant number in the capture box).
"""

from __future__ import annotations

import re

import numpy as np

_DIGITS = re.compile(r"\d+")


class DigitOCR:
    def __init__(self) -> None:
        # Imported lazily so unit tests / non-Windows dev don't need the heavy dep.
        from rapidocr_onnxruntime import RapidOCR

        self._engine = RapidOCR()

    def read_number(self, img: np.ndarray) -> int | None:
        """Return the most likely signature integer in the image, or None."""
        result, _ = self._engine(img)
        if not result:
            return None
        candidates: list[int] = []
        for _box, text, score in result:
            if score is not None and score < 0.4:
                continue
            for chunk in _DIGITS.findall(text.replace(" ", "")):
                # Signatures are 4-5 digits (2,000 .. ~64,500). Filter noise.
                if 3 <= len(chunk) <= 6:
                    candidates.append(int(chunk))
        if not candidates:
            return None
        # The signature is the largest number in the box (timers/percentages are smaller
        # or differently placed). Largest is a robust heuristic for the HUD layout.
        return max(candidates)
