'''
Module: external_apply.py — Universal Applier v1

Handles jobs whose Apply button leads OUTSIDE LinkedIn (non Easy Apply).

Flow:
1. Click the external Apply button and capture the URL of the tab that opens.
   The link is always recorded, so nothing is lost even when auto-fill is off.
2. If `external_apply_enabled` is False (default), the job is left for manual
   review with its direct application link.
3. If enabled, the ATS platform is detected:
   - Greenhouse / Lever / Ashby / generic single-page forms → auto-fill using
     config data (personals/questions), the QA database, and the AI client.
   - Workday / iCIMS / account-walled platforms → collected for manual review
     (multi-step signup flows are NOT automated in v1: they require account
     creation, email verification and usually CAPTCHA).
4. Submit is only clicked when every required field could be answered, and
   `pause_before_submit_external` (default True) asks for confirmation first.

File location: modules/external_apply.py
'''

import os
import re
import time
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from modules.open_chrome import driver, wait, actions
from modules.helpers import print_lg, critical_error_log, buffer
from modules.ai.qa_database import get_from_qa_database, save_to_qa_database


# ── Config (soft imports so missing flags never crash the bot) ─────────────────

def _cfg(module_name: str, var: str, default):
    try:
        mod = __import__(f"config.{module_name}", fromlist=[var])
        return getattr(mod, var, default)
    except Exception:
        return default


def _personal_field_map() -> list[tuple[re.Pattern, str]]:
    """Ordered (label-pattern → answer) mapping for standard ATS fields."""
    p = lambda v: _cfg("personals", v, "")
    q = lambda v: _cfg("questions", v, "")
    full_name = " ".join(x for x in (p("first_name"), p("middle_name"), p("last_name")) if x)
    pairs = [
        (r"\bfull ?name\b|nombre completo", full_name),
        (r"\bfirst ?name\b|\bnombre\b", p("first_name")),
        (r"\blast ?name\b|surname|apellido", p("last_name")),
        (r"e-?mail|correo", p("email") or _cfg("secrets", "username", "")),
        (r"phone|tel[eé]fono|mobile|celular", str(p("phone_number"))),
        (r"linkedin", q("linkedIn")),
        (r"website|portfolio|github|sitio web", q("website")),
        (r"\bcity\b|ciudad|location|ubicaci[oó]n", p("current_city")),
        (r"\bstate\b|provincia|departamento", p("state")),
        (r"zip|postal", str(p("zipcode"))),
        (r"country|pa[ií]s", p("country")),
        (r"salary|salario|compensation|expectativa", str(q("desired_salary") or "")),
        (r"years? of experience|años de experiencia", str(q("years_of_experience"))),
        (r"university|college|universidad|school", p("university")),
        (r"degree|t[ií]tulo|grado", p("degree")),
        (r"cover ?letter|carta", q("cover_letter")),
    ]
    return [(re.compile(rx, re.I), str(ans)) for rx, ans in pairs if str(ans).strip()]


# ── ATS detection ──────────────────────────────────────────────────────────────

_AUTOFILL_ATS = {
    "greenhouse": ("greenhouse.io",),
    "lever": ("lever.co",),
    "ashby": ("ashbyhq.com",),
}
_MANUAL_ATS = {
    "workday": ("myworkdayjobs.com", "workday.com"),
    "icims": ("icims.com",),
    "successfactors": ("successfactors.com", "sapsf.com"),
    "oraclecloud": ("oraclecloud.com", "taleo.net"),
}


def detect_ats(url: str) -> tuple[str, bool]:
    """Returns (platform_name, can_autofill) for a job application URL."""
    host = urlparse(url).netloc.lower()
    for name, domains in _AUTOFILL_ATS.items():
        if any(d in host for d in domains):
            return name, True
    for name, domains in _MANUAL_ATS.items():
        if any(d in host for d in domains):
            return name, False
    return "unknown", True  # try generic single-page fill; bail out if it looks hostile


# ── Label / field helpers ──────────────────────────────────────────────────────

def _element_label(el) -> str:
    """Best-effort human label for a form element."""
    try:
        el_id = el.get_attribute("id")
        if el_id:
            labels = driver.find_elements(By.CSS_SELECTOR, f'label[for="{el_id}"]')
            if labels and labels[0].text.strip():
                return labels[0].text.strip()
        for attr in ("aria-label", "placeholder", "name"):
            v = el.get_attribute(attr)
            if v and v.strip():
                return v.strip()
        parent_label = el.find_elements(By.XPATH, "./ancestor::label[1]")
        if parent_label and parent_label[0].text.strip():
            return parent_label[0].text.strip()
    except WebDriverException:
        pass
    return ""


def _is_required(el, label: str) -> bool:
    try:
        if el.get_attribute("required") or el.get_attribute("aria-required") == "true":
            return True
    except WebDriverException:
        pass
    return "*" in label or "required" in label.lower() or "obligatorio" in label.lower()


def _resolve_answer(label: str, options: list[str] | None, ai_client, job_description) -> str | None:
    """Answer resolution order: direct config mapping → QA database → AI."""
    for rx, ans in _personal_field_map():
        if rx.search(label):
            return ans
    cached = get_from_qa_database(label, options=options)
    if cached:
        print_lg(f"[External] QA database answer for '{label}': {cached}")
        return cached
    if ai_client:
        qtype = "single_select" if options else "text"
        ans = ai_client.answer_question(
            label, options=options, question_type=qtype,
            job_description=job_description,
            user_information_all=_cfg("questions", "user_information_all", None),
        )
        if isinstance(ans, str) and ans.strip():
            return ans.strip()
    return None


def _fill_select(sel_el, answer: str) -> bool:
    try:
        select = Select(sel_el)
        opts = [o.text.strip() for o in select.options]
        ans_low = answer.lower()
        for i, o in enumerate(opts):
            if o.lower() == ans_low or (o and (ans_low in o.lower() or o.lower() in ans_low)):
                select.select_by_index(i)
                return True
    except WebDriverException:
        pass
    return False


# ── Core form filling ──────────────────────────────────────────────────────────

def _fill_external_form(ai_client, job_description) -> tuple[int, int]:
    """
    Fills every fillable field on the current page.
    Returns (filled_count, unanswered_required_count).
    """
    filled, missing_required = 0, 0

    # Resume upload first — many ATS auto-parse it and prefill the rest
    resume_path = _cfg("questions", "default_resume_path", "")
    if resume_path and os.path.exists(resume_path):
        for finput in driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]'):
            try:
                finput.send_keys(os.path.abspath(resume_path))
                filled += 1
                print_lg("[External] Resume uploaded")
                time.sleep(2)  # let ATS parse the CV
                break
            except WebDriverException:
                continue

    selectors = 'input[type="text"], input[type="email"], input[type="tel"], input[type="url"], input[type="number"], textarea, select'
    for el in driver.find_elements(By.CSS_SELECTOR, selectors):
        try:
            if not el.is_displayed() or not el.is_enabled():
                continue
            if el.get_attribute("value"):
                continue  # already prefilled (by CV parsing or browser)
            label = _element_label(el)
            if not label:
                continue

            if el.tag_name == "select":
                options = [o.text.strip() for o in Select(el).options if o.text.strip()]
                answer = _resolve_answer(label, options, ai_client, job_description)
                if answer and _fill_select(el, answer):
                    filled += 1
                    save_to_qa_database(label, answer, options=options)
                elif _is_required(el, label):
                    missing_required += 1
            else:
                answer = _resolve_answer(label, None, ai_client, job_description)
                if answer:
                    el.clear()
                    el.send_keys(answer)
                    filled += 1
                    save_to_qa_database(label, answer)
                elif _is_required(el, label):
                    missing_required += 1
                    print_lg(f"[External] No answer for required field: '{label}'")
        except WebDriverException:
            continue

    return filled, missing_required


def _looks_like_account_wall() -> bool:
    src = driver.page_source.lower()
    return any(k in src for k in ("create account", "sign in to apply", "crear cuenta", "registrarse para aplicar", "create an account"))


def _find_submit_button():
    xpaths = [
        '//button[@type="submit" and not(@disabled)]',
        '//button[contains(translate(., "SUBMIT APLICAR ENVIAR", "submit aplicar enviar"), "submit")]',
        '//button[contains(., "Enviar") or contains(., "Aplicar") or contains(., "Apply")]',
        '//input[@type="submit"]',
    ]
    for xp in xpaths:
        els = [e for e in driver.find_elements(By.XPATH, xp) if e.is_displayed()]
        if els:
            return els[0]
    return None


def _submission_succeeded(url_before: str) -> bool:
    time.sleep(3)
    try:
        if driver.current_url != url_before:
            return True
        src = driver.page_source.lower()
        return any(k in src for k in ("thank you", "application received", "successfully submitted",
                                      "gracias por", "solicitud recibida", "hemos recibido"))
    except WebDriverException:
        return False


# ── Public entry point ─────────────────────────────────────────────────────────

def external_apply(job_id, job_link, resume, date_listed, application_link,
                   screenshot_name, tabs_count=0, ai_client=None,
                   job_description=None) -> tuple[bool, str, int]:
    """
    Handle a non-Easy-Apply job. Returns (skip, application_link, tabs_count):
    skip=False only when the application was actually submitted on the
    external site — the caller then records it as applied.
    """
    from modules.bot_ui import ui_confirm, ui_update_status
    close_tabs = _cfg("settings", "close_tabs", False)
    enabled = _cfg("settings", "external_apply_enabled", False)
    pause = _cfg("settings", "pause_before_submit_external", True)
    linkedin_tab = driver.current_window_handle

    try:
        # 1. Open the external application page
        tabs_before = driver.window_handles
        try:
            apply_btn = driver.find_element(By.XPATH, ".//button[contains(@class,'jobs-apply-button')]")
            driver.execute_script("arguments[0].click();", apply_btn)
        except NoSuchElementException:
            print_lg("[External] No Apply button found, skipping job.")
            return True, application_link, tabs_count
        buffer(2)

        new_tabs = [h for h in driver.window_handles if h not in tabs_before]
        if not new_tabs:
            print_lg("[External] Apply did not open a new tab, skipping.")
            return True, application_link, tabs_count

        driver.switch_to.window(new_tabs[0])
        tabs_count += 1
        for _ in range(10):  # wait for redirects to settle
            time.sleep(1)
            if driver.current_url not in ("about:blank", "") and "linkedin.com" not in driver.current_url:
                break
        application_link = driver.current_url
        print_lg(f"[External] Application link: {application_link}")

        if not enabled:
            print_lg("[External] Auto-fill disabled (external_apply_enabled=False). Link recorded for manual review.")
            return True, application_link, tabs_count

        # 2. Platform triage
        platform, can_autofill = detect_ats(application_link)
        print_lg(f"[External] Detected ATS: {platform} (autofill={can_autofill})")
        if not can_autofill or _looks_like_account_wall():
            print_lg(f"[External] {platform} requires an account/multi-step signup — left for manual review.")
            return True, application_link, tabs_count

        # 3. Fill the form
        ui_update_status("External Apply", f"Filling {platform} application…")
        filled, missing = _fill_external_form(ai_client, job_description)
        print_lg(f"[External] Filled {filled} fields, {missing} required fields unanswered.")
        if filled == 0 or missing > 0:
            print_lg("[External] Form incomplete — left for manual review (tab stays open).")
            return True, application_link, tabs_count

        # 4. Submit
        submit = _find_submit_button()
        if not submit:
            print_lg("[External] No submit button found — left for manual review.")
            return True, application_link, tabs_count
        if pause:
            decision = ui_confirm(
                "External application ready",
                f"The {platform} form was filled automatically.\nReview the tab and choose:",
                ["Submit", "Leave for manual review"],
            )
            if decision != "Submit":
                return True, application_link, tabs_count

        url_before = driver.current_url
        driver.execute_script("arguments[0].click();", submit)
        if _submission_succeeded(url_before):
            print_lg(f"[External] ✅ Application submitted on {platform}!")
            return False, application_link, tabs_count
        print_lg("[External] Could not confirm submission — left for manual review.")
        return True, application_link, tabs_count

    except Exception as e:
        critical_error_log("In external_apply", e)
        return True, application_link, tabs_count
    finally:
        try:
            if close_tabs and driver.current_window_handle != linkedin_tab:
                driver.close()
            driver.switch_to.window(linkedin_tab)
        except WebDriverException:
            try:
                driver.switch_to.window(linkedin_tab)
            except WebDriverException:
                pass
