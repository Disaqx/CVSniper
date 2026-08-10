"""Verifica el switch de modo, la URL de Easy Apply y las preguntas de conformidad.

Nada de esto necesita Selenium ni Tkinter: se extraen las funciones puras por AST.
"""
import ast, re, sys, unicodedata, importlib.util
from pathlib import Path
from urllib.parse import quote

RAIZ = Path(__file__).resolve().parent.parent   # la carpeta del proyecto

fallos = []
def check(nombre, obtenido, esperado):
    ok = obtenido == esperado
    if not ok:
        fallos.append(f"{nombre}: obtenido {obtenido!r}, esperado {esperado!r}")
    print(f"  [{'ok ' if ok else 'FALLO'}] {nombre}")

# =========================================================================
print("\n1. El switch de modo")
# =========================================================================
MODES = ("easy_apply", "external", "both")
def wants_easy(m): return m in ("easy_apply", "both")
def wants_ext(m):  return m in ("external", "both")

check("easy_apply -> easy si, externas no", (wants_easy("easy_apply"), wants_ext("easy_apply")), (True, False))
check("external  -> easy no, externas si", (wants_easy("external"), wants_ext("external")), (False, True))
check("both      -> las dos",              (wants_easy("both"), wants_ext("both")), (True, True))

# El switch fisico va izquierda->derecha: solo easy / ambas / solo externas.
# Es un orden DISTINTO al de MODES, que es el conjunto de valores validos.
src_ui = (RAIZ / "modules" / "bot_ui.py").read_text(encoding="utf-8")
arbol_ui = ast.parse(src_ui)
clase_sw = next(n for n in arbol_ui.body
                if isinstance(n, ast.ClassDef) and n.name == "ModeSwitch")
consts_sw = {}
for nodo in clase_sw.body:
    if isinstance(nodo, ast.Assign) and isinstance(nodo.targets[0], ast.Name):
        try:
            consts_sw[nodo.targets[0].id] = ast.literal_eval(nodo.value)
        except ValueError:
            pass

check("el switch va izquierda->derecha: easy, ambas, externas",
      list(consts_sw["ORDER"]), ["easy_apply", "both", "external"])
check("el orden del switch cubre exactamente los modos validos",
      sorted(consts_sw["ORDER"]), sorted(MODES))
check("hay color para los 3", sorted(consts_sw["COLORS"]), sorted(MODES))
check("hay etiqueta para los 3", sorted(consts_sw["LABEL_KEYS"]), sorted(MODES))

# Clicar el tercio N selecciona el modo N: es todo lo que hace _on_click.
def tercio(x, seg_w=38): return min(2, max(0, int((x - 1) // seg_w)))
check("clic a la izquierda -> solo easy apply", consts_sw["ORDER"][tercio(10)], "easy_apply")
check("clic en el centro   -> ambas",           consts_sw["ORDER"][tercio(57)], "both")
check("clic a la derecha   -> solo externas",   consts_sw["ORDER"][tercio(105)], "external")
check("clic fuera por la derecha no se sale",   consts_sw["ORDER"][tercio(999)], "external")
check("clic fuera por la izquierda no se sale", consts_sw["ORDER"][tercio(-5)], "easy_apply")

# y las claves i18n deben existir en ambos idiomas
spec = importlib.util.spec_from_file_location("i18n", RAIZ / "modules" / "i18n.py")
i18n = importlib.util.module_from_spec(spec); sys.modules["i18n"] = i18n; spec.loader.exec_module(i18n)
nombres_largos = re.findall(r'"(?:easy_apply|external|both)":\s+"(btn_mode_\w+)"', src_ui)
claves = list(consts_sw["LABEL_KEYS"].values()) + nombres_largos + ["msg_mode_changed"]
check("hay nombre largo para los 3 modos (la linea del log)", len(set(nombres_largos)), 3)
for lang, dic in i18n.TRANSLATIONS.items():
    check(f"i18n[{lang}] tiene las claves del switch", [c for c in claves if c not in dic], [])
    # Las etiquetas cortas no pueden crecer o se pisan dentro del switch.
    largas = [c for c in consts_sw["LABEL_KEYS"].values() if len(dic[c]) > 5]
    check(f"i18n[{lang}] etiquetas cortas de <=5 caracteres", largas, [])

# =========================================================================
print("\n2. La URL de Easy Apply (el filtro que se cayo)")
# =========================================================================
def construir(modo, easy_apply_only=True, career_ops=False, remote=False):
    u = "https://www.linkedin.com/jobs/search/?keywords=Help%20Desk"
    ea = bool(easy_apply_only and wants_easy(modo) and not wants_ext(modo) and not career_ops)
    if ea: u += "&f_LF=f_AL"
    if remote: u += "&f_WT=2"
    return u, ea

check("modo easy_apply -> f_LF=f_AL en la URL", construir("easy_apply")[1], True)
check("modo both -> SIN f_LF (hacen falta las externas)", construir("both")[1], False)
check("modo external -> SIN f_LF", construir("external")[1], False)
check("career-ops -> SIN f_LF", construir("easy_apply", career_ops=True)[1], False)
check("easy_apply_only=False -> SIN f_LF", construir("easy_apply", easy_apply_only=False)[1], False)
check("URL completa en modo easy_apply",
      construir("easy_apply", remote=True)[0],
      "https://www.linkedin.com/jobs/search/?keywords=Help%20Desk&f_LF=f_AL&f_WT=2")

# El bug reportado: en modo externas el toggle se marcaba igual desde el config.
# Ahora el estado deseado lo decide el MODO y se compara con el estado real.
src_js = (RAIZ / "modules" / "job_search.py").read_text(encoding="utf-8")
check("el toggle ya no se clica a ciegas desde easy_apply_only",
      "if easy_apply_only and not is_career_ops_mode()" in src_js, False)
check("apply_filters recibe el estado deseado del modo",
      "easy_apply_filter: bool | None = None" in src_js, True)
check("y lee el estado real antes de clicar",
      "aria-checked" in src_js and "if actual == deseado" in src_js, True)

# la decision del modo, replicada
def toggle_deseado(modo, easy_apply_only=True, career_ops=False):
    deseado = bool(easy_apply_only and wants_easy(modo) and not wants_ext(modo) and not career_ops)
    return False if career_ops else deseado

check("modo external -> toggle Easy Apply APAGADO", toggle_deseado("external"), False)
check("modo both     -> toggle Easy Apply APAGADO", toggle_deseado("both"), False)
check("modo easy_apply -> toggle ENCENDIDO", toggle_deseado("easy_apply"), True)

# y no debe clicar cuando el estado ya coincide (era lo que lo apagaba)
def va_a_clicar(actual, deseado): return actual != deseado
check("URL ya lo encendio -> NO se vuelve a clicar", va_a_clicar(True, True), False)
check("modo external y estaba encendido -> se APAGA", va_a_clicar(True, False), True)

# =========================================================================
print("\n3. Apply se clica UNA sola vez")
# =========================================================================
# El fallo real de los logs: se clicaba para detectar y otra vez para aplicar.
# El segundo clic encontraba un boton ya gastado -> "Apply did not open a new
# tab, skipping", que es lo que mato TODAS las externas.
src_bot = (RAIZ / "runAiBot.py").read_text(encoding="utf-8")
src_ext = (RAIZ / "modules" / "external_apply.py").read_text(encoding="utf-8")

check("el sondeo vive en external_apply, no duplicado en runAiBot",
      "def probe_apply_button" in src_ext, True)
check("runAiBot lo importa en vez de reimplementarlo",
      "probe_apply_button" in src_bot.split("\n")[0:120].__str__() or
      "from modules.external_apply import external_apply, probe_apply_button" in src_bot, True)
# runAiBot todavia puede clicar el boton de Easy Apply (lleva el guardia
# aria-label 'Easy' y es justo lo que hay que abrir). Lo que no puede es clicar
# el boton GENERICO: ese es el que abre las externas, y clicarlo aqui y otra vez
# dentro de external_apply es el bug.
sin_guardia = [l for l in src_bot.splitlines()
               if "jobs-apply-button" in l and "Easy" not in l]
check("runAiBot no clica el boton de Apply generico", sin_guardia, [])
check("la URL sondeada se le pasa a external_apply",
      "already_open_url=external_link_already_open" in src_bot, True)
check("si el sondeo no encuentra nada, no se llama a external_apply",
      "elif not external_link_already_open:" in src_bot, True)
check("ya no queda el 'skipping' que caia al doble click",
      "External apply detected via new tab, skipping" in src_bot, False)

# El sondeo tiene que cubrir las DOS formas de salir de LinkedIn.
check("cubre la pestana nueva", "if nuevas:" in src_ext, True)
check("cubre la navegacion en la misma pestana",
      "not _is_linkedin(actual)" in src_ext and "driver.back()" in src_ext, True)
check("espera a que la cadena de redirecciones se asiente",
      "def _settled_url" in src_ext, True)

# =========================================================================
print("\n3b. La UI: el switch en la cabecera, arriba a la derecha")
# =========================================================================
en_btn_frame = re.findall(r'self\.(\w+) = tk\.Button\(self\.btn_frame', src_ui)
check("la fila de accion sigue con 4 botones",
      sorted(en_btn_frame), ["career_ops_btn", "optimize_btn", "pause_btn", "stop_btn"])
check("el switch se empaqueta a la derecha de la cabecera",
      'self.mode_switch = ModeSwitch(self.header' in src_ui
      and 'self.mode_switch.pack(side="right"' in src_ui, True)
check("ya no existe el boton ciclico anterior", "self.mode_btn" in src_ui, False)
# El titulo se empaqueta DESPUES del switch: en Tk el ultimo cede el espacio, y
# al reves el switch se quedaba en una rendija ilegible.
pos_switch = src_ui.index('self.mode_switch.pack(side="right"')
pos_titulo = src_ui.index('self.title_label.pack(side="left"')
check("el titulo cede espacio al switch, no al reves", pos_titulo > pos_switch, True)
check("el cambio de idioma redibuja el switch",
      "self.mode_switch.redraw()" in src_ui, True)

# =========================================================================
print("\n3c. Puntos de pausa")
# =========================================================================
check("external_apply ya comprueba la pausa", src_ext.count("ui_pause_check()") >= 3, True)
check("el bucle del modal Easy Apply la comprueba",
      re.search(r'while next_button:\s*\n(\s*#[^\n]*\n)*\s*ui_pause_check\(\)', src_bot) is not None, True)

# =========================================================================
print("\n3d. El filtro Easy Apply no puede reaparecer solo")
# =========================================================================
arbol_js = ast.parse((RAIZ / "modules" / "job_search.py").read_text(encoding="utf-8"))
fn_ee = next(n for n in arbol_js.body
             if isinstance(n, ast.FunctionDef) and n.name == "ensure_easy_apply_state")

class _DriverFalso:
    def __init__(self, url): self.current_url = url; self.visitadas = []
    def get(self, u): self.visitadas.append(u); self.current_url = u

def rehacer(url, deseado):
    """Ejecuta la funcion real con un driver de mentira."""
    d = _DriverFalso(url)
    ns_js = {"re": re, "driver": d, "print_lg": lambda *a, **k: None,
             "buffer": lambda *a, **k: None}
    exec(compile(ast.Module([fn_ee], []), "<job_search>", "exec"), ns_js)
    cambio = ns_js["ensure_easy_apply_state"](deseado)
    return cambio, d.current_url

BASE = "https://www.linkedin.com/jobs/search/?keywords=Help+Desk&location=Bogota"
check("modo externas y el filtro reaparecio -> se quita",
      rehacer(BASE + "&f_LF=f_AL", False),
      (True, BASE))
check("modo externas y no estaba -> no se recarga la pagina",
      rehacer(BASE, False), (False, BASE))
check("modo easy apply y se cayo -> se repone",
      rehacer(BASE, True), (True, BASE + "&f_LF=f_AL"))
check("modo easy apply y ya estaba -> no se recarga",
      rehacer(BASE + "&f_LF=f_AL", True), (False, BASE + "&f_LF=f_AL"))
# Si el filtro era el PRIMER parametro, quitarlo se lleva la '?' por delante.
check("quitarlo como primer parametro no rompe la URL",
      rehacer("https://www.linkedin.com/jobs/search/?f_LF=f_AL&keywords=Help", False),
      (True, "https://www.linkedin.com/jobs/search/?keywords=Help"))
check("fuera de la pagina de resultados no toca nada",
      rehacer("https://www.linkedin.com/feed/", False),
      (False, "https://www.linkedin.com/feed/"))
check("se comprueba en cada pagina de resultados, no solo al filtrar",
      "if ensure_easy_apply_state(_ea_filtro):" in src_bot, True)

# =========================================================================
print("\n4. El bug de la captura: responder 'No' a '¿Esta de acuerdo con...?'")
# =========================================================================
# Se extrae la escalera de answer_common_questions y se ejecuta de verdad.
arbol = ast.parse((RAIZ / "modules" / "easy_apply.py").read_text(encoding="utf-8"))
fn = next(n for n in arbol.body
          if isinstance(n, ast.FunctionDef) and n.name == "answer_common_questions")

ns = {"re": re, "print_lg": lambda *a, **k: None,
      "__file__": str(RAIZ / "modules" / "easy_apply.py")}
# La funcion usa constantes del modulo (_SENSITIVE_KEYWORDS, NOTICE_WORDS...).
# Se ejecutan primero todas las asignaciones de nivel superior; las que
# dependen de selenium fallan y se ignoran, porque esta rama no las usa.
for nodo in arbol.body:
    if isinstance(nodo, ast.Assign):
        try:
            exec(compile(ast.Module([nodo], []), "<easy_apply>", "exec"), ns)
        except Exception:
            pass
exec(compile(ast.Module([fn], []), "<easy_apply>", "exec"), ns)
responder = ns["answer_common_questions"]

# Firma real: (label, answer) -> answer. Normaliza el label por dentro y
# devuelve `answer` sin tocar cuando ninguna rama coincide. SIN_TOCAR es ese
# valor pasado, y es lo que confirma que la escalera no se metio donde no debe.
SIN_TOCAR = "<sin cambiar>"
def preguntar(label):
    return responder(label, SIN_TOCAR)

print("   -- las de la captura --")
check("'¿Esta de acuerdo con ocupar el rol de QA Junior?'",
      preguntar("¿Esta de acuerdo con ocupar el rol de QA Junior?*"), "Yes")
check("'¿Esta de acuerdo con la banda salarial?'",
      preguntar("¿Esta de acuerdo con la banda salarial?*"), "Yes")
print("   -- otras variantes --")
check("'¿Estas de acuerdo con el horario?'",
      preguntar("¿Estas de acuerdo con el horario rotativo?"), "Yes")
check("'Do you agree to the salary range?'",
      preguntar("Do you agree to the salary range?"), "Yes")
check("'Would you accept this position?'",
      preguntar("Would you accept this position?"), "Yes")
print("   -- lo que NO debe tocar --")
check("una pregunta de habilidad se deja a la IA",
      preguntar("¿Posee experiencia en Desarrollo con Java y Spring/SpringBoot?"), SIN_TOCAR)
check("'¿Cuenta con titulo profesional de pregrado?' se deja a la IA",
      preguntar("¿Cuenta con titulo profesional de pregrado?"), SIN_TOCAR)
check("una pregunta de salario se deja a la IA",
      preguntar("¿Cual fue tu ultimo salario?"), SIN_TOCAR)

# =========================================================================
print("\n5. El aplicador externo")
# =========================================================================
arbol_ext = ast.parse(src_ext)
ns_ext = {"re": re, "urlparse": __import__("urllib.parse", fromlist=["urlparse"]).urlparse}
for nodo in arbol_ext.body:
    if isinstance(nodo, (ast.Assign, ast.FunctionDef)):
        try:
            exec(compile(ast.Module([nodo], []), "<external_apply>", "exec"), ns_ext)
        except Exception:
            pass   # lo que necesita selenium no hace falta para estas ramas

detect_ats = ns_ext["detect_ats"]
print("   -- triaje de plataformas --")
check("greenhouse se autollena",
      detect_ats("https://job-boards.greenhouse.io/acme/jobs/123"), ("greenhouse", True))
check("lever se autollena",
      detect_ats("https://jobs.lever.co/acme/abc-123/apply"), ("lever", True))
check("workable se autollena (no lo cubria)",
      detect_ats("https://apply.workable.com/acme/j/ABC/"), ("workable", True))
check("workday queda para revision manual",
      detect_ats("https://acme.wd1.myworkdayjobs.com/es/External/job/x"), ("workday", False))
check("icims queda para revision manual",
      detect_ats("https://careers-acme.icims.com/jobs/123/login"), ("icims", False))
check("un ATS desconocido se intenta igual",
      detect_ats("https://empleos.empresa.com/postular")[1], True)

print("   -- casillas de consentimiento --")
consent = ns_ext["_looks_like_consent"]
check("'I have read the privacy policy'", consent("I have read the privacy policy *"), True)
check("'Acepto los términos'",            consent("Acepto los términos y condiciones"), True)
check("'Autorizo el tratamiento de datos'", consent("Autorizo el tratamiento de datos"), True)
check("un campo normal no es consentimiento", consent("First name *"), False)
check("'Years of experience' no es consentimiento", consent("Years of experience"), False)

print("   -- comillas en los id de los ATS --")
xp = ns_ext["_xp_literal"]
check("id normal", xp("first_name"), '"first_name"')
check("id con comilla simple se envuelve en dobles", xp("a'b"), '"a\'b"')
check("id con comillas dobles se envuelve en simples", xp('a"b'), "'a\"b'")
check("id con los dos tipos de comilla usa concat()",
      xp('a"b\'c'), 'concat("a", \'"\', "b\'c")')

print("   -- lo que rompia el llenado --")
check("los input SIN atributo type ya se recogen",
      'input:not([type])' in src_ext, True)
check("las casillas y radios tambien",
      "_CHOICE_SELECTOR" in src_ext and "_fill_choice_inputs" in src_ext, True)
check("y los desplegables de React (Greenhouse/Ashby)",
      "_fill_combobox" in src_ext, True)
check("el muro de cuenta ya no se decide grepeando el HTML entero",
      "driver.page_source" in src_ext, False)
check("se decide por si hay formulario visible",
      "if any(e.is_displayed() for e in campos):\n            return False" in src_ext, True)
check("un cambio de URL a secas ya no cuenta como enviado",
      "_CONFIRM_WORDS" in src_ext and "aria-invalid" in src_ext, True)
check("la pregunta de un grupo de radios no sale de la etiqueta del radio",
      "pregunta = _group_question(el) or label" in src_ext, True)
check("los name con corchetes de los ATS se buscan por XPath, no por CSS",
      '@name={_xp_literal(nombre)}' in src_ext, True)
check("la pestana enviada se cierra siempre",
      "if tab_propia and tab_propia in driver.window_handles and (enviada or close_tabs):" in src_ext, True)

# La configuracion real del usuario: sin esto no se llena NADA.
sett = (RAIZ / "config" / "settings.py").read_text(encoding="utf-8")
check("external_apply_enabled esta encendido",
      re.search(r'^external_apply_enabled\s*=\s*True', sett, re.M) is not None, True)

# =========================================================================
print("\n" + "=" * 60)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos: print("  -", f)
    sys.exit(1)
print("Todo correcto.")
