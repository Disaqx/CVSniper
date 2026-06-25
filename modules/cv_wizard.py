'''
CVSniper - CV Auto-Configuration Wizard

Extrae datos del CV del usuario con IA y configura todos los archivos de config automaticamente.
Llamado en el primer inicio cuando faltan datos personales.
'''

import os
import json
from modules.i18n import T

_BASE   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PERS   = os.path.join(_BASE, "config", "personals.py")
_QUEST  = os.path.join(_BASE, "config", "questions.py")
_SEARCH = os.path.join(_BASE, "config", "search.py")
_SECR   = os.path.join(_BASE, "config", "secrets.py")

_LATAM_COUNTRIES = [
    "colombia", "venezuela", "mexico", "peru", "ecuador", "bolivia",
    "argentina", "chile", "paraguay", "uruguay", "cuba", "panama",
    "guatemala", "honduras", "el salvador", "costa rica", "nicaragua",
    "dominican republic", "republica dominicana", "puerto rico", "brazil", "brasil",
]

_CV_EXTRACT_PROMPT = """\
You are a professional resume parser for a LinkedIn job application bot.
Extract structured information from the CV below.
Return ONLY a valid JSON object — no markdown, no explanation, nothing else.

=== CRITICAL NAME PARSING RULES ===
Latin American names follow: [given name(s)] [paternal surname] [maternal surname]
A 3-word name is almost always: given_name + paternal_surname + maternal_surname — NOT given + middle + surname.
A 4-word name is almost always: given_name + middle_given_name + paternal_surname + maternal_surname.

Examples:
  "Camilo Villarraga Sandoval"      → first_name="Camilo"  middle_name=""        last_name="Villarraga Sandoval"
  "Camilo Andres Villarraga Sandoval" → first_name="Camilo" middle_name="Andres"  last_name="Villarraga Sandoval"
  "Camilo Andres Garcia Lopez"      → first_name="Camilo"  middle_name="Andres"  last_name="Garcia Lopez"

RULE: first_name = ONLY the very first word. last_name = ALL surnames (one or two). middle_name = remaining given names only.
NEVER treat a surname as a middle name. NEVER put only the maternal surname in last_name while leaving the paternal surname out.

=== ETHNICITY INFERENCE RULE ===
If country/location is from ANY Spanish-speaking Latin American country or Brazil
(Colombia, Venezuela, Mexico, Peru, Ecuador, Bolivia, Argentina, Chile, Paraguay,
Uruguay, Cuba, Panama, Guatemala, Honduras, El Salvador, Costa Rica, Nicaragua,
Dominican Republic, Puerto Rico, Brazil) → set ethnicity to "Hispanic/Latino"
If from Spain → "White"
If unknown or other → ""
Valid ethnicity values: "Hispanic/Latino", "White", "Black or African American",
"Asian", "American Indian or Alaska Native",
"Native Hawaiian or Other Pacific Islander", "Other", "Decline", ""

=== JOB SEARCH TERMS RULE ===
Based on their actual profession, skills and work experience, generate 6-10 specific
LinkedIn job titles they could realistically apply for. Be specific and match their field.
Examples:
  Psychologist  → ["Clinical Psychologist", "School Psychologist", "Organizational Psychologist",
                    "Mental Health Counselor", "HR Psychologist", "Child Psychologist"]
  System Admin  → ["System Administrator", "IT Support Specialist", "Network Administrator",
                    "Help Desk Technician", "Technical Support Engineer"]
  Accountant    → ["Accountant", "Financial Analyst", "Accounting Analyst",
                    "Tax Accountant", "Bookkeeper", "Finance Assistant"]

=== FIELDS TO EXTRACT ===
Use "" or [] or 0 if not found. Never omit a field.
{
  "first_name": "",
  "last_name": "",
  "middle_name": "",
  "phone_number": "",
  "current_city": "",
  "state": "",
  "country": "",
  "zipcode": "",
  "ethnicity": "",
  "gender": "",
  "university": "",
  "degree": "",
  "graduation_year": "",
  "field_of_study": "",
  "linkedIn": "",
  "website": "",
  "years_of_experience": 0,
  "desired_salary": 0,
  "require_visa": "",
  "recent_employer": "",
  "linkedin_headline": "",
  "linkedin_summary": "",
  "user_information_all": "",
  "search_terms": [],
  "search_location": "",
  "primary_focus_keywords": [],
  "secondary_focus_keywords": []
}

degree must be one of: "High School", "Associate's", "Bachelor's", "Master's", "Doctorate", "Other"
require_visa: "Yes" or "No" if inferable from citizenship/country, else ""
gender: "Male" or "Female" only if explicitly mentioned, else ""
years_of_experience: carefully sum each job duration in years (round DOWN, be conservative). List each position start→end, compute months, total. Do NOT use graduation year. If dates unclear, round down.
search_terms: generate in the SAME LANGUAGE as the CV (Spanish if CV is in Spanish, English if in English)
linkedin_headline: 6-10 word professional title
linkedin_summary: 3-4 sentence professional summary for LinkedIn
user_information_all: 200-300 word complete profile (name, skills, experience, education) the AI uses to answer job screening questions
search_location: city + country for LinkedIn search (e.g. "Bogota, Colombia")
primary_focus_keywords: 6-12 lowercase keywords from main job titles/roles
secondary_focus_keywords: 3-6 lowercase keywords for adjacent roles they could do remotely

CV TEXT:
{cv_text}
"""


def run_cv_wizard() -> bool:
    """
    Entry point. Shows the wizard dialog and runs auto-configuration if user uploads CV.
    Returns True if wizard completed (even partially), False if user chose manual setup.
    """
    from modules.bot_ui import ui_confirm, ui_alert, ui_update_status, _is_api_key_missing

    if _is_api_key_missing():
        ui_alert(T("wiz_api_key_title"), T("wiz_api_key_msg"))
        return False

    choice = ui_confirm(T("wiz_title"), T("wiz_msg"), [T("wiz_btn_upload"), T("wiz_btn_manual")])

    if choice != T("wiz_btn_upload"):
        return False

    from tkinter import filedialog
    file_path = filedialog.askopenfilename(
        title=T("wiz_pdf_dialog"),
        filetypes=[("PDF", "*.pdf"), ("*", "*.*")]
    )

    if not file_path:
        return False

    ui_update_status(T("wiz_status"), T("wiz_detail_pdf"))
    cv_text = _extract_pdf_text(file_path)
    if not cv_text:
        ui_alert(T("wiz_err_pdf_title"), T("wiz_err_pdf_msg"))
        return False

    ui_update_status(T("wiz_status"), T("wiz_detail_ai"))
    data = _call_ai(cv_text)
    if not data:
        ui_alert(T("wiz_err_ai_title"), T("wiz_err_ai_msg"))
        return False

    # Write what the AI extracted
    _write_data_to_configs(data, file_path)

    # Ask one-by-one for every field the AI couldn't fill
    data = _ask_missing_fields(data)
    _write_data_to_configs(data, file_path)

    name  = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or "?"
    terms = data.get("search_terms", [])
    city  = data.get("current_city", "") or data.get("search_location", "") or "?"
    yoe   = data.get("years_of_experience", "?")

    ui_alert(
        T("wiz_done_title"),
        f"{T('wiz_done_name')}:       {name}\n"
        f"{T('wiz_done_city')}:       {city}\n"
        f"{T('wiz_done_exp')}:  {yoe} {T('wiz_done_suffix_exp')}\n"
        f"{T('wiz_done_terms')}:    {len(terms)} {T('wiz_done_suffix_terms')}\n\n"
        f"{T('wiz_done_footer')}"
    )
    return True


# ─── Job Terms Wizard (standalone, no full CV re-upload needed) ──────────────

def run_job_terms_wizard() -> bool:
    """
    If search_terms is empty but a CV is already on file, use AI to generate
    search_terms, primary_focus_keywords, and secondary_focus_keywords.
    Returns True if terms were successfully generated and saved.
    """
    from modules.bot_ui import _read_py_var, _write_py_var, ui_confirm, ui_alert, ui_update_status

    search_terms = _read_py_var(_SEARCH, "search_terms")
    if search_terms and isinstance(search_terms, list) and len(search_terms) > 0:
        return False

    cv_path = str(_read_py_var(_QUEST, "default_resume_path") or "")
    if not cv_path or not os.path.exists(cv_path):
        return False

    choice = ui_confirm(T("job_terms_wiz_title"), T("job_terms_wiz_msg"),
                        [T("job_terms_btn_yes"), T("job_terms_btn_no")])
    if choice != T("job_terms_btn_yes"):
        return False

    ui_update_status(T("wiz_status"), T("wiz_detail_ai"))
    cv_text = _extract_pdf_text(cv_path)
    if not cv_text:
        ui_alert(T("wiz_err_pdf_title"), T("wiz_err_pdf_msg"))
        return False

    data = _call_ai(cv_text)
    if not data:
        ui_alert(T("wiz_err_ai_title"), T("wiz_err_ai_msg"))
        return False

    terms     = data.get("search_terms", [])
    primary   = data.get("primary_focus_keywords", [])
    secondary = data.get("secondary_focus_keywords", [])

    if terms:
        _write_py_var(_SEARCH, "search_terms", terms)
    if primary:
        _write_py_var(_SEARCH, "primary_focus_keywords", primary)
        _write_py_var(_SEARCH, "enable_job_focus_filter", True)
    if secondary:
        _write_py_var(_SEARCH, "secondary_focus_keywords", secondary)

    if terms:
        ui_alert(T("job_terms_done_title"),
                 T("job_terms_done_msg") + "\n".join(f"• {t}" for t in terms))
        return True

    return False


# ─── Ask missing fields one by one ───────────────────────────────────────────

def _ask_missing_fields(data: dict) -> dict:
    """
    For every important field the AI left blank, ask the user directly.
    Uses ui_ask_text for free text and ui_confirm for fixed choices.
    """
    from modules.bot_ui import ui_ask_text, ui_confirm

    title = "Completar configuracion"

    def _missing(key):
        val = data.get(key)
        if val is None or val == "" or val == [] or val == 0:
            return True
        if isinstance(val, str) and not val.strip():
            return True
        return False

    def _ask(key, question, placeholder=""):
        if _missing(key):
            v = ui_ask_text(title, question, placeholder)
            if v:
                data[key] = v

    def _choose(key, question, options):
        if _missing(key):
            choice = ui_confirm(title, question, options[:3])
            if choice:
                data[key] = choice

    # ── 1. Nombre ─────────────────────────────────────────────────────────────
    _ask("first_name",
         "¿Cuál es tu PRIMER nombre?\n"
         "(solo el primero — ej: Camilo)")

    _ask("last_name",
         "¿Cuáles son tus APELLIDOS?\n"
         "(uno o dos apellidos — ej: García López)")

    if _missing("middle_name"):
        v = ui_ask_text(title,
            "¿Tienes segundo nombre? (puedes saltar)", "")
        if v:
            data["middle_name"] = v

    # ── 2. Contacto ───────────────────────────────────────────────────────────
    _ask("phone_number",
         "Número de teléfono con código de país:\n"
         "(ej: 573001234567 para Colombia)")

    # ── 3. Ubicación ──────────────────────────────────────────────────────────
    _ask("current_city",
         "¿En qué ciudad vives actualmente?\n"
         "(ej: Bogotá)")

    _ask("country",
         "¿En qué país vives?\n"
         "(ej: Colombia)")

    _ask("state",
         "¿En qué departamento o estado vives?\n"
         "(ej: Cundinamarca, Antioquia)")

    _ask("zipcode",
         "¿Cuál es tu código postal?\n"
         "(puedes dejarlo vacío si no lo sabes)", "")

    if _missing("search_location"):
        city    = data.get("current_city", "")
        country = data.get("country", "")
        default = f"{city}, {country}".strip(", ") if (city or country) else ""
        v = ui_ask_text(title,
            "¿En qué ciudad/país buscas trabajo?\n"
            "(ej: Bogota, Colombia)",
            default)
        if v:
            data["search_location"] = v

    # ── 4. Cargos a buscar ────────────────────────────────────────────────────
    if _missing("search_terms"):
        v = ui_ask_text(title,
            "¿Qué cargos buscas en LinkedIn?\n"
            "Escribe separados por comas:\n"
            "(ej: Psicólogo clínico, Psicólogo escolar, Psicólogo organizacional)")
        if v:
            data["search_terms"] = [t.strip() for t in v.split(",") if t.strip()]

    # ── 5. Experiencia ────────────────────────────────────────────────────────
    if _missing("years_of_experience"):
        v = ui_ask_text(title, "¿Cuántos años de experiencia laboral tienes?\n(número)")
        if v:
            try:
                data["years_of_experience"] = int(v)
            except Exception:
                data["years_of_experience"] = v

    # ── 6. Educación ──────────────────────────────────────────────────────────
    _ask("university",
         "¿En qué institución estudiaste?\n"
         "(universidad o colegio — ej: Universidad Nacional de Colombia)")

    if _missing("degree"):
        choice = ui_confirm(title, "Nivel educativo más alto completado:",
                            ["Bachelor's", "Master's", "Doctorate"])
        if choice:
            data["degree"] = choice
        else:
            v = ui_ask_text(title,
                "Nivel educativo:\n"
                "High School / Associate's / Bachelor's / Master's / Doctorate / Other")
            if v:
                data["degree"] = v

    _ask("field_of_study",
         "¿Cuál fue tu área de estudio o carrera?\n"
         "(ej: Psicología, Administración de Empresas, Ingeniería de Sistemas)")

    _ask("graduation_year",
         "¿En qué año te graduaste? (ej: 2020)")

    # ── 7. EEO — Etnia ────────────────────────────────────────────────────────
    if _missing("ethnicity"):
        country_lower = str(data.get("country", "")).lower()
        default_eth = "Hispanic/Latino" if any(c in country_lower for c in _LATAM_COUNTRIES) else ""
        if not default_eth or _missing("ethnicity"):
            eth_choice = ui_confirm(title,
                "Origen étnico (formularios EEO de empleadores):",
                ["Hispanic/Latino", "White", "Black or African American"])
            if eth_choice:
                data["ethnicity"] = eth_choice
            else:
                eth2 = ui_confirm(title,
                    "Origen étnico (continuación):",
                    ["Asian", "Other", "Decline"])
                if eth2:
                    data["ethnicity"] = eth2
        else:
            data["ethnicity"] = default_eth

    # ── 8. Género ─────────────────────────────────────────────────────────────
    if _missing("gender"):
        choice = ui_confirm(title,
            "Género (para formularios EEO, puedes saltar):",
            ["Male", "Female", "Decline"])
        if choice:
            data["gender"] = choice if choice != "Decline" else "Decline"

    # ── 9 (nuevo). Discapacidad ───────────────────────────────────────────────
    if _missing("disability_status"):
        choice = ui_confirm(title,
            "¿Tienes alguna discapacidad? (formulario EEO):",
            ["No", "Yes", "Decline"])
        if choice:
            data["disability_status"] = choice

    # ── 9 (nuevo). Veterano ──────────────────────────────────────────────────
    if _missing("veteran_status"):
        choice = ui_confirm(title,
            "¿Eres veterano militar? (formulario EEO):",
            ["No", "Yes", "Decline"])
        if choice:
            data["veteran_status"] = choice

    # ── 9. Visa ───────────────────────────────────────────────────────────────
    if _missing("require_visa"):
        choice = ui_confirm(title,
            "¿Necesitas visa de trabajo para el país donde vas a aplicar?\n"
            "(si aplicas a empleos remotos internacionales responde Yes)",
            ["No", "Yes"])
        if choice:
            data["require_visa"] = choice

    # ── 10. Salario deseado ───────────────────────────────────────────────────
    if _missing("desired_salary"):
        v = ui_ask_text(title,
            "Salario deseado en números (puedes dejar 0 para saltar):", "0")
        if v and v.strip() != "0":
            try:
                data["desired_salary"] = int(v)
            except Exception:
                data["desired_salary"] = v

    # LinkedIn credentials are not asked here — the bot requires the user
    # to already be logged in to LinkedIn in Chrome before starting.

    return data


# ─── PDF Extraction ───────────────────────────────────────────────────────────

def _extract_pdf_text(file_path: str) -> str:
    try:
        import fitz
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
        return text.strip()
    except Exception as e:
        print(f"[CV Wizard] PDF extraction error: {e}")
        return ""


# ─── AI Extraction ───────────────────────────────────────────────────────────

def _call_ai(cv_text: str) -> dict | None:
    from modules.bot_ui import _read_py_var

    provider = str(_read_py_var(_SECR, "ai_provider") or "").lower()
    api_key  = str(_read_py_var(_SECR, "llm_api_key") or "")
    model    = str(_read_py_var(_SECR, "llm_model") or "")
    api_url  = str(_read_py_var(_SECR, "llm_api_url") or "")

    prompt = _CV_EXTRACT_PROMPT.replace("{cv_text}", cv_text[:12000])

    try:
        if provider == "gemini":
            return _call_gemini(prompt)
        elif provider in ("openai", "groq", "deepseek"):
            return _call_openai_compat(api_key, api_url, model, prompt)
        else:
            print(f"[CV Wizard] Unknown provider: {provider}")
            return None
    except Exception as e:
        print(f"[CV Wizard] AI call error: {e}")
        return None


def _call_gemini(prompt: str) -> dict | None:
    try:
        from modules.ai.geminiConnections import gemini_create_client, gemini_completion
        client = gemini_create_client()
        if not client:
            return None
        result = gemini_completion(client, prompt, is_json=True)
        if isinstance(result, dict):
            return result
        if isinstance(result, str):
            return json.loads(result)
        return None
    except Exception as e:
        print(f"[CV Wizard] Gemini error: {e}")
        return None


def _call_openai_compat(api_key: str, base_url: str, model: str, prompt: str) -> dict | None:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        return json.loads(raw)
    except Exception as e:
        print(f"[CV Wizard] OpenAI-compat error: {e}")
        return None


# ─── Write to config files ────────────────────────────────────────────────────

def _write_data_to_configs(data: dict, cv_path: str = ""):
    from modules.bot_ui import _write_py_var

    def _set(filepath, varname, value):
        if value not in (None, "", [], 0):
            _write_py_var(filepath, varname, value)

    # ── personals.py ──────────────────────────────────────────────────────────
    _set(_PERS, "first_name",        data.get("first_name", ""))
    _set(_PERS, "last_name",         data.get("last_name", ""))
    _set(_PERS, "middle_name",       data.get("middle_name", ""))
    _set(_PERS, "phone_number",      data.get("phone_number", ""))
    _set(_PERS, "current_city",      data.get("current_city", ""))
    _set(_PERS, "state",             data.get("state", ""))
    _set(_PERS, "country",           data.get("country", ""))
    _set(_PERS, "zipcode",           data.get("zipcode", ""))
    _set(_PERS, "university",        data.get("university", ""))
    _set(_PERS, "degree",            data.get("degree", ""))
    _set(_PERS, "graduation_year",   data.get("graduation_year", ""))
    _set(_PERS, "field_of_study",    data.get("field_of_study", ""))
    _set(_PERS, "ethnicity",         data.get("ethnicity", ""))
    _set(_PERS, "gender",            data.get("gender", ""))
    _set(_PERS, "disability_status", data.get("disability_status", ""))
    _set(_PERS, "veteran_status",    data.get("veteran_status", ""))

    # ── questions.py ──────────────────────────────────────────────────────────
    _set(_QUEST, "linkedIn",             data.get("linkedIn", ""))
    _set(_QUEST, "website",              data.get("website", ""))
    _set(_QUEST, "linkedin_headline",    data.get("linkedin_headline", ""))
    _set(_QUEST, "linkedin_summary",     data.get("linkedin_summary", ""))
    _set(_QUEST, "user_information_all", data.get("user_information_all", ""))
    _set(_QUEST, "recent_employer",      data.get("recent_employer", ""))
    _set(_QUEST, "require_visa",         data.get("require_visa", ""))

    yoe = data.get("years_of_experience")
    if yoe and yoe != 0:
        try:
            _write_py_var(_QUEST, "years_of_experience", str(int(yoe)))
        except Exception:
            pass

    sal = data.get("desired_salary")
    if sal and sal != 0:
        try:
            _write_py_var(_QUEST, "desired_salary", int(sal))
        except Exception:
            pass

    if cv_path:
        _write_py_var(_QUEST, "default_resume_path", os.path.normpath(cv_path))

    # ── search.py ─────────────────────────────────────────────────────────────
    _set(_SEARCH, "search_terms",             data.get("search_terms", []))
    _set(_SEARCH, "search_location",          data.get("search_location", ""))
    _set(_SEARCH, "primary_focus_keywords",   data.get("primary_focus_keywords", []))
    _set(_SEARCH, "secondary_focus_keywords", data.get("secondary_focus_keywords", []))

    if data.get("primary_focus_keywords"):
        _write_py_var(_SEARCH, "enable_job_focus_filter", True)
