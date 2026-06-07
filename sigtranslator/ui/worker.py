"""Background capture/OCR worker. Emits Qt signals consumed on the GUI thread.

Reuses the existing logic modules unchanged (capture, ocr, translate, mining). Qt
signals are delivered with a queued connection across threads, so emitting from this
worker thread and updating widgets in the slots is safe.
"""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Signal


class WorkerSignals(QObject):
    status = Signal(str)
    sig = Signal(object, object)   # (matches, number); (None, None) => clear
    mining = Signal(object)        # Plan or None


class Worker:
    def __init__(self, config) -> None:
        self.config = config
        self.signals = WorkerSignals()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @staticmethod
    def _fp(img):
        import numpy as np

        s = img[::8, ::8]
        return s.mean(axis=2) if s.ndim == 3 else s.astype("float32")

    def _run(self) -> None:
        import numpy as np

        from ..capture import Capture
        from ..mining import analyze, parse_rock_stats, turrets_from_loadout
        from ..ocr import DigitOCR
        from ..translate import translate_matches

        try:
            capture = Capture()
            ocr = DigitOCR(threads=self.config.ocr_threads)
        except Exception as exc:
            self.signals.status.emit(f"init failed: {exc}")
            return
        self.signals.status.emit("ready")

        last_fp = last_rfp = None
        was_enabled = self.config.enabled
        unchanged = lambda a, b: (  # noqa: E731
            a is not None and a.shape == b.shape and float(np.abs(a - b).mean()) < 2.0
        )

        while not self._stop.is_set():
            start = time.time()
            cfg = self.config

            # --- signatures ---
            if not cfg.calibrated:
                self.signals.status.emit("calibrate the signature box to start")
                self.signals.sig.emit(None, None)
            elif cfg.enabled:
                try:
                    if not was_enabled:
                        last_fp = None
                    img = capture.grab(cfg.region)
                    fp = self._fp(img)
                    if cfg.skip_unchanged and unchanged(last_fp, fp):
                        pass
                    else:
                        last_fp = fp
                        number = ocr.read_number(img)
                        matches = translate_matches(number, cfg.min_confidence) if number else []
                        self.signals.sig.emit(matches, number)
                        self.signals.status.emit(str(number) if number else "—")
                except Exception as exc:
                    self.signals.sig.emit(None, None)
                    self.signals.status.emit(f"sig error: {exc}")
            else:
                self.signals.sig.emit(None, None)
                self.signals.status.emit("paused")
            was_enabled = cfg.enabled

            # --- mining (independent) ---
            turrets = cfg.active_turrets()
            if cfg.mining_enabled and cfg.rock_calibrated and turrets:
                try:
                    rimg = capture.grab(cfg.rock_region)
                    rfp = self._fp(rimg)
                    if cfg.skip_unchanged and unchanged(last_rfp, rfp):
                        pass
                    else:
                        last_rfp = rfp
                        rock = parse_rock_stats(ocr.read_text(rimg))
                        self.signals.mining.emit(
                            analyze(rock, turrets_from_loadout(turrets)) if rock else None
                        )
                except Exception:
                    self.signals.mining.emit(None)
            else:
                self.signals.mining.emit(None)
                last_rfp = None

            time.sleep(max(0.0, 1.0 / max(0.5, cfg.scan_fps) - (time.time() - start)))

        capture.close()
