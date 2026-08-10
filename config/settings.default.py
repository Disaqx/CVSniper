###################################################### CONFIGURE YOUR BOT HERE ######################################################

# Idioma de la interfaz / UI Language  ("es" = Español, "en" = English)
ui_language = "es"

# >>>>>>>>>>> LinkedIn Settings <<<<<<<<<<<

# Que postulaciones atiende el bot / Which applications the bot handles:
# "easy_apply", "external" o "both". El boton de la ventana principal lo cambia.
application_mode = "easy_apply"

# Close the external application tabs. / Cerrar las pestañas de solicitudes externas.
# A SUBMITTED application always closes its tab. This decides what happens to the
# ones that could not be completed: True closes them anyway (the link is kept in
# the CSV), False leaves them open to finish by hand.
close_tabs = True

# >>>>>>>>>>> Universal Applier (External Apply) <<<<<<<<<<<

# Auto-fill external applications (Greenhouse, Lever, Ashby y formularios simples)?
# Workday/iCIMS y plataformas que exigen crear cuenta siempre quedan para revisión manual.
external_apply_enabled = False

# Pause for confirmation before submitting an external application?
# True asks every time; False fills, submits, verifies and moves on unattended.
# Leave it True until you have watched a few external applications go through.
pause_before_submit_external = True

# Follow easy applied companies
follow_companies = True

# Do you want the program to run continuously until you stop it?
run_non_stop = False
alternate_sortby = True
cycle_date_posted = True
stop_date_cycle_at_24hr = True


# >>>>>>>>>>> RESUME GENERATOR <<<<<<<<<<<

generated_resume_path = "all resumes/"


# >>>>>>>>>>> Global Settings <<<<<<<<<<<

file_name = "all excels/all_applied_applications_history.csv"
failed_file_name = "all excels/all_failed_applications_history.csv"
logs_folder_path = "logs/"

click_gap = 3
run_in_background = False
disable_extensions = False
safe_mode = True
smooth_scroll = True
keep_screen_awake = True
stealth_mode = True
showAiErrorAlerts = False
