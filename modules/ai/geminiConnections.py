"""Google Gemini client for the CV tools.

The job-application path uses `modules.ai.providers.GeminiProvider`; this file
exists only for the two callers that build a client directly — the CV Optimizer
and the CV wizard — because they run outside the provider abstraction.

Public surface:
    gemini_create_client() -> GenerativeModel | None
    gemini_completion(model, prompt, is_json=False) -> dict | str | None
"""

from __future__ import annotations

import importlib
import sys

from modules.helpers import convert_to_json, critical_error_log, print_lg

# Gemini refuses plenty of harmless resume text under its default thresholds —
# job descriptions mention "aggressive targets", "kill the competition" and
# similar. Blocking none keeps the CV tools usable; nothing here is user-facing
# content generation.
_SAFETY = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

_TEMPERATURE = 0.3
_MAX_TOKENS = 8192


def _current_secrets() -> dict:
    """Re-read config/secrets.py so a key changed in the UI takes effect."""
    try:
        if "config.secrets" in sys.modules:
            mod = importlib.reload(sys.modules["config.secrets"])
        else:
            mod = importlib.import_module("config.secrets")
        return {k: getattr(mod, k) for k in ("llm_api_key", "llm_model") if hasattr(mod, k)}
    except Exception as e:
        critical_error_log("Could not read config/secrets.py", e)
        return {}


def gemini_create_client():
    """Configure the SDK and return a model handle, or None on failure."""
    ajustes = _current_secrets()
    clave = str(ajustes.get("llm_api_key") or "").strip()
    modelo = str(ajustes.get("llm_model") or "").strip() or "gemini-2.5-flash"

    if not clave:
        print_lg("There is no llm_api_key in config/secrets.py.")
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        print_lg("google-generativeai is not installed. Run: pip install google-generativeai")
        return None

    try:
        genai.configure(api_key=clave)
        print_lg(f"Gemini client ready ({modelo}).")
        return genai.GenerativeModel(modelo)
    except Exception as e:
        critical_error_log("Could not create the Gemini client", e)
        return None


def gemini_completion(model, prompt: str, is_json: bool = False) -> dict | str | None:
    """Send a prompt and return the reply, parsed as JSON when asked.

    Returns None instead of raising: both callers already report a friendly
    error and fall back, and a traceback here would kill a CV generation that
    is otherwise recoverable.
    """
    if model is None:
        print_lg("The Gemini client is not available.")
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        print_lg("google-generativeai is not installed.")
        return None

    config = genai.types.GenerationConfig(
        temperature=_TEMPERATURE,
        max_output_tokens=_MAX_TOKENS,
        # Asking for JSON at the API level beats asking in the prompt: the model
        # cannot then wrap the object in ```json fences or chatty preamble.
        response_mime_type="application/json" if is_json else "text/plain",
    )

    try:
        print_lg("Calling the Gemini API...")
        respuesta = model.generate_content(
            prompt, generation_config=config, safety_settings=_SAFETY
        )
    except Exception as e:
        critical_error_log("The Gemini call failed", e)
        return None

    texto = ""
    try:
        texto = respuesta.text or ""
    except Exception:
        # .text raises when the reply was blocked or came back empty; dig the
        # parts out by hand so a partial answer is not thrown away.
        try:
            partes = []
            for cand in getattr(respuesta, "candidates", []) or []:
                for parte in getattr(getattr(cand, "content", None), "parts", []) or []:
                    if getattr(parte, "text", None):
                        partes.append(parte.text)
            texto = "".join(partes)
        except Exception:
            texto = ""

    if not texto.strip():
        motivo = ""
        try:
            fb = getattr(respuesta, "prompt_feedback", None)
            if fb and getattr(fb, "block_reason", None):
                motivo = f" (blocked: {fb.block_reason})"
        except Exception:
            pass
        print_lg(f"Gemini returned an empty reply{motivo}.")
        return None

    return convert_to_json(texto) if is_json else texto
