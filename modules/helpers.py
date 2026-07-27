"""Shared utilities: logging, pacing, JSON coercion and Chrome profile discovery.

Every other module leans on this one, so it deliberately imports nothing from
the project beyond the settings file — anything heavier would create cycles.
"""

from __future__ import annotations

import json
import os
import platform
import re
import tempfile
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep  # noqa: F401  re-exported: callers do `from helpers import sleep`
from typing import Any, Callable, Iterable

try:
    from config.settings import click_gap, logs_folder_path
except Exception:  # settings.py may not exist yet on a fresh checkout
    click_gap = 0
    logs_folder_path = "logs/"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LOG_READY = False


def _log_file() -> Path:
    """Path of today's log file, creating the folder on first use."""
    global _LOG_READY
    folder = Path(logs_folder_path or "logs/")
    if not _LOG_READY:
        folder.mkdir(parents=True, exist_ok=True)
        _LOG_READY = True
    return folder / f"{datetime.now():%Y-%m-%d}.log"


def print_lg(
    *msgs: str | dict,
    end: str = "\n",
    pretty: bool = False,
    flush: bool = False,
    from_critical: bool = False,
) -> None:
    """Print to the console and append the same text to today's log file.

    Mirrors `print` on purpose so it can be dropped in anywhere. `pretty`
    renders dicts and lists as indented JSON. `from_critical` tags the entry
    and keeps a failing logger from calling itself.
    """
    parts: list[str] = []
    for m in msgs:
        if pretty and isinstance(m, (dict, list)):
            parts.append(json.dumps(m, indent=2, ensure_ascii=False, default=str))
        else:
            parts.append(str(m))
    text = " ".join(parts)

    try:
        print(text, end=end, flush=flush)
    except UnicodeEncodeError:
        # Some Windows consoles are still cp1252 and choke on emoji
        print(text.encode("ascii", "replace").decode("ascii"), end=end, flush=flush)

    try:
        stamp = f"{datetime.now():%H:%M:%S}"
        level = "CRITICAL" if from_critical else "INFO"
        with open(_log_file(), "a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] [{level}] {text}{end or chr(10)}")
    except Exception:
        # Never let logging take the bot down
        pass


def critical_error_log(context: str, error: Exception | str) -> None:
    """Record an unexpected failure together with its traceback."""
    if isinstance(error, BaseException):
        detail = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        ).rstrip()
    else:
        detail = str(error)
    print_lg(f"{context}\n{detail}", from_critical=True)


# ---------------------------------------------------------------------------
# Pacing
# ---------------------------------------------------------------------------

def buffer(secs: float = 0) -> None:
    """Pause between actions, never shorter than the configured `click_gap`.

    Acting faster than a human is the quickest way to get flagged, so the
    setting acts as a floor rather than a fixed value.
    """
    try:
        floor = float(click_gap or 0)
    except (TypeError, ValueError):
        floor = 0.0
    wait = max(float(secs or 0), floor)
    if wait > 0:
        sleep(wait)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

_MD_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def convert_to_json(data: Any) -> dict | list | None:
    """Best-effort coercion of a model response into real Python data.

    Language models keep wrapping JSON in markdown fences or padding it with
    prose, so the text is cleaned before parsing and, failing that, the
    outermost {...} or [...] block is pulled out.
    """
    if data is None:
        return None
    if isinstance(data, (dict, list)):
        return data

    text = _MD_FENCE.sub("", str(data).strip()).strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    for opening, closing in (("{", "}"), ("[", "]")):
        i, j = text.find(opening), text.rfind(closing)
        if i != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except (json.JSONDecodeError, ValueError):
                continue

    print_lg(f"Could not parse this as JSON: {text[:200]}")
    return None


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def truncate_for_csv(data: Any, max_length: int = 131000,
                     suffix: str = "...[TRUNCATED]") -> str:
    """Shorten a value so csv.writer accepts it.

    Job descriptions and stack traces routinely blow past the field size limit,
    and the write fails for the whole row — losing the record of an application
    that did go out. Truncating keeps the row.
    """
    if data is None:
        return ""
    texto = str(data)
    if len(texto) <= max_length:
        return texto
    return texto[: max_length - len(suffix)] + suffix


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

# LinkedIn renders relative times in the interface language, so both wordings
# have to be understood — the bot runs against the Spanish UI too.
_UNITS = {
    "second": "seconds", "seconds": "seconds", "segundo": "seconds", "segundos": "seconds",
    "minute": "minutes", "minutes": "minutes", "minuto": "minutes", "minutos": "minutes",
    "hour": "hours", "hours": "hours", "hora": "hours", "horas": "hours",
    "day": "days", "days": "days", "dia": "days", "dias": "days",
    "week": "weeks", "weeks": "weeks", "semana": "weeks", "semanas": "weeks",
    "month": "months", "months": "months", "mes": "months", "meses": "months",
    "year": "years", "years": "years", "ano": "years", "anos": "years",
}

_TIEMPO = re.compile(r"(\d+)\s*([a-zA-Záéíóúñ]+)", re.IGNORECASE)


def calculate_date_posted(time_string: str) -> datetime | None:
    """Turn "3 days ago" / "hace 3 días" into a datetime.

    Returns None when the string cannot be read, so callers can log the raw
    text instead of crashing on an unfamiliar wording.
    """
    if not time_string:
        return None

    texto = str(time_string).lower()
    texto = (texto.replace("á", "a").replace("é", "e").replace("í", "i")
                  .replace("ó", "o").replace("ú", "u").replace("ñ", "n"))

    m = _TIEMPO.search(texto)
    if not m:
        return None

    try:
        cantidad = int(m.group(1))
    except ValueError:
        return None

    unidad = _UNITS.get(m.group(2))
    if not unidad:
        return None

    # timedelta has no months or years, so approximate with days
    if unidad == "months":
        delta = timedelta(days=cantidad * 30)
    elif unidad == "years":
        delta = timedelta(days=cantidad * 365)
    else:
        delta = timedelta(**{unidad: cantidad})

    return datetime.now() - delta


# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------

def make_directories(paths: Iterable[str]) -> None:
    """Create the folders these paths need.

    Callers pass a mix of folders and file paths, so anything with a suffix
    gets its parent created instead of a folder named after the file.
    """
    for raw in paths or []:
        if not raw:
            continue
        p = Path(str(raw))
        target = p.parent if p.suffix else p
        if not target or str(target) in (".", ""):
            continue
        try:
            target.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            critical_error_log(f"Could not create the folder '{target}'", e)


# ---------------------------------------------------------------------------
# Chrome profiles
# ---------------------------------------------------------------------------

def find_default_profile_directory() -> str | None:
    """Locate Chrome's User Data folder for the current OS, or None."""
    system = platform.system()
    candidates: list[Path] = []

    if system == "Windows":
        for var in ("LOCALAPPDATA", "APPDATA", "USERPROFILE"):
            base = os.environ.get(var)
            if base:
                candidates += [
                    Path(base) / "Google" / "Chrome" / "User Data",
                    Path(base) / "Local" / "Google" / "Chrome" / "User Data",
                ]
    elif system == "Darwin":
        candidates.append(
            Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
        )
    else:
        candidates += [
            Path.home() / ".config" / "google-chrome",
            Path.home() / ".config" / "chromium",
        ]

    for c in candidates:
        if c.is_dir():
            return str(c)
    return None


def get_default_temp_profile() -> str:
    """Path of the throwaway Chrome profile, created if missing.

    A dedicated profile keeps the bot's cookies and session away from the
    user's real browser data.
    """
    target = Path(tempfile.gettempdir()) / "cvsniper-chrome-profile"
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        critical_error_log(f"Could not create the temporary profile at '{target}'", e)
    return str(target)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def manual_login_retry(is_logged_in: Callable[[], bool], limit: int = 2) -> bool:
    """Hand control to the user when automatic login fails.

    Returns True as soon as `is_logged_in()` succeeds. After `limit` prompts it
    gives up and returns False, so a headless run shuts down cleanly instead of
    looping forever on an `input()` nobody can answer.
    """
    attempts = 0
    while attempts <= max(0, limit):
        try:
            if is_logged_in():
                return True
        except Exception as e:
            critical_error_log("Could not verify the login state", e)

        if attempts == limit:
            break
        attempts += 1

        print_lg("")
        print_lg("=" * 70)
        print_lg(" Automatic login did not go through.")
        print_lg(" Log in by hand in the browser window that just opened,")
        print_lg(f" then come back here and press Enter.  (attempt {attempts}/{limit})")
        print_lg("=" * 70)
        try:
            input(" Press Enter once you are logged in... ")
        except (EOFError, KeyboardInterrupt):
            print_lg("No console input available, giving up on manual login.")
            return False

    print_lg("Still not logged in after the manual attempts.")
    return False
