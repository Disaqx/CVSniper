# Cómo funciona CVSniper

Guía práctica para quien vaya a arreglar o ampliar el bot. La arquitectura
detallada (módulos, configuración, instalador, versiones) está en
[`CLAUDE.md`](../CLAUDE.md), en la raíz del repo: léela primero.

## Qué hace, en una frase

Abre Chrome con la sesión de LinkedIn del usuario, busca ofertas por cada
término de búsqueda y ubicación, filtra las que no encajan y se postula con
**Easy Apply** rellenando los formularios con la configuración del usuario, la
caché de preguntas y, si hace falta, una IA (Groq por defecto).

## Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Programa principal (bucle de búsqueda y postulación) | `runAiBot.py` (archivo grande, ~4500 líneas) |
| Abrir Chrome / modo sigiloso | `modules/open_chrome.py` → `_start_driver()`, `_with_timeout()` |
| Login en LinkedIn | `modules/linkedin_login.py` |
| Búsqueda, filtros y lectura de tarjetas de ofertas | `modules/job_search.py` (también construye/lee las URLs de búsqueda y elige el diseño de tarjeta) |
| Rellenar formularios de Easy Apply | `modules/easy_apply.py` |
| Ofertas externas (Greenhouse, Lever…) | `modules/external_apply.py` |
| Validación de la configuración al arrancar | `modules/validator.py` |
| Ventana de control y ajustes (Tkinter) | `modules/bot_ui.py` |
| Dashboard web (historial y «por qué se aplicó») | `app.py` + `templates/index.html` |
| Configuración del usuario | `config/*.py` (plantillas en `config/*.default.py`) |
| Registro completo de cada ejecución | `logs/log.txt` y `logs/AAAA-MM-DD.log` |
| Diagnóstico del DOM cuando no hay tarjetas | `logs/linkedin_search_layout_<búsqueda>_<fecha>.json` |
| Tests (sin pytest, sin abrir Chrome) | `python tests/test_filtros.py`, `python tests/test_modo.py`, `python tests/test_busqueda.py` |

En la versión instalada (instalador de Windows), todo vive en
`%LOCALAPPDATA%\Programs\CVSniper` con su propio Python en `python\`.

## El recorrido de una ejecución

1. **Arranque** (`runAiBot.py`): copia las plantillas de `config/` que falten
   y carga la configuración.
2. **Chrome** (`open_chrome._start_driver`): con `stealth_mode = True` usa
   `undetected_chromedriver` (oculta las marcas de automatización) dentro de
   `_with_timeout(…, 90 s)`. Si en Windows falla al descomprimir su driver
   (`FileExistsError`/`PermissionError`), mata los chromedriver que queden, borra
   `%APPDATA%\undetected_chromedriver\undetected_chromedriver.exe` y la carpeta
   `undetected`, y lo reintenta **una** vez. Si no, cae al driver normal de
   Selenium, también con tiempo límite (120 s). Cada paso se anota en el log y
   un vigilante escribe «still waiting on …» cada 30 s si algo se cuelga. Al
   final se fijan los tiempos máximos de carga de página (120 s) y de script
   (60 s), para que una pestaña colgada no congele la ejecución.
3. **Validación** (`validator.py`): comprueba la configuración, por ejemplo que
   exista el CV de `default_resume_path` (en `config/questions.py`). Si la ruta
   no existe, distingue si era absoluta («el archivo se movió o se renombró») o
   relativa («relativa a la carpeta del proyecto»), busca PDFs parecidos en esa
   carpeta y dice dónde cambiarla (Ajustes → pestaña «Respuestas» → «Ruta del
   CV (PDF)»). Si hay problemas, los lista y termina.
4. **Login** (`linkedin_login.py`): si no encuentra el enlace «Sign in», asume
   que ya hay sesión.
5. **Cliente de IA**: Groq por defecto (`config/secrets.py`).
6. **Bucle de búsqueda** (`runAiBot.apply_to_jobs`, línea ~430). Por cada
   término de búsqueda:
   - `job_search.build_search_url()` construye
     `https://www.linkedin.com/jobs/search/?keywords=…` y añade `&location=`,
     `&geoId=`, `&f_LF=f_AL` (solo Easy Apply), `&f_WT=2` (remoto) y `&f_JT=`.
   - `driver.get(url)` y `job_search.navigation_report()` compara lo pedido con
     la URL final: detecta el muro de login, la página nueva
     `/jobs/search-results/` y **cada filtro que LinkedIn se llevó**, con una
     línea `WARNING: LinkedIn quitó el filtro X` por cada uno. Ya no basta con
     que la URL contenga «search» y «keyword».
   - Si se perdió Easy Apply, reintenta **una** vez con el alias antiguo
     `f_AL=true` (el formato que en la prueba del 16-11-2026 mantuvo la página
     clásica). Si aun así no vuelve, sigue adelante y filtra tarjeta a tarjeta
     por la etiqueta «Easy Apply»/«Solicitud sencilla», saltándose las que dicen
     «Apply on company site»/«Solicitud en el sitio de la empresa».
   - `job_search.apply_filters()`: intenta fijar la ubicación, el interruptor
     de Easy Apply, la fecha y el orden **pulsando la interfaz**, buscando los
     elementos por su texto en inglés o español. Cada fase se anota en el log;
     si el panel de filtros no existe en ese diseño, lo dice y sigue con los
     filtros que ya vengan en la URL (no espera para siempre).
   - `job_search.find_job_cards()` busca las tarjetas en los diseños conocidos
     (tabla `JOB_CARD_LAYOUTS`): `li[data-occludable-job-id]` (clásico),
     `div.job-search-card[data-entity-urn="urn:li:jobPosting:<id>"]` (público,
     comprobado en vivo), `[data-job-id]` y, como último recurso, cualquier
     enlace `a[href*='/jobs/view/']`. El id sale del `data-*` o del final del
     slug del enlace; el título y la empresa, de los selectores del diseño y, si
     no, del texto de la tarjeta. Si no encuentra ninguna, guarda
     `logs/linkedin_search_layout_*.json` con la estructura real de la página y
     pasa al siguiente término.
   - `ensure_easy_apply_state()` sigue revisando en cada página que
     `f_LF=f_AL` siga en la URL clásica. En `/jobs/search-results/` **no**
     reescribe la URL (podría volver a redirigir): el filtro se aplica por
     tarjeta.
   - Para cada tarjeta: `get_job_main_details()` lee el id, el título, la
     empresa y el estado «Solicitado/Applied» (también busca el estado en el
     texto de la tarjeta, no solo en la clase antigua); luego filtros (lista
     negra, palabras prohibidas, años de experiencia, residencia) y Easy Apply
     (`easy_apply.py`). El botón de Apply se busca por clase **y** por su
     etiqueta («Easy Apply», «Solicitud sencilla», «Apply»), porque la página
     nueva no siempre conserva `jobs-apply-button`. El modal de Easy Apply se
     reconoce por su clase o por ser un diálogo con ese texto, y se excluye el
     panel de filtros (que también dice «Easy Apply»).
   - Cada descarte se cuenta por motivo (`note_skip`) y al final de cada
     término el log imprime **«Resumen de descartes …»** con cuántas ofertas se
     cayeron y por qué. Al arrancar se imprimen los **filtros activos**
     (enfoque, listas, experiencia, IA, residencia), que es lo que suele estar
     demasiado estricto cuando no se postula a nada.
   - Paginación: `go_to_next_page()` usa los botones numerados («Page N+1») o un
     botón «Next»/«Siguiente» con etiqueta exacta; si no hay ninguno, termina
     ese término.
   - Si no hay tarjetas → `TimeoutException` → «No (more) job listings for …»,
     y pasa al siguiente término.
7. **Barrido remoto** (`remote sweep`): repite los términos con las ubicaciones
   extra (Worldwide, Latin America, United States, Spain…).
8. **Dashboard** (`app.py`): además del historial, lee
   `all excels/application_notes.csv` y muestra una columna **«Por qué se
   aplicó»**: la puntuación y el motivo de la IA y, si se detectó un salario
   por debajo del objetivo, el aviso «Salario publicado ≈ $X, por debajo de tu
   objetivo; se aplicó igual». Es informativo: no cambia a qué se postula.
9. **Resumen** al final: postuladas, enlaces externos, fallidas y saltadas.
   El historial se guarda en `all excels/` y los motivos en
   `all excels/application_notes.csv`.

## De dónde sale cada mensaje del log

| Mensaje | Dónde |
|---|---|
| `Starting Chrome in stealth mode...` / `Launching (… giving up after 90s)` | `open_chrome._stealth_driver` |
| `Retrying stealth mode once with a clean driver cache...` / `Removed the stale undetected_chromedriver files: …` | `open_chrome._start_driver` → `_clear_uc_cache` |
| `Stealth mode could not start (undetected_chromedriver)` | `open_chrome._start_driver` (`except`) |
| `The standard Chrome driver did not start within 120s…` | `open_chrome._start_driver` (respaldo con `_with_timeout`) |
| `WARNING: still waiting on '<paso>' after Ns` | `helpers.timed_step` (lo usa `open_chrome`, `job_search`) |
| `The resume was not found at '…'` (+ rutas parecidas y dónde cambiarla) | `validator.resume_path_problem` |
| `Navigating directly to search URL...` / `Search navigation worked normally!` | `runAiBot.apply_to_jobs` |
| `Filtros activos: enfoque=…; títulos vetados=…; experiencia=…; IA=…` | `runAiBot.log_active_filters` |
| `WARNING: 'filtrar por área' está activado pero no tiene palabras clave…` | `runAiBot.log_active_filters` |
| `Resumen de descartes…` con cada motivo | `runAiBot.print_skip_summary` |
| `Salario publicado ≈ $… por debajo de tu objetivo; se aplicó igual.` | `job_search.salary_below_target` (va al dashboard, no al log) |
| `LinkedIn opened the NEW results page (/jobs/search-results/).` | `job_search.log_navigation_report` |
| `WARNING: LinkedIn quitó el filtro …` (uno por filtro perdido) | `job_search.log_navigation_report` |
| `Easy Apply is not in the results URL: each card will be checked…` | `runAiBot._apply_to_jobs_for_location` |
| `LinkedIn search layout: <diseño> (N tarjetas, selector: …)` | `job_search.find_job_cards` |
| `No job cards found with any known layout…` / `Saved a map of the results page to '…'` | `job_search.find_job_cards` / `dump_search_layout` |
| `Could not find location input field, but location was set via URL.` | `job_search.set_search_location` (~268) |
| `Easy Apply filter toggle not found (tried EN/ES labels…)` | `job_search.apply_filters` (tras `_set_easy_apply_toggle`) |
| `Filters panel not found on this LinkedIn layout…` | `job_search.apply_filters` |
| `Show results button not found — filters may already be applied.` | `job_search.apply_filters` |
| `No (more) job listings for "…", moving on…` | `runAiBot.apply_to_jobs` (~1008) |

## Reglas de la casa

- Probar antes de afirmar: un arreglo no está hecho hasta verlo funcionar
  (el log o una ejecución real), no basta con que «parezca correcto».
- Los tests extraen funciones puras con `ast`: **importar `job_search.py`
  abre Chrome**. Si añades lógica pura (parsear URLs, elegir selectores),
  sepárala en funciones que se puedan probar así.
- LinkedIn reparte los diseños poco a poco: cuando cambie otra vez, el log dirá
  qué diseño se detectó y, si no hubo tarjetas, quedará el mapa del DOM en
  `logs/linkedin_search_layout_*.json` para añadir el selector real sin adivinar.
- Nunca subir `config/*.py` (datos y contraseñas del usuario).
- Al publicar una versión: subir `modules/version.py`, escribir
  `installer/release-notes/vX.Y.Z.md` y crear la etiqueta `vX.Y.Z`
  (ver `CLAUDE.md`).
