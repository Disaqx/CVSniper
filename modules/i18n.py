'''
CVSniper - Internationalization (i18n) Module
All UI strings in both Spanish (es) and English (en).
Add new keys here as the app grows.
'''

import os
import ast

TRANSLATIONS = {
    "es": {
        # Main UI panel
        "title":                "CVSNIPER CONTROL",
        "title_career_ops":     "CVSNIPER - CAREER-OPS",
        "btn_pause":            "PAUSAR",
        "btn_resume":           "REANUDAR",
        "btn_career_ops":       "CAREER-OPS",
        "btn_optimize_cv":      "OPTIMIZAR CV",
        "btn_stop":             "DETENER",

        # Status messages
        "status_idle":          "Estado: Inactivo",
        "status_initializing":  "Inicializando",
        "status_configured":    "Estado: Configurado",
        "status_config_req":    "Configuracion requerida",
        "msg_ready":            "Bot listo para continuar.",
        "msg_fill_config":      "Por favor completa tus datos en la configuracion.",

        # CV Optimizer
        "cv_opt_title":         "Optimizador de CV",
        "cv_opt_question":      "?Deseas optimizar un CV existente o empezar de cero usando tus datos de configuracion?",
        "cv_opt_existing":      "EXISTENTE",
        "cv_opt_scratch":       "DE CERO",
        "cv_port_title":        "Portfolio",
        "cv_port_question":     "?Deseas incluir la pagina del Portfolio visual al final del CV?",
        "cv_port_yes":          "SI",
        "cv_port_no":           "NO",
        "cv_select_old":        "Seleccionar CV Viejo",
        "cv_optimizing":        "Optimizando CV con Inteligencia Artificial...",
        "cv_generating":        "Generando CV llamativo con tus datos de configuracion...",
        "cv_success_title":     "Exito!",
        "cv_success_opt":       "Se genero exitosamente tu CV optimizado y llamativo.",
        "cv_success_gen":       "Se genero exitosamente tu CV llamativo a partir de tu informacion basica.",
        "cv_saved":             "CV guardado en 'all resumes/'.",
        "cv_error_opt":         "Error al optimizar CV. Revisa la consola para mas detalles.",
        "cv_error_gen":         "Error al generar CV desde cero. Revisa la consola.",

        # Configuration panel
        "cfg_title":            "CONFIGURACION",
        "cfg_tab_search":       "Busqueda",
        "cfg_tab_personal":     "Personal",
        "cfg_tab_responses":    "Respuestas",
        "cfg_tab_bot":          "Bot",
        "cfg_save":             "GUARDAR",
        "cfg_cancel":           "CANCELAR",
        "cfg_saved_ok":         "Configuracion guardada correctamente",
        "cfg_saved_err":        "Errores en: ",

        # First-run / setup
        "setup_title":          "Configuracion Inicial Requerida",
        "setup_msg":            "Es la primera vez que ejecutas el bot o faltan tus datos personales.\n\nSe abrira la ventana de configuracion. Llena tus datos y presiona GUARDAR para continuar.",

        # LinkedIn reminder
        "linkedin_title":       "Antes de continuar",
        "linkedin_msg":         "Asegurate de que tu cuenta de LinkedIn este ABIERTA e INICIADA SESION en Google Chrome antes de continuar.\n\nEl bot usara tu sesion existente de Chrome para aplicar a trabajos automaticamente.\n\nSi no tienes tu cuenta abierta, abrela ahora y luego haz clic en CONTINUAR.",

        # Career-Ops mode
        "career_ops_on":        "Modo Career-Ops activado. Se omitira Easy Apply; todos los matches se abriran manualmente.",
        "career_ops_msg":       "El Modo Career-Ops esta activo:\n\n- Omitiendo postulaciones automaticas (Easy Apply).\n- Buscando y evaluando todas las vacantes usando IA.\n- Al encontrar 5 coincidencias, te preguntara si deseas abrirlas para postular manualmente.\n- Podras confirmar si ya aplicaste para continuar con el siguiente ciclo.",
        "career_ops_off":       "Modo Career-Ops desactivado. Regresando a Easy Apply automatico.",

        # Stop/confirm flow
        "btn_confirm":          "CONFIRMAR?",
        "btn_stopping":         "DETENIENDO...",
        "msg_confirm_stop":     "Haz clic en CONFIRMAR nuevamente para detener el bot.",
        "msg_stopping":         "Deteniendo bot...",

        # Console log messages
        "log_paused":           "Bot pausado.",
        "log_resumed":          "Bot reanudado.",

        # Language setting
        "lang_label":           "Idioma de la Interfaz",

        # Configuration enforcement
        "status_config_req":    "Configuracion requerida",
        "msg_config_req":       "Por favor completa tus datos en la configuracion.",
        "status_configured":    "Configurado",
        "msg_bot_ready":        "Bot listo para continuar.",
        "alert_api_key_title":  "Falta API Key de IA",
        "alert_api_key_msg":    "La IA esta activada pero falta la API Key.\n\nEn los ajustes (boton ⚙) → tab Bot → seccion IA:\n→ Pega tu API Key de Groq (gratis en console.groq.com)\n\nGuarda los cambios para continuar.",

        # CV Wizard
        "wiz_api_key_title":    "Configurar API Key primero",
        "wiz_api_key_msg":      "Para la configuracion automatica con IA necesitas\nuna API Key de Groq (100% gratis):\n\n  1. Ve a console.groq.com\n  2. Inicia sesion → API Keys → Create key\n  3. En los ajustes → tab Bot → IA Settings\n     pega tu key y haz clic en Guardar\n\nAl guardar, el asistente se abrira automaticamente\npara leer tu hoja de vida y configurar el bot.",
        "wiz_title":            "Configuracion Automatica",
        "wiz_msg":              "Bienvenido a CVSniper!\n\nPuedo leer tu hoja de vida (CV en PDF) y configurar\nel bot automaticamente:\n\n  • Tu nombre, ciudad, telefono\n  • Terminos de busqueda segun tu perfil\n  • Informacion para responder formularios\n  • Ruta de tu CV guardada\n\nSi no tienes tu CV a mano, puedes configurar manualmente.",
        "wiz_btn_upload":       "SUBIR MI CV",
        "wiz_btn_manual":       "CONFIGURAR MANUALMENTE",
        "wiz_pdf_dialog":       "Selecciona tu CV (PDF)",
        "wiz_status":           "Analizando CV",
        "wiz_detail_pdf":       "Extrayendo texto del PDF...",
        "wiz_detail_ai":        "Consultando IA para extraer tus datos...",
        "wiz_err_pdf_title":    "Error de lectura",
        "wiz_err_pdf_msg":      "No se pudo extraer texto del PDF.\n\nAsegurate de que el PDF no sea una imagen escaneada.\nPodras configurar manualmente en los ajustes.",
        "wiz_err_ai_title":     "Error de IA",
        "wiz_err_ai_msg":       "No se pudo procesar el CV con IA.\n\nVerifica tu API Key en los ajustes (⚙ → Bot → IA Settings)\ny vuelve a iniciar el bot.",
        "wiz_done_title":       "Configuracion Completada!",
        "wiz_done_name":        "Nombre",
        "wiz_done_city":        "Ciudad",
        "wiz_done_exp":         "Experiencia",
        "wiz_done_terms":       "Busquedas",
        "wiz_done_suffix_exp":  "años",
        "wiz_done_suffix_terms": "terminos configurados",
        "wiz_done_footer":      "Revisa y completa tus datos en los ajustes (boton ⚙).\nPresta atencion al tab Respuestas y al tab Busqueda.",

        # Job Terms Wizard
        "job_terms_wiz_title":  "Cargos de busqueda vacios",
        "job_terms_wiz_msg":    "No tienes cargos configurados para buscar en LinkedIn.\n\n¿Quieres que analice tu CV con IA para generar los mejores cargos automaticamente?",
        "job_terms_btn_yes":    "Si, analizar CV",
        "job_terms_btn_no":     "No, configurar manualmente",
        "job_terms_done_title": "Cargos Generados",
        "job_terms_done_msg":   "Se generaron los siguientes cargos de busqueda:\n\n",

        # CV Optimizer (optimize_cv_flow)
        "cv_opt_btn_existing":  "EXISTENTE",
        "cv_opt_btn_scratch":   "DE CERO",
        "cv_port_btn_yes":      "SI",
        "cv_port_btn_no":       "NO",
        "cv_log_optimizing":    "Optimizando CV con Inteligencia Artificial...",
        "cv_log_generating":    "Generando CV llamativo con tus datos de configuracion...",
        "cv_log_saved_opt":     "CV Optimizado guardado en 'all resumes/'.",
        "cv_log_saved_gen":     "CV Generado guardado en 'all resumes/'.",
        "cv_log_err_opt":       "Error al optimizar CV. Revisa la consola para mas detalles.",
        "cv_log_err_gen":       "Error al generar CV desde cero. Revisa la consola.",
    },
    "en": {
        # Main UI panel
        "title":                "CVSNIPER CONTROL",
        "title_career_ops":     "CVSNIPER - CAREER-OPS",
        "btn_pause":            "PAUSE",
        "btn_resume":           "RESUME",
        "btn_career_ops":       "CAREER-OPS",
        "btn_optimize_cv":      "OPTIMIZE CV",
        "btn_stop":             "STOP",

        # Status messages
        "status_idle":          "Status: Idle",
        "status_initializing":  "Initializing",
        "status_configured":    "Status: Configured",
        "status_config_req":    "Configuration required",
        "msg_ready":            "Bot ready to continue.",
        "msg_fill_config":      "Please complete your data in the configuration panel.",

        # CV Optimizer
        "cv_opt_title":         "CV Optimizer",
        "cv_opt_question":      "Do you want to optimize an existing CV or start from scratch using your configuration data?",
        "cv_opt_existing":      "EXISTING",
        "cv_opt_scratch":       "FROM SCRATCH",
        "cv_port_title":        "Portfolio",
        "cv_port_question":     "Do you want to include the visual Portfolio page at the end of the CV?",
        "cv_port_yes":          "YES",
        "cv_port_no":           "NO",
        "cv_select_old":        "Select Old CV",
        "cv_optimizing":        "Optimizing CV with Artificial Intelligence...",
        "cv_generating":        "Generating attractive CV from your configuration data...",
        "cv_success_title":     "Success!",
        "cv_success_opt":       "Your optimized and attractive CV was generated successfully.",
        "cv_success_gen":       "Your attractive CV was generated successfully from your basic information.",
        "cv_saved":             "CV saved to 'all resumes/'.",
        "cv_error_opt":         "Error optimizing CV. Check the console for details.",
        "cv_error_gen":         "Error generating CV from scratch. Check the console.",

        # Configuration panel
        "cfg_title":            "SETTINGS",
        "cfg_tab_search":       "Search",
        "cfg_tab_personal":     "Personal",
        "cfg_tab_responses":    "Responses",
        "cfg_tab_bot":          "Bot",
        "cfg_save":             "SAVE",
        "cfg_cancel":           "CANCEL",
        "cfg_saved_ok":         "Configuration saved successfully",
        "cfg_saved_err":        "Errors in: ",

        # First-run / setup
        "setup_title":          "Initial Setup Required",
        "setup_msg":            "This is your first time running the bot or your personal data is missing.\n\nThe settings panel will open. Fill in your data and press SAVE to continue.",

        # LinkedIn reminder
        "linkedin_title":       "Before you continue",
        "linkedin_msg":         "Make sure your LinkedIn account is OPEN and SIGNED IN on Google Chrome before continuing.\n\nThe bot will use your existing Chrome session to automatically apply to jobs.\n\nIf your account is not open, open it now and then click CONTINUE.",

        # Career-Ops mode
        "career_ops_on":        "Career-Ops Mode activated. Easy Apply will be skipped; all matches will open manually.",
        "career_ops_msg":       "Career-Ops Mode is active:\n\n- Skipping automatic applications (Easy Apply).\n- Searching and evaluating all vacancies using AI.\n- When 5 matches are found, it will ask if you want to open them for manual application.\n- You can confirm if you already applied to continue with the next cycle.",
        "career_ops_off":       "Career-Ops Mode deactivated. Returning to automatic Easy Apply.",

        # Stop/confirm flow
        "btn_confirm":          "CONFIRM?",
        "btn_stopping":         "STOPPING...",
        "msg_confirm_stop":     "Click CONFIRM? again to stop the bot.",
        "msg_stopping":         "Stopping bot...",

        # Console log messages
        "log_paused":           "Bot paused.",
        "log_resumed":          "Bot resumed.",

        # Language setting
        "lang_label":           "Interface Language",

        # Configuration enforcement
        "status_config_req":    "Configuration required",
        "msg_config_req":       "Please complete your data in the configuration panel.",
        "status_configured":    "Configured",
        "msg_bot_ready":        "Bot ready to continue.",
        "alert_api_key_title":  "Missing AI API Key",
        "alert_api_key_msg":    "AI is enabled but the API Key is missing.\n\nIn settings (⚙ button) → Bot tab → IA section:\n→ Paste your Groq API Key (free at console.groq.com)\n\nSave changes to continue.",

        # CV Wizard
        "wiz_api_key_title":    "Set up API Key first",
        "wiz_api_key_msg":      "To use the automatic AI configuration you need\na Groq API Key (100% free):\n\n  1. Go to console.groq.com\n  2. Sign in → API Keys → Create key\n  3. In settings → Bot tab → IA Settings\n     paste your key and click Save\n\nAfter saving, the wizard will open automatically\nto read your resume and configure the bot.",
        "wiz_title":            "Automatic Setup",
        "wiz_msg":              "Welcome to CVSniper!\n\nI can read your resume (PDF) and configure\nthe bot automatically:\n\n  • Your name, city, phone\n  • Job search terms based on your profile\n  • Information to answer application forms\n  • Your resume path saved\n\nIf you don't have your resume handy, you can configure manually.",
        "wiz_btn_upload":       "UPLOAD MY RESUME",
        "wiz_btn_manual":       "CONFIGURE MANUALLY",
        "wiz_pdf_dialog":       "Select your Resume (PDF)",
        "wiz_status":           "Analyzing Resume",
        "wiz_detail_pdf":       "Extracting text from PDF...",
        "wiz_detail_ai":        "Consulting AI to extract your data...",
        "wiz_err_pdf_title":    "Read Error",
        "wiz_err_pdf_msg":      "Could not extract text from the PDF.\n\nMake sure the PDF is not a scanned image.\nYou can configure manually in settings.",
        "wiz_err_ai_title":     "AI Error",
        "wiz_err_ai_msg":       "Could not process the resume with AI.\n\nCheck your API Key in settings (⚙ → Bot → IA Settings)\nand restart the bot.",
        "wiz_done_title":       "Setup Complete!",
        "wiz_done_name":        "Name",
        "wiz_done_city":        "City",
        "wiz_done_exp":         "Experience",
        "wiz_done_terms":       "Searches",
        "wiz_done_suffix_exp":  "years",
        "wiz_done_suffix_terms": "terms configured",
        "wiz_done_footer":      "Review and complete your data in settings (⚙ button).\nPay attention to the Responses and Search tabs.",

        # Job Terms Wizard
        "job_terms_wiz_title":  "Job search terms empty",
        "job_terms_wiz_msg":    "You have no job search terms configured for LinkedIn.\n\nDo you want me to analyze your resume with AI to automatically generate the best positions?",
        "job_terms_btn_yes":    "Yes, analyze resume",
        "job_terms_btn_no":     "No, configure manually",
        "job_terms_done_title": "Job Terms Generated",
        "job_terms_done_msg":   "The following job search terms were generated:\n\n",

        # CV Optimizer (optimize_cv_flow)
        "cv_opt_btn_existing":  "EXISTING",
        "cv_opt_btn_scratch":   "FROM SCRATCH",
        "cv_port_btn_yes":      "YES",
        "cv_port_btn_no":       "NO",
        "cv_log_optimizing":    "Optimizing CV with Artificial Intelligence...",
        "cv_log_generating":    "Generating attractive CV from your configuration data...",
        "cv_log_saved_opt":     "Optimized CV saved to 'all resumes/'.",
        "cv_log_saved_gen":     "Generated CV saved to 'all resumes/'.",
        "cv_log_err_opt":       "Error optimizing CV. Check the console for details.",
        "cv_log_err_gen":       "Error generating CV from scratch. Check the console.",
    }
}

_settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.py")
_lang_cache: dict = {}   # {"lang": "es", "mtime": 0.0}

def get_language() -> str:
    """Reads ui_language from settings.py, cached by file mtime."""
    try:
        mtime = os.path.getmtime(_settings_path)
        if _lang_cache.get("mtime") == mtime:
            return _lang_cache.get("lang", "es")
        with open(_settings_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "ui_language":
                        lang = ast.literal_eval(node.value)
                        _lang_cache["lang"] = lang
                        _lang_cache["mtime"] = mtime
                        return lang
    except Exception:
        pass
    return "es"

def T(key: str) -> str:
    """Returns the translated string for the current language."""
    lang = get_language()
    return TRANSLATIONS.get(lang, TRANSLATIONS["es"]).get(key, key)
