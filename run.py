"""PyInstaller entry point.

Uses an absolute import so the frozen build keeps the ``sigtranslator`` package
context (running ``sigtranslator/__main__.py`` directly as the script would strip
the package and break its relative imports).
"""

import os
import sys

# The windowed (no-console) build has no stdout/stderr, so the app's many print()
# status lines would otherwise raise. Send them to the void instead.
if sys.stdout is None or sys.stderr is None:
    _devnull = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = _devnull
    if sys.stderr is None:
        sys.stderr = _devnull

from sigtranslator.app import main

if __name__ == "__main__":
    sys.exit(main())
