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
llm_model   = "openai/gpt-oss-120b"
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

## Tests

`python tests/test_filtros.py` and `python tests/test_modo.py` (no pytest needed). They extract the pure predicates from the source with `ast` — importing `job_search.py` would launch Chrome — and run them against a fixed test profile, so they pass on a fresh clone without `config/*.py`. See `tests/README.md`. Runtime validation is still `modules/validator.py` at startup plus `logs/log.txt`.

## Windows installer (`installer/`)

`installer/CVSniper.iss` (Inno Setup 6) builds `CVSniper-Setup-<ver>.exe`: per-user install to `%LOCALAPPDATA%\Programs\CVSniper` (no admin), Start-menu/desktop shortcuts, an entry in Settings → Apps for uninstalling. It bundles a private Python (`{app}\python`, copied from a real CPython install so Tkinter is included — the embeddable zip lacks it) with `requirements.txt` preinstalled. `installer/build_installer.ps1` stages it (`git archive HEAD` → `build/app`, so gitignored personal config can never leak in) and calls ISCC. `.github/workflows/windows-installer.yml` builds it, silently installs + verifies + uninstalls on a clean runner, and attaches it to the Release on `v*` tags. Never change the `AppId` GUID (it identifies upgrades). The uninstaller only deletes `config/`, `all excels/`, `all resumes/`, `logs/` when the user says yes — never a blanket DelTree of `{app}`, which is also why the install dir page is disabled.

## Versioning and releases

`modules/version.py` holds `__version__`; bump it, then push a matching `vX.Y.Z` tag — the installer workflow refuses a tag that does not match, and attaches `CVSniper-Setup-X.Y.Z.exe` to that Release. `modules/updates.py` compares it against GitHub's latest release at startup.

## Credentials

`password` and `llm_api_key` live in the OS credential store via `modules/credentials.py` (`keyring`, service `CVSniper`). `config/secrets.py` holds `from_keyring("name")` for them, so `from config.secrets import llm_api_key` still yields the real value; `_read_py_var`/`_write_py_var` in `bot_ui.py` resolve/store them. Without a usable backend everything stays plain text, as before.

## Launchers

`INICIAR.bat` (Windows, double-click) and `start.sh` (Linux/macOS) are the beginner entry points: they check Python/Chrome, install dependencies on first run and start the bot. They are excluded from the release build, which ships its own `SETUP.bat` flow.

## Repo layout notes

- `scripts/` — dev/build utilities, not part of the running bot: `build_release.py`, `release.ps1`, `generate_cv_pdf.py`, `generate_cv_fullportfolio.py` (imported by `modules/ai/openaiConnections.py` as `scripts.generate_cv_fullportfolio`), `compress_pdf.py`, `merge_resumes.py`. They assume the repo root as CWD/base dir.
- `docs/sketches/` — HTML design mockups for the UI, not used at runtime.

## Progreso y Próximos Pasos (Roadmap)

Esta sección documenta el estado actual del proyecto y las mejoras futuras solicitadas por el usuario para ser leídas en las próximas sesiones.

**Completado (julio 2026):**
1. ✅ **Rediseño de la UI de Configuración:** `GlassSettings` en `modules/bot_ui.py` usa la misma paleta del dashboard (`#0a0a0c`, `#7F5AF0`, `#00E8C6`), acrylic blur y tabs custom. Verificado visualmente.
2. ✅ **Optimización de la Base de Datos QA:** `modules/ai/qa_database.py` ahora hace matching normalizado + difuso (sin cruzar skills distintas), valida respuestas cacheadas contra las opciones del select, cachea en memoria y lleva contadores de uso. Los providers consultan el caché antes de llamar a la API. La base legacy de la raíz se migró a `all excels/qa_database.json`.
3. ✅ **Aplicador Universal v1:** `modules/external_apply.py` — antes esta rama crasheaba (`external_apply` se llamaba sin existir). Ahora captura el link externo siempre y, con `external_apply_enabled = True` en settings, autollena Greenhouse/Lever/Ashby/formularios simples (CV + mapeo de campos + QA cache + IA) con pausa opcional antes de enviar (`pause_before_submit_external`).
4. ✅ **i18n completo de la ventana de settings:** todas las etiquetas y opciones de las 4 pestañas de `GlassSettings` usan `T("lbl_*")`/`T("opt_*")` de `modules/i18n.py` (es/en al 100%, sin strings hardcodeados). Toggle antialiased con PIL (caché de imágenes por root de Tk, no global). Smoke test: construir `GlassSettings` en ambos idiomas pasa sin errores ni warnings de Tcl.

5. ✅ **Fix del formulario bet365 (dropdowns trabados y respuestas invertidas):** tres bugs en `modules/easy_apply.py`, todos reproducidos con predicados puros antes de tocar código:
   - `answer_language_question` devolvía **el placeholder** (`"Select an option"`) como respuesta para idiomas que el usuario no habla, dejando el campo vacío → LinkedIn bloqueaba con "Please make a selection". Causa de fondo: el scan de "opción positiva" usaba substring `"si"`, que matchea `ba(si)c`/`(si)mple`/`profe(ssi)onal`, así que descartaba todas las opciones reales. Ahora nunca devuelve un placeholder y en escalas CEFR responde el nivel más bajo.
   - Polaridad de visa: `"Do you have the legal right to work ... WITHOUT the need for sponsorship?"` se respondía con `require_visa` (=No), o sea "no puedo trabajar aquí" → autorrechazo. Nuevo `resolve_work_authorization_answer()` detecta el fraseo invertido y voltea la respuesta.
   - El branch de ubicación secuestraba preguntas Sí/No que solo mencionaban "location"/"country" y respondía con un nombre de ciudad, que no matchea nada → caía en elección **aleatoria**. Nuevo guard `is_yes_no_options()`.
   - De paso: la lista de placeholders (duplicada en 3 sitios) es ahora `_PLACEHOLDER_WORDS` + `is_placeholder_option()`, y el matching de keywords cortos usa límites de palabra (`option_mentions()`).

6. ✅ **Ofertas que se saltaban sin motivo (octubre 2026):**
   - Cualquier error de Selenium en UNA oferta (tarjeta reciclada, elemento stale, búsqueda sin resultados → `TimeoutException`) caía en el `except WebDriverException` de "navegador cerrado" y **terminaba toda la ejecución**. Ahora cada oferta va en su propio try/except y solo un navegador muerto (`_browser_alive()`) corta el run; una búsqueda sin resultados pasa al siguiente término.
   - Las tarjetas debajo del scroll (LinkedIn las renderiza perezosamente) se saltaban por "no `<a>` tag": ahora se hace scroll a la tarjeta y se reintenta.
   - `title[:title.find("\n")]` cortaba la última letra de todo título de una línea.
   - `get_job_description` lanzaba `UnboundLocalError` cuando no encontraba la descripción.
   - `extract_years_of_experience` tomaba el máximo de cualquier "N years" (edad de la empresa, "nice to have", "preferred"); ahora solo cuenta años junto a "experience" que no estén marcados como deseables.
   - Filtro de residencia: "empresa ubicada en México" o "residents of the US" (descripción, no requisito) ya no descartan la oferta.

7. ✅ **Instalador de Windows** (`installer/`): setup.exe con Inno Setup, Python propio incluido, accesos en el menú Inicio y desinstalación desde Configuración → Aplicaciones. Lo construye y prueba (instalar/verificar/desinstalar) GitHub Actions.

8. ✅ **Ronda de mejoras (octubre 2026):**
   - "Ya postulado" se reconoce con LinkedIn en español (`is_applied_state()`: Applied/Solicitado/Postulado…).
   - El filtro de experiencia entiende "N años"/"3 a 5 años"; "deseable", "se valora", "fundada hace" no cuentan.
   - Career-Ops sin el proyecto externo `../career-ops` ya no entra en bucle de errores: recoge matches de LinkedIn (`career_ops_project_dir()`).
   - Contraseña de LinkedIn y API key en el almacén de credenciales del SO (`modules/credentials.py`, `keyring`): `secrets.py` guarda `from_keyring("...")`; los secrets.py en texto plano se migran solos al arrancar; sin almacén, todo sigue como antes.
   - Instalador construido desde `requirements.lock` (versiones exactas).
   - Tests en cada push (`.github/workflows/tests.yml`).
   - Aviso de versión nueva al arrancar (`modules/updates.py`, versión en `modules/version.py`; `check_for_updates` en settings).

**Pasos Faltantes (To-Do):**
1. **Aplicador Universal v2:** soporte multi-página (Workday) — hoy va a revisión manual. La creación automática de cuentas queda descartada por diseño: exige verificación de email y CAPTCHA, es frágil y arriesgado para la cuenta del usuario.
2. **Probar el Aplicador Universal en vivo:** correr el bot con `external_apply_enabled = True` y `pause_before_submit_external = True` sobre vacantes reales de Greenhouse/Lever y ajustar selectores según lo que falle.
