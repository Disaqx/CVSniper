# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**CVSniper** — a Python bot that automates LinkedIn Easy Apply job applications. It combines Selenium browser automation, a Tkinter floating control window, a Flask web dashboard, and optional AI assistance (multiple LLM providers) to find, filter, and fill out job applications.

## Running the bot

```bash
pip install -r requirements.txt
python runAiBot.py
```

On first run, config templates are auto-copied from `config/*.default.py` → `config/*.py`. The bot then opens Chrome, shows the Tkinter control window, and starts the Flask dashboard at `http://127.0.0.1:5000`.

**Keyboard shortcuts (while bot is running):**
- `Ctrl+P` — pause / resume
- `Ctrl+Q` / `Ctrl+C` — stop (5-second forced exit fallback)

## Building a release

```bash
python scripts/build_release.py
```

Produces `CVSniper_Release/` (folder) and `CVSniper_Release.zip`. The IGNORE set in `build_release.py` must include any temp/output dirs added to the project root, or they'll be copied into themselves recursively.

## Architecture

### Entry point: `runAiBot.py`
A single large file (~4500 lines) that is the main orchestrator. It:
1. Auto-copies missing config templates
2. Initializes Chrome via `modules/open_chrome.py`
3. Starts the UI (Tkinter + Flask) via `modules/bot_ui.py`
4. Imports all config with `from config.X import *`
5. Runs the main job-search loop: login → search → filter → Easy Apply

### Active modules (`modules/`)

| File | Role |
|------|------|
| `bot_ui.py` | Tkinter floating window + Flask dashboard launcher; all `ui_*` functions |
| `open_chrome.py` | Chrome/Selenium setup; stealth mode (undetected-chromedriver) and profile options |
| `clickers_and_finders.py` | DOM interaction primitives — XPath helpers, clicking, scrolling, form input |
| `helpers.py` | Logging, delay randomization, directory creation, CSV utilities |
| `validator.py` | Config validation (type, range, enum checks) run at startup |
| `cv_wizard.py` | AI-powered PDF CV extraction → auto-populates config fields |
| `i18n.py` | Translation system; all UI strings go through `t("key")`. Set via `ui_language` in settings.py |
| `ai/openaiConnections.py` | OpenAI + any OpenAI-compatible API (Groq, DeepSeek). Handles client creation, job evaluation, Q&A answering |
| `ai/geminiConnections.py` | Google Gemini integration (same interface) |
| `ai/deepseekConnections.py` | DeepSeek-specific client (thin wrapper over OpenAI-like API) |
| `ai/prompts.py` | All LLM prompt templates |
| `ai/qa_database.py` | JSON cache of AI Q&A responses (normalized + fuzzy matching, options-aware) to avoid duplicate API calls |
| `external_apply.py` | Universal Applier v1 — handles non-Easy-Apply jobs: records the external link, and (if `external_apply_enabled`) auto-fills Greenhouse/Lever/Ashby forms using config + QA cache + AI. Workday/iCIMS and account-walled sites go to manual review |

> Legacy directories `modules/modules/` and `modules/__deprecated__/` were removed. Do not recreate them — if you see `modules/modules/` reappear it's likely an import-typo artifact.

### Flask dashboard: `app.py`
Standalone READ-ONLY Flask server (launched in a thread by `bot_ui.py`). Serves the applied-jobs dashboard (`templates/index.html`) from the output CSVs. It does NOT configure the bot — all configuration happens in the Tkinter settings window (`GlassSettings` in `modules/bot_ui.py`), which edits the `config/*.py` files directly and hot-reloads them.

## Config system

**Python files in `config/`** (single source of truth for the bot):
- `personals.py` — name, phone, address, education, EEO answers
- `secrets.py` — LinkedIn credentials, AI provider settings
- `search.py` — job search terms, LinkedIn filters, bad_words list
- `settings.py` — behavior flags (`stealth_mode`, `run_in_background`, `click_gap`, etc.)
- `questions.py` — experience years, visa, salary, resume path, pause rules

All have `.default.py` templates committed to git. The real files are gitignored.

> `config/user_config.json` is a leftover from when the dashboard edited config; nothing reads it anymore.

## AI provider configuration (`config/secrets.py`)

```python
use_AI = True
ai_provider = "groq"          # "openai" | "gemini" | "deepseek" | "groq" | "ollama"
llm_api_url = "https://api.groq.com/openai/v1"
llm_api_key = "YOUR_KEY"
llm_model   = "llama-3.1-8b-instant"
llm_spec    = "openai-like"   # "openai-like" or "gemini"
```

Groq (free tier) is the recommended default. Any OpenAI-compatible endpoint works with `llm_spec = "openai-like"`.

## Output files

| Path | Content |
|------|---------|
| `all excels/all_applied_applications_history.csv` | Successful applications |
| `all excels/failed_applications.csv` | Failed attempts with error reason |
| `all excels/qa_database.json` | AI Q&A cache (single source; the old root-level `qa_database.json` is auto-migrated on first run) |
| `logs/log.txt` | Full execution log |
| `all resumes/` | Generated/uploaded CV PDFs |

## No test suite

There are no automated tests. Validation is done via `modules/validator.py` at startup and logging in `logs/log.txt`.

## Repo layout notes

- `scripts/` — dev/build utilities, not part of the running bot: `build_release.py`, `release.ps1`, `generate_cv_pdf.py`, `generate_cv_fullportfolio.py` (imported by `modules/ai/openaiConnections.py` as `scripts.generate_cv_fullportfolio`), `compress_pdf.py`, `merge_resumes.py`. They assume the repo root as CWD/base dir.
- `docs/sketches/` — HTML design mockups for the UI, not used at runtime.

## Progreso y Próximos Pasos (Roadmap)

Esta sección documenta el estado actual del proyecto y las mejoras futuras solicitadas por el usuario para ser leídas en las próximas sesiones.

**Completado (julio 2026):**
1. ✅ **Rediseño de la UI de Configuración:** `GlassSettings` en `modules/bot_ui.py` usa la misma paleta del dashboard (`#0a0a0c`, `#7F5AF0`, `#00E8C6`), acrylic blur y tabs custom. Verificado visualmente.
2. ✅ **Optimización de la Base de Datos QA:** `modules/ai/qa_database.py` ahora hace matching normalizado + difuso (sin cruzar skills distintas), valida respuestas cacheadas contra las opciones del select, cachea en memoria y lleva contadores de uso. Los providers consultan el caché antes de llamar a la API. La base legacy de la raíz se migró a `all excels/qa_database.json`.
3. ✅ **Aplicador Universal v1:** `modules/external_apply.py` — antes esta rama crasheaba (`external_apply` se llamaba sin existir). Ahora captura el link externo siempre y, con `external_apply_enabled = True` en settings, autollena Greenhouse/Lever/Ashby/formularios simples (CV + mapeo de campos + QA cache + IA) con pausa opcional antes de enviar (`pause_before_submit_external`).

**Pasos Faltantes (To-Do):**
1. **Aplicador Universal v2:** soporte multi-página (Workday) — hoy va a revisión manual. La creación automática de cuentas queda descartada por diseño: exige verificación de email y CAPTCHA, es frágil y arriesgado para la cuenta del usuario.
2. **Probar el Aplicador Universal en vivo:** correr el bot con `external_apply_enabled = True` y `pause_before_submit_external = True` sobre vacantes reales de Greenhouse/Lever y ajustar selectores según lo que falle.
