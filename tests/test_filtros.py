"""Ejercita los predicados de filtrado de job_search.py sin arrancar Selenium.

job_search.py importa modules.open_chrome, que ABRE Chrome al importarse. Asi que
en vez de importar el modulo, se extraen del fuente las funciones puras y se
ejecutan contra la config real del usuario.
"""
import ast, re, sys, io, importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent   # la carpeta del proyecto

# --- config real del usuario ---------------------------------------------
spec = importlib.util.spec_from_file_location("cfg_search", RAIZ / "config" / "search.py")
cfg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfg)

# --- extraer las funciones puras del modulo ------------------------------
fuente = (RAIZ / "modules" / "job_search.py").read_text(encoding="utf-8")
arbol = ast.parse(fuente)

QUIERO_FUNCS = {"_fold", "_contains_term", "is_title_blacklisted", "is_job_relevant",
                "extract_years_of_experience", "requires_ineligible_residency"}
QUIERO_VARS = {"_ACCENTS", "_CLEARANCE_PHRASES", "re_experience",
               "_RESIDENCY_PATTERNS", "_COUNTRY_NAMES"}

ns = {
    "re": re,
    "enable_job_focus_filter": cfg.enable_job_focus_filter,
    "primary_focus_keywords": cfg.primary_focus_keywords,
    "secondary_focus_keywords": cfg.secondary_focus_keywords,
    "title_bad_words": cfg.title_bad_words,
    "work_authorized_countries": cfg.work_authorized_countries,
    "work_authorized_regions": cfg.work_authorized_regions,
    "enable_residency_filter": cfg.enable_residency_filter,
    "print_lg": lambda *a, **k: None,
}

for nodo in arbol.body:
    if isinstance(nodo, ast.FunctionDef) and nodo.name in QUIERO_FUNCS:
        exec(compile(ast.Module([nodo], []), "<job_search>", "exec"), ns)
    elif isinstance(nodo, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in QUIERO_VARS for t in nodo.targets):
        exec(compile(ast.Module([nodo], []), "<job_search>", "exec"), ns)

faltan = QUIERO_FUNCS - set(ns)
assert not faltan, f"No se extrajeron: {faltan}"

fold           = ns["_fold"]
contains       = ns["_contains_term"]
title_blocked  = ns["is_title_blacklisted"]
relevant       = ns["is_job_relevant"]
years          = ns["extract_years_of_experience"]
CLEARANCE      = ns["_CLEARANCE_PHRASES"]

fallos = []
def check(nombre, obtenido, esperado):
    ok = obtenido == esperado
    if not ok:
        fallos.append(f"{nombre}: obtenido {obtenido!r}, esperado {esperado!r}")
    print(f"  [{'ok ' if ok else 'FALLO'}] {nombre}")

# =========================================================================
print("\n1. La regresion que motivo todo: 'secret' dentro de palabras españolas")
# =========================================================================
def dispara_clearance(desc):
    low = desc.lower()
    return next((p for p in CLEARANCE if p in low), None)

check("'secreto profesional' NO dispara clearance",
      dispara_clearance("Debe guardar el secreto profesional de la empresa."), None)
check("'Secretaria General' NO dispara clearance",
      dispara_clearance("Reporta a la Secretaria General de la compania."), None)
check("'secreto empresarial' NO dispara clearance",
      dispara_clearance("Manejo de informacion y secreto empresarial."), None)
check("'Top Secret' SI dispara",
      dispara_clearance("Must hold an active Top Secret authorization."), "top secret")
check("'security clearance' SI dispara",
      dispara_clearance("A security clearance is required."), "security clearance")
check("'polygraph' SI dispara",
      dispara_clearance("Candidates must pass a polygraph."), "polygraph")

# =========================================================================
print("\n2. bad_words ahora como palabra completa")
# =========================================================================
check("'PHP' no dispara dentro de una URL .php",
      contains("see https://portal.example.com/index.php for details", "PHP"), False)
check("'PHP' si dispara suelto",
      contains("experience with php and mysql required", "PHP"), True)
check("'.NET' no dispara en 'example.net'",
      contains("visit our site at careers.example.net today", ".NET"), False)
check("'.NET' si dispara suelto",
      contains("supporting legacy .net applications", ".NET"), True)
check("'CNC' no dispara dentro de 'CNCF'",
      contains("member of the cncf foundation", "CNC"), False)
check("'US Citizen' si dispara",
      contains("applicants must be a us citizen", "US Citizen"), True)

# =========================================================================
print("\n3. Lista negra de titulos (acentos y palabra completa)")
# =========================================================================
check("'Level 1 Help Desk' pasa",              title_blocked("Level 1 Help Desk Analyst"), None)
check("'Help Desk Tier I' pasa",               title_blocked("Help Desk Tier I"), None)
check("'Soporte Tecnico N1' pasa",             title_blocked("Soporte Tecnico N1"), None)
check("'Senior DevOps' se bloquea",            title_blocked("Senior DevOps Engineer"), "senior")
check("'Gerente de Sistemas' se bloquea",      title_blocked("Gerente de Sistemas"), "gerente")
check("'Medico General' se bloquea (sin acento)", title_blocked("Medico General"), "medico")
check("'Médico General' se bloquea (con acento)", title_blocked("Médico General"), "medico")
check("'Enfermera' se bloquea",                title_blocked("Enfermera de Turno"), "enfermera")
check("'Enfermero' se bloquea",                title_blocked("Enfermero Jefe"), "jefe")
# el falso positivo que justifica el limite de palabra:
check("'Leadership Support Associate' NO se bloquea por 'lead'",
      title_blocked("Leadership Support Associate"), None)

# =========================================================================
print("\n4. Filtro de foco: apagado por defecto, pero correcto si se enciende")
# =========================================================================
check("apagado -> todo es relevante", relevant("Chef de Cuisine", "On-site"), True)

ns["enable_job_focus_filter"] = True
check("encendido: 'Level 1 Help Desk' relevante", relevant("Level 1 Help Desk", "On-site"), True)
check("encendido: 'Soporte Técnico' con acento relevante", relevant("Soporte Técnico Bilingüe", "Remoto"), True)
check("encendido: 'NOC Analyst' relevante",      relevant("NOC Analyst", "On-site"), True)
check("encendido: 'POS System Administrator' relevante", relevant("POS System Administrator", "Remote"), True)
check("encendido: 'Chef de Cuisine' NO relevante", relevant("Chef de Cuisine", "On-site"), False)
ns["enable_job_focus_filter"] = cfg.enable_job_focus_filter

# =========================================================================
print("\n5. Tolerancia de experiencia (current=%s, tolerancia=%s)"
      % (cfg.current_experience, cfg.experience_tolerance))
# =========================================================================
techo = cfg.current_experience + cfg.experience_tolerance
def se_salta(desc):
    req = years(desc)
    return cfg.current_experience > -1 and req > techo

check("'2 years' pasa",                 se_salta("At least 2 years of experience."), False)
check("'5 years' ahora pasa (antes se saltaba)",
                                        se_salta("5 years of experience required."), False)
check("'6 years' pasa (justo en el techo)", se_salta("6 years of experience."), False)
check("'8 years' se salta",             se_salta("8 years of experience required."), True)

# =========================================================================
print("\n6. El caso que motivo esto: 'remoto en Mexico pero debes vivir en Mexico'")
# =========================================================================
residencia = ns["requires_ineligible_residency"]
def bloquea(desc): return residencia(desc) is not None

print("   -- se descartan --")
check("'must reside in Mexico'",
      bloquea("Fully remote role. Candidates must reside in Mexico."), True)
check("'must be located in the United States'",
      bloquea("100% remote. You must be located in the United States."), True)
check("'must be authorized to work in the US'",
      bloquea("Remote position. Must be authorized to work in the United States."), True)
check("'open only to residents of Spain'",
      bloquea("Remote. Open only to residents of Spain."), True)
check("'debes residir en Argentina'",
      bloquea("Trabajo remoto. Debes residir en Argentina."), True)
check("'this role is only available in Germany'",
      bloquea("This role is only available in Germany, fully remote."), True)

print("   -- se conservan --")
check("'must reside in Colombia' (su pais)",
      bloquea("Remote role. Must reside in Colombia."), False)
check("'residents of Latin America'",
      bloquea("Remote. Open to residents of Latin America."), False)
check("'must be located anywhere in LATAM'",
      bloquea("You must be located anywhere in LATAM."), False)
check("'work from anywhere'",
      bloquea("Fully remote, work from anywhere in the world."), False)
check("remoto sin exigencia de ubicacion",
      bloquea("Remote-first company headquartered in Berlin. We support our users 24/7."), False)
check("menciona un pais pero sin clausula de residencia",
      bloquea("Our largest customers are in Germany and Japan."), False)
check("'must reside in Colombia or Mexico'",
      bloquea("Remote. Must reside in Colombia or Mexico."), False)
check("devuelve la clausula, no solo True",
      isinstance(residencia("Remote. Must reside in Mexico."), str), True)

# =========================================================================
print("\n7. La URL del barrido remoto")
# =========================================================================
from urllib.parse import quote
GEO = {"worldwide": "92000000"}
def split_geo(e):
    n, _, p = str(e).partition("|"); n = n.strip()
    return n, (p.strip() or GEO.get(n.lower()))
def construir(term, entrada, remote, tipos=()):
    nombre, geo = split_geo(entrada)
    u = "https://www.linkedin.com/jobs/search/?keywords=" + quote(term)
    if nombre:
        u += "&location=" + quote(nombre)
        if geo: u += "&geoId=" + quote(geo)
    if remote:
        u += "&f_WT=2"
        if tipos: u += "&f_JT=" + quote(",".join(tipos))
    return u

check("local sin f_WT ni geoId",
      construir("Help Desk", "Bogotá, Colombia", False),
      "https://www.linkedin.com/jobs/search/?keywords=Help%20Desk&location=Bogot%C3%A1%2C%20Colombia")
check("Worldwide lleva su geoId",
      construir("Help Desk", "Worldwide", True),
      "https://www.linkedin.com/jobs/search/?keywords=Help%20Desk&location=Worldwide&geoId=92000000&f_WT=2")
check("freelance = f_JT=C",
      construir("Help Desk", "Worldwide", True, ["C"]),
      "https://www.linkedin.com/jobs/search/?keywords=Help%20Desk&location=Worldwide&geoId=92000000&f_WT=2&f_JT=C")
check("geoId manual con pipe",
      split_geo("European Union|91000000"), ("European Union", "91000000"))
check("pais sin geoId conocido -> solo texto",
      split_geo("Spain"), ("Spain", None))

# =========================================================================
print("\n8. Plan de busqueda (%d terminos)" % len(cfg.search_terms))
# =========================================================================
locales = cfg.search_location if isinstance(cfg.search_location, (list, tuple)) else [cfg.search_location]
plan = [(l, False) for l in locales]
if cfg.remote_worldwide:
    plan += [(l.strip(), True) for l in cfg.remote_search_locations if l and l.strip()]
check("pasadas totales = 1 local + %d remotas" % len(cfg.remote_search_locations),
      len(plan), 1 + len(cfg.remote_search_locations))
check("solo una pasada NO remota", sum(1 for _, r in plan if not r), 1)
print(f"     -> {len(plan)} ubicaciones x {len(cfg.search_terms)} terminos = "
      f"{len(plan)*len(cfg.search_terms)} busquedas, tope {cfg.switch_number} "
      f"postulaciones c/u")

# =========================================================================
print("\n" + "="*60)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos: print("  -", f)
    sys.exit(1)
print("Todo correcto.")
