"""PyInstaller entry point.

Uses an absolute import so the frozen build keeps the ``sigtranslator`` package
context (running ``sigtranslator/__main__.py`` directly as the script would strip
the package and break its relative imports).
"""

import sys

from sigtranslator.app import main

if __name__ == "__main__":
    sys.exit(main())
