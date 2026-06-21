'''
CVSniper - Internationalization (i18n) Module
All UI strings in both Spanish (es) and English (en).
Add new keys here as the app grows.
'''

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

        # Language setting
        "lang_label":           "Idioma de la Interfaz / UI Language",
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

        # Language setting
        "lang_label":           "Idioma de la Interfaz / UI Language",
    }
}

def get_language() -> str:
    """Reads ui_language from config/settings.py. Defaults to 'es'."""
    try:
        import ast, os
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.py")
        with open(settings_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "ui_language":
                        return ast.literal_eval(node.value)
    except Exception:
        pass
    return "es"

def T(key: str) -> str:
    """Returns the translated string for the current language."""
    lang = get_language()
    return TRANSLATIONS.get(lang, TRANSLATIONS["es"]).get(key, key)
