"""Main loop: capture -> OCR -> translate -> overlay, with a global toggle hotkey.

Tkinter must own the main thread, so the overlay runs there and the capture/OCR
work runs on a background worker that pushes label updates back to the overlay.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time

from . import __version__
from .config import Config
from .translate import translate


def _run_loop(config: Config, overlay, stop_event: threading.Event) -> None:
    """Background worker: grab the region, OCR it, translate, update the overlay."""
    from .capture import Capture
    from .ocr import DigitOCR

    capture = Capture()
    ocr = DigitOCR()
    print("[app] capture + OCR ready")

    while not stop_event.is_set():
        start = time.time()
        if config.enabled:
            try:
                img = capture.grab(config.region)
                number = ocr.read_number(img)
                match = translate(number) if number else None
                if match and match.confidence >= config.min_confidence:
                    overlay.update_async(match.label)
                else:
                    overlay.update_async(None)
            except Exception as exc:
                print(f"[app] loop error: {exc}")
                overlay.update_async(None)
        else:
            overlay.update_async(None)

        period = 1.0 / max(0.5, config.scan_fps)
        time.sleep(max(0.0, period - (time.time() - start)))

    capture.close()


def _register_hotkey(config: Config, overlay) -> None:
    try:
        import keyboard
    except Exception as exc:
        print(f"[app] hotkey disabled ({exc}); edit config.json 'enabled' instead")
        return

    def toggle():
        config.enabled = not config.enabled
        config.save()
        print(f"[app] overlay {'ON' if config.enabled else 'OFF'}")
        if not config.enabled:
            overlay.update_async(None)

    try:
        keyboard.add_hotkey(config.hotkey, toggle)
        print(f"[app] toggle hotkey: {config.hotkey}")
    except Exception as exc:
        print(f"[app] could not bind hotkey {config.hotkey}: {exc}")


def cmd_snapshot(config: Config) -> None:
    """Save what the capture region currently sees, for verifying calibration."""
    from .capture import Capture

    try:
        from PIL import Image
    except Exception:
        Image = None
    cap = Capture()
    img = cap.grab(config.region)
    cap.close()
    out = "snapshot.png"
    if Image is not None:
        # img is BGR; convert to RGB for a correct-looking PNG.
        Image.fromarray(img[:, :, ::-1]).save(out)
    else:
        import numpy as np

        np.save("snapshot.npy", img)
        out = "snapshot.npy"
    print(f"[snapshot] saved {out} for region {config.region}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sig-translator", description=__doc__)
    parser.add_argument("--version", action="version", version=f"sig-translator {__version__}")
    parser.add_argument("--calibrate", action="store_true", help="drag-select the capture region")
    parser.add_argument("--snapshot", action="store_true", help="save a PNG of the capture region")
    args = parser.parse_args(argv)

    config = Config.load()

    if args.calibrate:
        from .overlay import calibrate_region

        calibrate_region(config)
        return 0

    if args.snapshot:
        cmd_snapshot(config)
        return 0

    from .overlay import Overlay

    overlay = Overlay(config)
    stop_event = threading.Event()
    worker = threading.Thread(
        target=_run_loop, args=(config, overlay, stop_event), daemon=True
    )
    worker.start()
    _register_hotkey(config, overlay)

    print(f"[app] running at {config.scan_fps} fps; region {config.region}")
    print("[app] close this window to quit")
    try:
        overlay.run()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
