"""La página nueva de resultados de LinkedIn, el arranque de Chrome y el CV.

Igual que el resto de tests: se extraen las funciones puras con `ast` porque
importar `job_search.py` (o `open_chrome.py`) ABRE Chrome. Lo que se prueba es
el código que se publica, no una copia.

Los selectores y las URLs de los casos salen de páginas reales:
- la URL con la que LinkedIn redirigió a la página nueva (la del informe),
- el HTML público de /jobs/search/ descargado el 2026-11-16,
- los enlaces `/jobs/view/<slug>-<id>` que aparecen en todos los diseños.
"""
import ast
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

RAIZ = Path(__file__).resolve().parent.parent

fallos = []


def check(nombre, obtenido, esperado):
    ok = obtenido == esperado
    if not ok:
        fallos.append(f"{nombre}: obtenido {obtenido!r}, esperado {esperado!r}")
    print(f"  [{'ok ' if ok else 'FALLO'}] {nombre}")


def extraer(ruta: Path, funciones, variables, ns):
    """Ejecuta las funciones y constantes pedidas del fuente, en `ns`."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in arbol.body:
        if isinstance(nodo, ast.FunctionDef) and nodo.name in funciones:
            exec(compile(ast.Module([nodo], []), str(ruta), "exec"), ns)
        elif isinstance(nodo, (ast.Assign, ast.AnnAssign)):
            objetivos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
            if any(isinstance(t, ast.Name) and t.id in variables for t in objetivos):
                try:
                    exec(compile(ast.Module([nodo], []), str(ruta), "exec"), ns)
                except Exception:
                    pass
    return ns


sin_log = lambda *a, **k: None  # noqa: E731

# =========================================================================
print("\n1. Construir la URL de búsqueda")
# =========================================================================
js = extraer(
    RAIZ / "modules" / "job_search.py",
    {"build_search_url", "add_legacy_easy_apply"},
    {"_EASY_APPLY_TRUE"},
    {"quote": quote, "print_lg": sin_log},
)
build = js["build_search_url"]
legacy = js["add_legacy_easy_apply"]

BASE = "https://www.linkedin.com/jobs/search/?keywords=Analista%20de%20Tesorer%C3%ADa"
check("solo keywords",
      build("Analista de Tesorería"),
      BASE)
check("ubicación sola",
      build("Analista de Tesorería", location="Bogotá, Colombia"),
      BASE + "&location=Bogot%C3%A1%2C%20Colombia")
check("ubicación + geoId",
      build("Analista de Tesorería", location="Worldwide", geo_id="92000000"),
      BASE + "&location=Worldwide&geoId=92000000")
check("Easy Apply en la URL",
      build("Analista de Tesorería", location="Bogotá, Colombia", easy_apply=True),
      BASE + "&location=Bogot%C3%A1%2C%20Colombia&f_LF=f_AL")
check("barrido remoto: f_WT=2 y f_JT",
      build("Help Desk", location="Worldwide", geo_id="92000000",
            remote_only=True, job_types=["C"]),
      "https://www.linkedin.com/jobs/search/?keywords=Help%20Desk"
      "&location=Worldwide&geoId=92000000&f_WT=2&f_JT=C")
check("el alias no se duplica",
      legacy(BASE + "&f_AL=true"), BASE + "&f_AL=true")
check("el alias se añade una vez",
      legacy(BASE), BASE + "&f_AL=true")
check("el alias conserva lo que ya había",
      legacy(BASE + "&f_LF=f_AL"),
      BASE + "&f_LF=f_AL&f_AL=true")

# =========================================================================
print("\n2. Detectar la página y los filtros que LinkedIn se llevó")
# =========================================================================
js = extraer(
    RAIZ / "modules" / "job_search.py",
    {"_query_params", "_easy_apply_in", "search_design", "navigation_report"},
    {"SEARCH_PATH", "NEW_SEARCH_PATH", "_EASY_APPLY_TRUE", "FILTER_LABELS"},
    {"parse_qs": parse_qs, "urlsplit": urlsplit, "print_lg": sin_log},
)
search_design = js["search_design"]
report = js["navigation_report"]

check("diseño clásico", search_design(BASE), "classic")
check("diseño nuevo",
      search_design("https://www.linkedin.com/jobs/search-results/?keywords=x"),
      "search-results")
check("muro de login",
      search_design("https://www.linkedin.com/authwall?trk=bf&sessionRedirect=x"),
      "authwall")
check("otra página", search_design("https://www.linkedin.com/feed/"), "other")

SOLICITADA = ("https://www.linkedin.com/jobs/search/?keywords=Analista%20de%20Tesorer%C3%ADa"
              "&location=Colombia&geoId=104621616&f_LF=f_AL&f_WT=2&f_TPR=r604800&sortBy=DD")
# Exactamente la URL final del informe de la usuaria.
FINAL_NUEVA = ("https://www.linkedin.com/jobs/search-results/?currentJobId=4489590619"
               "&keywords=Analista%20de%20Tesorer%C3%ADa")
r = report(SOLICITADA, FINAL_NUEVA)
check("la página nueva se reconoce", r["design"], "search-results")
check("es una página de resultados (keywords sigue)", r["ok"], True)
check("no es un muro de login", r["authwall"], False)
check("se detecta que se pidió Easy Apply", r["easy_apply_requested"], True)
check("se detecta que Easy Apply se perdió", r["easy_apply_kept"], False)
check("se perdieron todos los filtros",
      r["dropped"], ["location", "geoId", "f_WT", "f_TPR", "sortBy", "easy_apply"])

r = report(SOLICITADA, SOLICITADA + "&position=1&pageNum=0")
check("página clásica: no se perdió nada", r["dropped"], [])
check("página clásica: Easy Apply sigue", r["easy_apply_kept"], True)
check("página clásica: ok", r["ok"], True)

r = report(SOLICITADA, "https://www.linkedin.com/authwall?trk=bf&sessionRedirect=" + quote(SOLICITADA))
check("muro de login: ok es False", r["ok"], False)
check("muro de login: se marca authwall", r["authwall"], True)

r = report(SOLICITADA, BASE + "&f_AL=true")
check("f_AL=true también cuenta como Easy Apply", r["easy_apply_kept"], True)
check("f_AL=true no se marca como perdido", "easy_apply" in r["dropped"], False)

r = report(BASE + "&f_WT=2", BASE)
check("solo se pierde lo que se había pedido", r["dropped"], ["f_WT"])

r = report(BASE, BASE + "&f_LF=f_AL")
check("LinkedIn puede devolver el filtro solo", r["added"], ["easy_apply"])

# =========================================================================
print("\n3. El id de la oferta, en cualquier diseño")
# =========================================================================
js = extraer(
    RAIZ / "modules" / "job_search.py",
    {"job_id_from_values"},
    {"_ID_IN_URL", "_ID_IN_URN"},
    {"re": re, "print_lg": sin_log},
)
job_id = js["job_id_from_values"]

# El href real de la página pública descargada el 2026-11-16.
HREF_PUBLICO = ("https://cl.linkedin.com/jobs/view/analista-financiero-y-tesorer%C3%ADa-"
                "at-empresa-confidencial-4485334635?position=1&pageNum=0")

check("data-occludable-job-id manda", job_id(occludable="4489590619"), "4489590619")
check("data-job-id sirve de respaldo", job_id(item_id="4476322788"), "4476322788")
check("urn:li:jobPosting", job_id(urn="urn:li:jobPosting:4485334635"), "4485334635")
check("id al final del slug del enlace", job_id(href=HREF_PUBLICO), "4485334635")
check("enlace corto /jobs/view/<id>",
      job_id(href="https://www.linkedin.com/jobs/view/4489590619/"), "4489590619")
check("sin datos no inventa", job_id(), None)
check("un enlace que no es de oferta", job_id(href="https://www.linkedin.com/feed/"), None)

# =========================================================================
print("\n4. Elegir el diseño de tarjeta y sus selectores")
# =========================================================================
js = extraer(
    RAIZ / "modules" / "job_search.py",
    {"pick_card_layout", "layout_by_name"},
    {"JOB_CARD_LAYOUTS"},
    {"print_lg": sin_log},
)
pick = js["pick_card_layout"]
layouts = {l["name"]: l for l in js["JOB_CARD_LAYOUTS"]}

check("se prefiere el diseño clásico si está",
      pick({"occludable-job-id": 25, "view-link": 25}), "occludable-job-id")
check("si no hay clásico, la tarjeta pública",
      pick({"job-search-card": 60, "view-link": 60}), "job-search-card")
check("el último recurso son los enlaces /jobs/view/",
      pick({"view-link": 60}), "view-link")
check("sin tarjetas no elige nada", pick({}), None)

check("el diseño clásico usa el selector real",
      layouts["occludable-job-id"]["card"],
      "li[data-occludable-job-id], div[data-occludable-job-id]")
check("el diseño público usa data-entity-urn (visto en vivo)",
      "data-entity-urn" in layouts["job-search-card"]["card"], True)
check("el respaldo son enlaces a /jobs/view/",
      layouts["view-link"]["card"], "a[href*='/jobs/view/']")
check("cada diseño trae título, empresa, ubicación y estado",
      [n for n, l in layouts.items()
       if not all(k in l for k in ("title", "company", "location", "state", "card"))], [])

# =========================================================================
print("\n5. Easy Apply en la propia tarjeta")
# =========================================================================
js = extraer(
    RAIZ / "modules" / "job_search.py",
    {"easy_apply_marker", "work_style_is_remote", "_fold"},
    {"_ACCENTS", "_EASY_APPLY_MARKERS", "_EXTERNAL_MARKERS"},
    {"print_lg": sin_log},
)
marcador = js["easy_apply_marker"]

check("'Easy Apply' en la tarjeta", marcador("... Easy Apply ..."), "easy")
check("'Solicitud sencilla' (LinkedIn en español)",
      marcador("Solicitud sencilla"), "easy")
check("'Postulación simplificada' con acento",
      marcador("Postulación simplificada"), "easy")
check("'Apply on company site'",
      marcador("Apply on company site (opens in a new tab)"), "external")
check("'Solicitud en el sitio de la empresa'",
      marcador("Solicitud en el sitio de la empresa"), "external")
# La tarjeta pública real no trae la insignia: no se puede concluir nada.
check("una tarjeta que no dice nada -> desconocido",
      marcador("Treasury Analyst Veta Virtual Chile 2 days ago"), None)
check("no confundir 'Applied' con Easy Apply", marcador("Applied 3 days ago"), None)
check("'remoto' se reconoce",
      js["work_style_is_remote"]("Remoto"), True)
check("'Remote (Hybrid)' se reconoce",
      js["work_style_is_remote"]("Remote (Hybrid)"), True)
check("'On-site' no es remoto", js["work_style_is_remote"]("On-site"), False)

# =========================================================================
print("\n6. El CV que no está: mensaje y sugerencias")
# =========================================================================
val = extraer(
    RAIZ / "modules" / "validator.py",
    {"_clean_path", "_fold_name", "looks_like_resume_name", "similar_pdfs",
     "resume_path_problem"},
    {"_RESUME_HINTS", "_PROJECT_ROOT"},
    {"os": os, "unicodedata": unicodedata, "print_lg": sin_log,
     "__file__": str(RAIZ / "modules" / "validator.py")},
)
problema = val["resume_path_problem"]
parecidos = val["similar_pdfs"]

carpeta = Path(tempfile.mkdtemp(prefix="cvsniper-cv-"))
try:
    original = carpeta / "HOJA_DE_VIDA_SANDRA_M.pdf"
    (carpeta / "HOJA_DE_VIDA_SANDRA.pdf").write_bytes(b"%PDF-1.4 de prueba")
    (carpeta / "CV_SANDRA_2026.pdf").write_bytes(b"%PDF-1.4 de prueba")
    (carpeta / "contrato_alquiler.pdf").write_bytes(b"%PDF-1.4 de prueba")
    (carpeta / "notas.txt").write_text("no es un pdf", encoding="utf-8")

    check("un PDF que sí existe no es un problema",
          problema(str(carpeta / "CV_SANDRA_2026.pdf")), None)
    check("se reconoce un nombre de CV", val["looks_like_resume_name"]("HOJA_DE_VIDA.pdf"), True)
    check("se reconoce un CV corto", val["looks_like_resume_name"]("cv-2026.pdf"), True)
    check("un contrato no parece un CV", val["looks_like_resume_name"]("contrato.pdf"), False)

    sugerencias = parecidos(str(original))
    nombres = [os.path.basename(s) for s in sugerencias]
    check("sugiere el PDF con el nombre más parecido primero",
          nombres[0], "HOJA_DE_VIDA_SANDRA.pdf")
    check("sugiere también el otro CV de la carpeta",
          "CV_SANDRA_2026.pdf" in nombres, True)
    check("no sugiere archivos que no son PDF", "notas.txt" in nombres, False)
    check("las sugerencias son rutas absolutas",
          all(os.path.isabs(s) for s in sugerencias), True)

    mensaje = problema(str(original))
    check("una ruta absoluta NO se llama relativa",
          "relative" in mensaje, False)
    check("dice que es una ruta absoluta", "absolute path" in mensaje, True)
    check("nombra el archivo que falta", "HOJA_DE_VIDA_SANDRA_M.pdf" in mensaje, True)
    check("sugiere el PDF parecido", "HOJA_DE_VIDA_SANDRA.pdf" in mensaje, True)
    check("explica dónde se cambia",
          'Respuestas' in mensaje and 'Ruta del CV (PDF)' in mensaje, True)
    check("y el nombre del ajuste en el config", "default_resume_path" in mensaje, True)

    relativo = problema(os.path.join("all resumes", "no_existe.pdf"))
    check("una ruta relativa sí se llama relativa", "relative" in relativo, True)
finally:
    shutil.rmtree(carpeta, ignore_errors=True)

# =========================================================================
print("\n7. El arranque de Chrome: ruta de caché y tiempo límite")
# =========================================================================
oc = extraer(
    RAIZ / "modules" / "open_chrome.py",
    {"uc_cache_paths", "_clear_uc_cache", "_with_timeout"},
    set(),
    {"os": os, "shutil": shutil, "print_lg": sin_log,
     "_cleanup_residual_chromedriver": lambda: None},
)
base, exe, undetected = oc["uc_cache_paths"](r"C:\Users\prueba\AppData\Roaming")
check("la caché de uc está bajo %APPDATA%",
      base, r"C:\Users\prueba\AppData\Roaming\undetected_chromedriver")
check("el exe que no se podía sobrescribir",
      exe, r"C:\Users\prueba\AppData\Roaming\undetected_chromedriver\undetected_chromedriver.exe")
check("la carpeta temporal que deja uc",
      undetected, r"C:\Users\prueba\AppData\Roaming\undetected_chromedriver\undetected")

# El FileExistsError real: hay que poder borrar el exe viejo y la carpeta.
carpeta_uc = Path(tempfile.mkdtemp(prefix="cvsniper-uc-"))
try:
    (carpeta_uc / "undetected_chromedriver.exe").write_bytes(b"viejo")
    (carpeta_uc / "undetected").mkdir()
    (carpeta_uc / "undetected" / "chromedriver.exe").write_bytes(b"viejo")
    oc["uc_cache_paths"] = lambda appdata=None: (
        str(carpeta_uc),
        str(carpeta_uc / "undetected_chromedriver.exe"),
        str(carpeta_uc / "undetected"),
    )
    borrados = oc["_clear_uc_cache"]()
    check("borra el exe viejo",
          (carpeta_uc / "undetected_chromedriver.exe").exists(), False)
    check("borra la carpeta undetected",
          (carpeta_uc / "undetected").exists(), False)
    check("informa qué borró", len(borrados), 2)
finally:
    shutil.rmtree(carpeta_uc, ignore_errors=True)

espera = oc["_with_timeout"]
check("devuelve el valor cuando termina a tiempo", espera(lambda: 7, 2, "prueba"), 7)


def _tarda():
    time.sleep(0.6)


try:
    espera(_tarda, 0.1, "la prueba lenta")
    check("un paso colgado lanza TimeoutError", False, True)
except TimeoutError as e:
    check("el error dice qué paso se colgó y cuánto se esperó",
          "la prueba lenta" in str(e) and "0.1s" in str(e), True)


def _falla():
    raise FileExistsError("WinError 183")


try:
    espera(_falla, 2, "prueba")
    check("los errores del worker se propagan", False, True)
except FileExistsError:
    check("los errores del worker se propagan", True, True)

# =========================================================================
print("\n8. El aviso de 'sigo esperando' de timed_step")
# =========================================================================
# La función instancia la clase, así que se ejecutan las dos.
arbol_ayuda = ast.parse((RAIZ / "modules" / "helpers.py").read_text(encoding="utf-8"))
clase = next(n for n in arbol_ayuda.body
             if isinstance(n, ast.ClassDef) and n.name == "_TimedStep")
mensajes: list[str] = []
ns_ayuda = {"threading": threading, "time": time, "print_lg": mensajes.append}
exec(compile(ast.Module([clase], []), "<helpers>", "exec"), ns_ayuda)
exec(compile(ast.Module([next(n for n in arbol_ayuda.body
                              if isinstance(n, ast.FunctionDef) and n.name == "timed_step")], []),
             "<helpers>", "exec"), ns_ayuda)
paso = ns_ayuda["timed_step"]

with paso("Paso rápido", slow_after=5, heartbeat=0):
    pass
check("un paso rápido no ensucia el log con un 'finished'",
      [m for m in mensajes if "finished" in m], [])
check("pero sí anuncia que empieza", mensajes, ["Paso rápido..."])

mensajes.clear()
with paso("Paso lento", slow_after=0.01, heartbeat=0.05):
    time.sleep(0.14)
check("avisa mientras sigue esperando",
      any("still waiting on 'Paso lento'" in m for m in mensajes), True)
check("y al terminar dice cuánto tardó",
      any(m.startswith("Paso lento finished in") for m in mensajes), True)

mensajes.clear()
try:
    with paso("Paso roto", slow_after=5, heartbeat=0):
        raise ValueError("boom")
except ValueError:
    pass
check("un paso que falla queda en el log",
      any("Paso roto failed after" in m and "ValueError" in m for m in mensajes), True)

# =========================================================================
print("\n9. _start_driver: el FileExistsError de undetected_chromedriver")
# =========================================================================
# Se ejecuta la función real con un Chrome de mentira: dos intentos de modo
# sigiloso como máximo, limpieza de la caché entre ellos, y caída al driver
# normal (con tiempo límite) si el segundo también falla.
import contextlib
from types import SimpleNamespace

oc2 = extraer(
    RAIZ / "modules" / "open_chrome.py",
    {"_with_timeout", "_start_driver"},
    {"STEALTH_TIMEOUT", "FALLBACK_TIMEOUT"},
    {"print_lg": sin_log,
     "_cleanup_residual_chromedriver": lambda: None,
     "timed_step": lambda *a, **k: contextlib.nullcontext()},
)


def arrancar(resultados):
    registro = {"stealth": 0, "limpiezas": 0, "cache": 0, "criticos": 0, "cerrado": 0}

    def stealth_falso():
        indice = registro["stealth"]
        registro["stealth"] += 1
        valor = resultados[indice] if indice < len(resultados) else resultados[-1]
        if isinstance(valor, BaseException):
            raise valor
        return valor

    ns = {
        "stealth_mode": True,
        "_close_bot_profile_chrome": lambda: registro.__setitem__("cerrado", registro["cerrado"] + 1),
        "_stealth_driver": stealth_falso,
        "_with_timeout": oc2["_with_timeout"],
        "_cleanup_residual_chromedriver": lambda: registro.__setitem__("limpiezas", registro["limpiezas"] + 1),
        "_clear_uc_cache": lambda: registro.__setitem__("cache", registro["cache"] + 1),
        "print_lg": sin_log,
        "critical_error_log": lambda *a, **k: registro.__setitem__("criticos", registro["criticos"] + 1),
        "timed_step": lambda *a, **k: contextlib.nullcontext(),
        "webdriver": SimpleNamespace(Chrome=lambda options=None: "DRIVER-NORMAL"),
        "ChromeOptions": lambda: "opciones",
        "_build_options": lambda opciones: opciones,
        "STEALTH_TIMEOUT": 5,
        "FALLBACK_TIMEOUT": 5,
    }
    exec(compile(ast.Module([next(n for n in ast.parse(
        (RAIZ / "modules" / "open_chrome.py").read_text(encoding="utf-8")).body
        if isinstance(n, ast.FunctionDef) and n.name == "_start_driver")], []),
        "<open_chrome>", "exec"), ns)
    return ns["_start_driver"](), registro


driver_final, reg = arrancar([FileExistsError("[WinError 183] ya existe"), "DRIVER-SIGILOSO"])
check("un FileExistsError se reintenta una vez", reg["stealth"], 2)
check("el reintento arranca el modo sigiloso", driver_final, "DRIVER-SIGILOSO")
check("entre intentos mata los chromedriver", reg["limpiezas"] >= 1, True)
check("entre intentos borra la caché de uc", reg["cache"] >= 1, True)
check("y no da el arranque por perdido", reg["criticos"], 0)

driver_final, reg = arrancar([FileExistsError("uno"), PermissionError("dos")])
check("si el exe sigue en uso también se reintenta", reg["stealth"], 2)
check("tras el segundo fallo cae al driver normal", driver_final, "DRIVER-NORMAL")
check("y lo registra como crítico", reg["criticos"], 1)
check("la caché se limpia en los dos intentos", reg["cache"], 2)

driver_final, reg = arrancar([RuntimeError("uc roto")])
check("un fallo distinto no se reintenta", reg["stealth"], 1)
check("y cae directo al driver normal", driver_final, "DRIVER-NORMAL")
check("queda registrado", reg["criticos"], 1)

# =========================================================================
print("\n" + "=" * 60)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo correcto.")
