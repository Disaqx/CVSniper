'''
Tells the user when a newer CVSniper has been published.

Whoever installed the bot with the Windows installer has no other way to hear
about fixes. One request to GitHub's public API at startup, in a background
thread, with a short timeout; any failure (offline, rate limit, no release yet)
is silent. Set `check_for_updates = False` in config/settings.py to turn it off.
'''
import json
import re
import threading
import urllib.request

from modules.version import __version__

REPO = "Disaqx/CVSniper"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


def _parts(version: str) -> tuple[int, ...]:
    '''"v1.2.10" -> (1, 2, 10). Pre-release suffixes are ignored.'''
    numeros = re.findall(r'\d+', str(version or "").split("-")[0])
    return tuple(int(n) for n in numeros[:3]) or (0,)


def is_newer(remote: str, local: str = __version__) -> bool:
    a, b = _parts(remote), _parts(local)
    largo = max(len(a), len(b))
    return a + (0,) * (largo - len(a)) > b + (0,) * (largo - len(b))


def latest_release(timeout: float = 5.0) -> tuple[str, str] | None:
    '''(version, page url) of the latest published release, or None.'''
    try:
        req = urllib.request.Request(_API_URL, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"CVSniper/{__version__}",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            datos = json.load(resp)
        tag = str(datos.get("tag_name") or "").strip()
        return (tag.lstrip("vV"), datos.get("html_url") or RELEASES_URL) if tag else None
    except Exception:
        return None


def check_in_background(notify) -> None:
    '''Calls notify(version, url) from a daemon thread if a newer release exists.'''
    def _run():
        encontrada = latest_release()
        if encontrada and is_newer(encontrada[0]):
            try:
                notify(*encontrada)
            except Exception:
                pass
    threading.Thread(target=_run, name="update-check", daemon=True).start()
