"""Sanity-checks the config files before the bot touches a browser.

The point is to fail in two seconds with a readable message instead of forty
minutes in, halfway through a run, with a TypeError deep inside Selenium. A
typo in `switch_number` or a resume path that no longer exists costs a whole
session otherwise.

Every problem is collected and reported at once. Fixing one error only to hit
the next on the following run is the thing this is meant to avoid.
"""

from __future__ import annotations

import os

from modules.helpers import print_lg

# Values LinkedIn's own filter UI accepts. Anything else is silently ignored by
# the site, which looks like the filter "not working" rather than a typo.
SORT_BY = {"", "Most recent", "Most relevant"}
DATE_POSTED = {"", "Any time", "Past month", "Past week", "Past 24 hours"}
EXPERIENCE_LEVEL = {
    "Internship", "Entry level", "Associate",
    "Mid-Senior level", "Director", "Executive",
}
JOB_TYPE = {
    "Full-time", "Part-time", "Contract", "Temporary",
    "Volunteer", "Internship", "Other",
}
ON_SITE = {"On-site", "Remote", "Hybrid"}
AI_PROVIDERS = {"openai", "deepseek", "gemini", "groq", "ollama", "together"}


class _Report:
    """Collects problems so they can all be shown in one go."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _check_number(r: _Report, name: str, value, *, minimum=None, maximum=None,
                  required: bool = True) -> None:
    if value in ("", None):
        if required:
            r.error(f"{name} is empty — it needs a number.")
        return
    try:
        n = float(value)
    except (TypeError, ValueError):
        r.error(f"{name} = {value!r} is not a number.")
        return
    if minimum is not None and n < minimum:
        r.error(f"{name} = {value} is below the minimum ({minimum}).")
    if maximum is not None and n > maximum:
        r.error(f"{name} = {value} is above the maximum ({maximum}).")


def _check_choice(r: _Report, name: str, value, allowed: set[str]) -> None:
    if value in ("", None):
        return
    if value not in allowed:
        opciones = ", ".join(sorted(x for x in allowed if x))
        r.error(f"{name} = {value!r} is not valid. Use one of: {opciones}")


def _check_list_choice(r: _Report, name: str, values, allowed: set[str]) -> None:
    if not values:
        return
    if not isinstance(values, (list, tuple, set)):
        r.error(f"{name} must be a list, e.g. {name} = []")
        return
    for v in values:
        if v not in allowed:
            opciones = ", ".join(sorted(allowed))
            r.error(f'{name} contains {v!r}, which is not valid. Options: {opciones}')


def _check_bool(r: _Report, name: str, value) -> None:
    if not isinstance(value, bool):
        r.error(
            f"{name} = {value!r} must be True or False, capitalised and without quotes."
        )


def validate_config() -> None:
    """Check every config file and stop the run if something is wrong.

    Raises SystemExit when there are errors, so the caller does not have to
    remember to check a return value.
    """
    r = _Report()

    # -- who you are --------------------------------------------------------
    try:
        from config.personals import first_name, last_name
        if not str(first_name or "").strip():
            r.error("first_name is empty in config/personals.py")
        if not str(last_name or "").strip():
            r.error("last_name is empty in config/personals.py")
    except ImportError as e:
        r.error(f"config/personals.py could not be read: {e}")

    # -- answers and resume -------------------------------------------------
    try:
        from config.questions import (
            confidence_level, current_ctc, default_resume_path,
            desired_salary, notice_period, years_of_experience,
        )
        if not default_resume_path:
            r.error("default_resume_path is empty in config/questions.py")
        elif not os.path.exists(default_resume_path):
            r.error(
                f"The resume was not found at '{default_resume_path}'. "
                "The path is relative to the project folder."
            )
        _check_number(r, "years_of_experience", years_of_experience, minimum=0, maximum=70)
        _check_number(r, "confidence_level", confidence_level, minimum=1, maximum=10)
        _check_number(r, "desired_salary", desired_salary, minimum=0, required=False)
        _check_number(r, "current_ctc", current_ctc, minimum=0, required=False)
        _check_number(r, "notice_period", notice_period, minimum=0, required=False)
    except ImportError as e:
        r.error(f"config/questions.py could not be read: {e}")

    # -- what to search for -------------------------------------------------
    try:
        from config.search import (
            date_posted, experience_level, job_type, on_site,
            search_terms, sort_by, switch_number,
        )
        if not search_terms:
            r.error("search_terms is empty in config/search.py — there is nothing to look for.")
        elif not isinstance(search_terms, (list, tuple)):
            r.error('search_terms must be a list, e.g. ["Help Desk", "IT Support"]')
        _check_number(r, "switch_number", switch_number, minimum=1)
        _check_choice(r, "sort_by", sort_by, SORT_BY)
        _check_choice(r, "date_posted", date_posted, DATE_POSTED)
        _check_list_choice(r, "experience_level", experience_level, EXPERIENCE_LEVEL)
        _check_list_choice(r, "job_type", job_type, JOB_TYPE)
        _check_list_choice(r, "on_site", on_site, ON_SITE)
    except ImportError as e:
        r.error(f"config/search.py could not be read: {e}")

    # -- behaviour ----------------------------------------------------------
    try:
        from config.settings import (
            click_gap, run_in_background, safe_mode, stealth_mode,
        )
        _check_number(r, "click_gap", click_gap, minimum=0, maximum=60)
        for nombre, valor in (
            ("run_in_background", run_in_background),
            ("safe_mode", safe_mode),
            ("stealth_mode", stealth_mode),
        ):
            _check_bool(r, nombre, valor)
        if run_in_background and not safe_mode:
            r.warn(
                "run_in_background with safe_mode off reuses your real Chrome "
                "profile headlessly. If Chrome is already open it will refuse "
                "to start."
            )
    except ImportError as e:
        r.error(f"config/settings.py could not be read: {e}")

    # -- credentials and AI -------------------------------------------------
    try:
        from config.secrets import ai_provider, llm_api_key, llm_api_url, llm_model, use_AI
        _check_bool(r, "use_AI", use_AI)
        if use_AI:
            proveedor = str(ai_provider or "").lower().strip()
            if proveedor not in AI_PROVIDERS:
                r.error(
                    f"ai_provider = {ai_provider!r} is not recognised. "
                    f"Options: {', '.join(sorted(AI_PROVIDERS))}"
                )
            if not str(llm_api_key or "").strip():
                r.error("use_AI is on but llm_api_key is empty in config/secrets.py")
            if not str(llm_model or "").strip():
                r.error("use_AI is on but llm_model is empty in config/secrets.py")
            if not str(llm_api_url or "").strip():
                r.warn("llm_api_url is empty — the provider default will be used.")
    except ImportError as e:
        r.error(f"config/secrets.py could not be read: {e}")

    # -- report -------------------------------------------------------------
    for w in r.warnings:
        print_lg(f"  WARNING: {w}")

    if r.errors:
        print_lg("")
        print_lg("=" * 70)
        print_lg(f" The configuration has {len(r.errors)} problem(s):")
        print_lg("=" * 70)
        for i, e in enumerate(r.errors, 1):
            print_lg(f"  {i}. {e}")
        print_lg("=" * 70)
        print_lg(" Fix them in the config/ files, or from the settings window,")
        print_lg(" and run the bot again.")
        print_lg("")
        raise SystemExit(1)

    print_lg("Configuration checked, everything looks right.")
