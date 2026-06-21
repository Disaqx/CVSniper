'''
CVSniper - CV Auto-Configuration Wizard

Extrae datos del CV del usuario con IA y configura todos los archivos de config automaticamente.
Llamado en el primer inicio cuando faltan datos personales.
'''

import os
import json
from modules.i18n import T

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PERS   = os.path.join(_BASE, "config", "personals.py")
_QUEST  = os.path.join(_BASE, "config", "questions.py")
_SEARCH = os.path.join(_BASE, "config", "search.py")
_SECR   = os.path.join(_BASE, "config", "secrets.py")

_CV_EXTRACT_PROMPT = """\
You are a professional resume parser. Extract structured information from the CV below.
Return ONLY a valid JSON object — no markdown, no explanation, nothing else.

Fields to extract (use "" or [] or 0 if not found — never omit a field):
{{
  "first_name": "",
  "last_name": "",
  "middle_name": "",
  "phone_number": "",
  "current_city": "",
  "state": "",
  "country": "",
  "zipcode": "",
  "university": "",
  "linkedIn": "",
  "website": "",
  "years_of_experience": 0,
  "recent_employer": "",
  "linkedin_headline": "",
  "linkedin_summary": "",
  "user_information_all": "",
  "search_terms": [],
  "search_location": "",
  "primary_focus_keywords": [],
  "secondary_focus_keywords": []
}}

Rules:
- years_of_experience: integer, estimate from total work history
- linkedin_headline: 6-10 word professional title (e.g. "IT Support Specialist | M365 | Active Directory")
- linkedin_summary: 3-4 sentence professional summary for LinkedIn
- user_information_all: complete 200-300 word professional profile (name, skills, experience, education, achievements) — the AI will use this to answer job screening questions
- search_terms: 5-8 specific LinkedIn job titles matching their profile (e.g. ["IT Support Specialist", "Help Desk Technician", "Technical Support Engineer"])
- search_location: city + country for LinkedIn search (e.g. "Bogota, Colombia")
- primary_focus_keywords: 6-12 lowercase keywords from their main job titles/roles for filtering job listings
- secondary_focus_keywords: 3-6 lowercase keywords for adjacent roles they could do remotely

CV TEXT:
{cv_text}
"""


def run_cv_wizard() -> bool:
    """
    Entry point. Shows the wizard dialog and runs auto-configuration if user uploads CV.
    Returns True if wizard completed (even partially), False if user chose manual setup.
    """
    from modules.bot_ui import ui_confirm, ui_alert, ui_update_status, _is_api_key_missing

    # If API key is not yet configured, can't use AI — guide user to settings first
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

    prompt = _CV_EXTRACT_PROMPT.format(cv_text=cv_text[:12000])  # cap at ~12k chars

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

def _write_data_to_configs(data: dict, cv_path: str):
    from modules.bot_ui import _write_py_var

    def _set(filepath, varname, value):
        if value not in (None, "", [], 0):
            _write_py_var(filepath, varname, value)

    # personals.py
    _set(_PERS, "first_name",   data.get("first_name", ""))
    _set(_PERS, "last_name",    data.get("last_name", ""))
    _set(_PERS, "middle_name",  data.get("middle_name", ""))
    _set(_PERS, "phone_number", data.get("phone_number", ""))
    _set(_PERS, "current_city", data.get("current_city", ""))
    _set(_PERS, "state",        data.get("state", ""))
    _set(_PERS, "country",      data.get("country", ""))
    _set(_PERS, "zipcode",      data.get("zipcode", ""))
    _set(_PERS, "university",   data.get("university", ""))

    # questions.py
    _set(_QUEST, "linkedIn",           data.get("linkedIn", ""))
    _set(_QUEST, "website",            data.get("website", ""))
    _set(_QUEST, "linkedin_headline",  data.get("linkedin_headline", ""))
    _set(_QUEST, "linkedin_summary",   data.get("linkedin_summary", ""))
    _set(_QUEST, "user_information_all", data.get("user_information_all", ""))
    _set(_QUEST, "recent_employer",    data.get("recent_employer", ""))

    yoe = data.get("years_of_experience")
    if yoe and yoe != 0:
        try:
            _write_py_var(_QUEST, "years_of_experience", str(int(yoe)))
        except Exception:
            pass

    if cv_path:
        _write_py_var(_QUEST, "default_resume_path", os.path.normpath(cv_path))

    # search.py
    _set(_SEARCH, "search_terms",            data.get("search_terms", []))
    _set(_SEARCH, "search_location",         data.get("search_location", ""))
    _set(_SEARCH, "primary_focus_keywords",  data.get("primary_focus_keywords", []))
    _set(_SEARCH, "secondary_focus_keywords", data.get("secondary_focus_keywords", []))

    if data.get("primary_focus_keywords"):
        _write_py_var(_SEARCH, "enable_job_focus_filter", True)
