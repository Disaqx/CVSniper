'''
Module: external_apply.py — Universal Applier v2

Handles jobs whose Apply button leads OUTSIDE LinkedIn (non Easy Apply).

Flow:
1. `probe_apply_button()` clicks the job's Apply button ONCE and says what
   happened: the Easy Apply modal opened, an external page opened, or nothing.
   It is the single place that clicks Apply — v1 clicked it twice (once to
   detect, once to apply) and the second click found nothing, which is the
   "Apply did not open a new tab, skipping" that filled the logs.
2. The external address is always recorded, so nothing is lost even when
   auto-fill is off.
3. If `external_apply_enabled` is True the page is reopened in a tab of our
   own and the ATS is triaged:
   - Greenhouse / Lever / Ashby / generic single-page forms → auto-fill from
     config (personals/questions), the QA database and the AI client.
   - Workday / iCIMS / account-walled platforms → link recorded for manual
     review (multi-step signup needs an account, email verification and
     usually CAPTCHA).
4. Submit is only clicked when every required field could be answered.
   `pause_before_submit_external` asks for confirmation first when True.
5. The tab is closed either way, so a long run does not bury Chrome in tabs.

File location: modules/external_apply.py
'''

import os
import re
import time
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from modules.open_chrome import driver
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
        (r"\bfirst ?name\b|\bgiven name\b|\bnombre\b", p("first_name")),
        (r"\blast ?name\b|surname|family name|apellido", p("last_name")),
        (r"e-?mail|correo", p("email") or _cfg("secrets", "username", "")),
        (r"phone|tel[eé]fono|mobile|celular|n[uú]mero", str(p("phone_number"))),
        (r"linkedin", q("linkedIn")),
        (r"github", q("website")),
        (r"website|portfolio|sitio web|personal site", q("website")),
        (r"\bcity\b|ciudad|location|ubicaci[oó]n|where are you based", p("current_city")),
        (r"\bstate\b|provincia|departamento|region", p("state")),
        (r"zip|postal", str(p("zipcode"))),
        (r"country|pa[ií]s", p("country")),
        (r"salary|salario|compensation|expectativa|pretensi[oó]n", str(q("desired_salary") or "")),
        (r"years? of experience|años de experiencia|a[nñ]os de experiencia", str(q("years_of_experience"))),
        (r"university|college|universidad|school|escuela", p("university")),
        (r"degree|t[ií]tulo|grado|education", p("degree")),
        (r"cover ?letter|carta de presentaci[oó]n", q("cover_letter")),
        (r"current company|empresa actual|employer", q("recent_employer")),
    ]
    return [(re.compile(rx, re.I), str(ans)) for rx, ans in pairs if str(ans).strip()]


# ── ATS detection ──────────────────────────────────────────────────────────────

_AUTOFILL_ATS = {
    "greenhouse": ("greenhouse.io",),
    "lever": ("lever.co",),
    "ashby": ("ashbyhq.com",),
    "workable": ("workable.com",),
    "recruitee": ("recruitee.com",),
    "smartrecruiters": ("smartrecruiters.com",),
    "breezy": ("breezy.hr",),
    "teamtailor": ("teamtailor.com",),
}
_MANUAL_ATS = {
    "workday": ("myworkdayjobs.com", "workday.com"),
    "icims": ("icims.com",),
    "successfactors": ("successfactors.com", "sapsf.com"),
    "oraclecloud": ("oraclecloud.com", "taleo.net"),
    "brassring": ("brassring.com", "kenexa.com"),
    "eightfold": ("eightfold.ai",),
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


# ── Reaching the external page ─────────────────────────────────────────────────

_APPLY_BTN_XP = (
    ".//button[contains(@class,'jobs-apply-button')] | "
    ".//a[contains(@class,'jobs-apply-button')]"
)


def _is_linkedin(url: str) -> bool:
    return "linkedin.com" in (url or "")


def _settled_url(timeout: float = 10) -> str | None:
    """
    Waits for the current tab to come to rest on a page outside LinkedIn.
    Apply links are usually a redirect chain (LinkedIn tracker → ATS → the
    form), so the first URL seen is rarely the one worth recording.
    """
    fin = time.time() + timeout
    ultima = None
    while time.time() < fin:
        try:
            actual = driver.current_url
        except WebDriverException:
            return None
        if actual and actual != "about:blank" and not _is_linkedin(actual):
            if actual == ultima:      # two reads in a row agree → chain finished
                return actual
            ultima = actual
        time.sleep(0.7)
    return ultima


def probe_apply_button(linkedin_tab: str) -> tuple[str, str | None]:
    """
    Clicks the job's Apply button once and classifies the outcome.

    Returns (kind, url):
      'easy_apply' — the Easy Apply modal opened (url is None)
      'external'   — an application page outside LinkedIn was reached; `url` is
                     its settled address and the browser is back on
                     `linkedin_tab` with no stray tabs left behind
      'none'       — the click led nowhere usable

    Both ways LinkedIn can send you out are handled: a new tab (the common
    case) and navigating this very tab. v1 only looked for a new tab, so
    same-tab redirects were reported as "Apply did not open a new tab".
    """
    try:
        apply_btn = driver.find_element(By.XPATH, _APPLY_BTN_XP)
    except NoSuchElementException:
        return "none", None

    tabs_before = set(driver.window_handles)
    url_before = driver.current_url
    try:
        # When Apply is a plain link, force it to open in its own tab. Letting
        # it navigate this one works, but coming back re-renders the results
        # and every job element the caller is holding goes stale. A <button>
        # ignores this, which is fine — those call window.open() themselves.
        driver.execute_script(
            "if (arguments[0].tagName === 'A') { arguments[0].target = '_blank'; }",
            apply_btn)
    except WebDriverException:
        pass
    try:
        driver.execute_script("arguments[0].click();", apply_btn)
    except WebDriverException:
        try:
            apply_btn.click()
        except WebDriverException:
            return "none", None

    fin = time.time() + 12
    while time.time() < fin:
        time.sleep(0.5)
        try:
            nuevas = [h for h in driver.window_handles if h not in tabs_before]
        except WebDriverException:
            break

        if nuevas:
            # A tab opened. Read where it lands, then close it: external_apply()
            # reopens the address itself, which keeps tab bookkeeping in one
            # place and works the same for the same-tab case below.
            try:
                driver.switch_to.window(nuevas[0])
                url = _settled_url()
            except WebDriverException:
                url = None
            for h in nuevas:
                try:
                    driver.switch_to.window(h)
                    driver.close()
                except WebDriverException:
                    pass
            try:
                driver.switch_to.window(linkedin_tab)
            except WebDriverException:
                pass
            return ("external", url) if url else ("none", None)

        try:
            if driver.find_elements(By.CLASS_NAME, "jobs-easy-apply-modal"):
                return "easy_apply", None
            actual = driver.current_url
        except WebDriverException:
            break

        if actual != url_before and not _is_linkedin(actual):
            # LinkedIn navigated this very tab to the ATS. Rare now that links
            # are forced to _blank above; going back re-renders the results
            # page, so the caller's job elements may go stale and cost it the
            # rest of that page (it moves on to the next search term).
            url = _settled_url() or actual
            print_lg("[External] Apply navigated the LinkedIn tab — going back.")
            try:
                driver.back()
                buffer(3)
            except WebDriverException:
                pass
            return "external", url

    return "none", None


# ── Label / field helpers ──────────────────────────────────────────────────────

# `input` with no type attribute defaults to text, and plenty of ATS omit it —
# the v1 selector missed every one of those fields.
_FILL_SELECTOR = (
    'input:not([type]), input[type="text"], input[type="email"], input[type="tel"], '
    'input[type="url"], input[type="number"], input[type="search"], textarea, select'
)
_CHOICE_SELECTOR = 'input[type="checkbox"], input[type="radio"]'
_COMBO_SELECTOR = (
    '[role="combobox"], [aria-haspopup="listbox"], .select__control, '
    '.select-shell__control'
)


def _element_label(el) -> str:
    """Best-effort human label for a form element."""
    try:
        el_id = el.get_attribute("id")
        if el_id:
            # CSS cannot escape every id an ATS invents; XPath takes it literally.
            labels = driver.find_elements(By.XPATH, f'//label[@for={_xp_literal(el_id)}]')
            if labels and labels[0].text.strip():
                return labels[0].text.strip()
        for attr in ("aria-label", "placeholder", "name", "data-qa"):
            v = el.get_attribute(attr)
            if v and v.strip():
                return v.strip()
        by_labelledby = el.get_attribute("aria-labelledby")
        if by_labelledby:
            for ref in by_labelledby.split():
                found = driver.find_elements(By.ID, ref)
                if found and found[0].text.strip():
                    return found[0].text.strip()
        parent_label = el.find_elements(By.XPATH, "./ancestor::label[1]")
        if parent_label and parent_label[0].text.strip():
            return parent_label[0].text.strip()
        # Last resort: the nearest preceding text in the field's own group.
        group = el.find_elements(By.XPATH, "./ancestor::*[self::div or self::fieldset][1]")
        if group and group[0].text.strip():
            return group[0].text.strip().split("\n")[0]
    except WebDriverException:
        pass
    return ""


def _xp_literal(value: str) -> str:
    """Quotes a string for XPath, including values containing quotes."""
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    partes = value.split('"')
    return "concat(" + ', \'"\', '.join(f'"{p}"' for p in partes) + ")"


def _is_required(el, label: str) -> bool:
    try:
        if el.get_attribute("required") or el.get_attribute("aria-required") == "true":
            return True
    except WebDriverException:
        pass
    low = label.lower()
    return "*" in label or "required" in low or "obligatorio" in low or "requerido" in low


# Consent boxes ("I have read the privacy policy") are required on nearly every
# Greenhouse and Lever form. v1 had no idea what to do with them, counted them
# as unanswered and bailed out of every single application because of it.
_CONSENT_HINTS = (
    "privacy", "privacidad", "terms", "términos", "terminos", "consent",
    "consentimiento", "acepto", "i agree", "i accept", "i acknowledge",
    "i have read", "he leído", "he leido", "gdpr", "data protection",
    "protección de datos", "proteccion de datos", "autorizo",
)
_AFFIRMATIVE = ("yes", "sí", "si", "i agree", "acepto", "true", "authorized", "autorizado")


def _looks_like_consent(label: str) -> bool:
    low = label.lower()
    return any(h in low for h in _CONSENT_HINTS)


def _group_question(el) -> str:
    """
    The question a radio belongs to, which is NOT its own label: asking
    _element_label() for it gives back "Yes", and answering the question "Yes?"
    is how you get a confidently wrong choice.
    """
    for xp in ("./ancestor::fieldset[1]//legend[1]",
               "./ancestor::*[@role='radiogroup'][1]",
               "./ancestor::fieldset[1]",
               "./ancestor::div[2]"):
        try:
            found = el.find_elements(By.XPATH, xp)
        except WebDriverException:
            continue
        if found:
            texto = (found[0].text or "").strip()
            if texto:
                return texto.split("\n")[0]
    return ""


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
        try:
            ans = ai_client.answer_question(
                label, options=options, question_type=qtype,
                job_description=job_description,
                user_information_all=_cfg("questions", "user_information_all", None),
            )
        except Exception as e:
            print_lg(f"[External] AI could not answer '{label}': {e}")
            return None
        if isinstance(ans, str) and ans.strip():
            return ans.strip()
    return None


def _fill_select(sel_el, answer: str) -> bool:
    try:
        select = Select(sel_el)
        opts = [o.text.strip() for o in select.options]
        ans_low = answer.lower()
        for i, o in enumerate(opts):
            if o.lower() == ans_low:
                select.select_by_index(i)
                return True
        for i, o in enumerate(opts):
            if o and (ans_low in o.lower() or o.lower() in ans_low):
                select.select_by_index(i)
                return True
    except WebDriverException:
        pass
    return False


def _fill_combobox(combo, answer: str) -> bool:
    """
    React comboboxes (Greenhouse's react-select, Ashby) have no <option> tags:
    you open the list, type, and click the option that appears.
    """
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", combo)
        combo.click()
        time.sleep(0.4)
        try:
            combo.send_keys(answer)
        except WebDriverException:
            entrada = combo.find_elements(By.CSS_SELECTOR, "input")
            if entrada:
                entrada[0].send_keys(answer)
        time.sleep(0.8)
        opciones = [o for o in driver.find_elements(
            By.CSS_SELECTOR, '[role="option"], .select__option, li[role="option"]')
            if o.is_displayed()]
        if not opciones:
            combo.send_keys(Keys.ESCAPE)
            return False
        ans_low = answer.lower()
        elegida = next((o for o in opciones if o.text.strip().lower() == ans_low), None)
        elegida = elegida or next((o for o in opciones if ans_low in o.text.strip().lower()), None)
        elegida = elegida or opciones[0]
        elegida.click()
        time.sleep(0.3)
        return True
    except WebDriverException:
        return False


def _already_answered(el) -> bool:
    try:
        if el.get_attribute("type") in ("checkbox", "radio"):
            return bool(el.is_selected())
        return bool((el.get_attribute("value") or "").strip())
    except WebDriverException:
        return True   # unreadable → do not touch it


# ── Core form filling ──────────────────────────────────────────────────────────

def _upload_resume() -> bool:
    resume_path = _cfg("questions", "default_resume_path", "")
    if not resume_path or not os.path.exists(resume_path):
        print_lg("[External] No resume file configured — skipping upload.")
        return False
    for finput in driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]'):
        try:
            driver.execute_script(
                "arguments[0].style.display='block';"
                "arguments[0].style.visibility='visible';"
                "arguments[0].style.height='1px';arguments[0].style.width='1px';",
                finput)
            finput.send_keys(os.path.abspath(resume_path))
            print_lg("[External] Resume uploaded")
            time.sleep(3)   # let the ATS parse the CV and prefill what it can
            return True
        except WebDriverException:
            continue
    return False


def _fill_choice_inputs(ai_client, job_description) -> tuple[int, list[str]]:
    """Checkboxes and radio groups. Returns (filled, unanswered_required_labels)."""
    filled, pendientes = 0, []
    grupos_hechos = set()

    for el in driver.find_elements(By.CSS_SELECTOR, _CHOICE_SELECTOR):
        try:
            if not el.is_displayed() or not el.is_enabled():
                continue
            tipo = el.get_attribute("type")
            label = _element_label(el)

            if tipo == "checkbox":
                if el.is_selected():
                    continue
                if _looks_like_consent(label) or _is_required(el, label):
                    driver.execute_script("arguments[0].click();", el)
                    filled += 1
                    continue
                continue   # optional, non-consent: leave it alone

            # radio: answer once per group name
            nombre = el.get_attribute("name") or label
            if nombre in grupos_hechos:
                continue
            # XPath rather than CSS: ATS field names carry brackets and dots
            # ("cards[abc][field]") that CSS would read as syntax.
            opciones = [r for r in driver.find_elements(
                By.XPATH, f'//input[@type="radio" and @name={_xp_literal(nombre)}]')
                if r.is_displayed()]
            if any(r.is_selected() for r in opciones):
                grupos_hechos.add(nombre)
                continue
            etiquetas = [(_element_label(r) or "", r) for r in opciones]
            pregunta = _group_question(el) or label
            elegida = None
            if _looks_like_consent(pregunta):
                elegida = next((r for t, r in etiquetas
                                if t.strip().lower() in _AFFIRMATIVE), None)
            if elegida is None:
                respuesta = _resolve_answer(pregunta, [t for t, _ in etiquetas],
                                            ai_client, job_description)
                if respuesta:
                    baja = respuesta.lower()
                    elegida = next((r for t, r in etiquetas if t.strip().lower() == baja), None)
                    elegida = elegida or next((r for t, r in etiquetas
                                               if t and (baja in t.lower() or t.lower() in baja)), None)
                    if elegida is not None:
                        save_to_qa_database(pregunta, respuesta,
                                            options=[t for t, _ in etiquetas])
            if elegida is not None:
                driver.execute_script("arguments[0].click();", elegida)
                filled += 1
                grupos_hechos.add(nombre)
            elif _is_required(el, pregunta):
                pendientes.append(pregunta or nombre)
        except WebDriverException:
            continue

    return filled, pendientes


def _fill_external_form(ai_client, job_description) -> tuple[int, list[str]]:
    """
    Fills every fillable field on the current page.
    Returns (filled_count, unanswered_required_labels).
    """
    from modules.bot_ui import ui_pause_check
    filled, pendientes = 0, []

    # Resume first — many ATS auto-parse it and prefill the rest of the form.
    if _upload_resume():
        filled += 1

    for el in driver.find_elements(By.CSS_SELECTOR, _FILL_SELECTOR):
        try:
            # One AI call per unanswered field, so this loop is as slow as the
            # Easy Apply modal and needs the same escape hatch.
            ui_pause_check()
            if not el.is_displayed() or not el.is_enabled():
                continue
            if _already_answered(el):
                continue   # prefilled by CV parsing or by the browser
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
                    pendientes.append(label)
            else:
                answer = _resolve_answer(label, None, ai_client, job_description)
                if answer:
                    try:
                        el.clear()
                    except WebDriverException:
                        pass
                    el.send_keys(answer)
                    filled += 1
                    save_to_qa_database(label, answer)
                elif _is_required(el, label):
                    pendientes.append(label)
        except WebDriverException:
            continue

    # React comboboxes have no <option> children, so the loop above never sees
    # them. Greenhouse and Ashby put required questions behind these.
    for combo in driver.find_elements(By.CSS_SELECTOR, _COMBO_SELECTOR):
        try:
            ui_pause_check()
            if not combo.is_displayed():
                continue
            if (combo.text or "").strip() and "select" not in (combo.text or "").lower():
                continue   # already shows a chosen value
            label = _element_label(combo)
            if not label:
                continue
            answer = _resolve_answer(label, None, ai_client, job_description)
            if answer and _fill_combobox(combo, answer):
                filled += 1
                save_to_qa_database(label, answer)
            elif _is_required(combo, label):
                pendientes.append(label)
        except WebDriverException:
            continue

    c_filled, c_pend = _fill_choice_inputs(ai_client, job_description)
    filled += c_filled
    pendientes += c_pend

    return filled, pendientes


def _looks_like_account_wall() -> bool:
    """
    True only when the page offers no form AND asks you to log in.

    v1 grepped the whole page source for "create account", which matches inline
    scripts and footer links on pages that have a perfectly fillable form — so
    it walked away from almost everything.
    """
    try:
        campos = driver.find_elements(By.CSS_SELECTOR, _FILL_SELECTOR + ', input[type="file"]')
        if any(e.is_displayed() for e in campos):
            return False
        texto = driver.find_element(By.TAG_NAME, "body").text.lower()
    except WebDriverException:
        return True
    return any(k in texto for k in (
        "create account", "create an account", "sign in to apply", "log in to apply",
        "crear cuenta", "crear una cuenta", "iniciar sesión para", "registrarse para",
    ))


def _find_submit_button():
    xpaths = [
        '//button[@type="submit" and not(@disabled)]',
        '//button[contains(translate(., "SUBMITAPLCRENVÍ", "submitaplcrenví"), "submit")]',
        '//button[contains(., "Enviar") or contains(., "Aplicar") or contains(., "Apply") '
        'or contains(., "Postular")]',
        '//input[@type="submit"]',
        '//*[@role="button" and (contains(., "Submit") or contains(., "Enviar"))]',
    ]
    for xp in xpaths:
        try:
            els = [e for e in driver.find_elements(By.XPATH, xp) if e.is_displayed() and e.is_enabled()]
        except WebDriverException:
            continue
        if els:
            return els[0]
    return None


_CONFIRM_WORDS = (
    "thank you", "thanks for applying", "application received", "application submitted",
    "successfully submitted", "we have received", "we've received",
    "gracias por", "solicitud recibida", "hemos recibido", "postulación enviada",
    "postulacion enviada", "aplicación recibida",
)


def _submission_succeeded(url_before: str, submit_el) -> bool:
    """
    v1 called any URL change a success, so a validation scroll that appended a
    fragment counted as an application sent. Confirmation text is the real
    signal; a vanished form plus a changed URL is the fallback.
    """
    time.sleep(4)
    try:
        if driver.find_elements(By.CSS_SELECTOR, '[aria-invalid="true"]'):
            print_lg("[External] The form came back with validation errors.")
            return False
        texto = driver.find_element(By.TAG_NAME, "body").text.lower()
    except WebDriverException:
        return False

    if any(k in texto for k in _CONFIRM_WORDS):
        return True

    try:
        sigue_visible = submit_el.is_displayed()
    except WebDriverException:
        sigue_visible = False
    try:
        cambio_url = driver.current_url != url_before
    except WebDriverException:
        cambio_url = False
    return (not sigue_visible) and cambio_url


# ── Public entry point ─────────────────────────────────────────────────────────

def external_apply(job_id, job_link, resume, date_listed, application_link,
                   screenshot_name, tabs_count=0, ai_client=None,
                   job_description=None, already_open_url=None) -> tuple[bool, str, int]:
    """
    Handle a non-Easy-Apply job. Returns (skip, application_link, tabs_count):
    skip=False only when the application was actually submitted on the
    external site — the caller then records it as applied.

    `already_open_url` is the address `probe_apply_button()` found while the
    caller was working out whether the job was Easy Apply. Apply is never
    clicked twice for the same job.
    """
    from modules.bot_ui import ui_confirm, ui_update_status, ui_pause_check
    ui_pause_check()
    enabled = _cfg("settings", "external_apply_enabled", False)
    pause = _cfg("settings", "pause_before_submit_external", False)
    # True (the default now) closes every external tab. False keeps the ones
    # that could not be completed, for finishing by hand.
    close_tabs = _cfg("settings", "close_tabs", True)
    linkedin_tab = driver.current_window_handle
    tab_propia = None
    enviada = False

    try:
        # 1. Work out where the application lives
        url = already_open_url
        if not url:
            kind, url = probe_apply_button(linkedin_tab)
            if kind != "external" or not url:
                print_lg("[External] No external application page found, skipping job.")
                return True, application_link, tabs_count
        application_link = url
        print_lg(f"[External] Application link: {url}")

        if not enabled:
            print_lg("[External] Auto-fill disabled (external_apply_enabled=False). "
                     "Link recorded for manual review.")
            return True, application_link, tabs_count

        # 2. Platform triage — before opening anything, so walled ATS cost nothing
        platform, can_autofill = detect_ats(url)
        print_lg(f"[External] Detected ATS: {platform} (autofill={can_autofill})")
        if not can_autofill:
            print_lg(f"[External] {platform} requires an account/multi-step signup — "
                     "left for manual review.")
            return True, application_link, tabs_count

        # 3. Open it in a tab of our own
        driver.switch_to.new_window("tab")
        tab_propia = driver.current_window_handle
        tabs_count += 1
        driver.get(url)
        buffer(3)
        try:
            application_link = driver.current_url or url
        except WebDriverException:
            pass

        if _looks_like_account_wall():
            print_lg("[External] The page asks for an account and shows no form — "
                     "left for manual review.")
            return True, application_link, tabs_count

        # 4. Fill the form
        ui_update_status("External Apply", f"Filling {platform} application…")
        filled, pendientes = _fill_external_form(ai_client, job_description)
        print_lg(f"[External] Filled {filled} fields, "
                 f"{len(pendientes)} required field(s) unanswered.")
        if filled == 0:
            print_lg("[External] Nothing could be filled — left for manual review.")
            return True, application_link, tabs_count
        if pendientes:
            print_lg("[External] Missing required: " + " | ".join(pendientes[:6]))
            return True, application_link, tabs_count

        # 5. Submit — last chance to stop before something leaves under the
        # user's real name.
        ui_pause_check()
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
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", submit)
            driver.execute_script("arguments[0].click();", submit)
        except WebDriverException as e:
            print_lg(f"[External] Could not click submit: {e}")
            return True, application_link, tabs_count

        if _submission_succeeded(url_before, submit):
            enviada = True
            print_lg(f"[External] ✅ Application submitted on {platform}!")
            ui_update_status("External Applied", f"{platform} application sent")
            return False, application_link, tabs_count

        print_lg("[External] Could not confirm submission — left for manual review.")
        return True, application_link, tabs_count

    except Exception as e:
        critical_error_log("In external_apply", e)
        return True, application_link, tabs_count
    finally:
        # A submitted application always closes; an unfinished one closes too
        # unless close_tabs was turned off to finish it by hand.
        try:
            if tab_propia and tab_propia in driver.window_handles and (enviada or close_tabs):
                driver.switch_to.window(tab_propia)
                driver.close()
        except WebDriverException:
            pass
        try:
            driver.switch_to.window(linkedin_tab)
        except WebDriverException:
            pass
