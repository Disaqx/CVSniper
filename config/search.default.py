'''
CVSniper - Template de Busqueda / Search Template

Este archivo se configura automaticamente al subir tu CV.
This file is auto-configured when you upload your CV.
'''

# Terminos de busqueda en LinkedIn / LinkedIn search terms
search_terms = []

# Ubicacion de busqueda / Search location
search_location = ""

# Buscar ademas empleos REMOTOS en otros paises / Also sweep for REMOTE jobs abroad
# OJO: el filtro "Remote" de LinkedIn significa "sin oficina", NO "contratamos
# desde cualquier pais". Eso se filtra abajo con work_authorized_countries.
remote_worldwide = True
remote_search_locations = [
    "Worldwide",
    "Latin America",
    "United States",
    "Spain",
]

# Tipos de contrato para el barrido remoto / Job types for the remote sweep
# F full-time · P part-time · C contract · T temporary · I internship · V volunteer
# LinkedIn no tiene filtro de freelance; "C" es lo mas parecido. Vacio = todos.
remote_job_types = []

# Cambiar busqueda cada N aplicaciones / Switch search every N applications
switch_number = 10

# Aleatorizar orden de busqueda / Randomize search order
randomize_search_order = True

# Filtros LinkedIn / LinkedIn Filters
sort_by = "Most recent"
date_posted = "Past week"
salary = ""

easy_apply_only = True

experience_level = []
job_type = []
on_site = []

companies = []
location = []
industry = []
job_function = []
job_titles = []
benefits = []
commitments = []

under_10_applicants = False
in_your_network = False
fair_chance_employer = False

pause_after_filters = False

# Palabras a evitar / Words to avoid
about_company_bad_words = []
about_company_good_words = []
bad_words = []

# Donde puedes trabajar legalmente / Where you can legally work.
# Descarta el empleo "remoto" que igual exige vivir en otro pais.
work_authorized_countries = []
work_authorized_regions = [
    'latin america', 'latam', 'south america', 'the americas', 'americas',
    'anywhere', 'worldwide', 'globally', 'global', 'any country', 'any location',
    'america latina', 'latinoamerica', 'cualquier pais',
]
enable_residency_filter = True

security_clearance = False
did_masters = False
current_experience = -1

# Anos de experiencia de mas que aun aceptas / Extra years above yours still worth applying to
experience_tolerance = 3

# Pre-filtro de IA / AI pre-screening. Salta empleos con puntaje menor a este (0 = nunca saltar)
ai_min_score = 25
ai_prescreen_strict = False

# Filtro de relevancia / Job focus filter
enable_job_focus_filter = False
primary_focus_keywords = []
secondary_focus_keywords = []

# Titulos que siempre se descartan / Titles always skipped
title_bad_words = []
