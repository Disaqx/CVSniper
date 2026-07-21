'''
CVSniper - Internationalization (i18n) Module

Loads UI strings from JSON files located in the `i18n/{lang}/` directory.
This allows for modular and easier management of translations.
'''

import ast
import json
import os

_TRANSLATIONS_CACHE = {}
_I18N_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "i18n")

def _load_language(lang_code: str) -> dict:
    """Loads all JSON files for a given language and merges them."""
    if lang_code in _TRANSLATIONS_CACHE:
        return _TRANSLATIONS_CACHE[lang_code]

    lang_dir = os.path.join(_I18N_DIR, lang_code)
    if not os.path.isdir(lang_dir):
        # Fallback to English if the language directory doesn't exist
        if lang_code != "en":
            return _load_language("en")
        return {}

    merged_translations = {}
    try:
        for filename in os.listdir(lang_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(lang_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    merged_translations.update(json.load(f))
        _TRANSLATIONS_CACHE[lang_code] = merged_translations
        return merged_translations
    except (IOError, json.JSONDecodeError) as e:
        print(f"[i18n] Error loading language '{lang_code}': {e}")
        return {}

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

        # Settings panel section titles
        "cfg_sec_linkedin":     "Cuenta LinkedIn",
        "cfg_sec_search_main":  "Terminos de busqueda",
        "cfg_sec_relevance":    "Filtro de relevancia",
        "cfg_sec_filters":      "Filtros LinkedIn",
        "cfg_sec_avoid":        "Palabras a evitar",
        "cfg_sec_personal":     "Datos personales",
        "cfg_sec_eeo":          "Igualdad de oportunidades",
        "cfg_sec_exp":          "Experiencia y salario",
        "cfg_sec_links":        "Links",
        "cfg_sec_texts":        "Textos largos",
        "cfg_sec_behavior":     "Comportamiento del bot",
        "cfg_sec_browser":      "Navegador y performance",
        "cfg_sec_cycles":       "Ciclos de busqueda",
        "cfg_sec_ai":           "Inteligencia Artificial",

        # Wizard — LinkedIn credentials
        "wiz_cred_title":       "Cuenta de LinkedIn",
        "wiz_cred_email":       "Correo de LinkedIn (usuario):\n(el mismo email con el que inicias sesion)",
        "wiz_cred_pass":        "Contrasena de LinkedIn:",

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
        "btn_skip":             "OMITIR",
        "btn_save":             "GUARDAR",
        "btn_browse":           "EXAMINAR",
        "btn_dashboard":        "Panel",
        "browse_pdf_title":     "Seleccionar CV (PDF)",
        "hint_one_per_line":    "(una por línea)",
        "cfg_field_search_terms": "Términos de búsqueda (search_terms)",
        "cfg_field_search_location": "Ubicación (search_location)",
        "cfg_field_primary_focus_keywords": "Palabras clave PRINCIPALES (Help Desk, Tech Support...)",
        "cfg_field_secondary_focus_keywords": "Palabras clave SECUNDARIAS (solo Remote/Hybrid)",
        "cfg_field_enable_job_focus_filter": "Activar filtro de relevancia (skip trabajos irrelevantes)",
        "cfg_field_switch_number": "Cambiar búsqueda cada N aplicaciones",
        "cfg_field_date_posted": "Fecha de publicación",
        "cfg_field_sort_by": "Ordenar por",
        "cfg_field_on_site": "Modalidad de trabajo",
        "cfg_field_experience_level": "Nivel de experiencia",
        "cfg_field_job_type": "Tipo de empleo",
        "cfg_field_easy_apply_only": "Solo Easy Apply",
        "cfg_field_randomize_search_order": "Aleatorizar orden de búsqueda",
        "cfg_field_bad_words": "Palabras malas en descripción (bad_words)",
        "cfg_field_about_company_bad_words": "Palabras malas en empresa",
        "cfg_field_current_experience": "Experiencia actual en años (-1 = ignorar)",
        "cfg_field_first_name": "Nombre (first_name)",
        "cfg_field_middle_name": "Segundo nombre (middle_name)",
        "cfg_field_last_name": "Apellido (last_name)",
        "cfg_field_phone_number": "Teléfono (phone_number)",
        "cfg_field_current_city": "Ciudad actual (current_city)",
        "cfg_field_state": "Estado/Departamento (state)",
        "cfg_field_country": "País (country)",
        "cfg_field_zipcode": "Código postal (zipcode)",
        "cfg_field_street": "Calle (street)",
        "cfg_field_university": "Institución educativa (university)",
        "cfg_field_degree": "Nivel de educación (degree)",
        "cfg_field_graduation_year": "Año de graduación (graduation_year)",
        "cfg_field_field_of_study": "Campo de estudio / Major (field_of_study)",
        "cfg_field_identification_number": "Número de identificación",
        "cfg_field_eeo_note": "Respuestas para formularios de igualdad de oportunidades (empleos en EE. UU.)",
        "cfg_field_gender": "Género",
        "cfg_field_ethnicity": "Etnia",
        "cfg_field_disability_status": "¿Tienes alguna discapacidad?",
        "cfg_field_veteran_status": "¿Veterano militar de EE. UU.?",
        "cfg_field_years_of_experience": "Años de experiencia a reportar",
        "cfg_field_desired_salary": "Salario anual deseado — solo número, en la moneda de la vacante (ej. 80000000 si es COP)",
        "cfg_field_current_ctc": "Salario anual actual — solo número, misma moneda (los formularios lo llaman CTC / current compensation)",
        "cfg_field_notice_period": "Días de preaviso para dejar tu empleo actual",
        "cfg_field_require_visa": "¿Necesitas que la empresa patrocine tu visa de trabajo?",
        "cfg_field_recent_employer": "Empleador más reciente",
        "cfg_field_confidence_level": "Qué tan seguras/positivas son las respuestas del bot (1 = conservador, 10 = muy seguro)",
        "cfg_field_us_citizenship": "Estatus migratorio en EE. UU. — solo aplica a vacantes de USA",
        "cfg_field_linkedin": "URL de LinkedIn",
        "cfg_field_website": "Portfolio / Website",
        "cfg_field_linkedin_headline": "Titular de LinkedIn",
        "cfg_field_linkedin_summary": "Resumen de LinkedIn",
        "cfg_field_cover_letter": "Carta de presentación",
        "cfg_field_user_information_all": "Información completa para IA",
        "cfg_field_default_resume_path": "Ruta del CV (PDF)",
        "cfg_field_pause_before_submit": "Pausar antes de enviar cada aplicación",
        "cfg_field_pause_at_failed_question": "Pausar si no puede responder una pregunta",
        "cfg_field_overwrite_previous_answers": "Sobreescribir respuestas anteriores",
        "cfg_field_run_non_stop": "Correr sin parar (run_non_stop)",
        "cfg_field_follow_companies": "Seguir empresas al aplicar",
        "cfg_field_close_tabs": "Cerrar tabs de aplicaciones externas",
        "cfg_field_external_apply_enabled": "Aplicador universal: autollenar solicitudes externas (Greenhouse/Lever)",
        "cfg_field_pause_before_submit_external": "Pausar antes de enviar solicitudes externas",
        "cfg_field_click_gap": "Pausa entre clicks (seg)",
        "cfg_field_run_in_background": "Correr en fondo (sin Chrome visible)",
        "cfg_field_smooth_scroll": "Scroll suave",
        "cfg_field_stealth_mode": "Modo stealth (anti-bot)",
        "cfg_field_safe_mode": "Modo seguro (perfil invitado)",
        "cfg_field_keep_screen_awake": "Mantener pantalla activa",
        "cfg_field_alternate_sortby": "Alternar orden de resultados",
        "cfg_field_cycle_date_posted": "Ciclar filtro de fecha automáticamente",
        "cfg_field_stop_date_cycle_at_24hr": "Parar ciclo al llegar a 24h",
        "cfg_field_ui_language": "Idioma de la interfaz",
        "cfg_field_use_AI": "Usar IA para evaluar vacantes y responder preguntas",
        "cfg_field_ai_provider": "Proveedor de IA",
        "cfg_field_llm_api_key": "API Key (en groq.com → API Keys → Create key)",
        "cfg_field_llm_model": "Modelo (ej. llama-3.1-8b-instant para Groq)",
        "cfg_field_llm_api_url": "URL de API (solo para OpenAI-compatibles / Ollama)",
        "opt_past_24_hours": "Últimas 24 horas",
        "opt_past_week": "Última semana",
        "opt_past_month": "Último mes",
        "opt_any_time": "Cualquier fecha",
        "opt_most_recent": "Más recientes",
        "opt_most_relevant": "Más relevantes",
        "opt_on_site": "Presencial",
        "opt_hybrid": "Híbrido",
        "opt_remote": "Remoto",
        "opt_internship": "Prácticas",
        "opt_entry_level": "Junior",
        "opt_associate": "Asociado",
        "opt_mid_senior": "Semi-Senior",
        "opt_director": "Director",
        "opt_executive": "Ejecutivo",
        "opt_full_time": "Tiempo completo",
        "opt_part_time": "Medio tiempo",
        "opt_contract": "Contrato",
        "opt_temporary": "Temporal",
        "opt_volunteer": "Voluntariado",
        "opt_high_school": "Bachillerato",
        "opt_associates": "Técnico",
        "opt_bachelors": "Pregrado",
        "opt_masters": "Maestría",
        "opt_doctorate": "Doctorado",
        "opt_other": "Otro",
        "opt_no": "No",
        "opt_yes": "Sí",
        "opt_decline": "Prefiero no decir",
        "career_ops_title": "Modo Career-Ops",
        "dashboard_opened": "Panel abierto",
        "status_init_msg": "CVSniper Control inicializado.",
        "cv_error_title": "Error",
        "cv_error_msg": "No se pudo optimizar el CV.\n\nVerifica que tu API Key sea válida en Ajustes → Bot → IA Settings.\nSi usas Gemini, genera una nueva key en aistudio.google.com\nSi usas Groq, verifica en console.groq.com",
        "cv_generate_error_msg": "No se pudo generar el CV.\n\nVerifica que tu API Key sea válida en Ajustes → Bot → IA Settings.\nSi usas Gemini, genera una nueva key en aistudio.google.com\nSi usas Groq, verifica en console.groq.com",
        "wizard_title_complete": "Completar configuración",
        "wizard_prompt_first_name": "¿Cuál es tu PRIMER nombre?\n(solo el primero — ej: Camilo)",
        "wizard_prompt_last_name": "¿Cuáles son tus APELLIDOS?\n(uno o dos apellidos — ej: García López)",
        "wizard_prompt_middle_name": "¿Tienes segundo nombre? (puedes saltar)",
        "wizard_prompt_phone": "Número de teléfono con código de país:\n(ej: 573001234567 para Colombia)",
        "wizard_prompt_current_city": "¿En qué ciudad vives actualmente?\n(ej: Bogotá)",
        "wizard_prompt_country": "¿En qué país vives?\n(ej: Colombia)",
        "wizard_prompt_state": "¿En qué departamento o estado vives?\n(ej: Cundinamarca, Antioquia)",
        "wizard_prompt_zipcode": "¿Cuál es tu código postal?\n(puedes dejarlo vacío si no lo sabes)",
        "wizard_prompt_search_location": "¿En qué ciudad/país buscas trabajo?\n(ej: Bogota, Colombia)",
        "wizard_prompt_search_terms": "¿Qué cargos buscas en LinkedIn?\nEscribe separados por comas:\n(ej: Psicólogo clínico, Psicólogo escolar, Psicólogo organizacional)",
        "wizard_prompt_years_experience": "¿Cuántos años de experiencia laboral tienes?\n(número)",
        "wizard_prompt_university": "¿En qué institución estudiaste?\n(universidad o colegio — ej: Universidad Nacional de Colombia)",
        "wizard_prompt_degree": "Nivel educativo más alto completado:",
        "wizard_prompt_degree_alt": "Nivel educativo:\nHigh School / Associate's / Bachelor's / Master's / Doctorate / Other",
        "wizard_prompt_field_of_study": "¿Cuál fue tu área de estudio o carrera?\n(ej: Psicología, Administración de Empresas, Ingeniería de Sistemas)",
        "wizard_prompt_graduation_year": "¿En qué año te graduaste? (ej: 2020)",
        "wizard_prompt_ethnicity": "Origen étnico (formularios EEO de empleadores):",
        "wizard_prompt_ethnicity_alt": "Origen étnico (continuación):",
        "wizard_prompt_gender": "Género (para formularios EEO, puedes saltar):",
        "wizard_prompt_disability": "¿Tienes alguna discapacidad? (formulario EEO):",
        "wizard_prompt_veteran": "¿Eres veterano militar? (formulario EEO):",
        "wizard_prompt_require_visa": "¿Necesitas visa de trabajo para el país donde vas a aplicar?\n(si aplicas a empleos remotos internacionales responde Yes)",
        "wizard_prompt_desired_salary": "Salario deseado en números (puedes dejar 0 para saltar):",

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

        # Settings panel section titles
        "cfg_sec_linkedin":     "LinkedIn Account",
        "cfg_sec_search_main":  "Search terms",
        "cfg_sec_relevance":    "Relevance filter",
        "cfg_sec_filters":      "LinkedIn filters",
        "cfg_sec_avoid":        "Words to avoid",
        "cfg_sec_personal":     "Personal data",
        "cfg_sec_eeo":          "Equal opportunity",
        "cfg_sec_exp":          "Experience & salary",
        "cfg_sec_links":        "Links",
        "cfg_sec_texts":        "Long text fields",
        "cfg_sec_behavior":     "Bot behavior",
        "cfg_sec_browser":      "Browser & performance",
        "cfg_sec_cycles":       "Search cycles",
        "cfg_sec_ai":           "Artificial Intelligence",

        # Wizard — LinkedIn credentials
        "wiz_cred_title":       "LinkedIn Account",
        "wiz_cred_email":       "LinkedIn email (username):\n(same email you use to log in)",
        "wiz_cred_pass":        "LinkedIn password:",

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
        "btn_skip":             "SKIP",
        "btn_save":             "SAVE",
        "btn_browse":           "BROWSE",
        "btn_dashboard":        "Dashboard",
        "browse_pdf_title":     "Select CV (PDF)",
        "hint_one_per_line":    "(one per line)",
        "cfg_field_search_terms": "Search terms (search_terms)",
        "cfg_field_search_location": "Location (search_location)",
        "cfg_field_primary_focus_keywords": "PRIMARY KEYWORDS (Help Desk, Tech Support...)",
        "cfg_field_secondary_focus_keywords": "SECONDARY KEYWORDS (remote/hybrid only)",
        "cfg_field_enable_job_focus_filter": "Enable relevance filter (skip irrelevant jobs)",
        "cfg_field_switch_number": "Change search every N applications",
        "cfg_field_date_posted": "Date posted",
        "cfg_field_sort_by": "Sort by",
        "cfg_field_on_site": "Work modality",
        "cfg_field_experience_level": "Experience level",
        "cfg_field_job_type": "Employment type",
        "cfg_field_easy_apply_only": "Easy Apply only",
        "cfg_field_randomize_search_order": "Randomize search order",
        "cfg_field_bad_words": "Bad words in description (bad_words)",
        "cfg_field_about_company_bad_words": "Bad words about the company",
        "cfg_field_current_experience": "Current experience in years (-1 = ignore)",
        "cfg_field_first_name": "Name (first_name)",
        "cfg_field_middle_name": "Middle name (middle_name)",
        "cfg_field_last_name": "Last name (last_name)",
        "cfg_field_phone_number": "Phone (phone_number)",
        "cfg_field_current_city": "Current city (current_city)",
        "cfg_field_state": "State/Department (state)",
        "cfg_field_country": "Country (country)",
        "cfg_field_zipcode": "ZIP/postal code (zipcode)",
        "cfg_field_street": "Street (street)",
        "cfg_field_university": "Educational institution (university)",
        "cfg_field_degree": "Education level (degree)",
        "cfg_field_graduation_year": "Graduation year (graduation_year)",
        "cfg_field_field_of_study": "Field of study / Major (field_of_study)",
        "cfg_field_identification_number": "Identification number",
        "cfg_field_eeo_note": "Responses for equal-opportunity forms (U.S. jobs)",
        "cfg_field_gender": "Gender",
        "cfg_field_ethnicity": "Ethnicity",
        "cfg_field_disability_status": "Do you have a disability?",
        "cfg_field_veteran_status": "U.S. military veteran?",
        "cfg_field_years_of_experience": "Years of experience to report",
        "cfg_field_desired_salary": "Desired annual salary — numbers only, in the vacancy currency (e.g. 80000000 for COP)",
        "cfg_field_current_ctc": "Current annual salary — numbers only, same currency (forms call it CTC / current compensation)",
        "cfg_field_notice_period": "Notice period in days to leave your current job",
        "cfg_field_require_visa": "Do you need the company to sponsor your work visa?",
        "cfg_field_recent_employer": "Most recent employer",
        "cfg_field_confidence_level": "How confident/positive should the bot's answers be (1 = conservative, 10 = very confident)",
        "cfg_field_us_citizenship": "U.S. immigration status — only applies to U.S. jobs",
        "cfg_field_linkedin": "LinkedIn URL",
        "cfg_field_website": "Portfolio / Website",
        "cfg_field_linkedin_headline": "LinkedIn headline",
        "cfg_field_linkedin_summary": "LinkedIn summary",
        "cfg_field_cover_letter": "Cover letter",
        "cfg_field_user_information_all": "Complete information for AI",
        "cfg_field_default_resume_path": "Resume path (PDF)",
        "cfg_field_pause_before_submit": "Pause before each application submission",
        "cfg_field_pause_at_failed_question": "Pause if the bot cannot answer a question",
        "cfg_field_overwrite_previous_answers": "Overwrite previous answers",
        "cfg_field_run_non_stop": "Run without stopping (run_non_stop)",
        "cfg_field_follow_companies": "Follow companies when applying",
        "cfg_field_close_tabs": "Close external application tabs",
        "cfg_field_external_apply_enabled": "Universal applicant: autofill external forms (Greenhouse/Lever)",
        "cfg_field_pause_before_submit_external": "Pause before sending external applications",
        "cfg_field_click_gap": "Pause between clicks (sec)",
        "cfg_field_run_in_background": "Run in background (without visible Chrome)",
        "cfg_field_smooth_scroll": "Smooth scrolling",
        "cfg_field_stealth_mode": "Stealth mode (anti-bot)",
        "cfg_field_safe_mode": "Safe mode (guest profile)",
        "cfg_field_keep_screen_awake": "Keep screen awake",
        "cfg_field_alternate_sortby": "Alternate result order",
        "cfg_field_cycle_date_posted": "Cycle date filter automatically",
        "cfg_field_stop_date_cycle_at_24hr": "Stop cycle when reaching 24h",
        "cfg_field_ui_language": "Interface language",
        "cfg_field_use_AI": "Use AI to evaluate jobs and answer questions",
        "cfg_field_ai_provider": "AI provider",
        "cfg_field_llm_api_key": "API Key (on groq.com → API Keys → Create key)",
        "cfg_field_llm_model": "Model (e.g. llama-3.1-8b-instant for Groq)",
        "cfg_field_llm_api_url": "API URL (only for OpenAI-compatible / Ollama)",
        "opt_past_24_hours": "Past 24 hours",
        "opt_past_week": "Past week",
        "opt_past_month": "Past month",
        "opt_any_time": "Any time",
        "opt_most_recent": "Most recent",
        "opt_most_relevant": "Most relevant",
        "opt_on_site": "On-site",
        "opt_hybrid": "Hybrid",
        "opt_remote": "Remote",
        "opt_internship": "Internship",
        "opt_entry_level": "Entry level",
        "opt_associate": "Associate",
        "opt_mid_senior": "Mid-Senior",
        "opt_director": "Director",
        "opt_executive": "Executive",
        "opt_full_time": "Full-time",
        "opt_part_time": "Part-time",
        "opt_contract": "Contract",
        "opt_temporary": "Temporary",
        "opt_volunteer": "Volunteer",
        "opt_high_school": "High School",
        "opt_associates": "Associate's",
        "opt_bachelors": "Bachelor's",
        "opt_masters": "Master's",
        "opt_doctorate": "Doctorate",
        "opt_other": "Other",
        "opt_no": "No",
        "opt_yes": "Yes",
        "opt_decline": "Decline to self-identify",
        "career_ops_title": "Career-Ops Mode",
        "dashboard_opened": "Dashboard opened",
        "status_init_msg": "CVSniper Control initialized.",
        "cv_error_title": "Error",
        "cv_error_msg": "Could not optimize the CV.\n\nVerify that your API Key is valid in Settings → Bot → IA Settings.\nIf you use Gemini, generate a new key at aistudio.google.com\nIf you use Groq, verify it at console.groq.com",
        "cv_generate_error_msg": "Could not generate the CV.\n\nVerify that your API Key is valid in Settings → Bot → IA Settings.\nIf you use Gemini, generate a new key at aistudio.google.com\nIf you use Groq, verify it at console.groq.com",
        "wizard_title_complete": "Complete setup",
        "wizard_prompt_first_name": "What is your FIRST name?\n(only the first one — e.g. Camilo)",
        "wizard_prompt_last_name": "What are your LAST NAMES?\n(one or two surnames — e.g. García López)",
        "wizard_prompt_middle_name": "Do you have a middle name? (you can skip)",
        "wizard_prompt_phone": "Phone number with country code:\n(e.g. 573001234567 for Colombia)",
        "wizard_prompt_current_city": "What city do you currently live in?\n(e.g. Bogotá)",
        "wizard_prompt_country": "What country do you live in?\n(e.g. Colombia)",
        "wizard_prompt_state": "What department or state do you live in?\n(e.g. Cundinamarca, Antioquia)",
        "wizard_prompt_zipcode": "What is your postal code?\n(you can leave it empty if you do not know it)",
        "wizard_prompt_search_location": "What city/country are you looking for work in?\n(e.g. Bogota, Colombia)",
        "wizard_prompt_search_terms": "What job titles are you looking for on LinkedIn?\nWrite them separated by commas:\n(e.g. Clinical psychologist, School psychologist, Organizational psychologist)",
        "wizard_prompt_years_experience": "How many years of work experience do you have?\n(number)",
        "wizard_prompt_university": "What institution did you study at?\n(university or college — e.g. Universidad Nacional de Colombia)",
        "wizard_prompt_degree": "Highest completed educational level:",
        "wizard_prompt_degree_alt": "Education level:\nHigh School / Associate's / Bachelor's / Master's / Doctorate / Other",
        "wizard_prompt_field_of_study": "What was your field of study or major?\n(e.g. Psychology, Business Administration, Systems Engineering)",
        "wizard_prompt_graduation_year": "What year did you graduate? (e.g. 2020)",
        "wizard_prompt_ethnicity": "Ethnic origin (EEO forms for employers):",
        "wizard_prompt_ethnicity_alt": "Ethnic origin (continued):",
        "wizard_prompt_gender": "Gender (for EEO forms, you can skip):",
        "wizard_prompt_disability": "Do you have a disability? (EEO form):",
        "wizard_prompt_veteran": "Are you a military veteran? (EEO form):",
        "wizard_prompt_require_visa": "Do you need a work visa for the country you will apply to?\n(if you apply to international remote jobs, answer Yes)",
        "wizard_prompt_desired_salary": "Desired salary in numbers (you can leave 0 to skip):",

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
