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


re_experience = re.compile(r'[(]?\s*(\d+)\s*[)]?\s*[-to]*\s*\d*[+]*\s*year[s]?', re.IGNORECASE)


def is_job_relevant(title: str, work_style: str) -> bool:
    '''
    Returns True if the job title matches the user's configured job focus.
    - Primary keywords: always allowed.
    - Secondary keywords: only allowed if work_style is Remote or Hybrid.
    - If enable_job_focus_filter is False, always returns True.
    '''
    try:
        if not enable_job_focus_filter:
            return True
        title_low = title.lower()
        # Check primary focus (always relevant)
        for kw in primary_focus_keywords:
            if kw.lower() in title_low:
                return True
        # Check secondary focus (only if Remote or Hybrid — EN and ES)
        style_low = work_style.lower() if work_style else ""
        if any(s in style_low for s in ["remote", "hybrid", "remoto", "híbrido", "hibrido"]):
            for kw in secondary_focus_keywords:
                if kw.lower() in title_low:
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


def apply_filters(location_str: str, sort_by: str, date_posted: str, pause_after_filters: bool) -> bool:
    '''
    Function to apply job search filters
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
        multi_sel_noWait(driver, on_site)
        if job_type or on_site: buffer(recommended_wait)

        if easy_apply_only and not is_career_ops_mode():
            _ea_clicked = False
            for _ea_lbl in ["Easy Apply", "Solicitud sencilla", "Postulacion simplificada", "Postulación simplificada"]:
                try:
                    _fc  = driver.find_element(By.XPATH, f'.//h3[normalize-space()="{_ea_lbl}"]/ancestor::fieldset')
                    _btn = _fc.find_element(By.XPATH, './/input[@role="switch"]')
                    scroll_to_view(driver, _btn)
                    actions.move_to_element(_btn).click().perform()
                    buffer(click_gap)
                    _ea_clicked = True
                    break
                except Exception:
                    continue
            if not _ea_clicked:
                print_lg("Easy Apply filter toggle not found (tried EN/ES labels)")

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
            if word.lower() in jobDescriptionLow:
                skipMessage = f'\n{jobDescription}\n\nContains bad word "{word}". Skipping this job!\n'
                skipReason = "Found a Bad Word in About Job"
                skip = True
                break
        if not skip and security_clearance == False and ('polygraph' in jobDescriptionLow or 'clearance' in jobDescriptionLow or 'secret' in jobDescriptionLow):
            skipMessage = f'\n{jobDescription}\n\nFound "Clearance" or "Polygraph". Skipping this job!\n'
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
            if current_experience > -1 and experience_required > current_experience + found_masters:
                skipMessage = f'\n{jobDescription}\n\nExperience required {experience_required} > Current Experience {current_experience + found_masters}. Skipping this job!\n'
                skipReason = "Required experience is high"
                skip = True
    except Exception as e:
        if jobDescription == "Unknown":    print_lg("Unable to extract job description!")
        else:
            experience_required = "Error in extraction"
            print_lg("Unable to extract years of experience required!")
            # print_lg(e)
    return jobDescription, experience_required, skip, skipReason, skipMessage
