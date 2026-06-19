[README.md](https://github.com/user-attachments/files/29143508/README.md)
# 🎯 CVSniper — Bot Automático de Aplicaciones en LinkedIn

CVSniper es un bot de automatización que aplica a empleos en LinkedIn de forma autónoma usando Selenium para el control del navegador e IA (OpenAI, DeepSeek o Gemini) para responder preguntas de los formularios y filtrar vacantes según tu perfil.

---

## 📁 Estructura del Proyecto

```
CVSniper-main/
│
├── runAiBot.py                  ← Punto de entrada principal del bot
├── app.py                       ← Servidor Flask (panel web + UI de escritorio)
├── compress_pdf.py              ← Utilidad para comprimir PDFs de CV
├── merge_resumes.py             ← Combina múltiples CVs en uno
│
├── config/                      ← Toda la configuración del usuario
│   ├── personals.py             ← Datos personales (nombre, teléfono, ciudad...)
│   ├── secrets.py               ← Credenciales de LinkedIn y clave de API de IA
│   ├── search.py                ← Preferencias de búsqueda de empleo
│   ├── settings.py              ← Configuración general del bot
│   └── questions.py             ← Ruta del CV y respuestas predefinidas
│
├── modules/                     ← Lógica interna del bot
│   ├── bot_ui.py                ← Interfaz gráfica de control (ventana flotante)
│   ├── helpers.py               ← Funciones utilitarias (logs, directorios, JSON)
│   ├── open_chrome.py           ← Inicialización del navegador Chrome/Selenium
│   ├── clickers_and_finders.py  ← Interacciones con elementos del DOM de LinkedIn
│   ├── validator.py             ← Validación de todos los archivos de configuración
│   │
│   ├── ai/                      ← Módulos de inteligencia artificial
│   │   ├── openaiConnections.py ← Integración con OpenAI (GPT)
│   │   ├── deepseekConnections.py ← Integración con DeepSeek
│   │   ├── geminiConnections.py ← Integración con Google Gemini
│   │   ├── prompts.py           ← Todos los prompts enviados a la IA
│   │   └── qa_database.py       ← Base de datos local de preguntas y respuestas
│   │
│   └── resumes/
│       ├── extractor.py         ← Extrae texto de un PDF de CV
│       └── generator.py        ← Generador de CVs personalizados (en desarrollo)
│
├── all excels/                  ← Salidas generadas: historial CSV, QA database
├── templates/                   ← Plantillas HTML para el panel web
└── setup/                       ← Scripts de instalación por sistema operativo
```

---

## ⚙️ Archivos de Configuración

Todos los archivos de `config/` deben configurarse antes de ejecutar el bot. Son el único lugar donde debes hacer cambios como usuario.

### `config/personals.py` — Tus datos personales

Contiene la información que el bot ingresa en los formularios de aplicación de LinkedIn.

```python
first_name = "Cesar"
last_name  = "Jimenez"

# ⚠️ IMPORTANTE: debe ser un string (con comillas)
phone_number = "573239301232"   # ✅ Correcto
# phone_number = 573239301232   # ❌ Incorrecto — causará error al ejecutar

current_city = "Bogotá"
country      = "Colombia"
state        = "Bogotá D.C."
zipcode      = "110111"

ethnicity        = "Hispanic/Latino"
gender           = "Male"
disability_status = "No"
veteran_status   = "No"
```

> **Error común:** `phone_number` definido como entero (sin comillas) causa `Invalid input for phone_number. Expecting a String!` y cierra el navegador.

---

### `config/secrets.py` — Credenciales e IA

```python
username    = "tu_correo@gmail.com"   # Correo de LinkedIn
password    = "tu_contraseña"         # Contraseña de LinkedIn
llm_api_key = "tu_clave_api"          # Clave de la IA que uses

use_AI      = True                    # Activar o desactivar IA
ai_provider = "gemini"                # "openai", "deepseek" o "gemini"
llm_spec    = "gemini"                # Debe coincidir con ai_provider
```

> **Advertencia de seguridad:** Nunca subas este archivo a GitHub. Agrega `config/secrets.py` a tu `.gitignore`.

---

### `config/search.py` — Preferencias de búsqueda

Define qué empleos busca el bot y con qué filtros.

```python
# Términos de búsqueda en LinkedIn
search_terms = [
    "IT Support Specialist",
    "Help Desk Technician",
    "Technical Support Engineer",
]

search_location = "Bogotá, Colombia"
switch_number   = 10       # Cambiar al siguiente término cada 10 aplicaciones
easy_apply_only = True     # Solo aplicar a trabajos con "Easy Apply"
date_posted     = "Past week"
sort_by         = "Most recent"

# Palabras prohibidas — si aparecen en la descripción, el bot omite el empleo
bad_words = ["US Citizen", "No C2C", "PHP", "Ruby"]

# Experiencia máxima requerida (en años). -1 = sin límite
current_experience = 3

# Filtro de relevancia de título
enable_job_focus_filter   = True
primary_focus_keywords    = ["help desk", "it support", "technical support", ...]
secondary_focus_keywords  = ["customer service", "customer success", ...]
```

---

### `config/settings.py` — Configuración del comportamiento del bot

```python
run_in_background  = False   # True = modo sin ventana (headless)
stealth_mode       = True    # Usa undetected-chromedriver para evadir detección
pause_before_submit = True   # Pausa para revisión antes de enviar cada solicitud
close_tabs         = False   # Cerrar pestañas de aplicaciones externas
follow_companies   = False   # Seguir empresas al aplicar
run_non_stop       = False   # Correr sin parar hasta que lo detengas

logs_folder_path   = "logs/"
```

---

### `config/questions.py` — CV y respuestas predefinidas

```python
# Ruta a tu CV en PDF
default_resume_path = "resumes/mi_cv.pdf"

# Respuestas por defecto para preguntas comunes
years_of_experience  = 3
desired_salary       = 60000000   # En la moneda de tu país
current_ctc          = 0
notice_period        = 30         # En días
```

---

## 🚀 Flujo de Ejecución

Cuando corres `python runAiBot.py`, el bot sigue estos pasos en orden:

```
1. Inicialización
   └─ Carga configuraciones de config/
   └─ Valida tipos de datos (validator.py)
   └─ Abre Chrome con Selenium (open_chrome.py)
   └─ Lanza la ventana de control UI (bot_ui.py)
   └─ Conecta con la IA elegida (openai/deepseek/gemini)

2. Login en LinkedIn
   └─ Navega a linkedin.com
   └─ Ingresa usuario y contraseña desde secrets.py
   └─ Espera confirmación de inicio de sesión

3. Búsqueda de empleos
   └─ Para cada término en search_terms:
       └─ Aplica filtros (fecha, tipo, nivel, salario...)
       └─ Itera sobre los resultados paginados

4. Evaluación de cada empleo
   └─ ¿Ya fue aplicado antes? → Saltar
   └─ ¿Contiene bad_words? → Saltar
   └─ ¿Título coincide con focus_keywords? → Continuar o saltar
   └─ IA evalúa si el perfil cumple los requisitos → Continuar o saltar

5. Proceso de aplicación (Easy Apply)
   └─ Hace clic en "Easy Apply"
   └─ Rellena cada paso del formulario:
       └─ Datos personales desde personals.py
       └─ Preguntas predefinidas desde questions.py
       └─ Preguntas desconocidas → responde con IA
       └─ Guarda respuesta en qa_database.json
   └─ Pausa para revisión (si pause_before_submit = True)
   └─ Envía la solicitud

6. Registro de resultados
   └─ Guarda en all excels/all_applied_applications_history.csv
   └─ Jobs fallidos van a all excels/failed_applications.csv
   └─ Logs detallados en logs/
```

---

## 🤖 Módulos de IA (`modules/ai/`)

### `openaiConnections.py` / `deepseekConnections.py` / `geminiConnections.py`

Cada archivo es el adaptador para su proveedor de IA. Los tres exponen las mismas funciones:

| Función | Qué hace |
|---|---|
| `*_create_client()` | Inicializa la conexión con la API del proveedor |
| `*_extract_skills(client, job_description)` | Extrae habilidades de la descripción del empleo en JSON |
| `*_answer_question(client, question, ...)` | Genera la respuesta para una pregunta del formulario |
| `*_evaluate_job(client, description, user_info)` | Evalúa si el perfil cumple los requisitos del empleo |
| `ai_close_openai_client(client)` | Cierra la sesión (solo OpenAI) |

El bot selecciona cuál usar según `ai_provider` en `secrets.py`.

---

### `prompts.py` — Plantillas de prompts

Centraliza todos los textos enviados a la IA:

- `extract_skills_prompt` — Extrae habilidades técnicas, blandas, requeridas y deseables de una descripción de empleo
- `ai_answer_prompt` — Responde preguntas del formulario como una persona real (fechas, años de experiencia, respuestas Sí/No, descripciones)
- `deepseek_extract_skills_prompt` — Versión optimizada para DeepSeek que fuerza salida JSON sin texto adicional

---

### `qa_database.py` — Base de datos de Q&A

Guarda y recupera respuestas previas en `all excels/qa_database.json` para no repetir consultas a la IA.

```python
save_to_qa_database("Years of experience", "3")
# → Guarda en qa_database.json

get_from_qa_database("Years of experience")
# → Retorna "3"
```

---

## 🖥️ Interfaz de Control (`modules/bot_ui.py`)

Ventana flotante en la esquina de la pantalla con:

- **Panel de logs** en tiempo real
- Botón **PAUSE** — pausa el bot de forma segura entre acciones
- Botón **STOP** — detiene completamente la ejecución
- Atajos de teclado: `Ctrl+Q` o `Ctrl+C` para detener, `Ctrl+P` para pausar

---

## 🌐 Servidor Web (`app.py`)

Servidor Flask que expone una API REST para consultar el historial de aplicaciones desde el navegador.

| Endpoint | Método | Descripción |
|---|---|---|
| `/` | GET | Página principal (index.html) |
| `/applied-jobs` | GET | Lista todos los empleos aplicados en CSV |
| `/applied-jobs/<job_id>` | PUT | Actualiza la fecha de aplicación de un empleo |

Para iniciarlo por separado (opcional):
```bash
python app.py
# Disponible en http://localhost:5000
```

---

## 🛠️ Módulos de Soporte

### `modules/helpers.py`
Funciones de utilidad usadas en todo el proyecto:
- `print_lg()` — imprime en consola y UI simultáneamente
- `critical_error_log()` — registra errores críticos con stack trace
- `convert_to_json()` — parsea respuestas de texto de la IA a diccionarios
- `make_directories()` — crea carpetas necesarias si no existen
- `calculate_date_posted()` — convierte texto como "hace 3 días" a fecha real

### `modules/open_chrome.py`
Inicializa el navegador Chrome con las opciones configuradas:
- Modo normal (selenium) o sigiloso (undetected-chromedriver)
- Modo headless para correr en background
- Perfil temporal de Chrome para aislar la sesión

### `modules/clickers_and_finders.py`
Funciones de Selenium para interactuar con LinkedIn:
- Encontrar campos de formulario por etiqueta, tipo o atributo
- Hacer clic con manejo de errores y reintentos
- Detectar popups, modales y diálogos de error

### `modules/validator.py`
Valida todos los archivos de config al inicio. Si encuentra un tipo incorrecto (como `phone_number` como entero), lanza un error descriptivo antes de que el bot empiece a aplicar.

---

## 📦 Instalación

### Requisitos
- Python 3.10+
- Google Chrome instalado
- Cuenta en LinkedIn
- Clave API de OpenAI, DeepSeek o Google Gemini (si usas IA)

### Pasos

**1. Instalar dependencias:**
```bash
pip install selenium undetected-chromedriver flask flask-cors openai google-generativeai pyautogui
```

O usar el script de instalación incluido:
```bash
# Windows
setup\windows-setup.bat

# Linux / Mac
bash setup/setup.sh
```

**2. Configurar los archivos en `config/`** (ver sección de configuración arriba)

**3. Ejecutar:**
```bash
python runAiBot.py
```

---

## 🐛 Errores Comunes y Soluciones

| Error | Causa | Solución |
|---|---|---|
| `Invalid input for phone_number. Expecting a String!` | `phone_number` definido sin comillas | Cambiar a `phone_number = "573239301232"` |
| `ImportError: cannot import name 'ai_evaluate_job'` | Función faltante en el módulo | Agregar la función `ai_evaluate_job` a `openaiConnections.py` |
| `Import "modules.ai.qa_database" could not be resolved` | Archivo `qa_database.py` no existe | Crear el archivo en `modules/ai/` |
| `Import "selenium.webdriver..." could not be resolved` | Selenium no instalado en el entorno activo | `pip install selenium` en el intérprete correcto del IDE |
| Bot cierra el navegador sin aplicar | Error de validación en config | Revisar logs/ para ver el detalle del error |

---

## 📊 Archivos de Salida (`all excels/`)

| Archivo | Contenido |
|---|---|
| `all_applied_applications_history.csv` | Historial de todos los empleos aplicados (ID, empresa, título, fecha, link) |
| `failed_applications.csv` | Empleos donde el bot falló o fue rechazado con el motivo |
| `qa_database.json` | Preguntas y respuestas guardadas por la IA para reutilización |

---

## ⚠️ Notas Importantes

- **LinkedIn puede detectar bots** y suspender tu cuenta. Usa `stealth_mode = True` y evita correr el bot durante horas inusuales.
- **Revisa siempre** los empleos antes de que el bot los envíe activando `pause_before_submit = True`.
- **Nunca subas `config/secrets.py` a Git.** Contiene tus credenciales.
- El bot está diseñado para `Easy Apply` solamente. Empleos con formulario externo se registran pero no se completan automáticamente.
