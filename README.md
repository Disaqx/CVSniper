# CVSniper — Bot Automático de Aplicaciones en LinkedIn

CVSniper automatiza el proceso de aplicar a empleos en LinkedIn usando Selenium para controlar el navegador e IA (OpenAI, DeepSeek o Gemini) para responder preguntas de formularios y filtrar vacantes según tu perfil.

> **Proyecto compartido:** cada persona configura sus propios datos desde la interfaz del bot. Nunca compartas ni subas a Git tus credenciales reales.

---

## Tabla de Contenidos

1. [Requisitos](#requisitos)
2. [Instalación](#instalación)
3. [Primer inicio — configuración desde la UI](#primer-inicio--configuración-desde-la-ui)
4. [Referencia de campos de configuración](#referencia-de-campos-de-configuración)
5. [Estructura del proyecto](#estructura-del-proyecto)
6. [Flujo de ejecución](#flujo-de-ejecución)
7. [Módulos de IA](#módulos-de-ia)
8. [Interfaz de control](#interfaz-de-control)
9. [Archivos de salida](#archivos-de-salida)
10. [Errores comunes](#errores-comunes)
11. [Novedades](#novedades)

---

## Requisitos

- Python 3.10 o superior
- Google Chrome instalado
- Cuenta activa en LinkedIn
- Clave API de uno de los siguientes proveedores de IA (si activas el uso de IA):
  - [OpenAI](https://platform.openai.com/api-keys)
  - [Google Gemini](https://aistudio.google.com/app/apikey)
  - [DeepSeek](https://platform.deepseek.com/)

---

## Instalación

**1. Clona el repositorio:**
```bash
git clone https://github.com/Disaqx/CVSniper.git
cd CVSniper
```

**2. Instala las dependencias:**
```bash
pip install selenium undetected-chromedriver flask flask-cors openai google-generativeai pyautogui
```

O usa el script incluido según tu sistema operativo:
```bash
# Windows
setup\windows-setup.bat

# Linux / Mac
bash setup/setup.sh
```

**3. Ejecuta el bot:**
```bash
python runAiBot.py
```

> No necesitas editar ningún archivo antes de ejecutar. La configuración completa se hace desde la interfaz gráfica.

---

## Primer inicio — configuración desde la UI

Al ejecutar el bot por primera vez (sin configuración previa), el proceso es completamente guiado:

### Paso 1 — CV Wizard (opcional)
Si aún no tienes datos personales configurados, aparece el **CV Wizard**: sube tu CV en PDF y el bot extrae automáticamente tu información usando IA y pre-rellena todos los campos de configuración por ti.

Si prefieres no usar el wizard, puedes cerrar ese diálogo y llenar los campos manualmente.

### Paso 2 — Panel de configuración
El panel de configuración se abre automáticamente con cuatro secciones:

| Sección | Qué configuras |
|---|---|
| **Datos personales** | Nombre, teléfono, ciudad, educación, igualdad de oportunidades |
| **Credenciales / IA** | Email y contraseña de LinkedIn, proveedor de IA y clave API |
| **Búsqueda** | Términos de búsqueda, ubicación, filtros, palabras prohibidas |
| **CV y respuestas** | Ruta del CV, años de experiencia, salario esperado, visa, etc. |

### Paso 3 — El bot arranca solo
Una vez que el nombre y la clave API están configurados, el bot detecta el cambio automáticamente, cierra el panel y empieza a buscar empleos sin que tengas que hacer nada más.

> **Para volver a la configuración en cualquier momento:** haz clic en el botón **Configuración** de la ventana de control flotante.

---

## Referencia de campos de configuración

Esta sección es una referencia de todos los campos que aparecen en el panel de configuración de la UI. No necesitas editar ningún archivo Python.

### Datos personales

| Campo | Descripción |
|---|---|
| `first_name` / `last_name` | Tu nombre completo tal como aparece en LinkedIn |
| `phone_number` | Número de teléfono **con código de país** (ej: `573001234567`) — siempre en formato texto |
| `current_city` | Ciudad actual. Si se deja vacío, el bot usa la ciudad del empleo |
| `state` / `zipcode` / `country` | Dirección de residencia |
| `university` | Institución educativa (colegio o universidad) |
| `degree` | Nivel educativo: `High School`, `Associate's`, `Bachelor's`, `Master's`, `Doctorate` o `Other` |
| `graduation_year` | Año de graduación en texto (ej: `"2021"`) |
| `field_of_study` | Área de estudio o major (ej: `Computer Science`, `IT Support`) |
| `ethnicity` | Opcional. Para preguntas EEO de empresas en EE.UU. Deja vacío para omitir |
| `gender` | Opcional. `Male`, `Female` o vacío |
| `disability_status` | `No` por defecto. Solo cambia si aplica |
| `veteran_status` | `No` por defecto |

### Credenciales e IA

| Campo | Descripción |
|---|---|
| `username` | Tu correo de LinkedIn |
| `password` | Tu contraseña de LinkedIn |
| `use_AI` | Activa o desactiva el uso de IA para responder preguntas |
| `ai_provider` | `openai`, `deepseek` o `gemini` |
| `llm_api_key` | Clave API del proveedor elegido |
| `llm_model` | Modelo a usar (ej: `gemini-2.5-flash`, `gpt-4o`, `deepseek-chat`) |

**Donde obtener la clave API:**

| Proveedor | Enlace |
|---|---|
| OpenAI | https://platform.openai.com/api-keys |
| Google Gemini | https://aistudio.google.com/app/apikey |
| DeepSeek | https://platform.deepseek.com/ |

### Búsqueda de empleos

| Campo | Descripción |
|---|---|
| `search_terms` | Lista de puestos a buscar (ej: `Software Engineer`, `Python Developer`) |
| `search_location` | Ciudad o región. Vacío = todo el mundo |
| `switch_number` | Cuántas aplicaciones hacer por término antes de pasar al siguiente |
| `date_posted` | Antigüedad máxima de la oferta: `Past 24 hours`, `Past week`, `Past month` |
| `sort_by` | `Most recent` o `Most relevant` |
| `experience_level` | Filtro de nivel: `Entry level`, `Mid-Senior level`, etc. |
| `job_type` | `Full-time`, `Part-time`, `Contract`, `Internship`, etc. |
| `on_site` | `On-site`, `Remote`, `Hybrid` |
| `bad_words` | Palabras que si aparecen en la descripción hacen que el bot ignore el empleo |
| `current_experience` | Años máximos de experiencia que acepta el bot. `-1` = sin límite |

### CV y respuestas

| Campo | Descripción |
|---|---|
| `default_resume_path` | Ruta al CV en PDF (relativa a la raíz del proyecto) |
| `years_of_experience` | Años de experiencia laboral general |
| `require_visa` | `Yes` o `No` según necesites visa de trabajo |
| `desired_salary` | Salario esperado en números |
| `notice_period` | Días de preaviso para dejar tu trabajo actual |
| `linkedIn` | URL de tu perfil de LinkedIn |
| `website` | Portafolio o sitio web personal (opcional) |
| `pause_before_submit` | `True` = el bot pausa antes de enviar cada aplicación para revisión manual |
| `pause_at_failed_question` | `True` = pausa si la IA no puede responder una pregunta |

---

## Estructura del Proyecto

```
CVSniper/
│
├── runAiBot.py                  <- Punto de entrada — ejecuta esto
│
├── config/                      <- Archivos generados automáticamente al primer inicio
│   ├── personals.py             <- Datos personales (gestionados por la UI)
│   ├── secrets.py               <- Credenciales e IA (gestionados por la UI)
│   ├── search.py                <- Preferencias de búsqueda (gestionadas por la UI)
│   ├── settings.py              <- Comportamiento del bot (gestionado por la UI)
│   └── questions.py             <- CV y respuestas comunes (gestionados por la UI)
│
├── modules/                     <- Lógica interna
│   ├── bot_ui.py                <- Ventana flotante de control + panel de configuración
│   ├── cv_wizard.py             <- Wizard de configuración automática desde CV
│   ├── helpers.py               <- Funciones utilitarias (logs, JSON, directorios)
│   ├── open_chrome.py           <- Inicialización de Chrome con Selenium
│   ├── clickers_and_finders.py  <- Interacciones con el DOM de LinkedIn
│   ├── validator.py             <- Valida los archivos de configuración al inicio
│   │
│   └── ai/                      <- Módulos de inteligencia artificial
│       ├── openaiConnections.py    <- Integración con OpenAI (GPT)
│       ├── deepseekConnections.py  <- Integración con DeepSeek
│       ├── geminiConnections.py    <- Integración con Google Gemini
│       ├── prompts.py              <- Plantillas de prompts enviados a la IA
│       └── qa_database.py          <- Caché local de preguntas y respuestas
│
├── all resumes/                 <- Coloca aquí tu CV en PDF
├── all excels/                  <- Salidas: historial CSV, base de datos QA
├── logs/                        <- Logs detallados de cada sesión
├── templates/                   <- Panel web de configuración (index.html)
└── setup/                       <- Scripts de instalación por sistema operativo
```

---

## Flujo de Ejecución

Cuando corres `python runAiBot.py` el bot sigue este proceso:

```
1. INICIO
   ├─ Auto-copia los templates de config/ si es primer inicio
   ├─ Abre Chrome con Selenium
   ├─ Lanza la ventana de control flotante
   └─ Si no hay datos → abre CV Wizard + panel de configuración

2. LOGIN EN LINKEDIN
   ├─ Navega a linkedin.com/feed
   └─ Inicia sesión con las credenciales configuradas

3. BUSQUEDA DE EMPLEOS
   └─ Para cada término en search_terms:
       ├─ Aplica los filtros configurados
       └─ Itera sobre los resultados página por página

4. EVALUACION DE CADA EMPLEO
   ├─ ¿Ya fue aplicado antes?         → Saltar
   ├─ ¿Contiene bad_words?            → Saltar
   ├─ ¿Título fuera del focus_filter? → Saltar
   └─ IA evalúa si el perfil cumple   → Continuar o saltar

5. APLICACION (Easy Apply)
   ├─ Clic en "Easy Apply"
   ├─ Paso 1: datos personales de la configuración
   ├─ Paso 2: preguntas conocidas de la configuración
   ├─ Paso 3: preguntas nuevas → IA las responde y las guarda en qa_database.json
   ├─ Revisión manual (si pause_before_submit = True)
   └─ Envío de la solicitud

6. REGISTRO
   ├─ Éxito → all excels/all_applied_applications_history.csv
   └─ Fallo  → all excels/failed_applications.csv
```

---

## Módulos de IA

El bot soporta tres proveedores de IA intercambiables. Se selecciona desde el panel de configuración en el campo `ai_provider`.

| Función | Qué hace |
|---|---|
| `*_create_client()` | Conecta con la API del proveedor |
| `*_extract_skills(client, job_description)` | Extrae habilidades requeridas del empleo en JSON |
| `*_answer_question(client, question, ...)` | Responde preguntas del formulario (texto, selección, sí/no) |
| `*_evaluate_job(client, description, user_info)` | Evalúa si tu perfil cumple los requisitos del empleo |

Todas las respuestas generadas por la IA se guardan en `all excels/qa_database.json` para no repetir consultas en futuras sesiones.

---

## Interfaz de Control

Al ejecutar el bot aparece una ventana flotante en la esquina de la pantalla con:

- **Panel de logs** con lo que hace el bot en tiempo real
- Botón **Configuración** — abre el panel web con todos los ajustes
- Botón **OPTIMIZAR CV** — lanza el wizard de optimización del CV con IA
- Botón **PAUSE** — pausa el bot entre acciones de forma segura
- Botón **STOP** — detiene la ejecución completamente
  - Requiere doble clic de confirmación (el botón cambia a naranja tras el primer clic)
  - Si Chrome o chromedriver no responde, fuerza la salida del proceso después de 5 segundos

Atajos de teclado:
- `Ctrl + Q` o `Ctrl + C` — detener (fuerza salida inmediata)
- `Ctrl + P` — pausar / reanudar

---

## Archivos de Salida

Todos los archivos se generan automáticamente en `all excels/`:

| Archivo | Contenido |
|---|---|
| `all_applied_applications_history.csv` | Historial completo: ID, empresa, título, link, fecha de aplicación |
| `failed_applications.csv` | Empleos fallidos con el motivo del error o rechazo |
| `qa_database.json` | Caché de preguntas y respuestas de la IA para reutilizar |

---

## Errores Comunes

| Error | Causa | Solución |
|---|---|---|
| `Invalid input for phone_number. Expecting a String!` | `phone_number` o `zipcode` definidos sin comillas | Corregirlo en el panel de configuración de la UI |
| Bot cierra navegador sin aplicar | Error en validación de configuración | Revisar `logs/` para ver el detalle del error |
| LinkedIn pide verificación / CAPTCHA | LinkedIn detectó actividad automatizada | Activar `stealth_mode = True` en configuración y reducir velocidad |
| El botón Stop no responde | Chrome/chromedriver colgado durante llamada a API | Espera hasta 5 segundos — el proceso se fuerza a cerrar automáticamente |
| CV Wizard no extrae datos correctamente | CV en formato imagen o sin texto seleccionable | Usa un PDF con texto real (no escaneado) |

---

## Seguridad

- **Nunca subas tus archivos de configuración a GitHub.** Los archivos `config/secrets.py` y `config/personals.py` están en `.gitignore` por defecto.
- Cada colaborador del proyecto configura sus propios datos localmente desde la UI.
- Los archivos `config/*.default.py` son plantillas vacías incluidas en el repo para que el bot pueda copiarlas al primer inicio.

---

## Notas Finales

- El bot está diseñado exclusivamente para **Easy Apply** de LinkedIn. Empleos con formulario externo se registran pero no se completan automáticamente.
- Usa `pause_before_submit = True` en la configuración al principio para revisar cada aplicación antes de enviarla.
- LinkedIn puede detectar y suspender cuentas por actividad automatizada excesiva. Usa el bot con moderación.

---

## Novedades

### Formularios — campos condicionales "If YES" resueltos
Algunos formularios de Easy Apply muestran campos de texto adicionales que solo aparecen cuando el usuario selecciona "Yes" en un radio previo (ej: *"If your answer is YES, please provide the name of the referring staff member"*). El bot ahora los maneja automáticamente:
- Si la respuesta final al radio es **"No"**, el bot primero hace clic en **"Yes"** para que React monte los campos condicionales en el DOM, les escribe **"N/A"** y luego hace clic en **"No"**. Esto evita que los campos obligatorios queden vacíos y bloqueen el envío del formulario.

### Prompts de IA mejorados
- Reglas explícitas para responder **"N/A"** en preguntas de referidos, conflictos de interés y campos condicionales follow-up.
- Evaluación de empleo más permisiva: solo rechaza candidatos claramente descalificados (gran brecha de experiencia, dominio completamente distinto, requisito legal inamovible o vacante exclusiva para personas con discapacidad).

### Nuevos campos de educación
Se agregaron `degree`, `graduation_year` y `field_of_study` al panel de configuración para que el bot pueda responder preguntas académicas en formularios sin depender de la IA.

### CV Wizard
En el primer inicio, el bot ofrece subir tu CV en PDF para que la IA extraiga automáticamente tus datos y rellene todos los campos de configuración. Ideal para usuarios que instalan el ejecutable sin conocimientos técnicos.

### Botón Stop — fuerza de salida garantizada
Se corrigió un bug donde el botón Stop dejaba de funcionar cuando Chrome/chromedriver estaba colgado. Ahora el proceso se fuerza a cerrar después de 5 segundos sin importar el estado del driver.

### [v1.0.0] Correcciones de estabilidad del bot

#### Bug: `pause_after_filters` — UnboundLocalError al iniciar búsqueda
Al iniciar el bot con un resume nuevo aparecía:
```
cannot access local variable 'pause_after_filters' where it is not associated with a value
```
Causa: `pause_after_filters` se asignaba dentro de `_apply_to_jobs_for_location` sin estar en la declaración `global`, haciendo que Python la tratara como variable local. Corregido añadiéndola al `global` statement.

#### Bug: Respuestas de experiencia incorrectas en formularios
El bot respondía indiscriminadamente con `years_of_experience` a **cualquier** pregunta que contuviera la palabra "experience" o "years". Por ejemplo, respondía "3" a "¿Cuántos años de experiencia tienes con Audio Visual Systems?" aunque el candidato no tuviera esa experiencia.

Se añadió la función `_resolve_experience_answer()` que distingue entre:
- Preguntas genéricas de experiencia total → responde `years_of_experience`
- Preguntas de experiencia específica en una habilidad → delega a la IA (si está activa); si no, devuelve `years_of_experience` como mejor estimado disponible

#### Bug: "Are you interested in a customer facing role?" — HELP NEEDED
Preguntas del tipo *"Are you interested in X?"*, *"Are you open to remote?"*, *"Are you willing to travel?"* no tenían regla en `answer_common_questions` y activaban la pausa de HELP NEEDED. Ahora se responden automáticamente con "Yes".
