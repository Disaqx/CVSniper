# CVSniper — Flujo de Configuración

> Generado por análisis de código (commit `74e0c46`+).
> Verificado leyendo `app.py`, `modules/bot_ui.py`, `runAiBot.py`, `build_release.py`.

## TL;DR

Hay **dos UIs** que editan configuración y **dos almacenes** de datos. Solo **una de las rutas** llega realmente al bot:

```
┌───────────────────────────┐         ┌────────────────────────────┐
│ Tkinter GlassSettings     │         │ Flask Dashboard (app.py)   │
│ (modules/bot_ui.py)       │         │ http://127.0.0.1:5000      │
└─────────────┬─────────────┘         └──────────────┬─────────────┘
              │ _write_py_var()                      │ POST /config
              │ (regex replace en .py)               │ save_user_config()
              ▼                                      ▼
   ┌──────────────────────┐              ┌─────────────────────────┐
   │ config/personals.py  │              │ config/user_config.json │
   │ config/secrets.py    │              │                         │
   │ config/search.py     │              │  ⚠️ NADIE LO LEE        │
   │ config/settings.py   │              │  (excepto Flask mismo)  │
   │ config/questions.py  │              └─────────────────────────┘
   └──────────┬───────────┘
              │ importlib.reload()
              │ (en runAiBot.main() y bot_ui.save)
              ▼
   ┌──────────────────────┐
   │ runAiBot.py runtime  │ ← fuente de verdad efectiva del bot
   └──────────────────────┘
```

## Hallazgo crítico

`config/user_config.json` es un **store huérfano**: solo `app.py` lo lee/escribe. **El bot nunca lo importa.** Los cambios hechos en el dashboard web **no se reflejan** en la ejecución del bot a menos que también se reescriban los `.py`.

Esto contradice `CLAUDE.md` que afirma *"runAiBot.py re-imports the Python config files on reload"* — sí los re-importa, pero re-importa los `.py`, **no traduce el JSON**. No existe ninguna función `json_to_py` ni `apply_user_config` en el repo (verificado con grep).

**Implicación práctica:** la única UI que realmente configura el bot es la **Tkinter GlassSettings**. El Flask dashboard funciona para *consultar* (`/applied-jobs`, listar resumes, validar) pero al guardar config queda desconectado.

## Flujo A — Tkinter (FUNCIONA)

`modules/bot_ui.py:880-916` (clase `GlassSettings._save_settings`):

1. Usuario edita campos en la ventana flotante.
2. Por cada campo, `_write_py_var(filepath, varname, val)` hace **regex replace** en el `.py` correspondiente.
3. Tras escribir, ejecuta `importlib.reload()` sobre:
   - `config.personals`, `config.questions`, `config.search`, `config.secrets`, `config.settings`
   - `modules.ai.openaiConnections` (para que CV Optimizer use API key fresca)
4. `runAiBot.main()` también re-importa al arrancar (`runAiBot.py:1019-1027`) para captar cambios hechos por el wizard.

## Flujo B — Flask (HUÉRFANO al guardar)

`app.py`:

| Endpoint | Qué hace | ¿Llega al bot? |
|---|---|---|
| `GET /config` | Devuelve `user_config.json` | N/A (lectura) |
| `POST /config` | Escribe `user_config.json` | ❌ **NO** |
| `GET /config/validate` | Valida `user_config.json` con reglas hardcodeadas | ❌ NO toca los `.py` |
| `GET /config/resumes` | Lista PDFs en `all resumes/` | ✅ OK (solo filesystem) |
| `GET/POST /config/questions-db` | Lee/escribe `config/questions_db.json` | ✅ Sí (lo lee el bot vía otro path) |
| `GET /applied-jobs` | Lee `all excels/all_applied_applications_history.csv` | ✅ OK |
| `PUT /applied-jobs/<id>` | Actualiza fecha en CSV | ✅ OK |

## Lo que `CLAUDE.md` debería decir

La frase actual:

> *"All config changes from the UI are written to `user_config.json`, then `runAiBot.py` re-imports the Python config files on reload."*

Es **incorrecta**. Lo correcto sería:

> *"Configuration changes go through two separate UIs:
> - **Tkinter GlassSettings** writes directly to `config/*.py` via regex replace and triggers `importlib.reload()`. This is the only path that actually updates the running bot.
> - **Flask dashboard** writes to `config/user_config.json`, which is currently NOT consumed by the bot. The JSON store is effectively orphaned for write operations; the dashboard is read-only in practice."*

## Recomendaciones (orden de impacto)

### 🔴 Alta — decidir arquitectura
Hay que elegir **una sola fuente de verdad**:

- **Opción A — JSON-first:** el bot lee `user_config.json` al arrancar; los `.py` quedan como defaults/migración. Requiere reescribir cómo se importan configs en `runAiBot.py` (`from config.X import *` → cargar JSON).
- **Opción B — PY-first (estado actual + parche):** añadir una función `apply_json_to_py()` en `app.py` que tras `POST /config` regenere los `.py` y dispare reload. Mucho menos invasivo.
- **Opción C — eliminar Flask config edits:** dejar el dashboard solo-lectura; toda edición pasa por Tkinter. Más simple, menos features.

### 🟡 Media — sincronización inicial
En `build_release.py:400-403` se crea `user_config.json` vacío. Mejor: generarlo desde los `.py` actuales para que el dashboard arranque pre-poblado.

### 🟢 Baja — limpieza
- Actualizar la frase incorrecta en `CLAUDE.md` (puedo hacerlo cuando confirmes qué dirección eliges).
- El bloque `import importlib, sys as _sys; for _mod_name in [...]` se duplica en `runAiBot.py:1020`, `validator.py:232`, `bot_ui.py:919-926` y dos veces en `openaiConnections.py`. Candidato a extraer a `helpers.reload_configs()`.

## Archivos referenciados

| Path | Líneas clave |
|---|---|
| `app.py` | 14, 21-36, 129-154 — definición y endpoints de config |
| `modules/bot_ui.py` | 880-934 — `_save_settings()` y reload post-save |
| `runAiBot.py` | 1019-1035 — reload de configs en `main()` |
| `modules/validator.py` | 232 — reload duplicado |
| `modules/ai/openaiConnections.py` | 369, 508 — reload duplicado para refrescar API key |
| `build_release.py` | 400-403 — crea `user_config.json` vacío |
