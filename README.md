# 🎯 CVSniper — Bot Automático de Aplicaciones en LinkedIn

CVSniper automatiza el proceso de aplicar a empleos en LinkedIn usando Selenium para controlar el navegador e IA (OpenAI, DeepSeek o Gemini) para responder preguntas de formularios y filtrar vacantes según tu perfil.

> **Proyecto compartido:** cada persona configura sus propios archivos en `config/` antes de ejecutar. Nunca compartas ni subas a Git los archivos con tus datos reales.

---

## 📋 Tabla de Contenidos

1. [Requisitos](#requisitos)
2. [Instalación](#instalación)
3. [Configuración inicial](#configuración-inicial)
4. [Estructura del proyecto](#estructura-del-proyecto)
5. [Flujo de ejecución](#flujo-de-ejecución)
6. [Módulos de IA](#módulos-de-ia)
7. [Interfaz de control](#interfaz-de-control)
8. [Archivos de salida](#archivos-de-salida)
9. [Errores comunes](#errores-comunes)
10. [Novedades](#novedades)

---

## ✅ Requisitos

- Python 3.10 o superior
- Google Chrome instalado
- Cuenta activa en LinkedIn
- Clave API de uno de los siguientes proveedores de IA (si activas `use_AI = True`):
  - [OpenAI](https://platform.openai.com/api-keys)
  - [Google Gemini](https://aistudio.google.com/app/apikey)
  - [DeepSeek](https://platform.deepseek.com/)

---

## 🚀 Instalación

**1. Clona el repositorio:**
```bash
git clone https://github.com/tu-usuario/CVSniper.git
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

**3. Configura tus archivos** (ver sección siguiente)

**4. Ejecuta el bot:**
```bash
python runAiBot.py
```

---

## ⚙️ Configuración Inicial

Antes de ejecutar el bot debes editar los siguientes archivos en la carpeta `config/`. Cada archivo tiene comentarios que explican cada campo.

> ⚠️ **Importante:** No subas estos archivos a GitHub si contienen tus datos reales. Agrega `config/secrets.py` y `config/personals.py` a tu `.gitignore`.

---

### 1. `config/personals.py` — Tus datos personales

Aquí van los datos que el bot ingresa en los formularios de aplicación.

```python
# Nombre legal
first_name  = "XXXX"
middle_name = ""          # Deja "" si no tienes segundo nombre
last_name   = "XXXX"

# ⚠️ phone_number DEBE ser un string (con comillas)
# Si lo defines sin comillas el bot fallará con un error
phone_number = "573001234567"   # ✅ Correcto
# phone_number = 573001234567   # ❌ Incorrecto → ERROR

# Ubicación
current_city = "XXXXX"         # Si lo dejas "" usa la ciudad del empleo
state        = "XXXXXXX"
zipcode      = "XXXXXX"         # También debe ser string (con comillas)
country      = "XXXXXX"

# Educación
university         = "Universidad XXXXX"
degree             = "Bachelor's"    # "High School", "Associate's", "Bachelor's", "Master's", "Doctorate" o "Other"
graduation_year    = "2021"          # Año de graduación (string con comillas)
field_of_study     = "Computer Science"  # Área de estudio / Major

# Preguntas de igualdad de oportunidades (EEO) — principalmente para empresas de EE.UU.
# Déjalas como "" si no quieres responderlas
ethnicity         = "Hispanic/Latino"   # o ""
gender            = "Male"              # o "" o "Female"
disability_status = "No"
veteran_status    = "No"

# Número de documento — deja "" si no quieres incluirlo
identification_number = ""
```

---

### 2. `config/secrets.py` — Credenciales e IA

```python
# Credenciales de LinkedIn
username = "tu_correo@gmail.com"
password = "tu_contraseña"

# ¿Quieres usar IA para responder preguntas y filtrar empleos?
use_AI = True   # True o False

# Proveedor de IA: "openai", "deepseek" o "gemini"
ai_provider = "gemini"

# URL base de la API (solo cambia si usas un modelo local)
llm_api_url = "https://generativelanguage.googleapis.com/"

# Tu clave API del proveedor elegido
llm_api_key = "TU_CLAVE_API_AQUI"

# Modelo a usar
# Ejemplos: "gpt-4o", "gemini-2.5-flash", "deepseek-chat"
llm_model = "gemini-2.5-flash"

# Debe coincidir con ai_provider
llm_spec = "gemini"   # "openai", "deepseek" o "gemini"

# ¿Mostrar la respuesta de la IA en tiempo real?
stream_output = False
```

**¿Cómo obtener tu clave API?**

| Proveedor | Dónde obtenerla |
|---|---|
| OpenAI | https://platform.openai.com/api-keys |
| Google Gemini | https://aistudio.google.com/app/apikey |
| DeepSeek | https://platform.deepseek.com/ |

---

### 3. `config/search.py` — Preferencias de búsqueda

Define qué empleos busca el bot y con qué filtros.

```python
# Términos de búsqueda — el bot los buscará uno por uno en LinkedIn
search_terms = [
    "Software Engineer",
    "Backend Developer",
    "Python Developer",
]

# Ciudad o región donde buscar empleos
search_location = "tu_ciudad"   # Deja "" para buscar en todo el mundo

# ¿Cuántas aplicaciones hacer por término antes de pasar al siguiente?
switch_number = 10

# ¿Buscar solo empleos con "Easy Apply"?
easy_apply_only = True

# Filtros adicionales (deja [] o "" para no filtrar)
date_posted      = "Past week"    # "", "Past 24 hours", "Past week", "Past month"
sort_by          = "Most recent"  # "", "Most recent", "Most relevant"
experience_level = []             # ["Entry level", "Associate", "Mid-Senior level", ...]
job_type         = []             # ["Full-time", "Part-time", "Contract", "Internship", ...]
on_site          = []             # ["On-site", "Remote", "Hybrid"]

# Palabras prohibidas — si aparecen en la descripción del empleo, el bot lo omite
bad_words = [
    "US Citizen",
    "Security Clearance",
    # Agrega las que necesites
]

# Empresas a evitar
about_company_bad_words = []   # Ej: ["Crossover"]

# Años de experiencia máximos que acepta el bot
# -1 = sin límite (aplica a todos sin importar experiencia requerida)
current_experience = 3

# ─── Filtro de relevancia de título (opcional) ───
# Si está activado, el bot solo aplica a empleos cuyo título
# coincida con alguna de las palabras clave definidas abajo.
enable_job_focus_filter = False   # Cambia a True para activarlo

# Aplica siempre que el título contenga alguna de estas palabras
primary_focus_keywords = [
    "developer",
    "engineer",
    "backend",
]

# Aplica solo si el empleo es Remote o Hybrid
secondary_focus_keywords = [
    "analyst",
    "consultant",
]
```

---

### 4. `config/questions.py` — CV y respuestas comunes

```python
# Ruta a tu CV en PDF (relativa a la raíz del proyecto)
default_resume_path = "all resumes/Mi_CV.pdf"

# Años de experiencia laboral
years_of_experience = 2

# ¿Necesitas visa de trabajo?
require_visa = "No"   # "Yes" o "No"

# Enlace a tu portafolio (deja "" si no tienes)
website = ""

# Enlace a tu perfil de LinkedIn
linkedIn = "https://www.linkedin.com/in/tu-usuario/"

# Salario esperado (en números, sin puntos ni comas)
desired_salary = 5000000

# CTC actual
current_ctc = 0

# Días de preaviso para dejar tu empleo actual
notice_period = 30
```

---

### 5. `config/settings.py` — Comportamiento del bot

```python
# ¿Correr el bot sin abrir ventana de Chrome?
run_in_background = False   # True = headless (sin interfaz visual)

# Modo sigiloso para evitar detección de LinkedIn
stealth_mode = True   # Recomendado dejarlo en True

# ¿Pausar antes de enviar cada aplicación para revisión manual?
pause_before_submit = True   # Recomendado True al inicio

# ¿Pausar si la IA no puede responder una pregunta del formulario?
pause_at_failed_question = True

# ¿Correr sin parar hasta que lo detengas manualmente?
run_non_stop = False

# ¿Seguir a las empresas al aplicar?
follow_companies = False
```

---

## 📁 Estructura del Proyecto

```
CVSniper/
│
├── runAiBot.py                  ← Punto de entrada — ejecuta esto
├── app.py                       ← Servidor Flask + interfaz gráfica (UI)
├── compress_pdf.py              ← Utilidad para comprimir PDFs del CV
├── merge_resumes.py             ← Combina múltiples CVs en uno solo
│
├── config/                      ← ⚙️ Configura estos archivos antes de ejecutar
│   ├── personals.py             ← Tus datos personales (nombre, teléfono, ciudad...)
│   ├── secrets.py               ← Credenciales de LinkedIn y clave API de IA
│   ├── search.py                ← Qué empleos buscar y con qué filtros
│   ├── settings.py              ← Comportamiento general del bot
│   └── questions.py             ← Ruta del CV y respuestas a preguntas comunes
│
├── modules/                     ← Lógica interna (no necesitas tocar esto)
│   ├── bot_ui.py                ← Ventana flotante de control del bot
│   ├── helpers.py               ← Funciones utilitarias (logs, JSON, directorios)
│   ├── open_chrome.py           ← Inicialización de Chrome con Selenium
│   ├── clickers_and_finders.py  ← Interacciones con el DOM de LinkedIn
│   ├── validator.py             ← Valida los archivos de configuración al inicio
│   │
│   └── ai/                      ← Módulos de inteligencia artificial
│       ├── openaiConnections.py ← Integración con OpenAI (GPT)
│       ├── deepseekConnections.py ← Integración con DeepSeek
│       ├── geminiConnections.py ← Integración con Google Gemini
│       ├── prompts.py           ← Plantillas de prompts enviados a la IA
│       └── qa_database.py       ← Caché local de preguntas y respuestas
│
├── all resumes/                 ← Coloca aquí tu CV en PDF
├── all excels/                  ← Salidas: historial CSV, base de datos QA
├── logs/                        ← Logs detallados de cada sesión
├── templates/                   ← Plantillas HTML del panel web
└── setup/                       ← Scripts de instalación por sistema operativo
```

---

## 🔄 Flujo de Ejecución

Cuando corres `python runAiBot.py` el bot sigue este proceso:

```
1. INICIO
   ├─ Carga y valida todos los archivos de config/
   ├─ Abre Chrome con Selenium
   ├─ Lanza la ventana de control (bot_ui.py)
   └─ Conecta con el proveedor de IA configurado

2. LOGIN EN LINKEDIN
   ├─ Navega a linkedin.com/feed
   └─ Inicia sesión con las credenciales de secrets.py

3. BÚSQUEDA DE EMPLEOS
   └─ Para cada término en search_terms:
       ├─ Aplica los filtros de search.py
       └─ Itera sobre los resultados página por página

4. EVALUACIÓN DE CADA EMPLEO
   ├─ ¿Ya fue aplicado antes?         → Saltar
   ├─ ¿Contiene bad_words?            → Saltar
   ├─ ¿Título fuera del focus_filter? → Saltar
   └─ IA evalúa si el perfil cumple   → Continuar o saltar

5. APLICACIÓN (Easy Apply)
   ├─ Clic en "Easy Apply"
   ├─ Paso 1: datos personales de personals.py
   ├─ Paso 2: preguntas conocidas de questions.py
   ├─ Paso 3: preguntas nuevas → IA las responde y las guarda en qa_database.json
   ├─ Revisión manual (si pause_before_submit = True)
   └─ Envío de la solicitud

6. REGISTRO
   ├─ Éxito → all excels/all_applied_applications_history.csv
   └─ Fallo  → all excels/failed_applications.csv
```

---

## 🤖 Módulos de IA

El bot soporta tres proveedores de IA intercambiables. Se selecciona con `ai_provider` en `secrets.py`.

| Función | Qué hace |
|---|---|
| `*_create_client()` | Conecta con la API del proveedor |
| `*_extract_skills(client, job_description)` | Extrae habilidades requeridas del empleo en JSON |
| `*_answer_question(client, question, ...)` | Responde preguntas del formulario (texto, selección, sí/no) |
| `*_evaluate_job(client, description, user_info)` | Evalúa si tu perfil cumple los requisitos del empleo |

Todas las respuestas generadas por la IA se guardan en `all excels/qa_database.json` para no repetir consultas en futuras sesiones.

---

## 🖥️ Interfaz de Control

Al ejecutar el bot aparece una ventana flotante en la esquina de la pantalla con:

- **Panel de logs** con lo que hace el bot en tiempo real
- Botón **PAUSE** — pausa el bot entre acciones de forma segura
- Botón **STOP** — detiene la ejecución completamente
  - Requiere doble clic de confirmación (el botón cambia a naranja tras el primer clic)
  - Si Chrome o chromedriver no responde, fuerza la salida del proceso después de 5 segundos

Atajos de teclado:
- `Ctrl + Q` o `Ctrl + C` — detener (fuerza salida inmediata)
- `Ctrl + P` — pausar / reanudar

---

## 📊 Archivos de Salida

Todos los archivos se generan automáticamente en `all excels/`:

| Archivo | Contenido |
|---|---|
| `all_applied_applications_history.csv` | Historial completo: ID, empresa, título, link, fecha de aplicación |
| `failed_applications.csv` | Empleos fallidos con el motivo del error o rechazo |
| `qa_database.json` | Caché de preguntas y respuestas de la IA para reutilizar |

---

## 🐛 Errores Comunes

| Error | Causa | Solución |
|---|---|---|
| `Invalid input for phone_number. Expecting a String!` | `phone_number` o `zipcode` definidos sin comillas | Agregar comillas: `phone_number = "573001234567"` |
| `ImportError: cannot import name 'ai_evaluate_job'` | Función faltante en módulo de IA | Revisar que `openaiConnections.py` esté actualizado |
| `Import "modules.ai.qa_database" could not be resolved` | Archivo `qa_database.py` no existe | Crear el archivo en `modules/ai/` |
| `Import "selenium..." could not be resolved` en el IDE | Selenium no instalado en el entorno activo | `pip install selenium` con el intérprete correcto del IDE |
| El bot cierra el navegador sin aplicar | Error en validación de config al inicio | Revisar `logs/` para ver el detalle del error |
| LinkedIn pide verificación / CAPTCHA | LinkedIn detectó actividad automatizada | Activar `stealth_mode = True` y reducir velocidad |

---

## 🔒 Seguridad

- **Nunca subas `config/secrets.py` ni `config/personals.py` a GitHub** con tus datos reales.
- Agrega estas líneas a tu `.gitignore`:
  ```
  config/secrets.py
  config/personals.py
  all excels/
  logs/
  all resumes/
  ```
- Cada colaborador del proyecto debe crear sus propios archivos de config localmente a partir de los templates incluidos.

---

## 📌 Notas Finales

- El bot está diseñado exclusivamente para **Easy Apply** de LinkedIn. Empleos con formulario externo se registran pero no se completan automáticamente.
- Usa `pause_before_submit = True` al principio para revisar cada aplicación antes de enviarla.
- LinkedIn puede detectar y suspender cuentas por actividad automatizada excesiva. Usa el bot con moderación.

---

## 🆕 Novedades

### Formularios — campos condicionales "If YES" resueltos
Algunos formularios de Easy Apply muestran campos de texto adicionales que solo aparecen en el DOM cuando el usuario selecciona "Yes" en un radio previo (ej: *"If your answer is YES, please provide the name of the referring staff member"*). El bot ahora los maneja automáticamente:
- Si la respuesta final al radio es **"No"**, el bot primero hace clic en **"Yes"** para que React monte los campos condicionales en el DOM, les escribe **"N/A"** usando el setter nativo de React, y luego hace clic en **"No"**. Esto evita que los campos obligatorios queden vacíos y bloqueen el envío del formulario.

### Prompts de IA mejorados
- Reglas explícitas para responder **"N/A"** en preguntas de referidos, conflictos de interés y campos condicionales follow-up.
- Evaluación de empleo más permisiva: solo rechaza candidatos claramente descalificados (gran brecha de experiencia, dominio completamente distinto, requisito legal inamovible o vacante exclusiva para personas con discapacidad).

### Nuevos campos de educación en `personals.py`
Se agregaron `degree`, `graduation_year` y `field_of_study` para que el bot pueda responder preguntas académicas en formularios sin depender de la IA.

### Botón Stop — fuerza de salida garantizada
Se corrigió un bug donde el botón Stop dejaba de funcionar cuando Chrome/chromedriver estaba colgado (por ejemplo, durante una llamada larga a la API de Gemini). Ahora, al confirmar el Stop, se lanza un hilo de seguridad que fuerza `os._exit(0)` después de 5 segundos, sin importar el estado del driver.
