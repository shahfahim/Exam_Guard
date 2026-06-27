# update_checker.py — ExamGuard Background Update Checker
#
# Silently polls GitHub Releases API once on startup.
# Calls the provided callback if a newer version is available.
# Never blocks the UI thread.

import json
import ssl
import threading
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    # certifi not available; fall back to system CA store (still validates)
    _SSL_CONTEXT = ssl.create_default_context()

from version import VERSION, RELEASES_URL

# GitHub API endpoint for latest release
_GITHUB_API_URL = "https://api.github.com/repos/shahfahim/Exam_Guard/releases/latest"
_REQUEST_TIMEOUT = 6       # seconds — fail fast to not slow startup
_USER_AGENT      = f"ExamGuard-UpdateChecker/{VERSION}"


def _parse_version(tag: str) -> tuple:
    """Convert 'v4.1.2' or '4.1.2' to (4, 1, 2)."""
    tag = tag.lstrip("v").strip()
    parts = tag.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return (0,)


def _check(callback) -> None:
    """Runs in a daemon thread. Calls callback(tag, url) if an update exists."""
    try:
        req = Request(
            _GITHUB_API_URL,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/vnd.github+json",
            },
        )
        with urlopen(req, timeout=_REQUEST_TIMEOUT,
                     context=_SSL_CONTEXT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        latest_tag = data.get("tag_name", "").strip()
        latest_url = data.get("html_url", RELEASES_URL)
        prerelease  = data.get("prerelease", False)
        draft       = data.get("draft", False)

        if not latest_tag or prerelease or draft:
            return

        latest  = _parse_version(latest_tag)
        current = _parse_version(VERSION)

        if latest > current:
            # Schedule callback on the calling thread via the passed function
            callback(latest_tag, latest_url)

    except (URLError, HTTPError, OSError, ValueError, KeyError):
        # Network unavailable, rate-limited, JSON parse error — silently ignore
        pass


def check_in_background(on_update_available) -> None:
    """
    Spawn a one-shot daemon thread to check for a newer release.

    Args:
        on_update_available: callable(tag: str, url: str)
            Called when a newer release is found. May be called from a
            background thread — use app.after(0, ...) to update the UI.

    Example::
        def _on_update(tag, url):
            app.after(0, lambda: show_update_banner(tag, url))

        update_checker.check_in_background(_on_update)
    """
    t = threading.Thread(
        target=_check,
        args=(on_update_available,),
        name="ExamGuard-UpdateChecker",
        daemon=True,
    )
    t.start()
