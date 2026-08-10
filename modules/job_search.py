import re
from typing import Literal
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import ElementClickInterceptedException
from modules.open_chrome import driver, wait, actions
from modules.helpers import print_lg, buffer, sleep, critical_error_log
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


re_experience = re.compile(r'[(]?\s*(\d+)\s*[)]?\s*[-to]*\s*\d*[+]*\s*year[s]?', re.IGNORECASE)

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
    r'residents? of\b[^.\n;]{0,90}',
    r'(?:debes?|deben|debera[s]?) (?:residir|vivir|estar (?:ubicad|radicad)[oa]s?)\b[^.\n;]{0,90}',
    r'(?:residir|radicad[oa]s?|ubicad[oa]s?) en\b[^.\n;]{0,90}',
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
                print_lg("Could not find location input field, but location was set via URL.")
        except Exception as e:
            print_lg(f"Location field adjustment skipped (location set via URL): {e}")


def _set_easy_apply_toggle(deseado: bool) -> None:
    '''
    Drives the Easy Apply switch to `deseado`, reading its current state first.

    Reading before clicking is what makes this safe to call in every mode. A
    blind click was wrong in both directions: it turned the filter back OFF when
    the URL had already switched it on (f_LF=f_AL), and it turned it ON from
    `easy_apply_only` even in external-only mode — which is why "external only"
    kept showing Easy Apply jobs.
    '''
    for lbl in ["Easy Apply", "Solicitud sencilla", "Postulacion simplificada", "Postulación simplificada"]:
        try:
            _fc = driver.find_element(By.XPATH, f'.//h3[normalize-space()="{lbl}"]/ancestor::fieldset')
            _btn = _fc.find_element(By.XPATH, './/input[@role="switch"]')
            _aria = (_btn.get_attribute("aria-checked") or "").lower()
            actual = (_aria == "true") if _aria in ("true", "false") else _btn.is_selected()
            if actual == deseado:
                print_lg(f"Easy Apply filter already {'on' if deseado else 'off'}")
                return
            scroll_to_view(driver, _btn)
            actions.move_to_element(_btn).click().perform()
            buffer(click_gap)
            print_lg(f"Easy Apply filter turned {'on' if deseado else 'off'}")
            return
        except Exception:
            continue
    print_lg("Easy Apply filter toggle not found (tried EN/ES labels)")


def ensure_easy_apply_state(deseado: bool) -> bool:
    '''
    Re-asserts the Easy Apply filter by rewriting the results URL.

    The toggle is not a one-off decision: LinkedIn brings `f_LF=f_AL` back on
    its own after some navigations, and the pill can survive a page turn — which
    is how an "external only" run drifts back into showing nothing but Easy
    Apply jobs. Reading the state off the URL is language-independent, unlike
    hunting for the translated toggle, and cheap enough to run on every page.

    Returns True when the page had to be reloaded, so the caller can wait for
    the listings again.
    '''
    try:
        url = driver.current_url
    except Exception:
        return False
    if not url or "/jobs/search" not in url:
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


def apply_filters(location_str: str, sort_by: str, date_posted: str, pause_after_filters: bool,
                  remote_only: bool = False, easy_apply_filter: bool | None = None) -> bool:
    '''
    Function to apply job search filters.
    `remote_only` forces the "Remote" workplace filter for this one search,
    regardless of the `on_site` config — used by the worldwide remote sweep.
    `easy_apply_filter` is the state the Easy Apply switch should end up in.
    None falls back to the `easy_apply_only` config; the caller passes it
    explicitly because the application mode, not the config, decides.
    '''
    ui_pause_check()  # honor pause/stop before starting the slow filter sequence
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
        wait.until(EC.presence_of_element_located((By.XPATH, _all_filters_xp))).click()
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
        _click_filter_span(sort_by)
        _click_filter_span(date_posted)
        buffer(recommended_wait)

        multi_sel_noWait(driver, experience_level)
        multi_sel_noWait(driver, companies, actions)
        if experience_level or companies: buffer(recommended_wait)

        multi_sel_noWait(driver, job_type)
        # On a remote sweep the URL already carries f_WT=2, so the modal opens
        # with Remote ticked. Clicking it here would toggle it back OFF — hence
        # the workplace options are left alone in that case.
        if not remote_only:
            multi_sel_noWait(driver, on_site)
        if job_type or (on_site and not remote_only): buffer(recommended_wait)

        _ea_deseado = easy_apply_only if easy_apply_filter is None else bool(easy_apply_filter)
        if is_career_ops_mode():
            _ea_deseado = False
        _set_easy_apply_toggle(_ea_deseado)

        multi_sel_noWait(driver, location)
        multi_sel_noWait(driver, industry)
        if location or industry: buffer(recommended_wait)

        multi_sel_noWait(driver, job_function)
        multi_sel_noWait(driver, job_titles)
        if job_function or job_titles: buffer(recommended_wait)

        if under_10_applicants: boolean_button_click(driver, actions, "Under 10 applicants")
        if in_your_network: boolean_button_click(driver, actions, "In your network")
        if fair_chance_employer: boolean_button_click(driver, actions, "Fair Chance Employer")

        wait_span_click(driver, salary)
        buffer(recommended_wait)

        multi_sel_noWait(driver, benefits)
        multi_sel_noWait(driver, commitments)
        if benefits or commitments: buffer(recommended_wait)

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

        if pause_after_filters and "Turn off Pause after search" == ui_confirm("Please check your results", "These are your configured search results and filter. It is safe to change them while this dialog is open, any changes later could result in errors and skipping this search run.", ["Turn off Pause after search", "Look's good, Continue"]):
            pause_after_filters = False

    except Exception as e:
        print_lg(f"Setting the preferences failed: {e}")
        # Continue silently — filters may be partially applied, bot will proceed

    return pause_after_filters



def get_page_info() -> tuple[WebElement | None, int | None]:
    '''
    Function to get pagination element and current page number
    '''
    try:
        pagination_element = try_find_by_classes(driver, ["jobs-search-pagination__pages", "artdeco-pagination", "artdeco-pagination__pages"])
        scroll_to_view(driver, pagination_element)
        current_page = int(pagination_element.find_element(By.XPATH, "//button[contains(@class, 'active')]").text)
    except Exception as e:
        print_lg("Failed to find Pagination element, hence couldn't scroll till end!")
        pagination_element = None
        current_page = None
        print_lg(e)
    return pagination_element, current_page



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
    '''
    skip = False
    try:
        job_details_button = job.find_element(By.TAG_NAME, 'a')
    except Exception:
        # LinkedIn sometimes occludes/recycles DOM elements; the <a> tag may
        # disappear from a listing that is still in the list. Skip safely.
        job_id = job.get_dom_attribute('data-occludable-job-id') or 'unknown'
        print_lg(f'Skipping job ID {job_id}: listing element has no <a> tag (DOM recycled by LinkedIn).')
        return (job_id, 'Unknown', 'Unknown', 'Unknown', 'Unknown', True)
    scroll_to_view(driver, job_details_button, True)
    job_id = job.get_dom_attribute('data-occludable-job-id')
    title = job_details_button.text
    title = title[:title.find("\n")]
    # company = job.find_element(By.CLASS_NAME, "job-card-container__primary-description").text
    # work_location = job.find_element(By.CLASS_NAME, "job-card-container__metadata-item").text
    other_details = job.find_element(By.CLASS_NAME, 'artdeco-entity-lockup__subtitle').text
    details_split = other_details.split(' · ')
    company = details_split[0]
    work_location = details_split[1] if len(details_split) > 1 else "Unknown"

    # Improved work style extraction
    work_style = "On-site" # Default
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
    try:
        if job.find_element(By.CLASS_NAME, "job-card-container__footer-job-state").text == "Applied":
            skip = True
            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
    except: pass
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



# Function to extract years of experience required from About Job
def extract_years_of_experience(text: str) -> int:
    # Extract all patterns like '10+ years', '5 years', '3-5 years', etc.
    matches = re.findall(re_experience, text)
    if len(matches) == 0:
        print_lg(f'\n{text}\n\nCouldn\'t find experience requirement in About the Job!')
        return 0
    return max([int(match) for match in matches if int(match) <= 12])



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
        jobDescription = find_by_class(driver, "jobs-box__html-content").text
        jobDescriptionLow = jobDescription.lower()
        skip = False
        skipReason = None
        skipMessage = None
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
