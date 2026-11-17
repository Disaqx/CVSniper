import re
import time
from typing import Literal
from urllib.parse import parse_qs, quote, urlsplit
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException
from modules.open_chrome import driver, wait, actions
from modules.helpers import print_lg, buffer, sleep, critical_error_log, timed_step
from modules.bot_ui import is_career_ops_mode, ui_confirm, ui_pause_check
from modules.clickers_and_finders import try_xp, find_by_class, try_find_by_classes, wait_span_click, multi_sel_noWait, scroll_to_view, boolean_button_click
from modules.easy_apply import discard_job
from config.search import (
    bad_words, about_company_good_words, about_company_bad_words,
    enable_job_focus_filter, primary_focus_keywords, secondary_focus_keywords,
    security_clearance, current_experience, did_masters,
    experience_level, companies, job_type, on_site, easy_apply_only,
    under_10_applicants, in_your_network, fair_chance_employer,
    salary, benefits, commitments, location, industry, job_function, job_titles,
)
from config.settings import click_gap
from config.personals import disability_status

try:
    from config.settings import logs_folder_path
except ImportError:
    logs_folder_path = "logs/"

# Settings added after the first release. Reading them defensively keeps an old
# config/search.py working instead of crashing the bot on import.
try:
    from config.search import title_bad_words
except ImportError:
    title_bad_words = []
try:
    from config.search import (work_authorized_countries, work_authorized_regions,
                               enable_residency_filter)
except ImportError:
    work_authorized_countries, work_authorized_regions = [], []
    enable_residency_filter = False
if not work_authorized_countries:
    # Left empty by the template. Without this fallback a fresh install would
    # skip jobs in the user's OWN country for requiring residency there.
    try:
        from config.personals import country as _pais_propio
        work_authorized_countries = [_pais_propio] if _pais_propio else []
    except ImportError:
        work_authorized_countries = []
try:
    from config.search import experience_tolerance
    # The settings panel can write this back as a string.
    experience_tolerance = int(experience_tolerance)
except (ImportError, TypeError, ValueError):
    experience_tolerance = 0
try:
    from modules.helpers import as_number as _as_number
    current_experience = int(_as_number(current_experience, -1))
except NameError:
    pass


# "3 years", "5+ yrs", "3-5 years", "2 to 4 years", and in Spanish "3 años",
# "3 a 5 años". A range yields its lower end. Spanish postings used to be
# invisible to the experience filter, because only "year" was recognised.
re_experience = re.compile(
    r'[(]?\s*(\d+)\s*[)]?\s*(?:(?:-|–|to|a)\s*\d+\s*)?[+]*\s*(?:years?|yrs?|a[ñn]os?)\b',
    re.IGNORECASE)

# 'secret' used to be matched as a bare substring, which fired on the Spanish
# words "secreto" and "secretaria" — present in a large share of Colombian
# postings — and silently threw those jobs away. Only real clearance wording
# should skip a job.
_CLEARANCE_PHRASES = (
    'security clearance', 'secret clearance', 'top secret', 'ts/sci',
    'dod clearance', 'active clearance', 'clearance required',
    'polygraph', 'poligrafo', 'polígrafo',
)

_ACCENTS = str.maketrans('áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')


def _fold(text: str) -> str:
    '''Lowercase and strip accents, so "Técnico" matches "tecnico".'''
    return (text or "").translate(_ACCENTS).lower()


def _contains_term(haystack_low: str, term: str) -> bool:
    '''
    Whole-word match, so "CNC" does not fire inside "CNCF" and "PHP" does not
    fire inside "phpMyAdmin".

    A plain \\b is not enough for dotted text: "\\bphp\\b" still matches the
    "php" in "index.php", and "\\.net\\b" still matches the "net" in
    "careers.example.net" — both of which are URLs, not skill requirements. So a
    dot counts as part of the word for the purpose of the left edge. The cost is
    that a term written ".NET" no longer matches "ASP.NET"; erring towards not
    skipping is the right side to fail on.
    '''
    term = (term or "").strip()
    if not term:
        return False
    pattern = re.escape(term.lower())
    # Left edge: never start mid-word, and never inside a dotted name/URL.
    pattern = (r'(?<![\w.])' if re.match(r'\w', term[0]) else r'(?<!\w)') + pattern
    # Right edge: only needed when the term itself ends in a word character.
    if re.search(r'\w$', term):
        pattern += r'\b'
    return re.search(pattern, haystack_low) is not None


# LinkedIn's Remote filter means "no office attendance", not "we hire from
# anywhere" — there is no filter for the latter. A posting that only accepts
# residents of one country says so in prose, so that prose is what gets read.
#
# Each pattern captures the words that FOLLOW the requirement, because that tail
# is where the place is named.
_RESIDENCY_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r'must (?:be )?(?:currently )?(?:reside|live|be located|be based|be situated)\b[^.\n;]{0,90}',
    r'(?:candidates?|applicants?|you) must be (?:located|based|residing|living)\b[^.\n;]{0,90}',
    r'must (?:be (?:legally )?(?:authoriz|authoris)ed|have (?:the )?(?:legal )?right) to work\b[^.\n;]{0,90}',
    r'(?:must be |are )?eligible to work\b[^.\n;]{0,90}',
    r'open only to\b[^.\n;]{0,90}',
    r'only (?:candidates|applicants|residents|those)\s+(?:in|from|located|residing|based)\b[^.\n;]{0,90}',
    r'(?:this role|this position|the role) is (?:only )?(?:available|open) (?:to|for|in)\b[^.\n;]{0,90}',
    # "residents of X" and "ubicada en X" on their own describe the company or
    # its customers far more often than they restrict the candidate ("we help
    # residents of the US save", "somos una empresa ubicada en Mexico"). Both
    # used to skip the job outright, so they now need a word that makes them a
    # requirement.
    r'(?:only|exclusively|limited to|restricted to)\s+(?:\w+\s+){0,2}residents? of\b[^.\n;]{0,90}',
    r'residents? of\b[^.\n;]{0,60}\bonly\b',
    r'(?:debes?|deben|debera[s]?) (?:residir|vivir|estar (?:ubicad|radicad)[oa]s?)\b[^.\n;]{0,90}',
    r'(?:indispensable|excluyente|imprescindible|requisito|obligatori[oa]|unicamente|solamente|solo)\b[^.\n;]{0,40}?'
    r'(?:residir|vivir|radicad[oa]s?|ubicad[oa]s?|residencia) en\b[^.\n;]{0,90}',
    r'(?:residir|vivir|radicad[oa]s?|ubicad[oa]s?|residencia) en\b[^.\n;]{0,60}?'
    r'(?:indispensable|excluyente|imprescindible|obligatori[oa])',
))

# Only needs to cover places that actually appear in these clauses. A country
# not listed here simply falls through to the AI rather than being skipped.
_COUNTRY_NAMES = (
    'united states', 'the us', 'the u.s.', 'usa', 'u.s.a', 'america',
    'canada', 'united kingdom', 'the uk', 'u.k.', 'england', 'ireland',
    'germany', 'alemania', 'france', 'francia', 'spain', 'espana',
    'portugal', 'italy', 'italia', 'netherlands', 'holanda', 'belgium',
    'switzerland', 'suiza', 'austria', 'poland', 'polonia', 'romania',
    'sweden', 'norway', 'denmark', 'finland', 'greece',
    'australia', 'new zealand', 'japan', 'japon', 'china', 'singapore',
    'india', 'pakistan', 'philippines', 'filipinas', 'indonesia', 'vietnam',
    'south africa', 'nigeria', 'kenya', 'egypt', 'israel', 'turkey',
    'united arab emirates', 'uae', 'saudi arabia', 'qatar',
    'mexico', 'brazil', 'brasil', 'argentina', 'chile', 'peru', 'ecuador',
    'uruguay', 'paraguay', 'bolivia', 'venezuela', 'costa rica', 'panama',
    'guatemala', 'honduras', 'el salvador', 'nicaragua',
    'dominican republic', 'republica dominicana', 'puerto rico', 'colombia',
    'european union', 'the eu', 'europe', 'europa', 'emea', 'apac', 'anz',
)


def requires_ineligible_residency(description: str) -> str | None:
    '''
    Returns the offending clause if the posting requires living in, or being
    authorised to work in, somewhere the user is not — else None.

    Deliberately cautious: it only skips when a residency clause names a place
    that is recognised AND not on the allowed lists. A clause naming nowhere in
    particular, or naming a country not in `_COUNTRY_NAMES`, is left for the AI
    pre-screening to judge. Skipping a job the user could have had costs more
    than one wasted application.
    '''
    if not enable_residency_filter:
        return None
    try:
        permitidos = [_fold(p) for p in
                      list(work_authorized_countries or []) + list(work_authorized_regions or [])
                      if p and str(p).strip()]
        texto = _fold(description)
        for patron in _RESIDENCY_PATTERNS:
            for clausula in patron.findall(texto):
                # An allowed place anywhere in the clause makes it fine — this
                # also covers "must reside in Colombia or Mexico".
                if any(_contains_term(clausula, p) for p in permitidos):
                    continue
                prohibido = next((c for c in _COUNTRY_NAMES if _contains_term(clausula, c)), None)
                if prohibido:
                    return clausula.strip()
        return None
    except Exception:
        return None  # Fail open


def is_title_blacklisted(title: str) -> str | None:
    '''
    Returns the offending word if the title is one the user never wants, else
    None. Runs whether or not the focus filter is on — it is the cheap guard
    that makes leaving the focus filter off safe.
    '''
    try:
        title_low = _fold(title)
        for word in title_bad_words or []:
            if _contains_term(title_low, _fold(word)):
                return word
        return None
    except Exception:
        return None  # Fail open


def is_job_relevant(title: str, work_style: str) -> bool:
    '''
    Returns True if the job title matches the user's configured job focus.
    - Primary keywords: always allowed.
    - Secondary keywords: only allowed if work_style is Remote or Hybrid.
    - If enable_job_focus_filter is False, always returns True.
    Accent-insensitive, so "Soporte Tecnico" and "Soporte Técnico" both match.
    '''
    try:
        if not enable_job_focus_filter:
            return True
        title_low = _fold(title)
        # Check primary focus (always relevant)
        for kw in primary_focus_keywords:
            if _fold(kw) in title_low:
                return True
        # Check secondary focus (only if Remote or Hybrid — EN and ES)
        style_low = _fold(work_style)
        if any(s in style_low for s in ["remote", "hybrid", "remoto", "hibrido"]):
            for kw in secondary_focus_keywords:
                if _fold(kw) in title_low:
                    return True
        return False
    except Exception:
        return True  # Fail open if config missing


# ---------------------------------------------------------------------------
# Search URLs and the two LinkedIn results pages
# ---------------------------------------------------------------------------
# LinkedIn is moving /jobs/search/ to /jobs/search-results/. On the new page the
# redirect drops most of the query string: `location`, `f_LF=f_AL` (Easy Apply),
# `f_WT`, `f_TPR` and `sortBy` disappear and only `keywords` (sometimes `geoId`
# and `f_SAL`) plus a `currentJobId` survive. The bot used to trust the URL it
# had asked for and then found no cards. Everything that builds or reads those
# URLs lives in this section, so the answer is in one place.

SEARCH_PATH = "/jobs/search/"
NEW_SEARCH_PATH = "/jobs/search-results/"

# Names for the log. Keys are the parameters LinkedIn drops.
FILTER_LABELS = {
    "keywords": "la búsqueda (keywords)",
    "location": "la ubicación (location)",
    "geoId": "el identificador de ubicación (geoId)",
    "easy_apply": "el filtro Easy Apply (f_LF/f_AL)",
    "f_WT": "la modalidad (f_WT: remoto/presencial)",
    "f_TPR": "la fecha de publicación (f_TPR)",
    "sortBy": "el orden (sortBy)",
    "f_JT": "el tipo de contrato (f_JT)",
    "f_SAL": "el salario (f_SAL)",
}

# Params that carry the same meaning as another one. Easy Apply used to be
# `f_AL=true` and is now `f_LF=f_AL`; a URL has the filter if either is there.
_EASY_APPLY_TRUE = {"f_al", "true", "1", "yes", "y"}


def _query_params(url: str) -> dict[str, list[str]]:
    """Query string of a URL as {name: [values]}, blank values included."""
    try:
        return parse_qs(urlsplit(url or "").query, keep_blank_values=True)
    except Exception:
        return {}


def _easy_apply_in(params: dict[str, list[str]]) -> bool:
    for valor in list(params.get("f_LF") or []) + list(params.get("f_AL") or []):
        if str(valor).strip().lower() in _EASY_APPLY_TRUE:
            return True
    return False


def search_design(url: str) -> str:
    """Which LinkedIn page this URL is: 'classic', 'search-results', 'authwall' or 'other'."""
    low = (url or "").lower()
    if "/authwall" in low or "/login" in low or "/signup" in low or "/checkpoint" in low:
        return "authwall"
    if NEW_SEARCH_PATH in low:
        return "search-results"
    if SEARCH_PATH in low:
        return "classic"
    return "other"


def build_search_url(search_term: str, location: str | None = None, geo_id: str | None = None,
                     easy_apply: bool = False, remote_only: bool = False,
                     job_types=()) -> str:
    """The results URL the bot asks LinkedIn for.

    Stays on the classic `/jobs/search/` path on purpose: it is the design the
    bot knows, and in a live check (anonymous session, 2026-11-16) LinkedIn kept
    every parameter there. The new page is chosen by LinkedIn, not by us, which
    is why `navigation_report()` exists.
    """
    url = "https://www.linkedin.com/jobs/search/?keywords=" + quote(str(search_term))
    if location and str(location).strip():
        url += "&location=" + quote(str(location).strip())
        # geoId wins over location on LinkedIn's side, which is what pins the
        # "Worldwide" sweep to the global scope instead of a guessed city.
        if geo_id:
            url += "&geoId=" + quote(str(geo_id))
    # `f_LF=f_AL` is Easy Apply today. `apply_filters()` also ticks the toggle,
    # but it finds it by its translated label and gives up silently when the
    # label does not match — which is how a run ends up walking external jobs.
    if easy_apply:
        url += "&f_LF=f_AL"
    # f_WT is LinkedIn's workplace-type filter: 1 on-site, 2 remote, 3 hybrid.
    if remote_only:
        url += "&f_WT=2"
        # f_JT is the job type. LinkedIn has no freelance filter; "C"
        # (Contract) is the nearest equivalent.
        if job_types:
            url += "&f_JT=" + quote(",".join(job_types))
    return url


def add_legacy_easy_apply(url: str) -> str:
    """Add the pre-2024 Easy Apply alias (`f_AL=true`) to a results URL.

    Used only as a retry when LinkedIn answered with the new page and dropped
    `f_LF`. Live check (anonymous, 2026-11-16): `/jobs/search-results/...&f_AL=true`
    is redirected back to `/jobs/search/` with all its parameters intact, while
    the same URL without it stays on the new page. The classic page ignores the
    alias when `f_LF=f_AL` is already doing the work.
    """
    if "f_al=true" in (url or "").lower():
        return url
    return url + ("&" if "?" in url else "?") + "f_AL=true"


def navigation_report(requested_url: str, final_url: str) -> dict:
    """Compare what was asked for with where LinkedIn actually landed.

    Returns:
        design              'classic' | 'search-results' | 'authwall' | 'other'
        ok                  the page is a results page for these keywords
        authwall            LinkedIn sent us to log in / sign up
        dropped             parameter keys the redirect lost
        added               ['easy_apply'] when LinkedIn put the filter back
        easy_apply_requested / easy_apply_kept
        classic             the final URL kept the design this bot knows
    """
    pedidos = _query_params(requested_url)
    obtenidos = _query_params(final_url)
    diseno = search_design(final_url)
    ea_pedido = _easy_apply_in(pedidos)
    ea_final = _easy_apply_in(obtenidos)

    informe = {
        "design": diseno,
        "classic": diseno == "classic",
        "authwall": diseno == "authwall",
        "ok": False,
        "dropped": [],
        "added": [],
        "easy_apply_requested": ea_pedido,
        "easy_apply_kept": ea_final,
    }

    if diseno in ("classic", "search-results"):
        # `keywords` is the only parameter both designs always keep; the result
        # page only exists if it is there (or was what we asked for).
        informe["ok"] = bool(obtenidos.get("keywords") or pedidos.get("keywords"))

    if diseno == "authwall":
        # The whole query string is inside `sessionRedirect`, so comparing the
        # parameters would only produce noise: nothing survived because nothing
        # was served. The authwall flag is the useful part.
        return informe

    if pedidos.get("keywords") and not obtenidos.get("keywords"):
        informe["dropped"].append("keywords")
    for parametro in ("location", "geoId", "f_WT", "f_TPR", "sortBy", "f_JT", "f_SAL"):
        if pedidos.get(parametro) and not obtenidos.get(parametro):
            informe["dropped"].append(parametro)
    if ea_pedido and not ea_final:
        informe["dropped"].append("easy_apply")
    if ea_final and not ea_pedido:
        informe["added"].append("easy_apply")

    return informe


def log_navigation_report(report: dict, final_url: str = "") -> None:
    """Write the navigation result to the log, one warning per lost filter."""
    if report.get("authwall"):
        print_lg("WARNING: LinkedIn took the browser to a login / sign-up wall instead of the results.")
    elif report.get("design") == "search-results":
        print_lg("LinkedIn opened the NEW results page (/jobs/search-results/).")
    if not report.get("ok"):
        print_lg(f"Direct navigation failed. URL did not become a results page: {final_url or '?'}")
    for parametro in report.get("dropped") or []:
        etiqueta = FILTER_LABELS.get(parametro, parametro)
        print_lg(f"WARNING: LinkedIn quitó {etiqueta} al abrir los resultados.")
    for parametro in report.get("added") or []:
        etiqueta = FILTER_LABELS.get(parametro, parametro)
        print_lg(f"LinkedIn puso {etiqueta} por su cuenta; se respetará en las tarjetas.")


# ---------------------------------------------------------------------------
# Where the job cards live: every layout the bot has seen, in one place
# ---------------------------------------------------------------------------
# Each entry says how to find a card and where that card keeps its id, title,
# company, location and "already applied" state. The bot picks the first layout
# that returns elements; the last one (plain /jobs/view/ links) is the safety
# net because every design so far renders those links.
#
# Verified against live pages / logs:
#   * `occludable-job-id`: the authenticated design the bot was written for,
#     `li[data-occludable-job-id]` (also seen in the 2026-10 logs).
#   * `job-search-card`: the public results page, checked live on 2026-11-16:
#     `div.job-search-card[data-entity-urn="urn:li:jobPosting:<id>"]` with
#     `h3.base-search-card__title`, `h4.base-search-card__subtitle`,
#     `span.job-search-card__location`.
#   * `job-id`: cards that carry `data-job-id` (the attribute other LinkedIn
#     scrapers cite as the most stable hook).
#   * `view-link`: `a[href*='/jobs/view/']`, present in every dump so far, with
#     the id at the end of the slug (`...-4485334635`).
JOB_CARD_LAYOUTS = (
    {
        "name": "occludable-job-id",
        "card": "li[data-occludable-job-id], div[data-occludable-job-id]",
        "id_attrs": ("data-occludable-job-id",),
        "title": (".job-card-list__title", "a.job-card-container__link", "h3", "h4"),
        "company": (".artdeco-entity-lockup__subtitle",
                    ".job-card-container__primary-description", "h4"),
        "location": (".job-card-container__metadata-item", ".artdeco-entity-lockup__caption"),
        "state": (".job-card-container__footer-job-state",),
    },
    {
        "name": "job-search-card",
        "card": "div.job-search-card[data-entity-urn], div.job-search-card",
        "id_attrs": ("data-entity-urn",),
        "title": ("h3.base-search-card__title", ".base-search-card__title"),
        "company": ("h4.base-search-card__subtitle", ".base-search-card__subtitle"),
        "location": (".job-search-card__location", ".base-search-card__metadata"),
        "state": (".job-search-card__footer-job-state",),
    },
    {
        "name": "job-id",
        "card": "[data-job-id]",
        "id_attrs": ("data-job-id",),
        "title": (".job-card-list__title", "a[href*='/jobs/view/']", "h3", "h4"),
        "company": (".artdeco-entity-lockup__subtitle", "h4"),
        "location": (".job-card-container__metadata-item",),
        "state": (".job-card-container__footer-job-state",),
    },
    {
        "name": "view-link",
        "card": "a[href*='/jobs/view/']",
        "id_attrs": (),
        "title": (),
        "company": (),
        "location": (),
        "state": (),
    },
)

# Which layout worked for the page currently open. Re-trying all four selectors
# on every page turn costs a round trip per selector for nothing.
_ACTIVE_LAYOUT: dict = {"name": None, "design": None}

_ID_IN_URL = re.compile(r"/jobs/view/(?:[^/?#]*-)?(\d{5,})")
_ID_IN_URN = re.compile(r"urn:li:jobPosting:(\d+)")


def job_id_from_values(occludable: str | None = None, item_id: str | None = None,
                       urn: str | None = None, href: str | None = None) -> str | None:
    """The numeric job id from whichever attribute this card uses.

    Precedence: the explicit card attributes first (they describe the card
    itself), then the urn, then the detail link — `.../jobs/view/<slug>-<id>`.
    """
    for valor in (occludable, item_id):
        if valor and str(valor).strip().isdigit():
            return str(valor).strip()
    if urn:
        encontrado = _ID_IN_URN.search(str(urn))
        if encontrado:
            return encontrado.group(1)
    if href:
        encontrado = _ID_IN_URL.search(str(href))
        if encontrado:
            return encontrado.group(1)
    return None


def pick_card_layout(candidates: dict[str, int]) -> str | None:
    """First layout, in priority order, that found at least one card."""
    for layout in JOB_CARD_LAYOUTS:
        if candidates.get(layout["name"], 0) > 0:
            return layout["name"]
    return None


def layout_by_name(name: str | None) -> dict:
    for layout in JOB_CARD_LAYOUTS:
        if layout["name"] == name:
            return layout
    return JOB_CARD_LAYOUTS[0]


# Badges a card shows when the listing can be applied to without leaving
# LinkedIn. The public page did not render one, so "not found" means "unknown",
# never "not Easy Apply".
_EASY_APPLY_MARKERS = (
    "easy apply", "solicitud sencilla", "postulacion simplificada",
    "postulación simplificada", "candidatura simplificada",
)
_EXTERNAL_MARKERS = (
    "apply on company site", "apply on company website", "apply externally",
    "solicitud en el sitio de la empresa", "postularse en el sitio de la empresa",
    "candidatura no site da empresa", "apply on company site (opens in a new tab)",
)


def easy_apply_marker(card_text: str) -> str | None:
    """'easy', 'external' or None (the card does not say).

    Used only when LinkedIn dropped the Easy Apply filter from the URL: the bot
    then refuses to open a listing the card itself labels as external, instead
    of walking into it and clicking Apply blindly. Unknown cards still go
    through, because the old design never printed the badge on the card.
    """
    texto = _fold(card_text)
    if any(marca in texto for marca in _EASY_APPLY_MARKERS):
        return "easy"
    if any(marca in texto for marca in _EXTERNAL_MARKERS):
        return "external"
    return None


def work_style_is_remote(work_style: str) -> bool:
    estilo = _fold(work_style)
    return any(palabra in estilo for palabra in ("remote", "remoto", "remota", "teletrabajo"))


# ---------------------------------------------------------------------------
# Reading the results page
# ---------------------------------------------------------------------------

def _attr(element: WebElement, name: str) -> str | None:
    try:
        return element.get_dom_attribute(name)
    except Exception:
        return None


def _dedupe_cards(cards: list[WebElement]) -> list[WebElement]:
    """One element per job id; a layout may match a card and its inner link."""
    unicos: list[WebElement] = []
    vistos: set[str] = set()
    for tarjeta in cards:
        identificador = job_id_from_values(
            occludable=_attr(tarjeta, "data-occludable-job-id"),
            item_id=_attr(tarjeta, "data-job-id"),
            urn=_attr(tarjeta, "data-entity-urn"),
            href=_attr(tarjeta, "href"),
        )
        if identificador:
            if identificador in vistos:
                continue
            vistos.add(identificador)
        unicos.append(tarjeta)
    return unicos


def find_job_cards(driver, timeout: float = 15, log: bool = True) -> list[WebElement]:
    """Return the job cards on the results page, whichever layout LinkedIn used.

    Retries the known layouts until one of them finds something or `timeout`
    runs out, then returns [] so the caller can move on to the next search term
    instead of dying with a TimeoutException from a hard-coded XPath.
    """
    fin = time.monotonic() + max(0.0, float(timeout))
    while True:
        for layout in JOB_CARD_LAYOUTS:
            try:
                elementos = driver.find_elements(By.CSS_SELECTOR, layout["card"])
            except Exception:
                elementos = []
            if not elementos:
                continue
            tarjetas = _dedupe_cards(elementos)
            if tarjetas:
                if _ACTIVE_LAYOUT["name"] != layout["name"]:
                    _ACTIVE_LAYOUT["name"] = layout["name"]
                    if log:
                        print_lg(
                            f"LinkedIn search layout: {layout['name']} "
                            f"({len(tarjetas)} tarjetas, selector: {layout['card']})"
                        )
                return tarjetas
        if time.monotonic() >= fin:
            if log:
                print_lg(
                    "No job cards found with any known layout "
                    f"(tried: {', '.join(l['name'] for l in JOB_CARD_LAYOUTS)})."
                )
            return []
        buffer(0.5)


def wait_for_job_cards(driver, timeout: float = 15) -> list[WebElement]:
    """Alias with the name the search loop reads better with."""
    return find_job_cards(driver, timeout)


def current_layout_name() -> str | None:
    return _ACTIVE_LAYOUT.get("name")


def reset_layout_cache() -> None:
    _ACTIVE_LAYOUT["name"] = None
    _ACTIVE_LAYOUT["design"] = None


def _card_container(job: WebElement) -> WebElement:
    """The whole card around a /jobs/view/ link.

    For the `view-link` layout the element found *is* the anchor, so title and
    company have to be read from its ancestors. The biggest ancestor within four
    levels is the card: LinkedIn's wrappers add the company, location and state.
    """
    try:
        return driver.execute_script(
            "let el = arguments[0], best = el;"
            "for (let i = 0; i < 4 && el; i++) { el = el.parentElement; if (!el) break;"
            "  const t = (el.innerText || '').trim();"
            "  if (t.length > (best.innerText || '').length + 15) best = el; }"
            "return best;",
            job,
        )
    except Exception:
        return job


def dump_search_layout(label: str = "") -> str | None:
    """Save the DOM and a map of the /jobs/view/ links when no cards are found.

    The next silent run leaves behind `logs/linkedin_search_layout_<...>.html`
    and a JSON summary of the element chain around each job link, so the next
    fix can use the real selectors instead of guessing them.
    """
    import json
    import os
    from datetime import datetime

    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    seguro = re.sub(r"[^A-Za-z0-9_-]+", "_", str(label).strip())[:40] or "search"
    carpeta = str(logs_folder_path or "logs/")
    try:
        os.makedirs(carpeta, exist_ok=True)
    except Exception:
        pass
    js = """
    const links = Array.from(document.querySelectorAll("a[href*='/jobs/view/']")).slice(0, 8);
    return JSON.stringify({
      url: location.href,
      title: document.title,
      jobLinks: links.length,
      cards: {
        occludable: document.querySelectorAll("[data-occludable-job-id]").length,
        entityUrn: document.querySelectorAll("[data-entity-urn*='jobPosting']").length,
        jobCardClass: document.querySelectorAll(".job-search-card, .job-card-container").length,
        dataJobId: document.querySelectorAll("[data-job-id]").length,
      },
      links: links.map(a => {
        const chain = [];
        let el = a;
        for (let i = 0; i < 5 && el; i++, el = el.parentElement) {
          chain.push({
            tag: el.tagName,
            cls: String(el.className || "").slice(0, 140),
            attrs: Array.from(el.attributes)
              .filter(x => x.name.startsWith("data-") || x.name === "role")
              .map(x => x.name + "=" + String(x.value).slice(0, 70))
          });
        }
        return {href: a.href, text: (a.innerText || "").trim().slice(0, 120), chain: chain};
      })
    }, null, 2);
    """
    try:
        resumen = driver.execute_script(js)
    except Exception as e:
        print_lg(f"Could not read the page structure: {e}")
        return None
    if not resumen:
        return None
    ruta_json = os.path.join(carpeta, f"linkedin_search_layout_{seguro}_{sello}.json")
    try:
        with open(ruta_json, "w", encoding="utf-8") as fh:
            fh.write(resumen)
    except Exception as e:
        print_lg(f"Could not save the page map: {e}")
        return None
    print_lg(f"Saved a map of the results page to '{ruta_json}'.")
    return ruta_json


def set_search_location(location_str: str) -> None:
    '''
    Function to set search location.
    Location is already embedded in the URL, so this function only verifies
    and adjusts the location field if needed.
    '''
    if location_str and location_str.strip():
        print_lg(f'Search location set via URL: "{location_str.strip()}"')
        # Give page time to load with location from URL
        buffer(2)
        try:
            # Try to find the location input to verify it was set correctly
            xpaths = [
                ".//input[@aria-label='City, state, or zip code' and not(@disabled)]",
                ".//input[contains(@id, 'jobs-search-box-location')]",
                ".//input[@placeholder='City, state, or zip code']",
                ".//input[contains(@id, 'location')]"
            ]
            search_location_ele = False
            for xpath in xpaths:
                search_location_ele = try_xp(driver, xpath, False)
                if search_location_ele: break

            if search_location_ele:
                current_value = search_location_ele.get_attribute('value') or ''
                if location_str.strip().lower() not in current_value.lower():
                    # Need to update the location field
                    search_location_ele.clear()
                    sleep(0.5)
                    search_location_ele.send_keys(Keys.CONTROL + "a")
                    search_location_ele.send_keys(Keys.DELETE)
                    sleep(0.5)
                    search_location_ele.send_keys(location_str.strip())
                    sleep(2)  # Wait for autocomplete dropdown
                    # Select the first autocomplete suggestion
                    try:
                        autocomplete_option = WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'search-typeahead-v2')]//li[1] | //div[contains(@class, 'basic-typeahead')]//li[1] | //div[contains(@id, 'typeahead')]//li[1]"))
                        )
                        autocomplete_option.click()
                        print_lg("Selected location from autocomplete dropdown.")
                    except:
                        # If no autocomplete dropdown, press Down+Enter to select first suggestion
                        search_location_ele.send_keys(Keys.ARROW_DOWN)
                        sleep(0.5)
                        search_location_ele.send_keys(Keys.ENTER)
                        print_lg("Selected location with keyboard navigation.")
                    buffer(3)  # Wait for page to reload with new location
                else:
                    print_lg(f'Location already set to "{current_value}", skipping update.')
            else:
                if search_design(driver.current_url) == "search-results":
                    print_lg(
                        "The new results page has no location box: the location can only "
                        "come from the URL. If LinkedIn dropped it, this search is not "
                        "limited to the requested place."
                    )
                else:
                    print_lg("Could not find location input field, but location was set via URL.")
        except Exception as e:
            print_lg(f"Location field adjustment skipped (location set via URL): {e}")


def _find_easy_apply_switch():
    """The Easy Apply switch, in any of the shapes LinkedIn has used.

    Old filter modal: an `input[role=switch]` inside the fieldset whose heading
    is the translated label. Newer pills: a `button[role=switch]` whose
    aria-label carries the label. Returns the element, or None.
    """
    labels = ["Easy Apply", "Solicitud sencilla", "Postulacion simplificada",
              "Postulación simplificada", "Candidatura simplificada"]
    for lbl in labels:
        xpaths = [
            f'.//h3[normalize-space()="{lbl}"]/ancestor::fieldset//input[@role="switch"]',
            f'.//h3[normalize-space()="{lbl}"]/ancestor::fieldset//*[@role="switch"]',
            f'.//label[contains(normalize-space(.), "{lbl}")]//*[@role="switch"]',
            f'.//*[@role="switch" and contains(translate(@aria-label,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"{lbl.lower()}")]',
            f'.//*[@role="switch"]/ancestor::*[contains(normalize-space(.), "{lbl}")][1]//*[@role="switch"]',
        ]
        for xp in xpaths:
            try:
                return driver.find_element(By.XPATH, xp)
            except Exception:
                continue
    return None


def easy_apply_toggle_state() -> bool | None:
    """Current state of the Easy Apply switch: True/False, or None if unknown."""
    boton = _find_easy_apply_switch()
    if boton is None:
        return None
    try:
        aria = (boton.get_attribute("aria-checked") or "").lower()
        if aria in ("true", "false"):
            return aria == "true"
        return bool(boton.is_selected())
    except Exception:
        return None


def _set_easy_apply_toggle(deseado: bool) -> bool:
    '''
    Drives the Easy Apply switch to `deseado`, reading its current state first.

    Reading before clicking is what makes this safe to call in every mode. A
    blind click was wrong in both directions: it turned the filter back OFF when
    the URL had already switched it on (f_LF=f_AL), and it turned it ON from
    `easy_apply_only` even in external-only mode — which is why "external only"
    kept showing Easy Apply jobs.

    Returns True when the switch was found (and left in the wanted state).
    '''
    boton = _find_easy_apply_switch()
    if boton is None:
        return False
    try:
        aria = (boton.get_attribute("aria-checked") or "").lower()
        actual = (aria == "true") if aria in ("true", "false") else bool(boton.is_selected())
        if actual == deseado:
            print_lg(f"Easy Apply filter already {'on' if deseado else 'off'}")
            return True
        scroll_to_view(driver, boton)
        try:
            actions.move_to_element(boton).click().perform()
        except Exception:
            driver.execute_script("arguments[0].click();", boton)
        buffer(click_gap)
        # Read it back: a click that lands on the wrong element looks identical
        # to one that worked until the next page load shows the wrong listings.
        confirmado = easy_apply_toggle_state()
        print_lg(
            f"Easy Apply filter turned {'on' if deseado else 'off'}"
            + ("" if confirmado in (None, deseado) else f" (but the switch still reads {confirmado})")
        )
        return True
    except Exception:
        return False


def ensure_easy_apply_state(deseado: bool) -> bool:
    '''
    Re-asserts the Easy Apply filter by rewriting the results URL.

    The toggle is not a one-off decision: LinkedIn brings `f_LF=f_AL` back on
    its own after some navigations, and the pill can survive a page turn — which
    is how an "external only" run drifts back into showing nothing but Easy
    Apply jobs. Reading the state off the URL is language-independent, unlike
    hunting for the translated toggle, and cheap enough to run on every page.

    On the NEW `/jobs/search-results/` page the URL has no filter parameters to
    rewrite and adding them can redirect again (verified: that path goes through
    `/authwall` when logged out, and LinkedIn chooses the design). There the
    filter is enforced card by card instead, so this does nothing and returns
    False.

    Returns True when the page had to be reloaded, so the caller can wait for
    the listings again.
    '''
    global _NEW_PAGE_FILTER_NOTICE
    try:
        url = driver.current_url
    except Exception:
        return False
    if not url or "/jobs/search" not in url:
        return False
    if NEW_SEARCH_PATH in url:
        if not _NEW_PAGE_FILTER_NOTICE:
            _NEW_PAGE_FILTER_NOTICE = True
            print_lg(
                "The new results page keeps no filter in the URL: the Easy Apply "
                "filter is applied on each card, not by rewriting the address."
            )
        return False

    tiene = "f_LF=f_AL" in url
    if tiene == deseado:
        return False

    if deseado:
        nueva = url + ("&" if "?" in url else "?") + "f_LF=f_AL"
    else:
        nueva = re.sub(r'[?&]f_LF=f_AL', '', url)
        # Removing the first parameter takes the '?' with it.
        if "?" not in nueva and "&" in nueva:
            nueva = nueva.replace("&", "?", 1)

    print_lg(f"Easy Apply filter {'restored on' if deseado else 'removed from'} the results URL")
    try:
        driver.get(nueva)
        buffer(3)
        return True
    except Exception as e:
        print_lg(f"Could not rewrite the results URL: {e}")
        return False


_NEW_PAGE_FILTER_NOTICE = False


def apply_filters(location_str: str, sort_by: str, date_posted: str, pause_after_filters: bool,
                  remote_only: bool = False, easy_apply_filter: bool | None = None) -> bool:
    '''
    Function to apply job search filters.
    `remote_only` forces the "Remote" workplace filter for this one search,
    regardless of the `on_site` config — used by the worldwide remote sweep.
    `easy_apply_filter` is the state the Easy Apply switch should end up in.
    None falls back to the `easy_apply_only` config; the caller passes it
    explicitly because the application mode, not the config, decides.

    Every phase logs before it starts (`timed_step`), so a run that goes silent
    here names the step it is stuck on instead of leaving an empty gap in the
    log. The filter panel is optional: on a LinkedIn layout that does not have
    it, this returns instead of spending the whole `wait` on a missing button.
    '''
    ui_pause_check()  # honor pause/stop before starting the slow filter sequence
    with timed_step("Reading the search location", slow_after=5, heartbeat=30):
        set_search_location(location_str)

    try:
        recommended_wait = 1 if click_gap < 1 else 0

        _all_filters_xp = (
            '//button['
            'normalize-space()="All filters" or '
            'normalize-space()="Todos los filtros" or '
            'normalize-space()="Alle Filter" or '
            'contains(@class,"search-reusables__all-filters-pill-button")]'
        )
        with timed_step("Opening the filters panel", slow_after=4, heartbeat=30):
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, _all_filters_xp))
                ).click()
            except Exception:
                print_lg(
                    "Filters panel not found on this LinkedIn layout — the filters "
                    "already in the URL are the only ones that will apply."
                )
                return pause_after_filters
            buffer(recommended_wait)

        _FILTER_SPAN_ES = {
            "Most recent":    "Más reciente",
            "Most relevant":  "Más relevante",
            "Any time":       "Cualquier momento",
            "Past month":     "Mes pasado",
            "Past week":      "Semana pasada",
            "Past 24 hours":  "Últimas 24 horas",
        }
        def _click_filter_span(text):
            if not wait_span_click(driver, text):
                _es = _FILTER_SPAN_ES.get(text)
                if _es:
                    wait_span_click(driver, _es)
        with timed_step("Setting sort order and date posted", slow_after=8, heartbeat=30):
            _click_filter_span(sort_by)
            _click_filter_span(date_posted)
            buffer(recommended_wait)

        with timed_step("Ticking experience level and companies", slow_after=8, heartbeat=30):
            multi_sel_noWait(driver, experience_level)
            multi_sel_noWait(driver, companies, actions)
            if experience_level or companies: buffer(recommended_wait)

        with timed_step("Ticking job type and workplace", slow_after=8, heartbeat=30):
            multi_sel_noWait(driver, job_type)
            # On a remote sweep the URL already carries f_WT=2, so the modal opens
            # with Remote ticked. Clicking it here would toggle it back OFF — hence
            # the workplace options are left alone in that case.
            if not remote_only:
                multi_sel_noWait(driver, on_site)
            if job_type or (on_site and not remote_only): buffer(recommended_wait)

        with timed_step("Setting the Easy Apply filter", slow_after=4, heartbeat=30):
            _ea_deseado = easy_apply_only if easy_apply_filter is None else bool(easy_apply_filter)
            if is_career_ops_mode():
                _ea_deseado = False
            if not _set_easy_apply_toggle(_ea_deseado):
                print_lg(
                    "Easy Apply filter toggle not found (tried EN/ES labels and both "
                    "switch shapes). The URL filter and the per-card check still apply."
                )

        with timed_step("Ticking location, industry, function and titles", slow_after=8, heartbeat=30):
            multi_sel_noWait(driver, location)
            multi_sel_noWait(driver, industry)
            if location or industry: buffer(recommended_wait)
            multi_sel_noWait(driver, job_function)
            multi_sel_noWait(driver, job_titles)
            if job_function or job_titles: buffer(recommended_wait)

        with timed_step("Ticking the remaining filter pills", slow_after=8, heartbeat=30):
            if under_10_applicants: boolean_button_click(driver, actions, "Under 10 applicants")
            if in_your_network: boolean_button_click(driver, actions, "In your network")
            if fair_chance_employer: boolean_button_click(driver, actions, "Fair Chance Employer")

            wait_span_click(driver, salary)
            buffer(recommended_wait)

            multi_sel_noWait(driver, benefits)
            multi_sel_noWait(driver, commitments)
            if benefits or commitments: buffer(recommended_wait)

        with timed_step("Pressing 'Show results'", slow_after=4, heartbeat=30):
            try:
                _show_xp = (
                    '//button['
                    'contains(translate(@aria-label,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"apply current filters to show") or '
                    'contains(translate(@aria-label,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"aplicar") or '
                    'contains(translate(@aria-label,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"mostrar") or '
                    'contains(@class,"search-reusables__secondary-filters-show-results-button")]'
                )
                show_results_button: WebElement = driver.find_element(By.XPATH, _show_xp)
                try:
                    show_results_button.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", show_results_button)
            except Exception:
                print_lg("Show results button not found — filters may already be applied.")

        if pause_after_filters:
            # A modal dialog that writes nothing looks exactly like a hang — the
            # 19:46 silence may have been this dialog waiting for a click.
            print_lg("Waiting for you to confirm the results in the control window (pause after search is ON).")
            if "Turn off Pause after search" == ui_confirm("Please check your results", "These are your configured search results and filter. It is safe to change them while this dialog is open, any changes later could result in errors and skipping this search run.", ["Turn off Pause after search", "Look's good, Continue"]):
                pause_after_filters = False
    except Exception as e:
        print_lg(f"Setting the preferences failed: {e}")
        # Continue silently — filters may be partially applied, bot will proceed

    return pause_after_filters



def get_page_info() -> tuple[WebElement | None, int | None]:
    '''
    Function to get pagination element and current page number.

    Returns (None, None) on the layouts that page differently (or load more on
    scroll). That is logged once as informational, not as an error: the caller
    asks `go_to_next_page()` what to do next.
    '''
    try:
        pagination_element = try_find_by_classes(driver, [
            "jobs-search-pagination__pages",
            "jobs-search-results-list__pagination",
            "artdeco-pagination",
            "artdeco-pagination__pages",
        ])
        scroll_to_view(driver, pagination_element)
        current_page = int(pagination_element.find_element(By.XPATH, "//button[contains(@class, 'active')]").text)
        return pagination_element, current_page
    except Exception:
        return None, None


def go_to_next_page(pagination_element: WebElement | None, current_page: int | None) -> bool:
    """Open the next results page. Returns False at the end of the results.

    Two designs: numbered pages (click "Page N+1") and a "Next" button. The new
    page may also load more cards on scroll; when neither control exists this
    returns False and the search term is done, which is what a page turn at the
    end of the list means anyway.
    """
    if pagination_element is not None and current_page:
        siguiente = current_page + 1
        xpaths = [
            f"//button[@aria-label='Page {siguiente}']",
            f"//button[@aria-label='Página {siguiente}']",
            f"//button[@aria-label='Página {siguiente}']",
            f"//button[normalize-space()='{siguiente}']",
        ]
        for xp in xpaths:
            try:
                pagination_element.find_element(By.XPATH, xp).click()
                print_lg(f"\n>-> Now on Page {siguiente} \n")
                buffer(2)
                return True
            except Exception:
                continue
        print_lg(f"\n>-> Didn't find Page {siguiente}. Probably at the end page of results!\n")
        return False

    # Exact labels only: a bare "contains(next)" also matches the arrows of
    # unrelated carousels on the same page and would click one of those.
    etiquetas = ("Next", "Next page", "Siguiente", "Página siguiente", "Suivant")
    for etiqueta in etiquetas:
        literales = [f"'{etiqueta}'"]
        xp = (
            "//button[@aria-label=" + literales[0] + " or @aria-label=" + literales[0].lower() + "]"
            " | //a[@aria-label=" + literales[0] + " or @aria-label=" + literales[0].lower() + "]"
            " | //button[normalize-space()=" + literales[0] + "]"
            " | //a[normalize-space()=" + literales[0] + "]"
        )
        try:
            cand = driver.find_element(By.XPATH, xp)
        except Exception:
            continue
        try:
            if not cand.is_displayed() or cand.get_attribute("disabled"):
                continue
            try:
                cand.click()
            except Exception:
                driver.execute_script("arguments[0].click();", cand)
            print_lg("\n>-> Moving to the next page of results\n")
            buffer(2)
            return True
        except Exception:
            continue

    print_lg("No pagination control on this layout; this search term is done.")
    return False



# The card footer LinkedIn shows once you have applied, in the interface
# languages people actually run it in. Comparing against the English word
# alone meant a Spanish LinkedIn never recognised a job as already applied to.
_APPLIED_STATES = ('applied', 'solicitado', 'solicitada', 'postulado', 'postulada',
                   'aplicado', 'aplicada', 'candidatura enviada', 'candidatado',
                   'candidatura', 'beworben', 'postule', 'candidature envoyee')


def is_applied_state(footer_text: str) -> bool:
    '''True if a job card's footer says you already applied ("Applied", "Solicitado", ...).'''
    texto = _fold(footer_text).strip()
    return any(texto == e or texto.startswith(e + ' ') for e in _APPLIED_STATES)


def _first_text(element: WebElement, selectors) -> str:
    """Text of the first selector that finds something, else ''."""
    for selector in selectors or ():
        try:
            encontrado = element.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        try:
            texto = (encontrado.text or "").strip()
        except Exception:
            texto = ""
        if not texto:
            try:
                texto = (encontrado.get_attribute("aria-label") or "").strip()
            except Exception:
                texto = ""
        if texto:
            return texto
    return ""


def _card_lines(card: WebElement) -> list[str]:
    try:
        return [linea.strip() for linea in (card.text or "").splitlines() if linea.strip()]
    except Exception:
        return []


def card_apply_marker(job: WebElement) -> str | None:
    """Whether this card says it is Easy Apply, external, or does not say.

    Only used when LinkedIn dropped the Easy Apply filter from the URL. The old
    design never printed the badge, so None (unknown) still gets opened and the
    apply button decides; a card that explicitly says "Apply on company site"
    is skipped before wasting a click.
    """
    try:
        tarjeta = _card_container(job) if current_layout_name() == "view-link" else job
        return easy_apply_marker((tarjeta.text or "") + "\n" + ("\n".join(_card_lines(tarjeta))))
    except Exception:
        return None


def get_job_main_details(job: WebElement, blacklisted_companies: set, rejected_jobs: set) -> tuple[str, str, str, str, str, bool]:
    '''
    # Function to get job main details.
    Returns a tuple of (job_id, title, company, work_location, work_style, skip)
    * job_id: Job ID
    * title: Job title
    * company: Company name
    * work_location: Work location of this job
    * work_style: Work style of this job (Remote, On-site, Hybrid)
    * skip: A boolean flag to skip this job

    Reads whichever card design is on screen (see JOB_CARD_LAYOUTS): the id from
    the card's own data-* attribute when it has one, otherwise from the
    `/jobs/view/<slug>-<id>` link. Title and company come from the layout's
    selectors, then from the link text, then from the card's own lines.
    '''
    skip = False
    job_details_button = None
    job_es_enlace = False
    layout = layout_by_name(current_layout_name())

    # The results list is "occludable": LinkedIn leaves a card empty until it
    # has been scrolled into view, and only then renders its <a>. Looking for
    # the link straight away skipped every card below the fold — usually most
    # of the page. So the card is scrolled to first and given a moment.
    for _intento in range(4):
        try:
            job_details_button = job.find_element(By.CSS_SELECTOR, "a[href*='/jobs/view/']")
            break
        except StaleElementReferenceException:
            raise  # the card is gone for good; waiting will not bring it back
        except Exception:
            scroll_to_view(driver, job)
            sleep(0.75)

    if job_details_button is None:
        # The `view-link` layout hands us the anchor itself; find_element looks
        # only at descendants, so the element has to be checked too.
        try:
            href_propio = job.get_attribute("href") or ""
        except Exception:
            href_propio = ""
        if "/jobs/view/" in href_propio:
            job_details_button = job
            job_es_enlace = True
        else:
            job_id = job_id_from_values(
                occludable=_attr(job, "data-occludable-job-id"),
                item_id=_attr(job, "data-job-id"),
                urn=_attr(job, "data-entity-urn"),
            ) or "unknown"
            print_lg(f'Skipping job ID {job_id}: listing never rendered its link (DOM recycled by LinkedIn).')
            return (job_id, 'Unknown', 'Unknown', 'Unknown', 'Unknown', True)

    card = _card_container(job) if job_es_enlace else job
    scroll_to_view(driver, job_details_button, True)

    try:
        href = job_details_button.get_attribute("href") or ""
    except Exception:
        href = ""
    job_id = job_id_from_values(
        occludable=_attr(card, "data-occludable-job-id") or _attr(job, "data-occludable-job-id"),
        item_id=_attr(card, "data-job-id") or _attr(job, "data-job-id"),
        urn=_attr(card, "data-entity-urn") or _attr(job, "data-entity-urn"),
        href=href,
    ) or "unknown"

    title = _first_text(card, layout["title"])
    if not title:
        try:
            title = (job_details_button.text or "").strip()
        except Exception:
            title = ""
    if not title:
        try:
            title = (job_details_button.get_attribute("aria-label") or "").strip()
        except Exception:
            title = ""
    lineas = _card_lines(card)
    if not title and lineas:
        title = lineas[0]
    # A card link's text can contain the title twice (visible + sr-only) or the
    # company on a second line; the first line is the title everywhere.
    title = title.split("\n", 1)[0].strip() or "Unknown"

    other_details = _first_text(card, layout["company"])
    work_location = _first_text(card, layout["location"]) or "Unknown"
    details_split = other_details.split(' · ') if other_details else []
    company = details_split[0].strip() if details_split and details_split[0].strip() else "Unknown"
    if work_location == "Unknown" and len(details_split) > 1:
        work_location = details_split[1].strip()

    if company == "Unknown" and lineas:
        # No selector matched: the first line that is not the title is the
        # company on every layout seen so far (title, company, location...).
        resto = [l for l in lineas if l != title and not is_applied_state(l)]
        if resto:
            company = resto[0]
    if work_location == "Unknown" and lineas:
        resto = [l for l in lineas if l not in (title, company) and not is_applied_state(l)]
        work_location = resto[0] if resto else "Unknown"

    # Improved work style extraction
    work_style = "On-site"  # Default
    if "(" in work_location and ")" in work_location:
        work_style = work_location[work_location.rfind('(')+1:work_location.rfind(')')]
        work_location = work_location[:work_location.rfind('(')].strip()
    elif len(details_split) > 2:
        work_style = details_split[2]

    # Skip if previously rejected due to blacklist or already applied
    if company in blacklisted_companies:
        print_lg(f'Skipping "{title} | {company}" job (Blacklisted Company). Job ID: {job_id}!')
        skip = True
    elif job_id in rejected_jobs:
        print_lg(f'Skipping previously rejected "{title} | {company}" job. Job ID: {job_id}!')
        skip = True
    if not skip:
        # The state element is the old design's footer; the text scan covers
        # cards that print "Solicitado" somewhere else in the card.
        estado = _first_text(card, layout["state"])
        aplicado = is_applied_state(estado) if estado else False
        if not aplicado:
            aplicado = any(is_applied_state(linea) for linea in lineas)
        if aplicado:
            skip = True
            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')

    try:
        if not skip:
            try:
                job_details_button.click()
            except ElementClickInterceptedException:
                print_lg(f'Click intercepted for "{title}". Attempting to dismiss modals and force click.')
                actions.send_keys(Keys.ESCAPE).perform()
                buffer(1)
                driver.execute_script("arguments[0].click();", job_details_button)
    except Exception as e:
        print_lg(f'Failed to click "{title} | {company}" job on details button. Job ID: {job_id}!')
        # print_lg(e)
        discard_job()
        driver.execute_script("arguments[0].click();", job_details_button) # To pass the error outside if it still fails
    buffer(click_gap)
    return (job_id,title,company,work_location,work_style,skip)


# Function to check for Blacklisted words in About Company
def check_blacklist(rejected_jobs: set, job_id: str, company: str, blacklisted_companies: set) -> tuple[set, set, WebElement] | ValueError:
    jobs_top_card = try_find_by_classes(driver, ["job-details-jobs-unified-top-card__primary-description-container","job-details-jobs-unified-top-card__primary-description","jobs-unified-top-card__primary-description","jobs-details__main-content"])
    about_company_org = find_by_class(driver, "jobs-company__box")
    scroll_to_view(driver, about_company_org)
    about_company_org = about_company_org.text
    about_company = about_company_org.lower()
    skip_checking = False
    for word in about_company_good_words:
        if word.lower() in about_company:
            print_lg(f'Found the word "{word}". So, skipped checking for blacklist words.')
            skip_checking = True
            break
    if not skip_checking:
        for word in about_company_bad_words:
            if word.lower() in about_company:
                rejected_jobs.add(job_id)
                blacklisted_companies.add(company)
                raise ValueError(f'\n"{about_company_org}"\n\nContains "{word}".')
    buffer(click_gap)
    scroll_to_view(driver, jobs_top_card)
    return rejected_jobs, blacklisted_companies, jobs_top_card



# A "N years" that is not about the candidate's experience: the company's age,
# a contract length, or a wish-list item. Taking the largest number in the
# whole description used to turn "we have been in business for 10 years" into
# "10 years of experience required" and silently drop the job.
_EXPERIENCE_WORDS = re.compile(r'experien|\bexp\b|background|track record|hands[- ]on|working (?:with|in|as|on)', re.IGNORECASE)
_NOT_REQUIRED_WORDS = re.compile(
    r'prefer|nice[- ]to[- ]have|a plus|bonus|ideally|desirable|desired|advantage|'
    r'\bwe have\b|\bwe\'ve\b|for over|founded|in business|history|\bago\b|'
    r'contract|deseable|valorable|preferible|preferentemente|se valora|un plus|'
    r'fundad|trayectoria de|\bhace\b|contrato', re.IGNORECASE)


def extract_years_of_experience(text: str) -> int:
    '''
    Years of experience the posting REQUIRES, or 0 if it does not say.

    Only a "N years" that sits next to the word experience (or similar) counts,
    and not when the same sentence marks it as preferred or is talking about the
    company. Of what is left, the largest figure wins, as before.
    '''
    requeridos = []
    for oracion in re.split(r'(?<=[.;!?\n])\s*|\s+[•·]\s+', text or ""):
        if not oracion.strip():
            continue
        for match in re.finditer(re_experience, oracion):
            years = int(match.group(1))
            if years > 12:
                continue
            # The words right after "N years" ("of experience in ...") or right
            # before it ("Experience: 3+ years") are what make it a requirement.
            cerca = oracion[max(0, match.start() - 40): match.end() + 60]
            if not _EXPERIENCE_WORDS.search(cerca):
                continue
            if _NOT_REQUIRED_WORDS.search(oracion):
                continue
            requeridos.append(years)
    if not requeridos:
        print_lg("Couldn't find a required years-of-experience in About the Job.")
        return 0
    return max(requeridos)



def get_job_description(
) -> tuple[
    str | Literal['Unknown'],
    int | Literal['Unknown'],
    bool,
    str | None,
    str | None
    ]:
    '''
    # Job Description
    Function to extract job description from About the Job.
    ### Returns:
    - `jobDescription: str | 'Unknown'`
    - `experience_required: int | 'Unknown'`
    - `skip: bool`
    - `skipReason: str | None`
    - `skipMessage: str | None`
    '''
    try:
        ##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
        jobDescription = "Unknown"
        ##<
        experience_required = "Unknown"
        found_masters = 0
        # Set before anything can fail: the except below returns them, and when
        # the description itself could not be found they were never assigned,
        # so the "fallback" raised UnboundLocalError instead.
        skip = False
        skipReason = None
        skipMessage = None
        jobDescription = find_by_class(driver, "jobs-box__html-content").text
        jobDescriptionLow = jobDescription.lower()
        for word in bad_words:
            if _contains_term(jobDescriptionLow, word):
                skipMessage = f'\n{jobDescription}\n\nContains bad word "{word}". Skipping this job!\n'
                skipReason = "Found a Bad Word in About Job"
                skip = True
                break
        if not skip and security_clearance == False:
            _hit = next((p for p in _CLEARANCE_PHRASES if p in jobDescriptionLow), None)
            if _hit:
                skipMessage = f'\n{jobDescription}\n\nFound "{_hit}". Skipping this job!\n'
                skipReason = "Asking for Security clearance"
                skip = True
        if not skip and disability_status == "No":
            disability_exclusive_phrases = [
                'vaga exclusiva para pcd', 'vaga exclusiva pcd', 'exclusiva para pessoas com deficiencia',
                'exclusiva para pcd', 'vagas pcd', 'vaga pcd', 'candidatos pcd', 'candidato pcd',
                'exclusive for people with disabilities', 'exclusively for disabled', 'only for disabled',
                'exclusive disability', 'persons with disabilities only', 'people with disabilities only',
                'exclusiva para personas con discapacidad', 'solo para personas con discapacidad',
                'exclusivo para discapacitados', 'vaga para deficiente', 'vagas para deficientes',
                'this role is exclusively', 'this position is exclusively for candidates with disab',
                'open only to candidates with disab',
            ]
            if any(phrase in jobDescriptionLow for phrase in disability_exclusive_phrases):
                skipMessage = f'\n{jobDescription}\n\nJob is exclusive for people with disabilities. Skipping!\n'
                skipReason = "Disability-exclusive job"
                skip = True
        if not skip:
            if did_masters and 'master' in jobDescriptionLow:
                print_lg(f'Found the word "master" in \n{jobDescription}')
                found_masters = 2
            experience_required = extract_years_of_experience(jobDescription)
            # Postings ask for the ceiling of a range and settle for less, so
            # allow `experience_tolerance` years of stretch before skipping.
            _ceiling = current_experience + found_masters + max(0, experience_tolerance)
            if current_experience > -1 and experience_required > _ceiling:
                skipMessage = f'\n{jobDescription}\n\nExperience required {experience_required} > {_ceiling} (your {current_experience} + {found_masters} masters + {max(0, experience_tolerance)} tolerance). Skipping this job!\n'
                skipReason = "Required experience is high"
                skip = True
    except Exception as e:
        if jobDescription == "Unknown":    print_lg("Unable to extract job description!")
        else:
            experience_required = "Error in extraction"
            print_lg("Unable to extract years of experience required!")
            # print_lg(e)
    return jobDescription, experience_required, skip, skipReason, skipMessage
