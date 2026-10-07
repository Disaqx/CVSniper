"""CV Optimizer: turns a PDF resume, or the config files, into a polished PDF.

Despite the name this is not the job-application AI path. Everything the bot
does while applying goes through `modules.ai.providers`, which handles every
backend behind one interface. What is left here is the CV Optimizer the
settings window calls, plus the two thin OpenAI helpers it needs.

Public surface, both called from modules/bot_ui.py:
    ai_optimize_existing_cv(file_path, include_portfolio=False) -> bool
    ai_generate_cv_from_config(include_portfolio=False) -> bool
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import traceback

from openai import OpenAI

from modules.helpers import critical_error_log, print_lg

try:
    from config.secrets import llm_api_key, llm_api_url, llm_model, stream_output
except Exception:
    llm_api_key = llm_api_url = llm_model = ""
    stream_output = False


# ---------------------------------------------------------------------------
# Config reloading
# ---------------------------------------------------------------------------
# The settings window can change the API key while the app is running. Python
# caches modules, so without an explicit reload the optimizer keeps using the
# key it saw at import time and fails with a stale-credentials error that looks
# like the key itself is wrong.

_SECRET_KEYS = (
    "llm_api_url", "llm_api_key", "llm_model",
    "use_AI", "ai_provider", "stream_output", "llm_spec",
)


def _refresh_secrets() -> dict:
    """Re-read config/secrets.py and return the current values."""
    valores: dict = {}
    try:
        if "config.secrets" in sys.modules:
            fresco = importlib.reload(sys.modules["config.secrets"])
        else:
            fresco = importlib.import_module("config.secrets")
        g = globals()
        for k in _SECRET_KEYS:
            if hasattr(fresco, k):
                valores[k] = getattr(fresco, k)
                g[k] = valores[k]
    except Exception as e:
        critical_error_log("Could not reload config/secrets.py", e)
    return valores


# ---------------------------------------------------------------------------
# OpenAI-compatible client
# ---------------------------------------------------------------------------

def ai_create_openai_client() -> OpenAI | None:
    """Build a client for whichever OpenAI-compatible endpoint is configured.

    `llm_api_url` is what makes this work with Groq, DeepSeek, Ollama or
    OpenAI itself — they all speak the same protocol, only the host changes.
    Returns None instead of raising so callers can report a friendly error.
    """
    ajustes = _refresh_secrets()
    clave = ajustes.get("llm_api_key", llm_api_key)
    url = ajustes.get("llm_api_url", llm_api_url)

    if not str(clave or "").strip():
        print_lg("There is no llm_api_key in config/secrets.py.")
        return None

    try:
        if str(url or "").strip():
            return OpenAI(base_url=url, api_key=clave)
        return OpenAI(api_key=clave)
    except Exception as e:
        critical_error_log("Could not create the AI client", e)
        return None


def ai_completion(
    client: OpenAI,
    messages: list[dict],
    response_format: dict | None = None,
    temperature: float = 0,
    stream: bool = stream_output,
) -> str | None:
    """Send a chat completion and return the reply text.

    `response_format` is passed through only when given: not every endpoint
    accepts it, and sending it to one that does not is a hard 400.
    """
    ajustes = _refresh_secrets()
    modelo = ajustes.get("llm_model", llm_model)
    if not modelo:
        print_lg("There is no llm_model in config/secrets.py.")
        return None

    from modules.ai.model_fallback import resolve_model
    modelo = resolve_model(client, modelo)

    kwargs: dict = {"model": modelo, "messages": messages, "temperature": temperature}
    if response_format:
        kwargs["response_format"] = response_format

    try:
        if stream:
            trozos: list[str] = []
            for trozo in client.chat.completions.create(stream=True, **kwargs):
                if trozo.choices and trozo.choices[0].delta.content:
                    texto = trozo.choices[0].delta.content
                    trozos.append(texto)
                    print_lg(texto, end="", flush=True)
            print_lg("")
            return "".join(trozos)

        respuesta = client.chat.completions.create(**kwargs)
        return respuesta.choices[0].message.content
    except Exception as e:
        critical_error_log("The AI call failed", e)
        return None


# ---------------------------------------------------------------------------
# CV Optimizer
# ---------------------------------------------------------------------------

_CV_PROMPT = """\
You are an expert resume writer and career strategist.

CRITICAL LANGUAGE RULE:
- First, detect the language of the RAW CV TEXT below (e.g. Spanish, English).
- Write the ENTIRE optimized CV in that SAME language. Do NOT translate.
  If the CV is in Spanish, every field, title, bullet and section header MUST be in Spanish.

OPTIMIZATION GOALS:
- Make each bullet impactful, metric-driven, and modern (start with strong action verbs).
- Do NOT invent facts, employers, dates, degrees, or numbers that are not in the source.
- Preserve ALL real information, especially:
  * The person's professional title / headline (the role under their name).
  * Every academic degree in the education section, with its institution and year
    (e.g. "Psicologo - Universidad Distrital Francisco Jose de Caldas, 2024").
    Never drop a degree the candidate already holds.
- The raw text may come from a multi-column PDF, so lines can be slightly out of order.
  Use your judgment to correctly pair each job/degree title with its company/institution and date.

Return ONLY a JSON object (no markdown, no commentary) with this EXACT structure:
{
    "name": "Full Name",
    "title": "Professional Title (in the CV's language)",
    "contact": ["Email: x@y.com", "Phone: +123", "Location: City"],
    "sections": [
        {
            "title": "SECTION HEADER (in the CV's language, e.g. EXPERIENCIA / FORMACION ACADEMICA)",
            "subsections": [
                {
                    "title": "Role or Degree at Company/Institution",
                    "date": "2020 - Presente",
                    "bullets": ["Logro 1", "Logro 2"]
                }
            ],
            "bullets": []
        },
        {
            "title": "HABILIDADES",
            "subsections": [],
            "bullets": ["Habilidad A", "Habilidad B"]
        }
    ]
}

Always include an education section containing every degree found in the source.

RAW CV TEXT:
CV_TEXT_PLACEHOLDER"""


def _read_pdf_text(file_path: str) -> str:
    """Pull the text out of a PDF, keeping multi-column layouts readable.

    `sort=True` orders fragments by visual position instead of draw order.
    Without it a two-column resume comes out interleaved line by line, and no
    model can pair a job title with the right employer from that soup.
    """
    import fitz  # pymupdf

    doc = fitz.open(file_path)
    try:
        return "\n".join(page.get_text("text", sort=True) for page in doc)
    finally:
        doc.close()


def _normalize_cv(raw: dict) -> dict:
    """Coerce whatever the model returned into the shape the PDF builder wants.

    Models rename keys and wrap the payload even when the schema is spelled
    out, so the aliases below are the ones seen in practice.
    """
    for envoltorio in ("cv", "resume", "candidate", "data", "result"):
        if isinstance(raw.get(envoltorio), dict):
            raw = raw[envoltorio]
            break

    alias = {
        "name": ("full_name", "candidate_name", "applicant_name", "firstName"),
        "title": ("professional_title", "job_title", "headline", "position"),
        "contact": ("contact_info", "contacts", "contact_details"),
        "sections": ("experience", "experiences", "resume_sections"),
    }
    por_defecto = {"name": "Candidate", "title": "", "contact": [], "sections": []}

    for clave, alternativas in alias.items():
        if clave in raw:
            continue
        for a in alternativas:
            if a in raw:
                raw[clave] = raw[a]
                break
        else:
            raw[clave] = por_defecto[clave]
    return raw


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def ai_optimize_existing_cv(file_path: str, include_portfolio: bool = False) -> bool:
    """Rewrite an existing PDF resume with the AI and render it as a new PDF."""
    try:
        from scripts.generate_cv_fullportfolio import (
            default_projects, generate_cv_pdf_simple,
            generate_full_portfolio, images_dir_default,
        )

        ajustes = _refresh_secrets()
        proveedor = str(ajustes.get("ai_provider", "")).lower()

        texto = _read_pdf_text(file_path)
        print_lg(f"[CV Optimizer] Extracted {len(texto)} chars from PDF")

        prompt = _CV_PROMPT.replace("CV_TEXT_PLACEHOLDER", texto)

        if proveedor == "gemini":
            from modules.ai.geminiConnections import gemini_completion, gemini_create_client
            client = gemini_create_client()
            if not client:
                print_lg("[CV Optimizer] ERROR: the Gemini client is None.")
                return False
            respuesta = gemini_completion(client, prompt, is_json=True)
        else:
            client = ai_create_openai_client()
            if not client:
                print_lg("[CV Optimizer] ERROR: the client is None. Check the API key.")
                return False
            respuesta = ai_completion(
                client,
                [{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )

        if respuesta is None:
            print_lg("[CV Optimizer] ERROR: the AI returned nothing.")
            return False

        if isinstance(respuesta, str):
            limpio = respuesta.strip().strip("`")
            if limpio.startswith("json"):
                limpio = limpio[4:].strip()
            cv = json.loads(limpio)
        else:
            cv = respuesta

        cv = _normalize_cv(cv)
        print_lg(
            f"[CV Optimizer] Normalized: name={cv.get('name')}, "
            f"sections={len(cv.get('sections', []))}"
        )

        nombre = str(cv.get("name", "Optimized")).replace(" ", "_")
        salida = os.path.join(_project_root(), "all resumes", f"{nombre}_CV_Optimized.pdf")
        os.makedirs(os.path.dirname(salida), exist_ok=True)

        try:
            generate_full_portfolio(
                cv, salida, include_portfolio=include_portfolio,
                projects=default_projects, images_dir=images_dir_default,
            )
        except Exception as e:
            print_lg(
                f"[CV Optimizer] Full portfolio failed ({e.__class__.__name__}), "
                "falling back to the simple PDF..."
            )
            generate_cv_pdf_simple(cv, salida)

        print_lg(f"[CV Optimizer] SUCCESS: saved to {salida}")
        return True

    except Exception as e:
        print_lg("[CV Optimizer] EXCEPTION in ai_optimize_existing_cv:")
        traceback.print_exc()
        critical_error_log("ai_optimize_existing_cv failed", e)
        return False


def ai_generate_cv_from_config(include_portfolio: bool = False) -> bool:
    """Build a CV from the details already in config/, with no source PDF."""
    try:
        from scripts.generate_cv_fullportfolio import (
            default_projects, generate_cv_from_basic_info, images_dir_default,
        )
        from modules.bot_ui import _read_py_var

        _refresh_secrets()
        raiz = _project_root()
        personals = os.path.join(raiz, "config", "personals.py")
        questions = os.path.join(raiz, "config", "questions.py")

        nombre = _read_py_var(personals, "first_name") or "John"
        apellido = _read_py_var(personals, "last_name") or "Doe"
        telefono = _read_py_var(personals, "phone_number") or ""
        ciudad = _read_py_var(personals, "current_city") or ""
        region = _read_py_var(personals, "state") or ""
        titulo = _read_py_var(questions, "linkedin_headline") or "Professional"

        salida = os.path.join(raiz, "all resumes", f"{nombre}_{apellido}_CV_Generado.pdf")
        os.makedirs(os.path.dirname(salida), exist_ok=True)

        generate_cv_from_basic_info(
            nombre, apellido, telefono, f"{ciudad}, {region}", titulo, salida,
            include_portfolio=include_portfolio,
            projects=default_projects, images_dir=images_dir_default,
        )
        print_lg(f"[CV Optimizer] SUCCESS: saved to {salida}")
        return True

    except Exception as e:
        print_lg("[CV Optimizer] EXCEPTION in ai_generate_cv_from_config:")
        traceback.print_exc()
        critical_error_log("ai_generate_cv_from_config failed", e)
        return False
