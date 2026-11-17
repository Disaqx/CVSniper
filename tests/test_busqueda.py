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

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

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
    {"_EASY_APPLY_TRUE", "_DATE_POSTED_TO_TPR", "_SORT_BY_TO_URL"},
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
check("fecha y orden viajan en la URL (para no abrir el panel de filtros)",
      build("Help Desk", location="Bogotá, Colombia",
            date_posted="Past week", sort_by="Most recent"),
      "https://www.linkedin.com/jobs/search/?keywords=Help%20Desk"
      "&location=Bogot%C3%A1%2C%20Colombia&f_TPR=r604800&sortBy=DD")
check("'Any time' no añade f_TPR",
      build("Help Desk", date_posted="Any time", sort_by="Most relevant"),
      "https://www.linkedin.com/jobs/search/?keywords=Help%20Desk&sortBy=R")
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
    {"_ID_IN_URL", "_ID_IN_URN", "_ID_IN_CURRENT"},
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
# La página nueva es una SPA: seleccionar una tarjeta pone currentJobId, no /jobs/view/.
check("currentJobId de la página nueva",
      job_id(href="https://www.linkedin.com/jobs/search-results/?currentJobId=4489590619&keywords=x"),
      "4489590619")
check("currentJobId no se confunde con otro parámetro",
      job_id(href="https://www.linkedin.com/jobs/search-results/?keywords=4489590619"), None)
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
check("la página nueva enlaza con currentJobId",
      layouts["current-job-id"]["card"], "a[href*='currentJobId=']")
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

print("   -- aviso de salario por debajo del objetivo (solo informativo) --")
js_sal = extraer(
    RAIZ / "modules" / "job_search.py",
    {"salary_below_target"},
    {"_SALARY_AMOUNT"},
    {"re": re, "print_lg": sin_log},
)
salario = js_sal["salary_below_target"]
aviso = salario("Salario: $3.000.000 COP, prestaciones de ley.", 4_000_000)
check("un salario por debajo del objetivo genera aviso", isinstance(aviso, str), True)
check("el aviso dice cuánto paga", "3.000.000" in (aviso or ""), True)
check("el aviso dice cuál es el objetivo", "4.000.000" in (aviso or ""), True)
check("y deja claro que se aplicó igual", "se aplicó igual" in (aviso or ""), True)
check("un salario por encima no genera aviso",
      salario("Pagamos $4.500.000 COP", 4_000_000), None)
check("'3,5 millones' se entiende",
      "3.500.000" in (salario("Salario de 3,5 millones", 4_000_000) or ""), True)
check("un rango que llega al objetivo no avisa",
      salario("$3.000.000 a $4.200.000", 4_000_000), None)
check("USD/EUR no se convierten a ojo",
      salario("USD 1,200 per month", 4_000_000), None)
check("sin cifras de salario no inventa",
      salario("Buscamos una persona proactiva.", 4_000_000), None)
check("sin objetivo configurado no avisa",
      salario("$1.000.000", 0), None)
check("el aviso no se dispara con un año o un id",
      salario("Experiencia de 3 años, cargo 2026", 4_000_000), None)

# El bug que este test vigila: el contenedor de una tarjeta subía hasta el <ul>
# con todas, y entonces "Applied" de CUALQUIER tarjeta marcaba todas como
# postuladas. La subida tiene que parar al llegar a más de un enlace de oferta.
src_job_search = (RAIZ / "modules" / "job_search.py").read_text(encoding="utf-8")
check("el contenedor se detiene antes de la lista completa",
      "length > 1" in src_job_search and "currentJobId=']" in src_job_search, True)

# =========================================================================
print("\n6b. La descripción en los diseños nuevos (sin la clase vieja)")
# =========================================================================
js_desc = extraer(
    RAIZ / "modules" / "job_search.py",
    {"_first_visible_text", "find_job_description_element", "find_company_box"},
    {"_DESCRIPTION_SELECTORS", "_COMPANY_BOX_SELECTORS"},
    {"By": By, "print_lg": sin_log},
)


class _NodoTexto:
    def __init__(self, text):
        self.text = text


class _DriverFalso:
    def __init__(self, mapa):
        self.mapa = mapa

    def find_elements(self, by, selector):
        return self.mapa.get(selector, [])


js_desc["driver"] = _DriverFalso({
    ".jobs-box__html-content": [],                       # el diseño viejo no está
    ".jobs-description__content": [_NodoTexto("x" * 80)],  # el nuevo sí
})
check("encuentra la descripción del diseño nuevo",
      (js_desc["find_job_description_element"]().text or "")[:1], "x")

js_desc["driver"] = _DriverFalso({
    ".jobs-box__html-content": [_NodoTexto("corta")],       # un rótulo, no la descripción
    "[data-testid='job-description']": [_NodoTexto("y" * 90)],
})
check("ignora un texto demasiado corto y sigue buscando",
      (js_desc["find_job_description_element"]().text or "")[:1], "y")

js_desc["driver"] = _DriverFalso({})
check("sin descripción devuelve None (y el bot sigue, no se cae)",
      js_desc["find_job_description_element"](), None)

js_desc["driver"] = _DriverFalso({
    ".jobs-company__box": [],
    "[data-testid='about-company']": [_NodoTexto("Somos una empresa con 20 años")],
})
check("encuentra 'Sobre la empresa' por el selector nuevo",
      "empresa" in js_desc["find_company_box"]().text, True)

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
print("\n10. Leer una tarjeta de cada diseño (con elementos de mentira)")
# =========================================================================
# El rediseño no puede probarse sin sesión de LinkedIn, pero sí se puede
# comprobar que la refactorización no cambió lo que se lee de la tarjeta
# clásica: mismo título, empresa, ubicación, modalidad y estado "Applied".
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

js2 = extraer(
    RAIZ / "modules" / "job_search.py",
    {"job_id_from_values", "pick_card_layout", "layout_by_name", "current_layout_name",
     "is_applied_state", "_first_text", "_card_lines", "_attr", "card_apply_marker",
     "easy_apply_marker", "get_job_main_details", "_fold"},
    {"JOB_CARD_LAYOUTS", "_ACTIVE_LAYOUT", "_APPLIED_STATES", "_ACCENTS",
     "_ID_IN_URL", "_ID_IN_URN", "_EASY_APPLY_MARKERS", "_EXTERNAL_MARKERS"},
    {"re": re,
     "By": By,
     "click_gap": 0,
     "NoSuchElementException": NoSuchElementException,
     "StaleElementReferenceException": __import__(
         "selenium.common.exceptions", fromlist=["StaleElementReferenceException"]
     ).StaleElementReferenceException,
     "ElementClickInterceptedException": __import__(
         "selenium.common.exceptions", fromlist=["ElementClickInterceptedException"]
     ).ElementClickInterceptedException,
     "print_lg": sin_log,
     "buffer": lambda *a, **k: None,
     "sleep": lambda *a, **k: None,
     "scroll_to_view": lambda *a, **k: None,
     "discard_job": lambda *a, **k: None,
     "actions": SimpleNamespace(send_keys=lambda *a, **k: None),
     "driver": SimpleNamespace(execute_script=lambda *a, **k: None,
                               current_url="https://www.linkedin.com/jobs/search/?keywords=x")},
)


class _Nodo:
    """Lo mínimo de un WebElement que usa get_job_main_details."""

    def __init__(self, text="", attrs=None, hijos=None, tag="div"):
        self.text = text
        self.tag_name = tag
        self._attrs = attrs or {}
        self._hijos = hijos or {}

    def find_element(self, by, selector):
        if selector in self._hijos:
            return self._hijos[selector]
        # Los selectores de enlace ahora agrupan dos formas ("/jobs/view/" o
        # "currentJobId="): vale cualquiera de las claves guardadas.
        for clave, hijo in self._hijos.items():
            if clave in selector or selector in clave:
                return hijo
        raise NoSuchElementException(selector)

    def find_elements(self, by, selector):
        return []

    def get_attribute(self, name):
        return self._attrs.get(name)

    def get_dom_attribute(self, name):
        return self._attrs.get(name)

    def click(self):
        pass

    def is_selected(self):
        return False


# --- diseño clásico: li[data-occludable-job-id] ---------------------------
ANCLA_CLASICA = _Nodo("Analista de Tesorería", {"href": "https://www.linkedin.com/jobs/view/analista-4489590619"},
                      tag="a")
TARJETA_CLASICA = _Nodo(
    "Analista de Tesorería\nAcme · Bogotá, Colombia (Remote)\nApplied",
    attrs={"data-occludable-job-id": "4489590619"},
    hijos={
        "a[href*='/jobs/view/']": ANCLA_CLASICA,
        "a.job-card-container__link": _Nodo("Analista de Tesorería"),
        ".artdeco-entity-lockup__subtitle": _Nodo("Acme · Bogotá, Colombia (Remote)"),
        ".job-card-container__metadata-item": _Nodo("Bogotá, Colombia (Remote)"),
        ".job-card-container__footer-job-state": _Nodo("Applied"),
    },
)
js2["_ACTIVE_LAYOUT"]["name"] = "occludable-job-id"
detalles = js2["get_job_main_details"](TARJETA_CLASICA, set(), set())
check("clásico: id", detalles[0], "4489590619")
check("clásico: título", detalles[1], "Analista de Tesorería")
check("clásico: empresa", detalles[2], "Acme")
check("clásico: ubicación sin la modalidad", detalles[3], "Bogotá, Colombia")
check("clásico: modalidad", detalles[4], "Remote")
check("clásico: ya postulado -> skip", detalles[5], True)

TARJETA_CLASICA._hijos[".job-card-container__footer-job-state"] = _Nodo("Be an early applicant")
TARJETA_CLASICA.text = "Analista de Tesorería\nAcme · Bogotá, Colombia (Remote)\nBe an early applicant"
detalles = js2["get_job_main_details"](TARJETA_CLASICA, set(), set())
check("clásico: sin postular -> no skip", detalles[5], False)

# --- diseño público: div.job-search-card[data-entity-urn] ------------------
ANCLA_PUBLICA = _Nodo("Analista Financiero y Tesorería",
                      {"href": "https://cl.linkedin.com/jobs/view/analista-financiero-y-tesoreria-at-"
                               "empresa-confidencial-4485334635?position=1&pageNum=0"}, tag="a")
TARJETA_PUBLICA = _Nodo(
    "Analista Financiero y Tesorería\nEmpresa confidencial\nHuechuraba, Santiago\n2 weeks ago",
    attrs={"data-entity-urn": "urn:li:jobPosting:4485334635"},
    hijos={
        "a[href*='/jobs/view/']": ANCLA_PUBLICA,
        "h3.base-search-card__title": _Nodo("Analista Financiero y Tesorería"),
        "h4.base-search-card__subtitle": _Nodo("Empresa confidencial"),
        ".job-search-card__location": _Nodo("Huechuraba, Santiago Metropolitan Region, Chile"),
    },
)
js2["_ACTIVE_LAYOUT"]["name"] = "job-search-card"
detalles = js2["get_job_main_details"](TARJETA_PUBLICA, set(), set())
check("público: id desde data-entity-urn", detalles[0], "4485334635")
check("público: título", detalles[1], "Analista Financiero y Tesorería")
check("público: empresa", detalles[2], "Empresa confidencial")
check("público: ubicación", detalles[3], "Huechuraba, Santiago Metropolitan Region, Chile")
check("público: sin estado -> no skip", detalles[5], False)

# Y sin ningún selector conocido (solo el texto de la tarjeta) tampoco se cae.
TARJETA_SIN_SELECTORES = _Nodo(
    "Treasury Analyst\nVeta Virtual\nSantiago, Chile\n2 days ago",
    hijos={"a[href*='/jobs/view/']": _Nodo(
        "Treasury Analyst",
        {"href": "https://cl.linkedin.com/jobs/view/treasury-analyst-at-veta-4489869210"}, tag="a")},
)
js2["_ACTIVE_LAYOUT"]["name"] = "view-link"
detalles = js2["get_job_main_details"](TARJETA_SIN_SELECTORES, set(), set())
check("sin selectores: id desde el enlace", detalles[0], "4489869210")
check("sin selectores: título de la 1ª línea", detalles[1], "Treasury Analyst")
check("sin selectores: empresa de la 2ª línea", detalles[2], "Veta Virtual")
check("sin selectores: ubicación de la 3ª línea", detalles[3], "Santiago, Chile")

# =========================================================================
print("\n11. El dashboard explica por qué se aplicó")
# =========================================================================
# app.py no abre Chrome ni Tk: se importa tal cual y se le apunta a una carpeta
# temporal con el historial y la hoja de motivos.
sys.path.insert(0, str(RAIZ))
import app as dashboard  # noqa: E402

carpeta_dash = Path(tempfile.mkdtemp(prefix="cvsniper-dash-"))
try:
    (carpeta_dash / "all_applied_applications_history.csv").write_text(
        "Job ID,Title,Company,Work Location,Work Style,About Job,Experience required,"
        "Skills required,HR Name,HR Link,Resume,Re-posted,Date Posted,Date Applied,"
        "Job Link,External Job link,Questions Found,Connect Request\n"
        "4489590619,Analista de Tesorería,Acme,Bogotá,On-site,desc,2,,N/A,N/A,x,"
        "False,,2026-11-17,https://www.linkedin.com/jobs/view/4489590619,Easy Applied,,\n",
        encoding="utf-8",
    )
    (carpeta_dash / "application_notes.csv").write_text(
        "Job ID,Date Applied,AI Score,AI Reason,Applied Despite\n"
        '4489590619,2026-11-17,40,Salario por debajo,'
        '"IA 40/100: Salario por debajo | Salario publicado ≈ $3.000.000 COP, '
        'por debajo de tu objetivo ($4.000.000); se aplicó igual."\n',
        encoding="utf-8",
    )
    dashboard.PATH = str(carpeta_dash) + os.sep
    dashboard.NOTES_FILE = str(carpeta_dash / "application_notes.csv")
    cliente = dashboard.app.test_client()
    respuesta = cliente.get("/applied-jobs")
    datos = respuesta.get_json()
    check("el endpoint responde", respuesta.status_code, 200)
    check("incluye la nota de la aplicación", len(datos), 1)
    check("puntuación de la IA", datos[0].get("AI_Score"), "40")
    check("explica que se aplicó igual",
          "se aplicó igual" in (datos[0].get("Applied_Despite") or ""), True)
    portada = cliente.get("/").get_data(as_text=True)
    check("la tabla del dashboard tiene la columna", "Por qué se aplicó" in portada, True)
finally:
    shutil.rmtree(carpeta_dash, ignore_errors=True)

# =========================================================================
print("\n12. Actualización automática")
# =========================================================================
import hashlib  # noqa: E402
import json  # noqa: E402

upd = extraer(
    RAIZ / "modules" / "updates.py",
    {"_pick_installer_asset", "installer_command", "_sha256", "_parts", "is_newer"},
    {"REPO"},
    {"re": re, "os": os, "hashlib": hashlib, "print_lg": sin_log,
     "__version__": "1.1.1"},
)

ASSETS = [
    {"name": "CVSniper-Setup-1.2.0.exe",
     "browser_download_url": "https://github.com/x/CVSniper-Setup-1.2.0.exe",
     "size": 123, "digest": "sha256:abc"},
    {"name": "CVSniper-Setup-1.1.9.exe",
     "browser_download_url": "https://github.com/x/CVSniper-Setup-1.1.9.exe"},
    {"name": "notas.txt", "browser_download_url": "https://github.com/x/notas.txt"},
]
elegido = upd["_pick_installer_asset"](ASSETS, "1.2.0")
check("elige el instalador de la versión publicada", elegido["name"], "CVSniper-Setup-1.2.0.exe")
check("y su URL de descarga", elegido["browser_download_url"].endswith("1.2.0.exe"), True)
check("ignora assets que no son el instalador",
      upd["_pick_installer_asset"]([{"name": "notas.txt"}], "1.2.0"), None)
check("si no hay coincidencia exacta, usa el primer setup",
      upd["_pick_installer_asset"](ASSETS, "9.9.9")["name"], "CVSniper-Setup-1.2.0.exe")

cmd = upd["installer_command"](r"C:\tmp\CVSniper-Setup-1.2.0.exe", r"C:\app\CVSniper.cmd")
check("instalación silenciosa (sin ventanas ni reinicio)",
      "/VERYSILENT" in cmd and "/SUPPRESSMSGBOXES" in cmd and "/NORESTART" in cmd, True)
check("cierra la app para reemplazar archivos",
      "/CLOSEAPPLICATIONS" in cmd and "/FORCECLOSEAPPLICATIONS" in cmd, True)
check("vuelve a abrir CVSniper al terminar",
      'start "" /min' in cmd and "CVSniper.cmd" in cmd, True)

_archivo = Path(tempfile.mkdtemp(prefix="cvsniper-sha-")) / "x.bin"
try:
    _archivo.write_bytes(b"cvsniper")
    check("el SHA-256 coincide con el valor conocido",
          upd["_sha256"](str(_archivo))[:16], hashlib.sha256(b"cvsniper").hexdigest()[:16])
finally:
    shutil.rmtree(_archivo.parent, ignore_errors=True)

check("1.2.0 es más nueva que 1.1.1", upd["is_newer"]("v1.2.0", "1.1.1"), True)
check("1.1.1 no es más nueva que 1.1.1", upd["is_newer"]("1.1.1", "1.1.1"), False)

# =========================================================================
print("\n" + "=" * 60)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo correcto.")
