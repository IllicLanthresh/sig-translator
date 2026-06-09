"""Entry point. By default opens the control-panel GUI (settings + on/off + calibrate).

The GUI owns the Tk root, the floating overlay, and the capture/OCR worker thread.
A couple of headless conveniences remain for power users / debugging.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import Config


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
    if Image is not None:
        Image.fromarray(img[:, :, ::-1]).save("snapshot.png")  # BGR -> RGB
        print(f"[snapshot] saved snapshot.png for region {config.region}")
    else:
        import numpy as np

        np.save("snapshot.npy", img)
        print(f"[snapshot] saved snapshot.npy for region {config.region}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sig-translator", description=__doc__)
    parser.add_argument("--version", action="version", version=f"sig-translator {__version__}")
    parser.add_argument("--snapshot", action="store_true", help="save a PNG of the capture region and exit")
    parser.add_argument("--legacy", action="store_true", help="launch the old Tkinter UI")
    parser.add_argument("--proto", action="store_true", help="throwaway hold-to-interact overlay spike")
    parser.add_argument("--proto-key", default="scroll lock", help="hold key for --proto")
    args = parser.parse_args(argv)

    if args.proto:
        from .proto_hold_overlay import run as run_proto

        return run_proto(args.proto_key)

    config = Config.load()

    if args.snapshot:
        cmd_snapshot(config)
        return 0

    if args.legacy:
        from .gui import ControlPanel

        ControlPanel(config).run()
        return 0

    from .ui.app import run  # new Qt UI

    return run()


if __name__ == "__main__":
    sys.exit(main())
