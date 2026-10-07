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


def _cleanup_residual_chromedriver():
    """Kill any orphaned chromedriver if launch fails."""
    import platform
    import subprocess
    import time

    if platform.system() == "Windows":
        try:
            subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
        except Exception:
            pass


def _start_driver():
    """Open Chrome, preferring the patched driver when stealth mode is on.

    undetected_chromedriver hides the automation flags LinkedIn looks for, but
    it trails Chrome releases and breaks on upgrade day. When that happens the
    plain Selenium driver still works, so the failure is downgraded to a
    warning rather than killing the run.
    """
    if stealth_mode:
        try:
            import undetected_chromedriver as uc

            print_lg("Starting Chrome in stealth mode...")
            version_main = _get_chrome_major_version()
            uc_kwargs = {"options": _build_options(uc.ChromeOptions())}
            chrome_bin = _find_chrome_binary()
            if chrome_bin:
                uc_kwargs["browser_executable_path"] = chrome_bin
            if version_main:
                uc_kwargs["version_main"] = version_main
            return uc.Chrome(**uc_kwargs)
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
