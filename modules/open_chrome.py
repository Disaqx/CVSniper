"""Boots the Chrome session the whole bot shares.

Importing this module starts a browser. That is deliberate — callers do
`from modules.open_chrome import driver, wait, actions` and expect a live
session — but it means importing it from a test or a tool will also open a
window, so import it late rather than at the top of a utility.

Exports:
    driver   the WebDriver every module drives
    wait     a WebDriverWait bound to that driver
    actions  an ActionChains bound to that driver
"""

from __future__ import annotations

import sys

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys  # noqa: F401  re-exported via `import *`
from selenium.webdriver.support.ui import WebDriverWait

from modules.helpers import (
    critical_error_log,
    find_default_profile_directory,
    get_default_temp_profile,
    print_lg,
)

try:
    from config.settings import (
        disable_extensions,
        run_in_background,
        safe_mode,
        stealth_mode,
    )
except Exception:
    disable_extensions = False
    run_in_background = False
    safe_mode = True
    stealth_mode = True

# How long `wait.until(...)` gives up after. LinkedIn is slow enough that
# anything under ~10s produces flaky false negatives on a cold page load.
WAIT_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------

def _profile_directory() -> str | None:
    """Which Chrome profile to run against.

    `safe_mode` keeps the bot in a throwaway profile so it never touches the
    user's real cookies, history or saved passwords. With it off, the bot
    reuses the installed Chrome profile, which is what lets it inherit an
    already-logged-in LinkedIn session instead of typing credentials.
    """
    if safe_mode:
        return get_default_temp_profile()
    real = find_default_profile_directory()
    if real:
        return real
    print_lg("Chrome's profile folder was not found, falling back to a temporary one.")
    return get_default_temp_profile()


def _build_options(options: ChromeOptions) -> ChromeOptions:
    """Apply the settings that are identical for both driver flavours."""
    perfil = _profile_directory()
    if perfil:
        options.add_argument(f"--user-data-dir={perfil}")

    if run_in_background:
        options.add_argument("--headless=new")
    if disable_extensions:
        options.add_argument("--disable-extensions")

    # Quality-of-life: no first-run wizards, no password-manager popups
    # stealing focus mid-application, and a window big enough that LinkedIn
    # serves the desktop layout the selectors were written against.
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_experimental_option(
        "prefs",
        {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        },
    )
    return options


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _get_chrome_major_version() -> int | None:
    """Attempt to detect the installed Google Chrome major version."""
    import os
    import platform
    import re
    import subprocess

    system = platform.system()
    if system == "Windows":
        try:
            import winreg

            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for subkey in (
                    r"Software\Google\Chrome\BLBeacon",
                    r"SOFTWARE\Google\Chrome\BLBeacon",
                    r"SOFTWARE\Wow6432Node\Google\Update\ClientState\{8A69D345-D564-463c-AFF1-A69D9E530F96}",
                ):
                    try:
                        with winreg.OpenKey(root, subkey) as key:
                            val, _ = winreg.QueryValueEx(key, "version")
                            m = re.match(r"^(\d+)\.", str(val))
                            if m:
                                return int(m.group(1))
                    except OSError:
                        continue
        except Exception:
            pass

        for base in [
            os.environ.get("ProgramFiles", ""),
            os.environ.get("ProgramFiles(x86)", ""),
            os.environ.get("LocalAppData", ""),
        ]:
            if not base:
                continue
            app_dir = os.path.join(base, "Google", "Chrome", "Application")
            if os.path.isdir(app_dir):
                try:
                    for item in os.listdir(app_dir):
                        m = re.match(r"^(\d+)\.\d+\.\d+\.\d+$", item)
                        if m:
                            return int(m.group(1))
                except Exception:
                    pass
    elif system == "Darwin":
        try:
            cmd = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"]
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            m = re.search(r"(\d+)\.", out)
            if m:
                return int(m.group(1))
        except Exception:
            pass
    else:
        for binary in ("google-chrome", "google-chrome-stable", "chromium"):
            try:
                out = subprocess.check_output([binary, "--version"], text=True, stderr=subprocess.DEVNULL)
                m = re.search(r"(\d+)\.", out)
                if m:
                    return int(m.group(1))
            except Exception:
                continue
    return None


def _find_chrome_binary() -> str | None:
    """Locate chrome.exe / google-chrome.

    undetected_chromedriver only looks in a few fixed folders and, when Chrome
    lives anywhere else (another drive, per-user install), hands Selenium None
    -> "Binary Location Must be a String". Selenium's own manager finds it via
    the registry, so do the same here and pass the path explicitly.
    """
    import os
    import platform
    import shutil

    if platform.system() == "Windows":
        try:
            import winreg

            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(
                        root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
                    ) as key:
                        path, _ = winreg.QueryValueEx(key, None)
                        if path and os.path.isfile(path):
                            return str(path)
                except OSError:
                    continue
        except Exception:
            pass
        for base in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
            root = os.environ.get(base, "")
            path = os.path.join(root, "Google", "Chrome", "Application", "chrome.exe")
            if root and os.path.isfile(path):
                return path
    elif platform.system() == "Darwin":
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.isfile(path):
            return path
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _selenium_manager_chrome() -> str | None:
    """Chrome path as resolved (or downloaded) by Selenium Manager."""
    import os

    try:
        from selenium.webdriver.common.selenium_manager import SeleniumManager

        paths = SeleniumManager().binary_paths(["--browser", "chrome"])
        path = paths.get("browser_path")
        return path if path and os.path.isfile(path) else None
    except Exception:
        return None


def _cleanup_residual_chromedriver():
    """Kill any orphaned chromedriver if launch fails."""
    import platform
    import subprocess
    import time

    if platform.system() == "Windows":
        try:
            for exe in ("chromedriver.exe", "undetected_chromedriver.exe"):
                subprocess.run(["taskkill", "/F", "/IM", exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
        except Exception:
            pass
    _close_bot_profile_chrome()


def _close_bot_profile_chrome():
    """Close Chrome windows left running on the bot's throwaway profile.

    A crashed run (or a failed stealth start, which launches Chrome before
    giving up) leaves Chrome holding that profile, and the next start then dies
    with "Chrome failed to start: crashed". Only the temporary profile is
    touched — never the user's real browser.
    """
    import platform
    import subprocess
    import time

    if not safe_mode or platform.system() != "Windows":
        return
    script = (
        "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
        "Where-Object { $_.CommandLine -like '*cvsniper-chrome-profile*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        time.sleep(1)
    except Exception:
        pass


# undetected_chromedriver has no timeout of its own: when Chrome never answers
# on the debugging port it waits forever and the UI sits on "Starting Chrome
# in stealth mode...". Past this, give up and use the standard driver.
STEALTH_TIMEOUT = 90


def _with_timeout(fn, seconds: int):
    """Run `fn` in a worker thread; raise TimeoutError if it does not return."""
    import threading

    result: dict = {}

    def run():
        try:
            result["value"] = fn()
        except BaseException as e:  # noqa: BLE001 - re-raised in the caller
            result["error"] = e

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        # Kill what it launched so the late thread fails instead of leaving a
        # second Chrome holding the profile the fallback needs.
        _cleanup_residual_chromedriver()
        raise TimeoutError(f"stealth start did not finish in {seconds}s")
    if "error" in result:
        raise result["error"]
    return result["value"]


def _binary_major_version(path: str) -> int | None:
    """Major version of a given chrome.exe, read from its install layout.

    Stable installs keep a `<version>` folder next to chrome.exe; Chrome for
    Testing (what Selenium Manager downloads) has the version in its path.
    """
    import os
    import re

    m = re.search(r"[\\/](\d{2,4})\.\d+\.\d+\.\d+[\\/]", path)
    if m:
        return int(m.group(1))
    try:
        for item in os.listdir(os.path.dirname(path)):
            m = re.match(r"^(\d{2,4})\.\d+\.\d+\.\d+$", item)
            if m:
                return int(m.group(1))
    except OSError:
        pass
    return None


def _start_driver():
    """Open Chrome, preferring the patched driver when stealth mode is on.

    undetected_chromedriver hides the automation flags LinkedIn looks for, but
    it trails Chrome releases and breaks on upgrade day. When that happens the
    plain Selenium driver still works, so the failure is downgraded to a
    warning rather than killing the run.
    """
    _close_bot_profile_chrome()
    if stealth_mode:
        try:
            import undetected_chromedriver as uc

            print_lg("Starting Chrome in stealth mode...")
            chrome_bin = _find_chrome_binary() or _selenium_manager_chrome()
            if not chrome_bin:
                # uc would crash with "Binary Location Must be a String"
                raise RuntimeError(
                    "Google Chrome was not found. Install it from "
                    "https://www.google.com/chrome/ for stealth mode."
                )
            # The version of the binary actually launched, not whatever the
            # registry remembers: a mismatch makes uc fetch the wrong driver.
            version_main = _binary_major_version(chrome_bin) or _get_chrome_major_version()
            print_lg(f"  Chrome {version_main or '?'}: {chrome_bin}")
            print_lg(f"  Launching (the first run downloads a driver; giving up after {STEALTH_TIMEOUT}s)...")
            uc_kwargs = {
                "options": _build_options(uc.ChromeOptions()),
                "browser_executable_path": chrome_bin,
            }
            if version_main:
                uc_kwargs["version_main"] = version_main
            return _with_timeout(lambda: uc.Chrome(**uc_kwargs), STEALTH_TIMEOUT)
        except Exception as e:
            critical_error_log(
                "Stealth mode could not start (undetected_chromedriver). "
                "Falling back to the standard driver — LinkedIn is more likely "
                "to flag the session.",
                e,
            )
            _cleanup_residual_chromedriver()

    print_lg("Starting Chrome...")
    return webdriver.Chrome(options=_build_options(ChromeOptions()))


try:
    driver = _start_driver()
except Exception as e:
    critical_error_log("Chrome could not be started", e)
    print_lg("")
    print_lg("Chrome did not start. The usual causes are:")
    print_lg("  - Chrome is not installed, or is too old for the driver")
    print_lg("  - another Chrome is already using this profile: close it and retry")
    print_lg("  - stealth mode is behind a fresh Chrome release: set")
    print_lg("    stealth_mode = False in config/settings.py")
    sys.exit(1)

wait = WebDriverWait(driver, WAIT_TIMEOUT)
actions = ActionChains(driver)

try:
    driver.maximize_window()
except Exception:
    # Headless and some window managers reject this; harmless either way
    pass
