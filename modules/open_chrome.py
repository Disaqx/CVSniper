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
            return uc.Chrome(options=_build_options(uc.ChromeOptions()))
        except Exception as e:
            critical_error_log(
                "Stealth mode could not start (undetected_chromedriver). "
                "Falling back to the standard driver — LinkedIn is more likely "
                "to flag the session.",
                e,
            )

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
