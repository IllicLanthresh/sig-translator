"""Optional, fail-silent check for a newer release on GitHub.

This is the app's *only* network call, and it's entirely optional: if there's no
internet (or anything goes wrong), it just returns ``None`` and the app runs exactly
as before. It does not download or install anything -- it only compares version
numbers so the UI can point the user at the Releases page.
"""

from __future__ import annotations

import json
import urllib.request

_REPO = "IllicLanthresh/sig-translator"
RELEASES_URL = f"https://github.com/{_REPO}/releases/latest"
_API_URL = f"https://api.github.com/repos/{_REPO}/releases/latest"


def _parse(version: str) -> tuple[int, ...]:
    """Turn 'v0.1.11' / '0.1.11' into (0, 1, 11) for comparison."""
    parts = []
    for chunk in version.lstrip("vV").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_for_update(current: str, timeout: float = 4.0) -> str | None:
    """Return the latest release tag (e.g. 'v0.1.12') if it is newer than ``current``.

    Returns ``None`` if up to date, or on ANY error (offline, timeout, rate limit,
    bad response) -- it never raises, so a failed check is invisible to the user.
    """
    try:
        req = urllib.request.Request(_API_URL, headers={"User-Agent": "sig-translator"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        tag = data.get("tag_name")
        if tag and _parse(tag) > _parse(current):
            return tag
    except Exception:
        return None
    return None
