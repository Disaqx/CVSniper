# Imports
import os
import sys

# Ensure the project root is always in sys.path regardless of how Python is invoked
# (needed when using embedded Python where cwd != sys.path[0])
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import csv
import re
import time
import shutil
import pyautogui
from urllib.parse import quote

# ── Auto-copy config templates if personal config files are missing ──────────
_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
for _cfg_name in ["personals", "secrets", "questions", "resume", "search", "settings"]:
    _real = os.path.join(_CONFIG_DIR, f"{_cfg_name}.py")
    _tmpl = os.path.join(_CONFIG_DIR, f"{_cfg_name}.default.py")
    if not os.path.exists(_real) and os.path.exists(_tmpl):
        shutil.copy(_tmpl, _real)
        print(f"[Setup] Created {_cfg_name}.py from template. Please fill in your data.")

# Set CSV field size limit to prevent field size errors
csv.field_size_limit(1000000)  # Set to 1MB instead of default 131KB

from random import choice, shuffle, randint
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.select import Select
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, NoSuchWindowException, ElementNotInteractableException, WebDriverException

from config.personals import *
from config.questions import *
from config.search import *
from config.secrets import use_AI, username, password, ai_provider
from config.settings import *

from modules.open_chrome import *
from modules.helpers import *
from modules.clickers_and_finders import *
from modules.validator import validate_config
from modules.bot_ui import ui_start, ui_update_status, ui_alert, ui_confirm, ui_pause_check, is_career_ops_mode, ui_enforce_configuration

if use_AI:
    from modules.ai.openaiConnections import ai_create_openai_client, ai_extract_skills, ai_answer_question, ai_evaluate_job, ai_close_openai_client
    from modules.ai.deepseekConnections import deepseek_create_client, deepseek_extract_skills, deepseek_answer_question, deepseek_evaluate_job
    from modules.ai.geminiConnections import gemini_create_client, gemini_extract_skills, gemini_answer_question, gemini_evaluate_job

from typing import Literal
from modules.ai.qa_database import save_to_qa_database


pyautogui.FAILSAFE = False
# Start the Controller UI (driver is ready after open_chrome import)
ui_start(driver)
ui_enforce_configuration()

# ── Flask dashboard starts in background (opens only when user clicks the button) ──
from modules.bot_ui import start_flask_dashboard, open_dashboard_in_browser, FLASK_URL
start_flask_dashboard()

ui_update_status("Initializing", "Starting CVSniper...")
# if use_resume_generator:    from resume_generator import is_logged_in_GPT, login_GPT, open_resume_chat, create_custom_resume


#< Global Variables and logics

if run_in_background == True:
    pause_at_failed_question = False
    pause_before_submit = False
    run_non_stop = False

first_name = first_name.strip()
middle_name = middle_name.strip()
last_name = last_name.strip()
full_name = first_name + " " + middle_name + " " + last_name if middle_name else first_name + " " + last_name

useNewResume = True
randomly_answered_questions = set()

tabs_count = 1
easy_applied_count = 0
external_jobs_count = 0
failed_count = 0
skip_count = 0
dailyEasyApplyLimitReached = False

re_experience = re.compile(r'[(]?\s*(\d+)\s*[)]?\s*[-to]*\s*\d*[+]*\s*year[s]?', re.IGNORECASE)

desired_salary_lakhs = str(round(desired_salary / 100000, 2))
desired_salary_monthly = str(round(desired_salary/12, 2))
desired_salary = str(desired_salary)

current_ctc_lakhs = str(round(current_ctc / 100000, 2))
current_ctc_monthly = str(round(current_ctc/12, 2))
current_ctc = str(current_ctc)

notice_period_months = str(notice_period//30)
notice_period_weeks = str(notice_period//7)
notice_period = str(notice_period)

aiClient = None
##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
about_company_for_ai = None # TODO extract about company for AI
##<

class CareerOpsActivatedException(Exception):
    pass

#>

top_manual_jobs = []

def add_to_manual_jobs(job_id, title, company, score, reason, link=None):
    global top_manual_jobs
    job_link = link if link else f"https://www.linkedin.com/jobs/view/{job_id}"
    if not any(j['link'] == job_link for j in top_manual_jobs):
        top_manual_jobs.append({
            'job_id': job_id,
            'title': title,
            'company': company,
            'link': job_link,
            'score': score,
            'reason': reason
        })


def check_and_prompt_career_ops() -> bool:
    '''
    Checks if top_manual_jobs has 5 or more jobs, and prompts the user.
    Returns True if we should continue searching, False if we should stop.
    '''
    global top_manual_jobs
    if len(top_manual_jobs) >= 5:
        # Ask the user: "¿Quieres abrir los 5 para aplicar?"
        decision = ui_confirm("Career-Ops", "¿Quieres abrir los 5 para aplicar?", ["Yes", "No"])
        if decision == "Yes":
            # Open the 5 jobs in browser
            for job in top_manual_jobs[:5]:
                try:
                    driver.execute_script("window.open(arguments[0], '_blank');", job['link'])
                except Exception as ex:
                    print_lg(f"Failed to open link: {job['link']}", ex)
            
            # Ask the user: "¿Ya aplicaste?"
            applied_decision = "No"
            while applied_decision != "Yes":
                applied_decision = ui_confirm("Career-Ops", "¿Ya aplicaste?", ["Yes", "No"])
                if applied_decision == "No":
                    time.sleep(2)
                    ui_pause_check()
            
            # Ask: "¿Quieres buscar otros 5?"
            search_more = ui_confirm("Career-Ops", "¿Quieres buscar otros 5?", ["Yes", "No"])
            if search_more == "Yes":
                top_manual_jobs = top_manual_jobs[5:]
                print_lg("[Career-Ops Mode] Kept remaining jobs, continuing search for another 5 jobs.")
                ui_update_status("Career-Ops: Searching", f"Continuing cycle... ({len(top_manual_jobs)}/5 matches)")
                return True
            else:
                top_manual_jobs.clear()
                print_lg("[Career-Ops Mode] User chose not to search for more. Exiting loop.")
                return False
        else:
            top_manual_jobs.clear()
            print_lg("[Career-Ops Mode] User declined opening jobs. Exiting loop.")
            return False
    return True


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


#< Login Functions
def is_logged_in_LN() -> bool:
    '''
    Function to check if user is logged-in in LinkedIn
    * Returns: `True` if user is logged-in or `False` if not
    '''
    if driver.current_url == "https://www.linkedin.com/feed/": return True
    if try_linkText(driver, "Sign in"): return False
    if try_xp(driver, '//button[@type="submit" and contains(text(), "Sign in")]'):  return False
    if try_linkText(driver, "Join now"): return False
    print_lg("Didn't find Sign in link, so assuming user is logged in!")
    return True


def login_LN() -> None:
    '''
    Function to login for LinkedIn
    * Tries to login using given `username` and `password` from `secrets.py`
    * If failed, tries to login using saved LinkedIn profile button if available
    * If both failed, asks user to login manually
    '''
    # Find the username and password fields and fill them with user credentials
    driver.get("https://www.linkedin.com/login")
    if username == "username@example.com" and password == "example_password":
        ui_alert("Login Manually", "User did not configure username and password in secrets.py, hence can't login automatically! Please login manually!")
        print_lg("User did not configure username and password in secrets.py, hence can't login automatically! Please login manually!")
        manual_login_retry(is_logged_in_LN, 2)
        return
    try:
        wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Forgot password?")))
        try:
            text_input_by_ID(driver, "username", username, 1)
        except Exception as e:
            print_lg("Couldn't find username field.")
            # print_lg(e)
        try:
            text_input_by_ID(driver, "password", password, 1)
        except Exception as e:
            print_lg("Couldn't find password field.")
            # print_lg(e)
        # Find the login submit button and click it
        driver.find_element(By.XPATH, '//button[@type="submit" and contains(text(), "Sign in")]').click()
    except Exception as e1:
        try:
            profile_button = find_by_class(driver, "profile__details")
            profile_button.click()
        except Exception as e2:
            # print_lg(e1, e2)
            print_lg("Couldn't Login!")

    try:
        # Wait until successful redirect, indicating successful login
        wait.until(EC.url_to_be("https://www.linkedin.com/feed/")) # wait.until(EC.presence_of_element_located((By.XPATH, '//button[normalize-space(.)="Start a post"]')))
        return print_lg("Login successful!")
    except Exception as e:
        print_lg("Seems like login attempt failed! Possibly due to wrong credentials or already logged in! Try logging in manually!")
        # print_lg(e)
        manual_login_retry(is_logged_in_LN, 2)
#>



def get_applied_job_ids() -> set[str]:
    '''
    Function to get a `set` of applied job's Job IDs
    * Returns a set of Job IDs from existing applied jobs history csv file
    '''
    job_ids: set[str] = set()
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                job_ids.add(row[0])
    except FileNotFoundError:
        print_lg(f"The CSV file '{file_name}' does not exist.")
    return job_ids



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


def apply_filters(location_str: str) -> None:
    '''
    Function to apply job search filters
    '''
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

        global pause_after_filters
        if pause_after_filters and "Turn off Pause after search" == ui_confirm("Please check your results", "These are your configured search results and filter. It is safe to change them while this dialog is open, any changes later could result in errors and skipping this search run.", ["Turn off Pause after search", "Look's good, Continue"]):
            pause_after_filters = False

    except Exception as e:
        print_lg(f"Setting the preferences failed: {e}")
        # Continue silently — filters may be partially applied, bot will proceed



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
    job_details_button = job.find_element(By.TAG_NAME, 'a')  # job.find_element(By.CLASS_NAME, "job-card-list__title")  # Problem in India
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
        


# Function to upload resume
def upload_resume(modal: WebElement, resume: str) -> tuple[bool, str]:
    try:
        modal.find_element(By.NAME, "file").send_keys(os.path.abspath(resume))
        return True, os.path.basename(default_resume_path)
    except: return False, "Previous resume"


def resolve_value_for_category(category: str, var_name: str = None, direct_value = None):
    if direct_value is not None:
        return direct_value
        
    var_map = {
        "visa": "require_visa",
        "relocation": "Yes",
        "shifts": "Yes",
        "current_salary": "current_ctc",
        "desired_salary": "desired_salary",
        "experience": "years_of_experience",
        "phone": "phone_number",
        "address": "street",
        "city": "current_city",
        "state": "state",
        "zip": "zipcode",
        "country": "country",
        "school": "university",
        "gender": "gender",
        "disability": "disability_status",
        "veteran": "veteran_status",
        "citizenship": "us_citizenship",
        "notice": "notice_period",
        "summary": "linkedin_summary",
        "cover_letter": "cover_letter"
    }
    
    target_var = var_name or var_map.get(category)
    if not target_var:
        return None
        
    if target_var in ["Yes", "No"]:
        return target_var
        
    val = globals().get(target_var)
    if val is not None:
        return val
        
    return None


def find_matching_option(options_text_list: list[str], target_answer) -> int | None:
    if target_answer is None or str(target_answer).strip() == "":
        # If there's only one valid option and it's a "Yes" variant, pick it automatically (forced acceptance)
        valid_opts = [o for o in options_text_list if not any(w in o.lower() for w in ["select", "selecciona", "elegir", "choose", "opcion"])]
        if len(valid_opts) == 1:
            opt_low = valid_opts[0].lower()
            if any(ys == opt_low or ys in opt_low.split() for ys in ["yes", "sí", "si", "acepto", "agree", "i do", "i have"]):
                return options_text_list.index(valid_opts[0])
        return None
        
    target_str = str(target_answer).lower().strip()
    
    yes_syns = {"yes", "si", "sí", "agree", "i do", "i have", "aceptar", "tengo", "disponible", "true", "cierto"}
    no_syns = {"no", "disagree", "i don't", "i do not", "no tengo", "rechazar", "false", "falso"}
    decline_syns = {"decline", "prefer not to say", "not wish", "don't wish", "prefer not", "not want", "omitir", "no deseo", "no responder", "no declarar", "no decir"}
    
    # 1. Exact or normalized check
    for idx, opt in enumerate(options_text_list):
        opt_str = opt.lower().strip()
        if target_str == opt_str:
            return idx
            
    # 2. Match standard groups
    if target_str in yes_syns:
        for idx, opt in enumerate(options_text_list):
            opt_str = opt.lower().strip()
            if opt_str in yes_syns or any(ys in opt_str for ys in ["yes", "sí", "si", "tengo", "dispon", "agree"]):
                return idx
    elif target_str in no_syns:
        for idx, opt in enumerate(options_text_list):
            opt_str = opt.lower().strip()
            if opt_str in no_syns or any(ns in opt_str for ns in ["no", "disagree"]):
                return idx
    elif target_str in decline_syns:
        for idx, opt in enumerate(options_text_list):
            opt_str = opt.lower().strip()
            if opt_str in decline_syns or any(ds in opt_str for ds in ["decline", "not to say", "no deseo", "no responder", "omitir"]):
                return idx
                
    # 3. Gender specific matches
    if target_str in ["male", "hombre", "masculino"]:
        for idx, opt in enumerate(options_text_list):
            opt_str = opt.lower().strip()
            if opt_str in ["male", "hombre", "masculino", "varon", "varón"]:
                return idx
    elif target_str in ["female", "mujer", "femenino"]:
        for idx, opt in enumerate(options_text_list):
            opt_str = opt.lower().strip()
            if opt_str in ["female", "mujer", "femenino"]:
                return idx
                
    # 4. Substring containment check
    for idx, opt in enumerate(options_text_list):
        opt_str = opt.lower().strip()
        if target_str in opt_str or opt_str in target_str:
            return idx
            
    # 5. Alphanumeric only check — skip placeholder options to avoid false matches (e.g. "no" in "selectanoption")
    _placeholder_words = {"select", "selecciona", "elegir", "choose", "unselected", "opcion", "seleccione"}
    target_alnum = "".join(c for c in target_str if c.isalnum())
    for idx, opt in enumerate(options_text_list):
        if any(w in opt.lower() for w in _placeholder_words):
            continue
        opt_alnum = "".join(c for c in opt.lower() if c.isalnum())
        if target_alnum and opt_alnum and (target_alnum in opt_alnum or opt_alnum in target_alnum):
            return idx
            
    return None


def answer_language_question(label_org: str, question_type: str, options_text=None) -> str | None:
    # Normalize label string to remove accents
    import unicodedata
    norm = "".join(c for c in unicodedata.normalize('NFD', label_org) if unicodedata.category(c) != 'Mn').lower().strip()
    
    # 1. Check if it matches our specific supported languages
    is_spanish = any(w in norm for w in ["spanish", "espanol", "castellano"])
    is_english = any(w in norm for w in ["english", "ingles"])
    is_german = any(w in norm for w in ["german", "aleman", "deutsch"])
    
    # 2. Check for other explicit languages
    other_languages = [
        "portuguese", "portugues", "portuguesa", "brasil", "brazil", "portugal",
        "russian", "ruso", "rusa", "russkiy", "russkii", "russkom", "русский", "русском",
        "french", "frances", "italy", "italian", "italiano", "chinese", "chino", "china",
        "japanese", "japones", "japan", "korean", "coreano", "korea", "dutch", "neerlandes",
        "holandes", "arabic", "arabe", "hindi", "bengali", "punjabi", "swedish", "sueco",
        "polish", "polaco", "turkish", "turco", "vietnamese", "vietnamita"
    ]
    is_other_lang = any(w in norm for w in other_languages)
    
    # 3. Check if it is a general language question
    is_lang_q = any(w in norm for w in ["language", "idioma", "habla", "speak", "proficiency", "competence", "competencia", "conversational", "fluent", "level of", "nivel de"])
    
    # If it is not a language question and does not contain any language keywords, return None
    if not (is_spanish or is_english or is_german or is_other_lang or is_lang_q):
        return None
        
    # Resolve the target language profile
    if is_spanish:
        if question_type in ["select", "radio", "combobox"] and options_text:
            for opt in options_text:
                opt_lower = opt.lower()
                if any(w in opt_lower for w in ["native", "nativo", "fluent", "bilingual", "bilingue", "c2"]):
                    return opt
            yes_idx = find_matching_option(options_text, "Yes")
            if yes_idx is not None:
                return options_text[yes_idx]
        return "Native"
        
    elif is_english:
        if question_type in ["select", "radio", "combobox"] and options_text:
            for opt in options_text:
                opt_lower = opt.lower()
                # C1 level matches advanced, fluent, proficient, c1, etc.
                if any(w in opt_lower for w in ["advanced", "avanzado", "fluent", "proficient", "c1", "c2", "professional", "professional working"]):
                    return opt
            yes_idx = find_matching_option(options_text, "Yes")
            if yes_idx is not None:
                return options_text[yes_idx]
        return "C1/Advanced"
        
    elif is_german:
        if question_type in ["select", "radio", "combobox"] and options_text:
            for opt in options_text:
                opt_lower = opt.lower()
                # A2 level matches basic, elementary, a2, beginner
                if any(w in opt_lower for w in ["elementary", "basic", "principiante", "a1", "a2", "limited", "beginner"]):
                    return opt
            yes_idx = find_matching_option(options_text, "Yes")
            if yes_idx is not None:
                return options_text[yes_idx]
        return "A2/Elementary"
        
    # If it's another language OR a general language question we don't speak:
    else:
        # We don't speak it!
        if question_type in ["select", "radio", "combobox"] and options_text:
            no_idx = find_matching_option(options_text, "No")
            if no_idx is not None:
                return options_text[no_idx]
            for opt in options_text:
                opt_lower = opt.lower()
                if any(w in opt_lower for w in ["none", "no proficiency", "ninguno", "sin conocimiento", "don't speak", "do not speak"]):
                    return opt
            # Return the first option that isn't positive
            for opt in options_text:
                opt_lower = opt.lower()
                if not any(w in opt_lower for w in ["yes", "si", "sí", "fluent", "native", "advanced", "intermediate"]):
                    return opt
            return options_text[0]
        return "No"


def resolve_salary_expectation(question_text: str, is_current=False, work_location: str = "") -> str:
    question_lower = question_text.lower()
    work_loc_lower = work_location.lower() if work_location else ""
    
    # Determine currency
    is_usd = False
    is_cop = False
    
    if any(w in question_lower for w in ["usd", "us dollar", "dolar", "dollar", "dollars", "dolares", "dólar", "dólares"]):
        is_usd = True
    elif any(w in question_lower for w in ["cop", "colombian", "colombia", "pesos", "peso"]):
        is_cop = True
    else:
        # Default based on work location
        if "colombia" in work_loc_lower:
            is_cop = True
        else:
            is_usd = True # Default to USD for remote/worldwide if not specified
            
    if is_current:
        monthly_cop = 4000000.0
        monthly_usd = 1200.0
    else:
        monthly_cop = 4000000.0
        monthly_usd = 1100.0
        
    if is_usd:
        base_salary = monthly_usd
    else:
        base_salary = monthly_cop
        
    # Check if yearly or monthly
    is_yearly = any(w in question_lower for w in ["year", "annual", "ano", "anual", "yearly", "annually", "/yr", "per year", "per annum"])
    
    if is_yearly:
        salary = base_salary * 12
    else:
        salary = base_salary
        
    # Check scaling (million/millones/millon/etc.)
    if any(w in question_lower for w in ["millon", "millones", "million", "millón"]):
        salary = salary / 1000000.0
        return f"{salary:.1f}"
    elif "lakh" in question_lower:
        salary = salary / 100000.0
        return f"{salary:.1f}"
        
    if salary.is_integer():
        return str(int(salary))
    return str(salary)



# Function to answer common questions for Easy Apply
_SENSITIVE_KEYWORDS = [
    # Criminal / legal
    'criminal', 'felony', 'felon', 'misdemeanor', 'misdemeanour', 'convicted', 'conviction',
    'arrested', 'arrest', 'criminal record', 'criminal charge', 'criminal act',
    'criminal offense', 'criminal offence', 'background disclosure', 'criminal history',
    'criminal background', 'penal', 'acto criminal', 'antecedentes penales', 'delito',
    'condena', 'arrestado', 'crimen', 'historial criminal',
    # Previous employment at this company
    'previously employed by us', 'former employee of', 'worked for us before',
    'previously worked here', 'have you worked here', 'been employed by this company',
    'previously been employed by', 'have you previously been employed', 'been previously employed by',
    'previously worked for', 'formerly worked for', 'former employee at',
    'empleado anteriormente aqui', 'trabajado aqui antes', 'ex empleado de',
    'ha trabajado anteriormente en', 'fue empleado de', 'trabajo antes en',
    # Previous applications
    'previously applied', 'applied here before', 'applied to this company before',
    'interviewed here before', 'previous application', 'aplicado anteriormente',
    'aplicado antes a esta empresa', 'entrevistado aqui antes',
    # Other negative disclosures
    'drug use', 'drug test', 'substance abuse', 'terminated for cause', 'dismissed for cause',
    'misconduct', 'uso de drogas', 'despedido por causa', 'mala conducta',
    # --- Conflict of interest / relationships ---
    'conflict of interest', 'conflicto de interes', 'conflicto de interés',
    'family relationship', 'relacion familiar', 'relación familiar',
    'contractual relationship', 'relacion contractual', 'relación contractual',
    'family and/or contractual', 'direct competitor', 'competidor directo',
    'staff member', 'board member', 'shareholder', 'accionista',
    'family member who works', 'familiar que trabaja',
    'government entity', 'government official', 'entidad gubernamental', 'funcionario',
    'public official', 'funcionario publico', 'funcionario público',
    'employee of our company', 'empleado de nuestra empresa',
    'relationship with any', 'relationship with a',
    'personal relationship', 'relacion personal', 'relación personal',
    'economic relationship', 'relacion economica', 'relación económica',
    'related to any', 'related to an employee',
    # --- Current Education / Employment (uncheck to reveal 'To' dates) ---
    'currently attend', 'currently work', 'trabajo actualmente', 'estudio actualmente',
    'actualmente asisto', 'trabajando actualmente', 'estudiando actualmente',
]

def is_sensitive_question(label: str) -> bool:
    """Returns True if the question involves criminal history, prior employment, or other sensitive disclosures that should always be answered 'No'."""
    import unicodedata
    norm = "".join(c for c in unicodedata.normalize('NFD', label) if unicodedata.category(c) != 'Mn').lower()
    return any(w in norm for w in _SENSITIVE_KEYWORDS)


def answer_common_questions(label: str, answer: str) -> str:
    import json
    import os
    import unicodedata

    norm_label = "".join(c for c in unicodedata.normalize('NFD', label) if unicodedata.category(c) != 'Mn').lower()

    if any(w in norm_label for w in _SENSITIVE_KEYWORDS):
        return 'No'

    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "config", "questions_db.json")
    mappings = []
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r', encoding='utf-8') as db_file:
                db_data = json.load(db_file)
                mappings = db_data.get("mappings", [])
        except Exception:
            pass

    for item in mappings:
        category = item.get("category")
        patterns = item.get("patterns", [])
        if category in ["visa", "relocation", "shifts"] and any(pat in norm_label for pat in patterns):
            if "value" in item:
                return item["value"]
            elif item.get("var_name") == "require_visa":
                return require_visa

    if any(w in norm_label for w in ['sponsorship', 'visa', 'patrocinio', 'visado']):
        answer = require_visa
    elif any(w in norm_label for w in ['relocate', 'relocation', 'reubicacion', 'reubicar', 'traslado', 'mudarse', 'cambio de residencia']):
        answer = 'Yes'
    elif any(phrase in norm_label for phrase in [
        'have read and accept', 'i accept the terms', 'i agree to the terms', 'agree to the privacy',
        'terms and conditions', 'terms & conditions', 'privacy policy', 'terms of service',
        'accept wizeline', 'accept the policy', 'acepto los terminos', 'acepto la politica',
        'lei y acepto', 'he leido y acepto', 'leido y aceptado',
    ]):
        answer = 'Yes'
    return answer


# Function to answer the questions for Easy Apply
def answer_questions(modal: WebElement, questions_list: set, work_location: str, job_description: str | None = None ) -> set:
    import json
    import os
    import unicodedata
    
    def normalize_label(label_str: str) -> str:
        if not label_str:
            return ""
        return "".join(c for c in unicodedata.normalize('NFD', label_str) if unicodedata.category(c) != 'Mn').lower().strip()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "config", "questions_db.json")
    mappings = []
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r', encoding='utf-8') as db_file:
                db_data = json.load(db_file)
                mappings = db_data.get("mappings", [])
        except Exception as db_err:
            print_lg(f"Error loading questions_db.json: {db_err}")

    def match_rules(label_str: str):
        norm = normalize_label(label_str)
        for item in mappings:
            patterns = item.get("patterns", [])
            if any(pat in norm for pat in patterns):
                return item
        return None

    # Get all questions from the page (including custom ATS groupings that lack standard attributes)
    all_questions = modal.find_elements(By.XPATH, ".//div[@data-test-form-element] | .//div[contains(@class, 'jobs-easy-apply-form-section__grouping') and not(.//div[@data-test-form-element])]")

    _prev_q_text = ""  # Tracks the previous visible QBlock label to detect conditional "if YES" hidden inputs

    _IF_YES_KEYWORDS = [
        'if yes', 'if your answer is yes', 'if so', 'if applicable',
        'en caso afirmativo', 'if you answered yes', 'si la respuesta es si',
        'si su respuesta es si', 'si es si',
    ]

    for Question in all_questions:
        if is_career_ops_mode():
            raise CareerOpsActivatedException()
        ui_pause_check()
        # Skip hidden elements. For conditional "if YES" input blocks, inject N/A before skipping.
        # LinkedIn renders label and input as SEPARATE data-test-form-element divs: the outer label
        # block is visible (logged below), but the inner input block is hidden when parent = "No".
        # _prev_q_text carries the previous visible block's text so we know what the hidden block is for.
        try:
            if not Question.is_displayed():
                if any(w in _prev_q_text for w in _IF_YES_KEYWORDS):
                    try:
                        _hidden_inp = try_xp(Question, ".//input | .//textarea", False)
                        if _hidden_inp:
                            print_lg(f"[HiddenQBlock] Injecting N/A into conditional field (prev label: {_prev_q_text[:60]})")
                            driver.execute_script("""
                                var el = arguments[0];
                                var proto = el.tagName === 'TEXTAREA'
                                    ? window.HTMLTextAreaElement.prototype
                                    : window.HTMLInputElement.prototype;
                                var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                                setter.call(el, 'N/A');
                                ['input', 'change', 'blur'].forEach(function(t) {
                                    el.dispatchEvent(new Event(t, {bubbles: true, cancelable: true}));
                                });
                            """, _hidden_inp)
                    except Exception as _hqe:
                        print_lg(f"[HiddenQBlock] injection error: {_hqe}")
                    _prev_q_text = ""  # Reset so next hidden QBlock doesn't reuse this signal
                continue
        except Exception:
            pass
        # Debug: log what each question block contains
        try:
            _q_preview = Question.text.replace('\n', ' | ')[:120]
            print_lg(f"[QBlock] {_q_preview}")
            _prev_q_text = _q_preview.lower()
        except Exception:
            _prev_q_text = ""
        # Diagnostic: log all inputs found in this QBlock to reveal hidden-input types
        try:
            _dbg_inputs = Question.find_elements(By.XPATH, ".//input | .//textarea | .//select")
            if _dbg_inputs:
                _dbg_types = [f"{el.tag_name}[{el.get_attribute('type') or 'no-type'}]" for el in _dbg_inputs]
                print_lg(f"[QBlock-Fields] {_dbg_types}")
        except Exception:
            pass
        # Check if it's a select Question
        select = try_xp(Question, ".//select", False)
        if select:
            label_org = "Unknown"
            try:
                label_el = Question.find_element(By.TAG_NAME, "label")
                try: label_el = label_el.find_element(By.CLASS_NAME,'visually-hidden')
                except: pass
                label_org = label_el.text
            except:
                pass
            if not label_org or label_org == "Unknown":
                try:
                    q_text = Question.text.strip()
                    if q_text: label_org = q_text.split('\n')[0].strip()
                except: pass
            ui_update_status("Answering Modal", action_text=f"Select: {label_org}")
            answer = ""
            label = normalize_label(label_org)
            selected_option = ""
            select_obj = Select(select)
            try: selected_option = select_obj.first_selected_option.text
            except: pass
            
            optionsText = []
            options = '"List of phone country codes"'
            if label != "phone country code":
                optionsText = [option.text for option in select_obj.options]
                options = "".join([f' "{option}",' for option in optionsText])
            prev_answer = selected_option
            
            is_default_option = any(w in selected_option.lower() for w in ["select", "selecciona", "elegir", "choose", "unselected", "opcion", "seleccione"]) or selected_option == ""
            
            try:
                if Question.find_elements(By.XPATH, ".//*[contains(@class, 'artdeco-inline-feedback--error')]"):
                    is_default_option = True
            except: pass
            
            if overwrite_previous_answers or is_default_option:
                lang_answer = answer_language_question(label_org, "select", optionsText)
                if lang_answer is not None:
                    answer = lang_answer
                elif is_sensitive_question(label_org):
                    answer = 'No'
                else:
                    db_match = match_rules(label_org)
                    if db_match:
                        category = db_match.get("category")
                        var_name = db_match.get("var_name")
                        direct_value = db_match.get("value_text") or db_match.get("value")
                        answer = resolve_value_for_category(category, var_name, direct_value)
                    else:
                        if any(w in label for w in ['email', 'correo']):
                            answer = prev_answer
                        elif any(w in label for w in ['gender', 'sex', 'genero', 'sexo']):
                            answer = gender
                        elif any(w in label for w in ['disability', 'discapacidad', 'limitacion']):
                            answer = disability_status
                        elif any(w in label for w in ['proficiency', 'competencia', 'nivel', 'idioma']):
                            answer = 'Professional'
                        elif any(loc_word in label for loc_word in ['location', 'city', 'state', 'country', 'ubicacion', 'ciudad', 'estado', 'pais', 'direccion']):
                            if any(w in label for w in ['country', 'pais']):
                                answer = country
                            elif any(w in label for w in ['state', 'estado', 'departamento', 'provincia']):
                                answer = state
                            elif any(w in label for w in ['city', 'ciudad', 'municipio']):
                                answer = current_city if current_city else work_location
                            else:
                                answer = work_location
                        # --- Education dropdowns: use configured education data ---
                        elif any(w in label for w in ['school', 'university', 'college', 'universidad', 'colegio', 'escuela', 'institution', 'institucion']):
                            # Try smart matching: split university name into keywords and find best option
                            uni_keywords = [w for w in university.lower().replace('(','').replace(')','').split() if len(w) > 3]
                            best_match = None
                            best_score = 0
                            for opt in optionsText:
                                opt_l = opt.lower()
                                score = sum(1 for kw in uni_keywords if kw in opt_l)
                                if score > best_score:
                                    best_score = score
                                    best_match = opt
                            if best_match and best_score > 0:
                                answer = best_match
                            else:
                                answer = university  # Will use find_matching_option later
                        elif any(w in label for w in ['degree', 'titulo', 'titulacion', 'nivel educativo', 'education level', 'nivel academico', 'academic level', 'highest level']):
                            # Map configured degree to available options
                            degree_keywords = {
                                'High School': ['high school', 'secundaria', 'bachiller', 'bachillerato', 'preparatoria', 'secundario'],
                                "Associate's": ['associate', 'tecnico', 'técnico', 'tecnologo', 'tecnólogo', 'ciclo'],
                                "Bachelor's": ['bachelor', 'licenciatura', 'pregrado', 'ingenier', 'universitario'],
                                "Master's": ['master', 'maestria', 'maestría', 'posgrado', 'postgrado'],
                                'Doctorate': ['doctor', 'phd', 'doctorado'],
                            }
                            _deg_lower = degree.lower()
                            _kws = []
                            for deg_name, kws in degree_keywords.items():
                                if any(k in _deg_lower for k in kws) or _deg_lower in deg_name.lower():
                                    _kws = kws
                                    break
                            best_match = None
                            best_score = 0
                            for opt in optionsText:
                                opt_l = opt.lower()
                                score = sum(1 for kw in _kws if kw in opt_l)
                                if score > best_score:
                                    best_score = score
                                    best_match = opt
                            answer = best_match if best_match else degree
                        elif any(w in label for w in ['field of study', 'major', 'campo de estudio', 'especialidad', 'carrera', 'discipline']):
                            answer = field_of_study
                        elif any(w in label for w in ['graduation year', 'year graduated', 'año de graduacion', 'año graduacion', 'año egreso']):
                            answer = graduation_year
                        # Terms & Conditions / Privacy Policy acceptance
                        elif any(w in label for w in [
                            'i have read and accept', 'i agree', 'i accept', 'terms and conditions',
                            'privacy policy', 'i have read', 'acepto', 'he leido', 'he leído',
                            'terminos y condiciones', 'términos y condiciones', 'politica de privacidad',
                            'política de privacidad', 'condiciones de uso', 'reglamento'
                        ]):
                            answer = 'Yes'
                        # How did you find out about this job
                        elif any(w in label for w in [
                            'how did you find', 'how did you hear', 'how did you learn', 'how did you know',
                            'where did you find', 'where did you hear', 'source of', 'job source',
                            'como te enteraste', 'como se entero', 'como supiste', 'donde viste',
                            'donde encontraste', 'fuente de empleo', 'como conociste'
                        ]):
                            # Truthful: we found the job on LinkedIn — try to match LinkedIn option
                            answer = 'LinkedIn'
                        else:
                            answer = answer_common_questions(label_org, answer)
                
                # Use our robust option matcher!
                match_idx = find_matching_option(optionsText, answer)
                print_lg(f"Select '{label_org}': answer='{answer}', match_idx={match_idx}, options={optionsText}")
                if match_idx is not None:
                    target_text = optionsText[match_idx].strip()
                    _selection_verified = False

                    # 1. Programmatic selection FIRST — no visual dropdown opening needed
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select)
                    time.sleep(0.3)
                    try:
                        select_obj.select_by_visible_text(target_text)
                        print_lg(f"select_by_visible_text succeeded: '{target_text}'")
                    except Exception as _e1:
                        print_lg(f"select_by_visible_text failed: {_e1}")
                        try:
                            select_obj.select_by_index(match_idx)
                            print_lg(f"select_by_index succeeded: {match_idx}")
                        except Exception as _e2:
                            print_lg(f"select_by_index failed: {_e2}")

                    # 2. Fire React/framework events so the component state updates
                    try:
                        _opt_value = select_obj.options[match_idx].get_attribute("value") or target_text
                        driver.execute_script("""
                        var sel = arguments[0];
                        var val = arguments[1];
                        var setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
                        setter.call(sel, val);
                        ['mousedown','mouseup','click','input','change','blur'].forEach(function(t){
                            sel.dispatchEvent(new Event(t, {bubbles:true, cancelable:true}));
                        });
                        """, select, _opt_value)
                    except Exception as _e3:
                        print_lg(f"JS event dispatch failed: {_e3}")

                    # 3. Verify selection
                    try:
                        _now_selected = select_obj.first_selected_option.text.strip()
                        if _now_selected.lower() == target_text.lower():
                            _selection_verified = True
                            print_lg(f"Selection verified: '{_now_selected}'")
                        else:
                            print_lg(f"Selection NOT verified: expected '{target_text}', got '{_now_selected}'")
                    except Exception:
                        pass

                    # 4. Visual fallback — only if programmatic approach didn't verify
                    if not _selection_verified:
                        try:
                            # Click to open the dropdown, then look for visual DOM option elements
                            try: select.click()
                            except: driver.execute_script("arguments[0].click();", select)
                            time.sleep(0.8)

                            _vis_xpaths = (
                                "//div[@role='option'] | //li[@role='option'] | "
                                "//div[@role='listbox']//div | //ul[@role='listbox']//li"
                            )
                            _vis_clicked = False
                            for _vo in driver.find_elements(By.XPATH, _vis_xpaths):
                                try:
                                    if _vo.is_displayed() and _vo.text.strip().lower() == target_text.lower():
                                        _vo.click()
                                        _vis_clicked = True
                                        print_lg(f"Visual option clicked: '{_vo.text.strip()}'")
                                        time.sleep(0.4)
                                        break
                                except Exception: continue

                            if not _vis_clicked:
                                # Keyboard fallback: type first char to jump to option, then Enter
                                from selenium.webdriver.common.keys import Keys as _Keys
                                from selenium.webdriver.common.action_chains import ActionChains as _AC
                                _ac = _AC(driver)
                                _ac.move_to_element(select).click().send_keys(target_text[0]).perform()
                                time.sleep(0.3)
                                _ac.send_keys(_Keys.RETURN).perform()
                        except Exception as _e4:
                            print_lg(f"Visual select fallback failed: {_e4}")

                    answer = optionsText[match_idx]
                else:
                    foundOption = False
                    # --- Do NOT use AI for institution names: it confabulates wrong institutions/countries ---
                    # But DO use AI for degree and field of study so it can map "Bachelor's" to "Undergraduate", etc.
                    _skip_ai_education = any(w in label for w in [
                        'school', 'university', 'college', 'universidad', 'colegio', 'escuela', 'institution', 'institucion'
                    ])
                    if use_AI and aiClient and optionsText and not _skip_ai_education:
                        if is_career_ops_mode():
                            raise CareerOpsActivatedException()
                        try:
                            print_lg(f"Asking AI to select an option for: {label_org}")
                            ai_answer = None
                            if ai_provider.lower() in ("openai", "groq"):
                                ai_answer = ai_answer_question(aiClient, label_org, options=optionsText, question_type="single_select", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                ai_answer = deepseek_answer_question(aiClient, label_org, options=optionsText, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                ai_answer = gemini_answer_question(aiClient, label_org, options=optionsText, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            
                            if ai_answer and isinstance(ai_answer, str):
                                ai_match_idx = find_matching_option(optionsText, ai_answer)
                                if ai_match_idx is not None:
                                    try:
                                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select)
                                        time.sleep(1)
                                        try: select.click()
                                        except: driver.execute_script("arguments[0].click();", select)
                                        time.sleep(1)
                                        
                                        opt = select_obj.options[ai_match_idx]
                                        try: opt.click()
                                        except: driver.execute_script("arguments[0].click();", opt)
                                        time.sleep(1)
                                        
                                        try: select_obj.select_by_index(ai_match_idx)
                                        except: pass
                                        
                                        js_script = """
                                        var select = arguments[0];
                                        var idx = arguments[1];
                                        select.selectedIndex = idx;
                                        select.value = select.options[idx].value;
                                        var nativeSelectValueSetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set;
                                        nativeSelectValueSetter.call(select, select.options[idx].value);
                                        select.dispatchEvent(new Event('focus', { bubbles: true }));
                                        select.dispatchEvent(new Event('input', { bubbles: true }));
                                        select.dispatchEvent(new Event('change', { bubbles: true }));
                                        select.dispatchEvent(new Event('blur', { bubbles: true }));
                                        """
                                        driver.execute_script(js_script, select, ai_match_idx)
                                    except Exception as e:
                                        print_lg(f"React hack failed: {e}")
                                        try: select_obj.select_by_index(ai_match_idx)
                                        except: pass
                                    answer = optionsText[ai_match_idx]
                                    foundOption = True
                                    print_lg(f'AI successfully selected: "{answer}"')
                        except Exception as e:
                            print_lg("AI failed to select option", e)

                    if not foundOption:
                        # --- IMPORTANT: Do NOT randomly select for critical education fields ---
                        _is_education_field = any(w in label for w in [
                            'school', 'university', 'college', 'universidad', 'colegio', 'escuela', 'institution',
                            'degree', 'titulo', 'titulacion', 'nivel educativo', 'education level',
                            'field of study', 'major', 'campo de estudio', 'especialidad', 'carrera'
                        ])
                        if _is_education_field:
                            # Try to find 'Other' or 'Not Listed' to avoid blocking the application
                            other_idx = None
                            for idx, opt in enumerate(optionsText):
                                opt_low = opt.lower()
                                if any(w in opt_low for w in ["other", "not listed", "otro", "no listado", "none of the above", "ninguno"]):
                                    other_idx = idx
                                    break
                            
                            if other_idx is not None:
                                print_lg(f'Education field "{label_org}" had no exact match. Selecting "Other" fallback.')
                                try:
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select)
                                    time.sleep(1)
                                    try: select.click()
                                    except: driver.execute_script("arguments[0].click();", select)
                                    time.sleep(1)
                                    opt = select_obj.options[other_idx]
                                    try: opt.click()
                                    except: driver.execute_script("arguments[0].click();", opt)
                                    time.sleep(1)
                                    try: select_obj.select_by_index(other_idx)
                                    except: pass
                                    js_script = """
                                    var select = arguments[0]; var idx = arguments[1];
                                    select.selectedIndex = idx; select.value = select.options[idx].value;
                                    var nativeSelectValueSetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set;
                                    nativeSelectValueSetter.call(select, select.options[idx].value);
                                    select.dispatchEvent(new Event('focus', { bubbles: true })); select.dispatchEvent(new Event('input', { bubbles: true }));
                                    select.dispatchEvent(new Event('change', { bubbles: true })); select.dispatchEvent(new Event('blur', { bubbles: true }));
                                    """
                                    driver.execute_script(js_script, select, other_idx)
                                except: pass
                                answer = optionsText[other_idx]
                            else:
                                print_lg(f'Education field "{label_org}" had no good match. Leaving as-is to avoid wrong data (e.g. random country).')
                                randomly_answered_questions.add((f'{label_org} [ {options} ]', "select"))
                                answer = prev_answer  # Keep original selection ("Select an option")
                        else:
                            print_lg(f'Failed to find an option with text "{answer}" for question labelled "{label_org}", answering randomly!')
                            rand_idx = randint(1, len(select_obj.options)-1)
                            try:
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select)
                                time.sleep(1)
                                try: select.click()
                                except: driver.execute_script("arguments[0].click();", select)
                                time.sleep(1)
                                
                                opt = select_obj.options[rand_idx]
                                try: opt.click()
                                except: driver.execute_script("arguments[0].click();", opt)
                                time.sleep(1)
                                
                                try: select_obj.select_by_index(rand_idx)
                                except: pass
                                
                                js_script = """
                                var select = arguments[0];
                                var idx = arguments[1];
                                select.selectedIndex = idx;
                                select.value = select.options[idx].value;
                                var nativeSelectValueSetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set;
                                nativeSelectValueSetter.call(select, select.options[idx].value);
                                select.dispatchEvent(new Event('focus', { bubbles: true }));
                                select.dispatchEvent(new Event('input', { bubbles: true }));
                                select.dispatchEvent(new Event('change', { bubbles: true }));
                                select.dispatchEvent(new Event('blur', { bubbles: true }));
                                """
                                driver.execute_script(js_script, select, rand_idx)
                            except Exception as e:
                                print_lg(f"React hack failed: {e}")
                                try: select_obj.select_by_index(rand_idx)
                                except: pass
                            answer = optionsText[rand_idx]
                            randomly_answered_questions.add((f'{label_org} [ {options} ]',"select"))
            else:
                answer = prev_answer
                save_to_qa_database(label_org, answer)
            ui_update_status("Answering Modal", action_text=f"Filled Select: {answer}")
            questions_list.add((f'{label_org} [ {options} ]', answer, "select", prev_answer))
            continue
        
        # Check if it's a radio Question
        radio = try_xp(Question, './/fieldset[@data-test-form-builder-radio-button-form-component="true"]', False)
        if radio:
            prev_answer = None
            label_el = try_xp(radio, './/span[@data-test-form-builder-radio-button-form-component__title]', False)
            try: label_el = find_by_class(label_el, "visually-hidden", 2.0)
            except: pass
            label_org = label_el.text if label_el else "Unknown"
            ui_update_status("Answering Modal", action_text=f"Radio: {label_org}")
            answer = 'Yes'
            label = normalize_label(label_org)

            label_org_full = label_org + ' [ '
            inputs = radio.find_elements(By.TAG_NAME, 'input')
            radio_options = []
            options_text_list = []
            
            for idx, inp in enumerate(inputs):
                inp_id = inp.get_attribute("id")
                option_label = try_xp(radio, f'.//label[@for="{inp_id}"]', False)
                label_text = option_label.text if option_label else "Unknown"
                options_text_list.append(label_text)
                
                radio_options.append({
                    "input": inp,
                    "label": option_label,
                    "text": label_text
                })
                
                # Check if selected
                if inp.is_selected():
                    prev_answer = f'"{label_text}"<{inp.get_attribute("value")}>'
                label_org_full += f' "{label_text}"<{inp.get_attribute("value")}>,'
            
            label_org_full += ' ]'

            if overwrite_previous_answers or prev_answer is None:
                # Check for language question first!
                lang_answer = answer_language_question(label_org, "radio", options_text_list)
                if lang_answer is not None:
                    answer = lang_answer
                elif is_sensitive_question(label_org):
                    answer = 'No'
                else:
                    db_match = match_rules(label_org)
                    if db_match:
                        category = db_match.get("category")
                        var_name = db_match.get("var_name")
                        direct_value = db_match.get("value")
                        answer = resolve_value_for_category(category, var_name, direct_value)
                    else:
                        if any(w in label for w in ['citizenship', 'employment eligibility', 'ciudadania', 'nacionalidad', 'permiso']):
                            answer = us_citizenship
                        elif any(w in label for w in ['veteran', 'protected', 'veterano', 'protegido']):
                            answer = veteran_status
                        elif any(w in label for w in ['disability', 'handicapped', 'discapacidad', 'limitacion']):
                            answer = disability_status
                        elif any(w in label for w in ['how did you find', 'how did you hear', 'how did you learn', 'como te enteraste', 'como se entero', 'como supiste', 'como supieron', 'donde viste', 'donde encontraste', 'fuente de', 'source of']):
                            # Truthful: we found the job on LinkedIn
                            answer = 'LinkedIn'
                        else:
                            answer = answer_common_questions(label_org, answer)
                
                # Find matching label
                match_idx = find_matching_option(options_text_list, answer)
                label_to_click = None
                if match_idx is not None:
                    target_opt = radio_options[match_idx]
                    label_to_click = target_opt["label"]
                    answer = target_opt["text"]
                else:
                    if use_AI and aiClient:
                        if is_career_ops_mode():
                            raise CareerOpsActivatedException()
                        try:
                            print_lg(f"Asking AI to answer Radio question: {label_org}")
                            ai_answer = None
                            if ai_provider.lower() in ("openai", "groq"):
                                ai_answer = ai_answer_question(aiClient, label_org, options=options_text_list, question_type="single_select", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                ai_answer = deepseek_answer_question(aiClient, label_org, options=options_text_list, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                ai_answer = gemini_answer_question(aiClient, label_org, options=options_text_list, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            
                            if ai_answer and isinstance(ai_answer, str):
                                ai_match_idx = find_matching_option(options_text_list, ai_answer)
                                if ai_match_idx is not None:
                                    label_to_click = radio_options[ai_match_idx]["label"]
                                    answer = radio_options[ai_match_idx]["text"]
                        except Exception as e:
                            print_lg("AI failed to answer Radio question", e)
                
                # "Yes first" helper: for "No" answers, temporarily click "Yes" so React renders
                # conditional required fields (e.g. "If YES, provide name..."), fill them with
                # N/A via the React native setter, then proceed to click the actual "No" answer.
                def _yes_first_fill_conditionals(final_answer_text):
                    if (final_answer_text or '').lower().strip() not in ('no', 'false', 'nein', 'non', 'não', 'нет'):
                        return
                    _yes_el = None
                    for _ro in radio_options:
                        if _ro.get('text', '').lower().strip() in ('yes', 'sí', 'si', 'oui', 'ja', 'да', 'sim', 'true'):
                            _yes_el = _ro.get('label')
                            break
                    if not _yes_el:
                        return
                    try:
                        try: _yes_el.click()
                        except: driver.execute_script("arguments[0].click();", _yes_el)
                        time.sleep(0.6)  # Wait for React to mount conditional fields
                        _cfilled = driver.execute_script("""
                            var phrases=['if your answer is yes','if yes','if so','if applicable',
                                'en caso afirmativo','if you answered yes','si la respuesta es si','si su respuesta es si'];
                            var filled=[];
                            document.querySelectorAll('label').forEach(function(lbl){
                                if(lbl.offsetParent===null) return;
                                var txt=(lbl.textContent||'').toLowerCase().trim();
                                if(!phrases.some(function(p){return txt.indexOf(p)!==-1;})) return;
                                var inp=null,forId=lbl.getAttribute('for');
                                if(forId) inp=document.getElementById(forId);
                                if(!inp){
                                    var par=lbl.parentElement;
                                    for(var d=0;d<5&&par;d++){
                                        inp=par.querySelector('input:not([type=hidden]):not([type=radio]):not([type=checkbox]),textarea');
                                        if(inp) break; par=par.parentElement;
                                    }
                                }
                                if(!inp||(inp.value&&inp.value.trim())) return;
                                var proto=inp.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;
                                var s=Object.getOwnPropertyDescriptor(proto,'value').set;
                                s.call(inp,'N/A');
                                ['input','change','blur'].forEach(function(t){inp.dispatchEvent(new Event(t,{bubbles:true,cancelable:true}));});
                                filled.push(lbl.textContent.trim().substring(0,60));
                            });
                            return filled;
                        """)
                        if _cfilled:
                            for _cf in _cfilled:
                                print_lg(f"[YesFirst] Set N/A for: {_cf}")
                    except Exception as _yfe:
                        print_lg(f"[YesFirst] error: {_yfe}")

                if label_to_click:
                    _yes_first_fill_conditionals(answer)
                    try:
                        label_to_click.click()
                    except Exception:
                        try:
                            actions.move_to_element(label_to_click).click().perform()
                        except Exception:
                            try:
                                driver.execute_script("arguments[0].click();", label_to_click)
                            except Exception as click_err:
                                print_lg(f"Failed to click radio option: {answer}", click_err)
                    time.sleep(0.4)  # Let React hide/show conditional fields before next iteration
                else:
                    # No direct match and no AI answer — safe fallback
                    # For Yes/No questions, always default to 'No' (safer than random 'Yes')
                    _opt_texts_lower = [o['text'].lower().strip() for o in radio_options]
                    _no_idx = None
                    for _i, _t in enumerate(_opt_texts_lower):
                        if _t in ('no', 'no.', 'ninguno', 'ninguna', 'nope'):
                            _no_idx = _i
                            break
                    if _no_idx is not None:
                        ele = radio_options[_no_idx]["label"]
                        answer = radio_options[_no_idx]["text"]
                    else:
                        ele = radio_options[0]["label"] if radio_options else None
                    if ele:
                        _yes_first_fill_conditionals(answer)
                        try:
                            ele.click()
                        except Exception:
                            try:
                                actions.move_to_element(ele).click().perform()
                            except Exception:
                                driver.execute_script("arguments[0].click();", ele)
                        time.sleep(0.4)  # Let React hide/show conditional fields before next iteration
                        randomly_answered_questions.add((label_org_full, "radio"))
            else:
                answer = prev_answer
                save_to_qa_database(label_org, answer)
                
            ui_update_status("Answering Modal", action_text=f"Filled Radio: {answer}")
            questions_list.add((label_org_full, answer, "radio", prev_answer))
            continue

        # Check if it's a text question
        text = try_xp(Question, ".//input[@type='text']", False)
        if text:
            # Handle hidden conditional fields (e.g. "If YES, provide details" when parent radio was "No")
            try:
                if not text.is_displayed():
                    _hidden_q = ""
                    try: _hidden_q = Question.text[:80].replace('\n', ' ')
                    except: pass
                    print_lg(f"[HiddenInput] injecting N/A: {_hidden_q}")
                    try:
                        driver.execute_script("""
                            var el = arguments[0];
                            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            setter.call(el, 'N/A');
                            ['input', 'change', 'blur'].forEach(function(t) {
                                el.dispatchEvent(new Event(t, {bubbles: true, cancelable: true}));
                            });
                        """, text)
                        print_lg("[HiddenInput] injection done")
                    except Exception as _he:
                        print_lg(f"[HiddenInput] injection failed: {_he}")
                    continue
            except Exception:
                pass
            do_actions = False
            label_el = try_xp(Question, ".//label[@for]", False)
            try: label_el = label_el.find_element(By.CLASS_NAME,'visually-hidden')
            except: pass
            label_org = label_el.text if label_el else "Unknown"
            ui_update_status("Answering Modal", action_text=f"Text: {label_org}")
            answer = ""
            label = normalize_label(label_org)

            # Extract full question block text for richer AI context (includes hints, descriptions, etc.)
            try:
                question_full_text = Question.text.strip()
            except Exception:
                question_full_text = label_org

            has_error = False
            error_msg = ""
            try:
                error_els = Question.find_elements(By.XPATH, ".//*[contains(@class, 'artdeco-inline-feedback--error')]")
                if error_els:
                    has_error = True
                    error_msg = error_els[0].text
            except: pass

            prev_answer = text.get_attribute("value")
            if not prev_answer or overwrite_previous_answers or has_error:
                matched_val = None

                # "If YES" conditional follow-ups: always N/A regardless of error state.
                # These must be checked BEFORE the `not has_error` guard so that when LinkedIn
                # shows them with a validation error on retry, they still get answered.
                _is_if_yes_field = any(w in label for w in [
                    'if yes', 'if your answer is yes', 'if applicable',
                    'si la respuesta es si', 'si su respuesta es si', 'si es si',
                    'en caso afirmativo', 'if you answered yes', 'if so',
                ])
                if _is_if_yes_field:
                    if '*' not in label_org and 'obligatorio' not in label:
                        matched_val = "[SKIP]"
                    else:
                        matched_val = "N/A"
                        print_lg(f"[IfYes] '{label_org[:60]}' → N/A")

                # Referral questions: default to N/A (only when no error, to avoid loops)
                elif any(w in label for w in [
                    'referral', 'referido', 'referred by', 'referrer', 'quien te refirio',
                    'quien lo refirio', 'codigo de referencia', 'referral code', 'referral id',
                    'employee referral', 'internal referral', 'referral name', 'refer a friend',
                ]) and not has_error:
                    matched_val = "N/A"

                # If there is no error, try other local rules
                elif not has_error:
                    # Check for language question first!
                    lang_answer = answer_language_question(label_org, "text")
                    if lang_answer is not None:
                        matched_val = lang_answer
                else:
                    # Error on non-"if YES" field: quick fallback for numeric/decimal language questions
                    lang_answer = answer_language_question(label_org, "text")
                    if lang_answer is not None and any(w in error_msg.lower() for w in ["número", "numero", "number", "decimal"]):
                        print_lg(f"Quick fallback: form expects a number for language question '{label_org}'. Using 10.0.")
                        matched_val = "10.0"

                if matched_val is None and not has_error:
                        db_match = match_rules(label_org)
                        if db_match:
                            category = db_match.get("category")
                            var_name = db_match.get("var_name")
                            direct_value = db_match.get("value_text") or db_match.get("value")
                            
                            if category in ["current_salary", "desired_salary"]:
                                matched_val = resolve_salary_expectation(label_org, category == "current_salary", work_location)
                            elif category == "notice":
                                if any(w in label for w in ['month', 'mes']):
                                    matched_val = notice_period_months
                                elif any(w in label for w in ['week', 'semana']):
                                    matched_val = notice_period_weeks
                                else:
                                    matched_val = notice_period
                            else:
                                matched_val = resolve_value_for_category(category, var_name, direct_value)
                                if category == "city":
                                    do_actions = True
                
                # If local rules worked (and no error), use it
                if matched_val is not None:
                    answer = matched_val
                # Otherwise, fallback to AI (which will receive the error_message if there is one)
                else:
                    if use_AI and aiClient:
                        if is_career_ops_mode():
                            raise CareerOpsActivatedException()
                        try:
                            # Pass full question block text when it adds context beyond just the label
                            ai_question = label_org
                            if question_full_text and question_full_text.lower() != label_org.lower() and len(question_full_text) > len(label_org) + 5:
                                ai_question = f"{label_org}\n\n[Full question context: {question_full_text}]"
                            if ai_provider.lower() in ("openai", "groq"):
                                ai_answer = ai_answer_question(aiClient, ai_question, question_type="text", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                ai_answer = deepseek_answer_question(aiClient, ai_question, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                ai_answer = gemini_answer_question(aiClient, ai_question, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all, error_message=error_msg if has_error else None)
                            
                            if ai_answer is not None and isinstance(ai_answer, str) and len(ai_answer) > 0:
                                print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{ai_answer}"')
                                answer = ai_answer
                        except Exception as e:
                                print_lg("Failed to get AI answer!", e)
                        
                        if answer == "":
                            if any(w in label for w in ['notice', 'aviso', 'preaviso', 'notificacion']):
                                if any(w in label for w in ['month', 'mes']):
                                    answer = notice_period_months
                                elif any(w in label for w in ['week', 'semana']):
                                    answer = notice_period_weeks
                                else: 
                                    answer = notice_period
                            elif any(w in label for w in ['salary', 'compensation', 'ctc', 'pay', 'salario', 'salarial', 'sueldo', 'remuneracion', 'expectativa', 'expectativas', 'pretension', 'pretensiones', 'pretendido', 'pretendida', 'aspiracion', 'aspiraciones', 'tarifa', 'cobro', 'pago']): 
                                answer = resolve_salary_expectation(label_org, any(w in label for w in ['current', 'present', 'actual', 'presente', 'ultimo', 'último']), work_location)
                            elif any(w in label for w in ['experience', 'years', 'experiencia', 'anos', 'ano', 'tiempo']): 
                                answer = years_of_experience
                            elif any(w in label for w in ['phone', 'mobile', 'telefono', 'celular', 'movil']): 
                                answer = phone_number
                            elif any(w in label for w in ['street', 'calle']): 
                                answer = street
                            elif any(w in label for w in ['city', 'location', 'address', 'ciudad', 'ubicacion', 'direccion']):
                                answer = current_city if current_city else work_location
                                do_actions = True
                            elif any(w in label for w in ['signature', 'firma']): 
                                answer = full_name
                            elif any(w in label for w in ['name', 'nombre', 'apellido']):
                                if any(w in label for w in ['full', 'completo']): 
                                    answer = full_name
                                elif any(w in label for w in ['first', 'primer']) and not any(w in label for w in ['last', 'apellido']): 
                                    answer = first_name
                                elif any(w in label for w in ['middle', 'segundo']) and not any(w in label for w in ['last', 'apellido']): 
                                    answer = middle_name
                                elif any(w in label for w in ['last', 'apellido']) and not any(w in label for w in ['first', 'nombre']): 
                                    answer = last_name
                                elif any(w in label for w in ['employer', 'empleador']): 
                                    answer = recent_employer
                                else: 
                                    answer = full_name
                            elif 'linkedin' in label: 
                                answer = linkedIn
                            elif any(w in label for w in ['website', 'blog', 'portfolio', 'link', 'sitio web', 'portafolio', 'enlace']): 
                                answer = website
                            elif any(w in label for w in ['scale of 1-10', 'escala del 1 al 10', 'escala de 1 a 10', 'escala 1-10']): 
                                answer = confidence_level
                            elif any(w in label for w in ['headline', 'titular', 'encabezado']): 
                                answer = linkedin_headline
                            elif any(w in label for w in ['state', 'province', 'estado', 'provincia', 'departamento']): 
                                answer = state
                            elif any(w in label for w in ['zip', 'postal', 'code', 'codigo postal']): 
                                answer = zipcode
                            elif any(w in label for w in ['country', 'pais']): 
                                answer = country
                            elif any(w in label for w in ['school', 'university', 'college', 'universidad', 'colegio', 'escuela']): 
                                answer = university
                            else: 
                                answer = answer_common_questions(label_org, answer)
                
                if answer == "":
                    randomly_answered_questions.add((label_org, "text"))
                    answer = ""
                    db_fallback = match_rules(label_org)
                    if db_fallback:
                        cat = db_fallback.get("category")
                        if cat in ["desired_salary", "current_salary"]:
                            answer = resolve_salary_expectation(label_org, cat == "current_salary", work_location)
                        elif cat == "experience":
                            answer = years_of_experience
                        elif cat == "phone":
                            answer = phone_number
                        else:
                            answer = "0"
                    else:
                        if any(w in label for w in ['if yes', 'if your answer is yes', 'if applicable', 'si la respuesta es si', 'si su respuesta es si', 'si es si', 'en caso afirmativo', 'if you answered yes', 'if so']):
                            answer = "[SKIP]" if ('*' not in label_org and 'obligatorio' not in label) else "N/A"
                        elif any(w in label for w in ['salary', 'pay', 'rate', 'compensation', 'ctc', 'expect', 'salario', 'salarial', 'sueldo', 'remuneracion', 'expectativa', 'expectativas', 'pretension', 'pretensiones', 'pretendido', 'pretendida', 'aspiracion', 'aspiraciones', 'tarifa', 'pago']): 
                            answer = resolve_salary_expectation(label_org, any(w in label for w in ['current', 'present', 'actual', 'presente', 'ultimo', 'último']), work_location)
                        elif any(w in label for w in ['currency', 'moneda']): 
                            answer = "COP" if current_city == "Bogotá" else "USD"
                        elif any(re.search(r'\b' + w + r'\b', label) for w in ['name', 'nombre']): 
                            answer = full_name
                        elif any(re.search(r'\b' + w + r'\b', label) for w in ['document', 'documento', 'cedula', 'identificacion', 'identification', 'c.c.', 'c.c', 'dni']) or \
                             (re.search(r'\bid\b', label) and not any(w in label for w in ['referral', 'referido', 'employee', 'empleado', 'contact', 'job', 'posting', 'requisition', 'req'])):
                            try: answer = identification_number
                            except NameError: answer = "1000708811"
                        elif any(re.search(r'\b' + w + r'\b', label) for w in ['number', 'phone', 'telefono', 'celular', 'movil']): 
                            answer = phone_number
                        else: 
                            answer = years_of_experience if any(w in label for w in ['year', 'experience', 'ano', 'anos', 'experiencia', 'tiempo']) else "0"
                
                if not isinstance(answer, str): 
                    answer = str(answer)
                
                # If AI returned an empty string for a required field, force it to "N/A"
                if answer.strip() == "" and ('*' in label_org or 'obligatorio' in label):
                    answer = "N/A"

                # Check entire Question text for decimal requirements (including help texts / validation errors)
                if any(w in question_full_text.lower() for w in ['decimal', 'mayor que 0.0', 'mayor que 0,0', 'greater than 0.0', 'greater than 0,0', 'mayor a 0.0', 'mayor a 0,0']):
                    try:
                        val = float(answer)
                        answer = f"{val:.1f}"
                    except ValueError:
                        pass

                if do_actions:
                    # City/location fields: strip accents so autocomplete matches correctly
                    import unicodedata as _ud
                    answer_no_accent = "".join(
                        c for c in _ud.normalize('NFD', answer)
                        if _ud.category(c) != 'Mn'
                    )
                    try:
                        text.clear()
                    except: pass
                    text.send_keys(answer_no_accent)
                    sleep(2)
                    try:
                        options = driver.find_elements(By.XPATH, "//div[@role='option'] | //li[@role='option']")
                        clicked = False
                        for opt in options:
                            if opt.is_displayed() and opt.text.strip().lower() != "select an option":
                                # Just click the first valid option that isn't the placeholder
                                opt.click()
                                clicked = True
                                break
                        if not clicked:
                            text.send_keys(Keys.ARROW_DOWN)
                            sleep(0.5)
                            text.send_keys(Keys.TAB)
                        sleep(1)
                    except: pass
                else:
                    try:
                        text.clear()
                    except: pass
                    try:
                        driver.execute_script("""
                            var el = arguments[0];
                            var val = arguments[1];
                            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            nativeInputValueSetter.call(el, val);
                            el.dispatchEvent(new Event('focus', { bubbles: true }));
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            el.dispatchEvent(new Event('blur', { bubbles: true }));
                        """, text, answer)
                    except:
                        text.send_keys(answer)
            else:
                answer = prev_answer
                save_to_qa_database(label_org, answer)
            ui_update_status("Answering Modal", action_text=f"Filled Text: {answer}")
            questions_list.add((label, text.get_attribute("value"), "text", prev_answer))
            continue

        # Check if it's a combobox (LinkedIn's custom dropdown)
        combobox = try_xp(Question, ".//input[@role='combobox'] | .//button[@role='combobox']", False)
        if combobox and not try_xp(Question, ".//select", False):
            label_el = try_xp(Question, ".//label[@for]", False)
            try: label_el = label_el.find_element(By.CLASS_NAME,'visually-hidden')
            except: pass
            label_org = label_el.text if label_el else "Unknown"
            ui_update_status("Answering Modal", action_text=f"Combobox: {label_org}")
            answer = "Yes"
            label_lower = normalize_label(label_org)
            
            try:
                actions.move_to_element(combobox).click().perform()
                sleep(1)
                
                list_items = driver.find_elements(By.XPATH, "//div[@role='listbox']//div[contains(@class, 'artdeco-dropdown__item')] | //div[@role='listbox']//li | //div[@role='listbox']//div[@role='option']")
                
                if combobox.tag_name == "input" and not list_items:
                    lang_answer = answer_language_question(label_org, "combobox")
                    if lang_answer is not None:
                        answer = lang_answer
                    else:
                        db_match = match_rules(label_org)
                        if db_match:
                            category = db_match.get("category")
                            var_name = db_match.get("var_name")
                            direct_value = db_match.get("value")
                            answer = resolve_value_for_category(category, var_name, direct_value)
                        else:
                            if 'phone' in label_lower or 'telefono' in label_lower or 'celular' in label_lower or 'country' in label_lower or 'pais' in label_lower:
                                answer = 'Colombia'
                            elif 'city' in label_lower or 'ciudad' in label_lower or 'location' in label_lower or 'ubicacion' in label_lower:
                                answer = current_city if current_city else work_location
                            else:
                                if use_AI and aiClient:
                                    if is_career_ops_mode():
                                        raise CareerOpsActivatedException()
                                    try:
                                        if ai_provider.lower() in ("openai", "groq"):
                                            answer = ai_answer_question(aiClient, label_org, question_type="text", job_description=job_description, user_information_all=user_information_all)
                                        elif ai_provider.lower() == "deepseek":
                                            answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                                        elif ai_provider.lower() == "gemini":
                                            answer = gemini_answer_question(aiClient, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                                    except Exception as e:
                                        print_lg("AI failed to answer combobox text input", e)
                                        
                    if not isinstance(answer, str): answer = ""
                    combobox.clear()
                    combobox.send_keys(answer)
                    sleep(2)
                    actions.send_keys(Keys.ARROW_DOWN).send_keys(Keys.ENTER).perform()
                else:
                    optionsText = [item.text.strip() for item in list_items if item.text.strip()]
                    foundOption = False
                    
                    lang_answer = answer_language_question(label_org, "combobox", optionsText)
                    if lang_answer is not None:
                        answer = lang_answer
                        match_idx = find_matching_option(optionsText, answer)
                        if match_idx is not None:
                            actions.move_to_element(list_items[match_idx]).click().perform()
                            answer = optionsText[match_idx]
                            foundOption = True
                    
                    if not foundOption:
                        db_match = match_rules(label_org)
                        if db_match:
                            category = db_match.get("category")
                            var_name = db_match.get("var_name")
                            direct_value = db_match.get("value")
                            answer = resolve_value_for_category(category, var_name, direct_value)
                        else:
                            if 'gender' in label_lower or 'sex' in label_lower or 'genero' in label_lower or 'sexo' in label_lower: 
                                answer = gender
                            elif 'disability' in label_lower or 'discapacidad' in label_lower: 
                                answer = disability_status
                            elif 'proficiency' in label_lower or 'competencia' in label_lower or 'nivel' in label_lower: 
                                answer = 'Professional'
                            elif any(loc_word in label_lower for loc_word in ['location', 'city', 'state', 'country', 'ubicacion', 'ciudad', 'estado', 'pais']):
                                if any(w in label_lower for w in ['country', 'pais']):
                                    answer = country 
                                elif any(w in label_lower for w in ['state', 'estado', 'departamento', 'provincia']):
                                    answer = state
                                elif any(w in label_lower for w in ['city', 'ciudad']):
                                    answer = current_city if current_city else work_location
                                else:
                                    answer = work_location
                            else: 
                                answer = answer_common_questions(label_org, answer)

                    # Use our robust option matcher!
                    match_idx = find_matching_option(optionsText, answer)
                    if match_idx is not None:
                        actions.move_to_element(list_items[match_idx]).click().perform()
                        answer = optionsText[match_idx]
                        foundOption = True
                    else:
                        if use_AI and aiClient and optionsText:
                            if is_career_ops_mode():
                                raise CareerOpsActivatedException()
                            try:
                                print_lg(f"Asking AI to select an option for combobox: {label_org}")
                                ai_answer = None
                                if ai_provider.lower() in ("openai", "groq"):
                                    ai_answer = ai_answer_question(aiClient, label_org, options=optionsText, question_type="single_select", job_description=job_description, user_information_all=user_information_all)
                                elif ai_provider.lower() == "deepseek":
                                    ai_answer = deepseek_answer_question(aiClient, label_org, options=optionsText, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                                elif ai_provider.lower() == "gemini":
                                    ai_answer = gemini_answer_question(aiClient, label_org, options=optionsText, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                                
                                if ai_answer and isinstance(ai_answer, str):
                                    ai_match_idx = find_matching_option(optionsText, ai_answer)
                                    if ai_match_idx is not None:
                                        actions.move_to_element(list_items[ai_match_idx]).click().perform()
                                        answer = optionsText[ai_match_idx]
                                        foundOption = True
                                        print_lg(f'AI successfully selected combobox option: "{answer}"')
                            except Exception as e:
                                print_lg("AI failed to select combobox option", e)

                        if not foundOption:
                            if list_items:
                                actions.move_to_element(list_items[0]).click().perform()
                                answer = optionsText[0] if optionsText else "Yes"
                            else:
                                actions.send_keys(Keys.ARROW_DOWN).send_keys(Keys.ENTER).perform()
                
                ui_update_status("Answering Modal", action_text=f"Filled Combobox: {answer}")
                questions_list.add((f'{label_org} [Combobox]', answer, "combobox", "None"))
            except Exception as e:
                print_lg(f"Failed to interact with combobox for {label_org}", e)
            continue
        
        text_area = try_xp(Question, ".//textarea", False)
        if text_area:
            try:
                if not text_area.is_displayed():
                    try:
                        driver.execute_script("""
                            var el = arguments[0];
                            var setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                            setter.call(el, 'N/A');
                            ['input', 'change', 'blur'].forEach(function(t) {
                                el.dispatchEvent(new Event(t, {bubbles: true, cancelable: true}));
                            });
                        """, text_area)
                    except Exception:
                        pass
                    continue
            except Exception:
                pass
            label_el = try_xp(Question, ".//label[@for]", False)
            try: label_el = label_el.find_element(By.CLASS_NAME,'visually-hidden')
            except: pass
            label_org = label_el.text if label_el else "Unknown"
            ui_update_status("Answering Modal", action_text=f"Textarea: {label_org}")
            answer = ""
            label = normalize_label(label_org)
            prev_answer = text_area.get_attribute("value")
            if not prev_answer or overwrite_previous_answers:
                # 1. Check language questions
                lang_answer = answer_language_question(label_org, "textarea")
                if lang_answer is not None:
                    answer = lang_answer
                else:
                    # 2. Check mappings/rules
                    db_match = match_rules(label_org)
                    matched_val = None
                    if db_match:
                        category = db_match.get("category")
                        var_name = db_match.get("var_name")
                        direct_value = db_match.get("value_text") or db_match.get("value")
                        
                        if category in ["current_salary", "desired_salary"]:
                            matched_val = resolve_salary_expectation(label_org, category == "current_salary", work_location)
                        elif category == "notice":
                            if any(w in label for w in ['month', 'mes']):
                                matched_val = notice_period_months
                            elif any(w in label for w in ['week', 'semana']):
                                matched_val = notice_period_weeks
                            else:
                                matched_val = notice_period
                        else:
                            matched_val = resolve_value_for_category(category, var_name, direct_value)
                    
                    if matched_val is not None:
                        answer = matched_val
                    else:
                        # 3. Code-based fallback checks
                        if any(w in label for w in ['notice', 'aviso', 'preaviso', 'notificacion']):
                            if any(w in label for w in ['month', 'mes']):
                                answer = notice_period_months
                            elif any(w in label for w in ['week', 'semana']):
                                answer = notice_period_weeks
                            else: 
                                answer = notice_period
                        elif any(re.search(r'\b' + w + r'\b', label) for w in ['document', 'documento', 'cedula', 'id', 'identificacion', 'identification', 'c.c.', 'c.c', 'dni']):
                            try:
                                answer = identification_number
                            except NameError:
                                answer = "1000708811" # Safety fallback
                        elif any(w in label for w in ['salary', 'compensation', 'ctc', 'pay', 'salario', 'salarial', 'sueldo', 'remuneracion', 'expectativa', 'expectativas', 'pretension', 'pretensiones', 'pretendido', 'pretendida', 'aspiracion', 'aspiraciones', 'tarifa', 'cobro', 'pago']): 
                            answer = resolve_salary_expectation(label_org, any(w in label for w in ['current', 'present', 'actual', 'presente', 'ultimo', 'último']), work_location)
                        elif any(w in label for w in ['experience', 'years', 'experiencia', 'anos', 'ano', 'tiempo']): 
                            answer = years_of_experience
                        elif any(re.search(r'\b' + w + r'\b', label) for w in ['number', 'phone', 'telefono', 'celular', 'movil']): 
                            answer = phone_number
                        elif any(w in label for w in ['street', 'calle']): 
                            answer = street
                        elif any(w in label for w in ['city', 'location', 'address', 'ciudad', 'ubicacion', 'direccion']):
                            answer = current_city if current_city else work_location
                        elif any(w in label for w in ['signature', 'firma']): 
                            answer = full_name
                        elif any(w in label for w in ['name', 'nombre', 'apellido']):
                            if any(w in label for w in ['full', 'completo']): 
                                answer = full_name
                            elif any(w in label for w in ['first', 'primer']) and not any(w in label for w in ['last', 'apellido']): 
                                answer = first_name
                            elif any(w in label for w in ['middle', 'segundo']) and not any(w in label for w in ['last', 'apellido']): 
                                answer = middle_name
                            elif any(w in label for w in ['last', 'apellido']) and not any(w in label for w in ['first', 'nombre']): 
                                answer = last_name
                            elif any(w in label for w in ['employer', 'empleador']): 
                                answer = recent_employer
                            else: 
                                answer = full_name
                        elif 'linkedin' in label: 
                            answer = linkedIn
                        elif any(w in label for w in ['website', 'blog', 'portfolio', 'link', 'sitio web', 'portafolio', 'enlace']): 
                            answer = website
                        elif any(w in label for w in ['scale of 1-10', 'escala del 1 al 10', 'escala de 1 a 10', 'escala 1-10']): 
                            answer = confidence_level
                        elif any(w in label for w in ['headline', 'titular', 'encabezado']): 
                            answer = linkedin_headline
                        elif any(w in label for w in ['state', 'province', 'estado', 'provincia', 'departamento']): 
                            answer = state
                        elif any(w in label for w in ['zip', 'postal', 'code', 'codigo postal']): 
                            answer = zipcode
                        elif any(w in label for w in ['country', 'pais']): 
                            answer = country
                        elif any(w in label for w in ['school', 'university', 'college', 'universidad', 'colegio', 'escuela']): 
                            answer = university
                        elif any(w in label for w in ['summary', 'resumen', 'perfil', 'extracto']): 
                            answer = linkedin_summary
                        elif any(w in label for w in ['cover', 'carta', 'presentacion']): 
                            answer = cover_letter
                        else: 
                            answer = answer_common_questions(label_org, answer)
                
                # 4. AI or fallback to db defaults
                if answer == "":
                    if use_AI and aiClient:
                        if is_career_ops_mode():
                            raise CareerOpsActivatedException()
                        try:
                            if ai_provider.lower() in ("openai", "groq"):
                                answer = ai_answer_question(aiClient, label_org, question_type="textarea", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                answer = gemini_answer_question(aiClient, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            
                            if answer and isinstance(answer, str) and len(answer) > 0 and answer != "0":
                                print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{answer}"')
                            else:
                                randomly_answered_questions.add((label_org, "textarea"))
                                answer = ""
                                db_fallback = match_rules(label_org)
                                if db_fallback:
                                    cat = db_fallback.get("category")
                                    if cat in ["desired_salary", "current_salary"]:
                                        answer = resolve_salary_expectation(label_org, cat == "current_salary", work_location)
                                    elif cat == "experience":
                                        answer = years_of_experience
                                    elif cat == "phone":
                                        answer = phone_number
                                    else:
                                        answer = "0"
                                else:
                                    if any(w in label for w in ['salary', 'pay', 'rate', 'compensation', 'ctc', 'salario', 'salarial', 'sueldo', 'remuneracion', 'expectativa', 'expectativas', 'pretension', 'pretensiones', 'pretendido', 'pretendida', 'aspiracion', 'aspiraciones']):
                                        answer = resolve_salary_expectation(label_org, False, work_location)
                                    elif any(w in label for w in ['years', 'experiencia', 'anos', 'ano', 'tiempo']): 
                                        answer = years_of_experience
                        except Exception as e:
                            print_lg("Failed to get AI answer for textarea!", e)
                            randomly_answered_questions.add((label_org, "textarea"))
                            answer = ""
                            db_fallback = match_rules(label_org)
                            if db_fallback:
                                cat = db_fallback.get("category")
                                if cat in ["desired_salary", "current_salary"]:
                                    answer = resolve_salary_expectation(label_org, cat == "current_salary", work_location)
                                elif cat == "experience":
                                    answer = years_of_experience
                                elif cat == "phone":
                                    answer = phone_number
                                else:
                                    answer = "0"
                    else:
                        randomly_answered_questions.add((label_org, "textarea"))
                        answer = ""
                        db_fallback = match_rules(label_org)
                        if db_fallback:
                            cat = db_fallback.get("category")
                            if cat in ["desired_salary", "current_salary"]:
                                answer = resolve_salary_expectation(label_org, cat == "current_salary", work_location)
                            elif cat == "experience":
                                answer = years_of_experience
                            elif cat == "phone":
                                answer = phone_number
                            else:
                                answer = "0"
                        else:
                            if any(w in label for w in ['salary', 'pay', 'rate', 'compensation', 'ctc', 'expect', 'salario', 'salarial', 'sueldo', 'remuneracion', 'expectativa', 'expectativas', 'pretension', 'pretensiones', 'pretendido', 'pretendida', 'aspiracion', 'aspiraciones', 'tarifa', 'pago']):
                                answer = resolve_salary_expectation(label_org, any(w in label for w in ['current', 'present', 'actual', 'presente', 'ultimo', 'último']), work_location)
                            elif any(w in label for w in ['name', 'nombre']): 
                                answer = full_name
                            elif any(w in label for w in ['number', 'phone', 'telefono', 'celular', 'movil']): 
                                answer = phone_number
                            else: 
                                answer = years_of_experience if any(w in label for w in ['year', 'experience', 'ano', 'anos', 'experiencia', 'tiempo']) else "0"
                if not isinstance(answer, str): 
                    answer = str(answer)
                
                if answer == "[SKIP]":
                    answer = ""
                
                # Check entire Question text for decimal requirements (including help texts / validation errors)
                question_full_text = Question.text.lower()
                if any(w in question_full_text for w in ['decimal', 'mayor que 0.0', 'mayor que 0,0', 'greater than 0.0', 'greater than 0,0', 'mayor a 0.0', 'mayor a 0,0']):
                    try:
                        val = float(answer)
                        answer = f"{val:.1f}"
                    except ValueError:
                        pass
                        
                try: text_area.clear()
                except: pass
                try:
                    driver.execute_script("""
                        var el = arguments[0];
                        var val = arguments[1];
                        var nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                        nativeTextAreaValueSetter.call(el, val);
                        el.dispatchEvent(new Event('focus', { bubbles: true }));
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new Event('blur', { bubbles: true }));
                    """, text_area, answer)
                except:
                    text_area.send_keys(answer)
            else:
                answer = prev_answer
                save_to_qa_database(label_org, answer)
                
            ui_update_status("Answering Modal", action_text=f"Filled Textarea: {answer}")
            questions_list.add((label, text_area.get_attribute("value"), "textarea", prev_answer))
            continue

        # Check if it's a checkbox question
        checkbox = try_xp(Question, ".//input[@type='checkbox']", False)
        if checkbox:
            label = try_xp(Question, ".//span[@class='visually-hidden']", False)
            label_org = label.text if label else "Unknown"
            if not label_org or label_org == "Unknown":
                try:
                    q_text = Question.text.strip()
                    if q_text: label_org = q_text.split('\n')[0].strip()
                except: pass
            ui_update_status("Answering Modal", action_text=f"Checkbox: {label_org}")
            label = label_org.lower()
            answer = try_xp(Question, ".//label[@for]", False)  # Sometimes multiple checkboxes are given for 1 question, Not accounted for that yet
            answer = answer.text if answer else "Unknown"
            prev_answer = checkbox.is_selected()
            checked = prev_answer

            if overwrite_previous_answers or not prev_answer:
                desired = True  # default: check the box
                if is_sensitive_question(label_org):
                    desired = False
                else:
                    # --- Work model checkbox logic ---
                    # Detect if this is a work model question (Onsite/Hybrid/Remote)
                    _work_model_q_words = ["work model", "modelo de trabajo", "comfortable working", "which of the following work", "modalidad", "modality"]
                    _is_work_model_q = any(w in label for w in _work_model_q_words)
                    if not _is_work_model_q:
                        # Also check if the checkbox option itself is an onsite/hybrid/remote keyword
                        _option_low = answer.lower() if answer else ""
                        _is_work_model_q = any(w in _option_low for w in ["onsite", "on-site", "on site", "hybrid", "hybride", "remote", "work from home", "presencial", "virtual", "teletrabajo"])
                    if _is_work_model_q:
                        _option_low = answer.lower() if answer else ""
                        _is_onsite_option = any(w in _option_low for w in ["onsite", "on-site", "on site", "presencial", "in-person", "in office"])
                        _is_remote_option = any(w in _option_low for w in ["remote", "work from home", "virtual", "teletrabajo", "wfh"])
                        _is_hybrid_option = any(w in _option_low for w in ["hybrid", "hybrido", "híbrido", "blended"])
                        # Check if job is IT/tech or customer service based on job_description
                        _desc_low = (job_description or "").lower()
                        _is_cs_job = any(w in _desc_low for w in ["customer service", "customer support", "servicio al cliente", "atención al cliente", "atencion al cliente", "call center"])
                        _is_it_job = any(w in _desc_low for w in ["it support", "tech support", "technical support", "help desk", "helpdesk", "systems admin", "sysadmin", "soporte tecnico", "soporte técnico"])
                        if _is_cs_job and not _is_it_job:
                            # Customer Service: only Remote/Virtual is acceptable, not Onsite or Hybrid
                            desired = _is_remote_option
                        else:
                            # IT jobs or generic: all work models are fine (Onsite, Hybrid, Remote)
                            desired = True
                    else:
                        db_match = match_rules(label_org)
                        if db_match:
                            val = str(db_match.get("value", "Yes"))
                            desired = val.lower() not in ("no", "false", "0")
                        else:
                            common_ans = answer_common_questions(label_org, "Yes")
                            desired = common_ans.lower() not in ("no", "false", "0")

                    if use_AI and aiClient:
                        if is_career_ops_mode():
                            raise CareerOpsActivatedException()
                        try:
                            ai_ans = None
                            if ai_provider.lower() in ("openai", "groq"):
                                ai_ans = ai_answer_question(aiClient, label_org, options=["Yes", "No"], question_type="single_select", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                ai_ans = deepseek_answer_question(aiClient, label_org, options=["Yes", "No"], question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                ai_ans = gemini_answer_question(aiClient, label_org, options=["Yes", "No"], question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            if ai_ans and isinstance(ai_ans, str):
                                desired = ai_ans.strip().lower() not in ("no", "false", "0")
                        except Exception as e:
                            print_lg("Failed to get AI answer for checkbox!", e)

                if desired != prev_answer:
                    try:
                        actions.move_to_element(checkbox).click().perform()
                        checked = desired
                    except Exception as e:
                        print_lg("Checkbox click failed!", e)

            ui_update_status("Answering Modal", action_text=f"Checked Checkbox: {checked}")
            questions_list.add((f'{label} ([X] {answer})', checked, "checkbox", prev_answer))
            continue


    # Select todays date
    try_xp(driver, "//button[contains(@aria-label, 'This is today')]")

    # Collect important skills
    # if 'do you have' in label and 'experience' in label and ' in ' in label -> Get word (skill) after ' in ' from label
    # if 'how many years of experience do you have in ' in label -> Get word (skill) after ' in '

    # JS sweep: fill all "If YES" conditional text fields with N/A.
    # Uses textContent (reads hidden elements too) so it works regardless of CSS visibility or React render state.
    try:
        filled = driver.execute_script("""
            var IF_YES_PHRASES = [
                'if your answer is yes', 'if yes', 'if so', 'if applicable',
                'en caso afirmativo', 'if you answered yes',
                'si la respuesta es si', 'si su respuesta es si'
            ];
            var modal = arguments[0];
            var labels = modal.querySelectorAll('label');
            var filled = [];
            labels.forEach(function(lbl) {
                var txt = (lbl.textContent || '').toLowerCase().trim();
                var matches = IF_YES_PHRASES.some(function(p) { return txt.indexOf(p) !== -1; });
                if (!matches) return;
                // Find target input: first by label[for], then by sibling search
                var inp = null;
                var forId = lbl.getAttribute('for');
                if (forId) inp = document.getElementById(forId);
                if (!inp) {
                    var parent = lbl.parentElement;
                    for (var d = 0; d < 5 && parent; d++) {
                        inp = parent.querySelector('input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]), textarea');
                        if (inp) break;
                        parent = parent.parentElement;
                    }
                }
                if (!inp) return;
                // Skip if already has a value
                if (inp.value && inp.value.trim() !== '') return;
                var proto = inp.tagName === 'TEXTAREA'
                    ? window.HTMLTextAreaElement.prototype
                    : window.HTMLInputElement.prototype;
                var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                setter.call(inp, 'N/A');
                ['input', 'change', 'blur'].forEach(function(t) {
                    inp.dispatchEvent(new Event(t, {bubbles: true, cancelable: true}));
                });
                filled.push(lbl.textContent.trim().substring(0, 60));
            });
            return filled;
        """, modal)
        if filled:
            for _f in filled:
                print_lg(f"[JSSweep] Set N/A for: {_f}")
    except Exception as _jse:
        print_lg(f"[JSSweep] error: {_jse}")

    return questions_list




def external_apply(pagination_element: WebElement, job_id: str, job_link: str, resume: str, date_listed, application_link: str, screenshot_name: str) -> tuple[bool, str, int]:
    '''
    Function to open new tab and save external job application links
    '''
    global tabs_count, dailyEasyApplyLimitReached
    if easy_apply_only:
        try:
            if "exceeded the daily application limit" in driver.find_element(By.CLASS_NAME, "artdeco-inline-feedback__message").text: dailyEasyApplyLimitReached = True
        except: pass
        print_lg("Easy apply failed I guess!")
        if pagination_element != None: return True, application_link, tabs_count
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3')]"))).click() # './/button[contains(span, "Apply") and not(span[contains(@class, "disabled")])]'
        wait_span_click(driver, "Continue", 1, True, False)
        windows = driver.window_handles
        tabs_count = len(windows)
        driver.switch_to.window(windows[-1])
        application_link = driver.current_url
        print_lg('Got the external application link "{}"'.format(application_link))
        if close_tabs and driver.current_window_handle != linkedIn_tab: driver.close()
        driver.switch_to.window(linkedIn_tab)
        return False, application_link, tabs_count
    except Exception as e:
        # print_lg(e)
        print_lg("Failed to apply!")
        failed_job(job_id, job_link, resume, date_listed, "Probably didn't find Apply button or unable to switch tabs.", e, application_link, screenshot_name)
        global failed_count
        failed_count += 1
        return True, application_link, tabs_count



def follow_company(modal: WebDriver = driver) -> None:
    '''
    Function to follow or un-follow easy applied companies based om `follow_companies`
    '''
    try:
        follow_checkbox_input = try_xp(modal, ".//input[@id='follow-company-checkbox' and @type='checkbox']", False)
        if follow_checkbox_input and follow_checkbox_input.is_selected() != follow_companies:
            try_xp(modal, ".//label[@for='follow-company-checkbox']")
    except Exception as e:
        print_lg("Failed to update follow companies checkbox!", e)
    


#< Failed attempts logging
def failed_job(job_id: str, job_link: str, resume: str, date_listed, error: str, exception: Exception, application_link: str, screenshot_name: str) -> None:
    '''
    Function to update failed jobs list in excel
    '''
    try:
        with open(failed_file_name, 'a', newline='', encoding='utf-8') as file:
            fieldnames = ['Job ID', 'Job Link', 'Resume Tried', 'Date listed', 'Date Tried', 'Assumed Reason', 'Stack Trace', 'External Job link', 'Screenshot Name']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if file.tell() == 0: writer.writeheader()
            writer.writerow({'Job ID':truncate_for_csv(job_id), 'Job Link':truncate_for_csv(job_link), 'Resume Tried':truncate_for_csv(resume), 'Date listed':truncate_for_csv(date_listed), 'Date Tried':datetime.now(), 'Assumed Reason':truncate_for_csv(error), 'Stack Trace':truncate_for_csv(exception), 'External Job link':truncate_for_csv(application_link), 'Screenshot Name':truncate_for_csv(screenshot_name)})
            file.close()
    except Exception as e:
        print_lg("Failed to update failed jobs list!", e)
        ui_alert("Failed Logging", "Failed to update the excel of failed jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file")


def screenshot(driver: WebDriver, job_id: str, failedAt: str) -> str:
    '''
    Function to to take screenshot for debugging
    - Returns screenshot name as String
    '''
    screenshot_name = "{} - {} - {}.png".format( job_id, failedAt, str(datetime.now()) )
    path = logs_folder_path+"/screenshots/"+screenshot_name.replace(":",".")
    # special_chars = {'*', '"', '\\', '<', '>', ':', '|', '?'}
    # for char in special_chars:  path = path.replace(char, '-')
    driver.save_screenshot(path.replace("//","/"))
    return screenshot_name
#>



def submitted_jobs(job_id: str, title: str, company: str, work_location: str, work_style: str, description: str, experience_required: int | Literal['Unknown', 'Error in extraction'], 
                   skills: list[str] | Literal['In Development'], hr_name: str | Literal['Unknown'], hr_link: str | Literal['Unknown'], resume: str, 
                   reposted: bool, date_listed: datetime | Literal['Unknown'], date_applied:  datetime | Literal['Pending'], job_link: str, application_link: str, 
                   questions_list: set | None, connect_request: Literal['In Development']) -> None:
    '''
    Function to create or update the Applied jobs CSV file, once the application is submitted successfully
    '''
    try:
        with open(file_name, mode='a', newline='', encoding='utf-8') as csv_file:
            fieldnames = ['Job ID', 'Title', 'Company', 'Work Location', 'Work Style', 'About Job', 'Experience required', 'Skills required', 'HR Name', 'HR Link', 'Resume', 'Re-posted', 'Date Posted', 'Date Applied', 'Job Link', 'External Job link', 'Questions Found', 'Connect Request']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            if csv_file.tell() == 0: writer.writeheader()
            writer.writerow({'Job ID':truncate_for_csv(job_id), 'Title':truncate_for_csv(title), 'Company':truncate_for_csv(company), 'Work Location':truncate_for_csv(work_location), 'Work Style':truncate_for_csv(work_style), 
                            'About Job':truncate_for_csv(description), 'Experience required': truncate_for_csv(experience_required), 'Skills required':truncate_for_csv(skills), 
                                'HR Name':truncate_for_csv(hr_name), 'HR Link':truncate_for_csv(hr_link), 'Resume':truncate_for_csv(resume), 'Re-posted':truncate_for_csv(reposted), 
                                'Date Posted':truncate_for_csv(date_listed), 'Date Applied':truncate_for_csv(date_applied), 'Job Link':truncate_for_csv(job_link), 
                                'External Job link':truncate_for_csv(application_link), 'Questions Found':truncate_for_csv(questions_list), 'Connect Request':truncate_for_csv(connect_request)})
        csv_file.close()
    except Exception as e:
        print_lg("Failed to update submitted jobs list!", e)
        ui_alert("Failed Logging", "Failed to update the excel of applied jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file")



# Function to discard the job application
def discard_job() -> None:
    actions.send_keys(Keys.ESCAPE).perform()
    wait_span_click(driver, 'Discard', 2)






# Function to check if LinkedIn daily limit has been reached
def check_daily_limit() -> bool:
    global dailyEasyApplyLimitReached
    if is_career_ops_mode():
        return False
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        limit_phrases = [
            "exceeded the daily application limit",
            "limit daily submissions",
            "apply tomorrow",
            "límite de solicitudes",
            "solicitar mañana",
            "vuelve a solicitar",
            "limitamos el número de solicitudes"
        ]
        if any(phrase.lower() in page_text for phrase in limit_phrases):
            print_lg("\n###############  Daily application limit for Easy Apply is reached!  ###############\n")
            ui_alert("Daily Limit Reached", "LinkedIn is limiting your daily submissions to prevent bots.\nThe bot will now stop. Save this job and apply tomorrow.")
            dailyEasyApplyLimitReached = True
            return True
    except:
        pass
    return False


# Function to apply to jobs
def apply_to_jobs(search_terms: list[str]) -> None:
    locations = search_location if isinstance(search_location, (list, tuple)) else [search_location]
    for location in locations:
        _apply_to_jobs_for_location(search_terms, location)
        if dailyEasyApplyLimitReached and not is_career_ops_mode(): return


# Function to apply to jobs for a specific location
def _apply_to_jobs_for_location(search_terms: list[str], location: str) -> None:
    applied_jobs = get_applied_job_ids()
    rejected_jobs = set()
    blacklisted_companies = set()
    global current_city, failed_count, skip_count, easy_applied_count, external_jobs_count, tabs_count, pause_before_submit, pause_at_failed_question, useNewResume, top_manual_jobs
    current_city = current_city.strip()
    top_manual_jobs.clear()

    if randomize_search_order:  shuffle(search_terms)
    for searchTerm in search_terms:
        ui_pause_check()
        status_prefix = "Career-Ops: Searching" if is_career_ops_mode() else "Searching"
        status_details = f"'{searchTerm}' in '{location}' ({len(top_manual_jobs)}/5 matches)" if is_career_ops_mode() else f"'{searchTerm}' in '{location}'"
        ui_update_status(status_prefix, status_details)
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={quote(searchTerm)}&location={quote(location.strip())}" if location and location.strip() else f"https://www.linkedin.com/jobs/search/?keywords={quote(searchTerm)}"
        print_lg("\n________________________________________________________________________________________________________________________\n")
        print_lg(f'\n>>>> Now searching for "{searchTerm}" in "{location}" <<<<\n')

        # Navigate directly to the search URL (Portmaster firewall disabled)
        page_loaded = False
        print_lg(f"Navigating directly to search URL...")
        try:
            driver.get(search_url)
            buffer(5)
            
            current_url = driver.current_url
            print_lg(f"After navigation - URL: {current_url}")
            
            if "search" in current_url.lower() and "keyword" in current_url.lower():
                page_loaded = True
                print_lg("Search navigation worked normally!")
            else:
                print_lg("Direct navigation failed. URL did not change to search results.")
                
        except Exception as e:
            print_lg(f"Navigation failed: {e}")
            page_loaded = False
        
        if not page_loaded:
            print_lg(f"SKIPPING search term '{searchTerm}' - navigation failed.")
            continue

        apply_filters(location)
        if check_daily_limit():
            return

        current_count = 0
        try:
            while current_count < switch_number:
                ui_pause_check()
                # Wait until job listings are loaded
                wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[@data-occludable-job-id]")))

                pagination_element, current_page = get_page_info()

                # Find all job listings in current page
                buffer(3)
                job_listings = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")  

            
                for job in job_listings:
                    ui_pause_check()
                    if keep_screen_awake: pyautogui.press('shiftright')
                    if current_count >= switch_number: break
                    print_lg("\n-@-\n")

                    job_id,title,company,work_location,work_style,skip = get_job_main_details(job, blacklisted_companies, rejected_jobs)

                    if skip:
                        if is_career_ops_mode():
                            ui_update_status("Career-Ops: Skipping Job", f"{title} at {company} (Already Applied / Blacklisted) ({len(top_manual_jobs)}/5 matches)")
                        continue

                    # Job focus filter — skip if title doesn't match user's focus areas
                    if not is_job_relevant(title, work_style):
                        _kw_preview = " / ".join((primary_focus_keywords[:3] if primary_focus_keywords else []) + (secondary_focus_keywords[:2] if secondary_focus_keywords else []))
                        print_lg(f'Skipping "{title}" — not in focus areas ({_kw_preview or "none configured"})')
                        if is_career_ops_mode():
                            ui_update_status("Career-Ops: Skipping Job", f"{title} at {company} (Not in focus areas) ({len(top_manual_jobs)}/5 matches)")
                        skip_count += 1
                        continue

                    status_prefix = "Career-Ops: Processing" if is_career_ops_mode() else "Processing Job"
                    status_details = f"{title} at {company} ({len(top_manual_jobs)}/5 matches)" if is_career_ops_mode() else f"{title} at {company}"
                    ui_update_status(status_prefix, status_details)
                    if check_daily_limit():
                        return

                    # Redundant fail safe check for applied jobs!
                    try:
                        if job_id in applied_jobs or find_by_class(driver, "jobs-s-apply__application-link", 2):
                            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
                            if is_career_ops_mode():
                                ui_update_status("Career-Ops: Skipping Job", f"{title} at {company} (Already Applied) ({len(top_manual_jobs)}/5 matches)")
                            continue
                    except Exception as e:
                        print_lg(f'Trying to Apply to "{title} | {company}" job. Job ID: {job_id}')

                    job_link = "https://www.linkedin.com/jobs/view/"+job_id
                    application_link = "Easy Applied"
                    date_applied = "Pending"
                    hr_link = "Unknown"
                    hr_name = "Unknown"
                    connect_request = "In Development" # Still in development
                    date_listed = "Unknown"
                    skills = "Needs an AI" # Still in development
                    resume = "Pending"
                    reposted = False
                    questions_list = None
                    screenshot_name = "Not Available"

                    try:
                        rejected_jobs, blacklisted_companies, jobs_top_card = check_blacklist(rejected_jobs,job_id,company,blacklisted_companies)
                    except ValueError as e:
                        print_lg(e, 'Skipping this job!\n')
                        if is_career_ops_mode():
                            ui_update_status("Career-Ops: Skipping Job", f"{title} at {company} (Blacklist Match: {str(e)}) ({len(top_manual_jobs)}/5 matches)")
                        failed_job(job_id, job_link, resume, date_listed, "Found Blacklisted words in About Company", e, "Skipped", screenshot_name)
                        skip_count += 1
                        continue
                    except Exception as e:
                        print_lg("Failed to scroll to About Company!")
                        # print_lg(e)



                    # Hiring Manager info
                    try:
                        hr_info_card = WebDriverWait(driver,2).until(EC.presence_of_element_located((By.CLASS_NAME, "hirer-card__hirer-information")))
                        hr_link = hr_info_card.find_element(By.TAG_NAME, "a").get_attribute("href")
                        hr_name = hr_info_card.find_element(By.TAG_NAME, "span").text
                        # if connect_hr:
                        #     driver.switch_to.new_window('tab')
                        #     driver.get(hr_link)
                        #     wait_span_click("More")
                        #     wait_span_click("Connect")
                        #     wait_span_click("Add a note")
                        #     message_box = driver.find_element(By.XPATH, "//textarea")
                        #     message_box.send_keys(connect_request_message)
                        #     if close_tabs: driver.close()
                        #     driver.switch_to.window(linkedIn_tab) 
                        # def message_hr(hr_info_card):
                        #     if not hr_info_card: return False
                        #     hr_info_card.find_element(By.XPATH, ".//span[normalize-space()='Message']").click()
                        #     message_box = driver.find_element(By.XPATH, "//div[@aria-label='Write a message…']")
                        #     message_box.send_keys()
                        #     try_xp(driver, "//button[normalize-space()='Send']")        
                    except Exception as e:
                        print_lg(f'HR info was not given for "{title}" with Job ID: {job_id}!')
                        # print_lg(e)


                    # Calculation of date posted
                    try:
                        # try: time_posted_text = find_by_class(driver, "jobs-unified-top-card__posted-date", 2).text
                        # except: 
                        time_posted_text = jobs_top_card.find_element(By.XPATH, './/span[contains(normalize-space(), " ago")]').text
                        print("Time Posted: " + time_posted_text)
                        if time_posted_text.__contains__("Reposted"):
                            reposted = True
                            time_posted_text = time_posted_text.replace("Reposted", "")
                        date_listed = calculate_date_posted(time_posted_text.strip())
                    except Exception as e:
                        print_lg("Failed to calculate the date posted!",e)


                    description, experience_required, skip, reason, message = get_job_description()
                    ui_pause_check()
                    if skip:
                        print_lg(message)
                        if is_career_ops_mode():
                            ui_update_status("Career-Ops: Skipping Job", f"{title} at {company} ({reason}) ({len(top_manual_jobs)}/5 matches)")
                        failed_job(job_id, job_link, resume, date_listed, reason, message, "Skipped", screenshot_name)
                        rejected_jobs.add(job_id)
                        skip_count += 1
                        continue

                    current_eval_score = 5
                    eval_reason = "No reason provided by AI."
                    
                    if use_AI and description != "Unknown":
                        ##> ------ AI Pre-screening Feature ------
                        try:
                            if is_career_ops_mode():
                                ui_update_status("Career-Ops: AI Pre-screening", f"{title} at {company} ({len(top_manual_jobs)}/5 matches)")
                            print_lg("Pre-screening job requirements with AI...")
                            eval_result = {"meets_requirements": True, "reason": "Default"}
                            
                            if ai_provider.lower() in ("openai", "groq"):
                                eval_result = ai_evaluate_job(aiClient, description, user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                eval_result = deepseek_evaluate_job(aiClient, description, user_information_all)
                            elif ai_provider.lower() == "gemini":
                                eval_result = gemini_evaluate_job(aiClient, description, user_information_all)
                                
                            if isinstance(eval_result, dict) and not eval_result.get("meets_requirements", True):
                                reason = eval_result.get("reason", "AI determined user does not meet core requirements.")
                                message = f'\n{description}\n\nAI Pre-screening failed: {reason}. Skipping this job!\n'
                                print_lg(message)
                                if is_career_ops_mode():
                                    ui_update_status("Career-Ops: Skipping Job", f"{title} at {company} (AI Pre-screening: {reason}) ({len(top_manual_jobs)}/5 matches)")
                                failed_job(job_id, job_link, resume, date_listed, "AI Pre-screening Rejected", message, "Skipped", screenshot_name)
                                rejected_jobs.add(job_id)
                                skip_count += 1
                                continue
                            else:
                                print_lg("AI Pre-screening passed. Proceeding with application...")
                                if isinstance(eval_result, dict):
                                    try:
                                        current_eval_score = int(eval_result.get("score", 5))
                                    except:
                                        pass
                                    eval_reason = eval_result.get("reason", "AI pre-screening passed.")
                        except Exception as e:
                            print_lg("Failed to evaluate job with AI:", e)
                        ##<

                        ##> ------ Yang Li : MARKYangL - Feature ------
                        try:
                            if ai_provider.lower() in ("openai", "groq"):
                                skills = ai_extract_skills(aiClient, description)
                            elif ai_provider.lower() == "deepseek":
                                skills = deepseek_extract_skills(aiClient, description)
                            elif ai_provider.lower() == "gemini":
                                skills = gemini_extract_skills(aiClient, description)
                            else:
                                skills = "In Development"
                            print_lg(f"Extracted skills using {ai_provider} AI")
                        except Exception as e:
                            print_lg("Failed to extract skills:", e)
                            skills = "Error extracting skills"
                        ##<

                    ui_pause_check()

                    if is_career_ops_mode():
                        print_lg(f"[Career-Ops Mode] Skipping auto-apply for '{title} | {company}' and collecting for manual review.")
                        add_to_manual_jobs(job_id, title, company, current_eval_score, f"Career-Ops Match: {eval_reason}")
                        current_count += 1
                        external_jobs_count += 1
                        applied_jobs.add(job_id)
                        ui_update_status("Collected Career-Ops Job", f"{title} at {company} (Score: {current_eval_score}) ({len(top_manual_jobs)}/5 matches)")
                        
                        if not check_and_prompt_career_ops():
                            return
                        continue

                    uploaded = False
                    # Case 1: Easy Apply Button
                    # First try the classic button with "Easy" in aria-label
                    is_easy_apply = try_xp(driver, ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3') and contains(@aria-label, 'Easy')]")
                    # Fallback 1: check if apply link contains Easy Apply URL pattern
                    if not is_easy_apply:
                        try:
                            apply_link_el = driver.find_element(By.XPATH, ".//a[contains(@href, 'openSDUIApplyFlow=true')]")
                            if apply_link_el:
                                apply_link_el.click()
                                is_easy_apply = True
                                print_lg("Detected Easy Apply via URL pattern (openSDUIApplyFlow)")
                        except:
                            pass
                    # Fallback 2: click any Apply button and check if Easy Apply modal appears
                    if not is_easy_apply:
                        try:
                            apply_btn = driver.find_element(By.XPATH, ".//button[contains(@class,'jobs-apply-button')]")
                            if apply_btn:
                                tabs_before = len(driver.window_handles)
                                apply_btn.click()
                                buffer(click_gap)
                                tabs_after = len(driver.window_handles)
                                if tabs_after > tabs_before:
                                    # New tab opened — external apply, close it and go back
                                    driver.switch_to.window(driver.window_handles[-1])
                                    if close_tabs and driver.current_window_handle != linkedIn_tab: driver.close()
                                    driver.switch_to.window(linkedIn_tab)
                                    print_lg("External apply detected via new tab, skipping")
                                else:
                                    try:
                                        find_by_class(driver, "jobs-easy-apply-modal")
                                        is_easy_apply = True
                                        print_lg("Detected Easy Apply via modal appearance after click")
                                    except:
                                        # Modal didn't appear — dismiss
                                        try: actions.send_keys(Keys.ESCAPE).perform()
                                        except: pass
                        except:
                            pass
                    if is_easy_apply:
                        try: 
                            if is_career_ops_mode():
                                raise CareerOpsActivatedException()
                            try:
                                errored = ""
                                modal = find_by_class(driver, "jobs-easy-apply-modal")
                                wait_span_click(modal, "Next", 1)
                                # if description != "Unknown":
                                #     resume = create_custom_resume(description)
                                resume = "Previous resume"
                                next_button = True
                                questions_list = set()
                                next_counter = 0
                                while next_button:
                                    if is_career_ops_mode():
                                        raise CareerOpsActivatedException()
                                    next_counter += 1
                                    if next_counter >= 15: 
                                        if pause_at_failed_question:
                                            screenshot(driver, job_id, "Needed manual intervention for failed question")
                                            ui_alert("Help Needed", "Couldn't answer one or more questions.\nPlease click \"Continue\" once done.\nDO NOT CLICK Back, Next or Review button in LinkedIn.\n\n\n\n\nYou can turn off \"Pause at failed question\" setting in config.py")
                                            next_counter = 1
                                            continue
                                        if questions_list: print_lg("Stuck for one or some of the following questions...", questions_list)
                                        screenshot_name = screenshot(driver, job_id, "Failed at questions")
                                        errored = "stuck"
                                        raise Exception("Seems like stuck in a continuous loop of next, probably because of new questions.")
                                    questions_list = answer_questions(modal, questions_list, work_location, job_description=description)
                                    if useNewResume and not uploaded: uploaded, resume = upload_resume(modal, default_resume_path)
                                    try: next_button = modal.find_element(By.XPATH, './/button[contains(normalize-space(.), "Review") or contains(@aria-label, "Review")]') 
                                    except NoSuchElementException:  next_button = modal.find_element(By.XPATH, './/button[contains(normalize-space(.), "Next") or contains(@aria-label, "next") or contains(@aria-label, "Next")]')
                                    try: 
                                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                                        time.sleep(0.5)
                                        try: next_button.click()
                                        except Exception: driver.execute_script("arguments[0].click();", next_button)
                                    except Exception:
                                        try:
                                            time.sleep(1)
                                            try: next_button = modal.find_element(By.XPATH, './/button[contains(normalize-space(.), "Review") or contains(@aria-label, "Review")]') 
                                            except: next_button = modal.find_element(By.XPATH, './/button[contains(normalize-space(.), "Next") or contains(@aria-label, "next") or contains(@aria-label, "Next")]')
                                            driver.execute_script("arguments[0].click();", next_button)
                                        except Exception as e:
                                            print_lg(f"Failed to click Next/Review: {e}")
                                            break
                                    buffer(click_gap)

                            except NoSuchElementException: errored = "nose"
                            finally:
                                if is_career_ops_mode():
                                    pass
                                else:
                                    if questions_list and errored != "stuck": 
                                        print_lg("Answered the following questions...", questions_list)
                                        print("\n\n" + "\n".join(str(question) for question in questions_list) + "\n\n")
                                    wait_span_click(driver, "Review", 1, scrollTop=True)
                                    cur_pause_before_submit = pause_before_submit
                                    if errored != "stuck" and cur_pause_before_submit:
                                        decision = ui_confirm("Confirm your information", '1. Please verify your information.\n2. If you edited something, please return to this final screen.\n3. DO NOT CLICK "Submit Application".\n\n\n\n\nYou can turn off "Pause before submit" setting in config.py\nTo TEMPORARILY disable pausing, click "Disable Pause"', ["Disable Pause", "Discard Application", "Submit Application"])
                                        if decision == "Discard Application": raise Exception("Job application discarded by user!")
                                        pause_before_submit = False if "Disable Pause" == decision else True
                                        # try_xp(modal, ".//span[normalize-space(.)='Review']")
                                    follow_company(modal)
                                    if wait_span_click(driver, "Submit application", 5, scrollTop=True) or wait_span_click(driver, "Submit", 3, scrollTop=True): 
                                        date_applied = datetime.now()
                                        if not wait_span_click(driver, "Done", 2): actions.send_keys(Keys.ESCAPE).perform()
                                    elif errored != "stuck" and cur_pause_before_submit and "Yes" in ui_confirm("Failed to find Submit Application!", "You submitted the application, didn't you?", ["Yes", "No"]):
                                        date_applied = datetime.now()
                                        wait_span_click(driver, "Done", 2)
                                    else:
                                        print_lg("Since, Submit Application failed, discarding the job application...")
                                        # if screenshot_name == "Not Available":  screenshot_name = screenshot(driver, job_id, "Failed to click Submit application")
                                        # else:   screenshot_name = [screenshot_name, screenshot(driver, job_id, "Failed to click Submit application")]
                                        if errored == "nose": raise Exception("Failed to click Submit application 😑")


                        except CareerOpsActivatedException:
                            print_lg("[Career-Ops Mode] Activated during Easy Apply. Aborting auto-apply and collecting job.")
                            discard_job()
                            add_to_manual_jobs(job_id, title, company, current_eval_score, f"Career-Ops Match: {eval_reason}")
                            applied_jobs.add(job_id)
                            current_count += 1
                            external_jobs_count += 1
                            ui_update_status("Collected Career-Ops Job", f"{title} at {company} (Score: {current_eval_score}) ({len(top_manual_jobs)}/5 matches)")
                            
                            if not check_and_prompt_career_ops():
                                return
                            continue

                        except Exception as e:
                            print_lg("Failed to Easy apply!")
                            add_to_manual_jobs(job_id, title, company, current_eval_score, f"Easy Apply failed: {eval_reason}")
                            # print_lg(e)
                            critical_error_log("Somewhere in Easy Apply process",e)
                            failed_job(job_id, job_link, resume, date_listed, "Problem in Easy Applying", e, application_link, screenshot_name)
                            failed_count += 1
                            discard_job()
                            if check_daily_limit():
                                return
                            continue
                    else:
                        # Case 2: Apply externally
                        add_to_manual_jobs(job_id, title, company, current_eval_score, f"External Apply: {eval_reason}")
                        skip, application_link, tabs_count = external_apply(pagination_element, job_id, job_link, resume, date_listed, application_link, screenshot_name)
                        if dailyEasyApplyLimitReached and not is_career_ops_mode():
                            print_lg("\n###############  Daily application limit for Easy Apply is reached!  ###############\n")
                            return
                        if skip: continue

                    submitted_jobs(job_id, title, company, work_location, work_style, description, experience_required, skills, hr_name, hr_link, resume, reposted, date_listed, date_applied, job_link, application_link, questions_list, connect_request)
                    if uploaded:   useNewResume = False

                    print_lg(f'Successfully saved "{title} | {company}" job. Job ID: {job_id} info')
                    current_count += 1
                    if application_link == "Easy Applied": easy_applied_count += 1
                    else:   external_jobs_count += 1
                    applied_jobs.add(job_id)



                # Switching to next page
                if pagination_element == None:
                    print_lg("Couldn't find pagination element, probably at the end page of results!")
                    break
                try:
                    pagination_element.find_element(By.XPATH, f"//button[@aria-label='Page {current_page+1}']").click()
                    print_lg(f"\n>-> Now on Page {current_page+1} \n")
                except NoSuchElementException:
                    print_lg(f"\n>-> Didn't find Page {current_page+1}. Probably at the end page of results!\n")
                    break

        except (NoSuchWindowException, WebDriverException) as e:
            print_lg("Browser window closed or session is invalid. Ending application process.", e)
            raise e # Re-raise to be caught by main
        except Exception as e:
            print_lg("Failed to find Job listings!")
            critical_error_log("In Applier", e)
            try:
                print_lg(driver.page_source, pretty=True)
            except Exception as page_source_error:
                print_lg(f"Failed to get page source, browser might have crashed. {page_source_error}")
            # print_lg(e)

        
def interruptible_sleep(seconds: float):
    initial_mode = is_career_ops_mode()
    steps = int(seconds * 10)
    for _ in range(steps):
        time.sleep(0.1)
        ui_pause_check()
        if is_career_ops_mode() != initial_mode:
            break


def run_career_ops_cycle():
    import subprocess
    import re
    import os

    global top_manual_jobs

    base_dir = os.path.dirname(os.path.abspath(__file__))
    career_ops_dir = os.path.abspath(os.path.join(base_dir, "../career-ops"))

    print_lg(f"[Career-Ops] Path to career-ops project: {career_ops_dir}")

    # 1. Run scan.mjs
    ui_update_status("Career-Ops: Scanning", "Scanning external portals via career-ops...")
    print_lg("[Career-Ops] Running scan.mjs...")

    try:
        process = subprocess.Popen(
            ["node", "scan.mjs"],
            cwd=career_ops_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8"
        )

        while True:
            line = process.stdout.readline()
            if not line:
                break
            stripped = line.strip()
            if stripped:
                print_lg(f"[Career-Ops Scan] {stripped}")
                if stripped.startswith("+ "):
                    ui_update_status("Career-Ops: Found Job", stripped[2:])
                elif "Scanning" in stripped or "Fetching" in stripped:
                    ui_update_status("Career-Ops: Scanning", stripped)

        process.wait()
        print_lg(f"[Career-Ops] Scan completed with exit code: {process.returncode}")
    except Exception as e:
        print_lg(f"[Career-Ops] Error executing scan.mjs: {e}")
        ui_update_status("Career-Ops: Scan Error", str(e))
        interruptible_sleep(5)
        return

    # 2. Read pipeline.md
    pipeline_path = os.path.join(career_ops_dir, "data/pipeline.md")
    if not os.path.exists(pipeline_path):
        print_lg(f"[Career-Ops] pipeline.md not found at: {pipeline_path}")
        ui_update_status("Career-Ops: Error", "pipeline.md not found")
        interruptible_sleep(5)
        return

    with open(pipeline_path, "r", encoding="utf-8") as f:
        pipeline_content = f.read()

    parts = re.split(r'^##\s+', pipeline_content, flags=re.MULTILINE)
    pending_section = ""
    processed_section = ""

    for part in parts:
        if part.startswith("Pendientes"):
            pending_section = part
        elif part.startswith("Procesadas") or part.startswith("Processed"):
            processed_section = part

    lines = pending_section.split("\n")
    new_pending_lines = []
    jobs_to_process = []

    for line in lines:
        match = re.match(r'^\s*-\s*\[\s*\]\s*(https?:\/\/\S+)(?:\s*\|\s*([^|]+)\s*\|\s*([^|]+))?', line)
        if match:
            url = match.group(1).strip()
            company = match.group(2).strip() if match.group(2) else "Unknown"
            title = match.group(3).strip() if match.group(3) else "Unknown Job"
            jobs_to_process.append({
                "line": line,
                "url": url,
                "company": company,
                "title": title
            })
        else:
            if line.strip() and not line.startswith("Pendientes"):
                new_pending_lines.append(line)

    if not jobs_to_process:
        print_lg("[Career-Ops] No pending jobs to evaluate.")
        ui_update_status("Career-Ops: Idle", "No pending jobs in pipeline.md")
        if len(top_manual_jobs) > 0:
            prompt_open_remaining()
        interruptible_sleep(10)
        return

    print_lg(f"[Career-Ops] Found {len(jobs_to_process)} pending jobs to evaluate.")

    # 3. Process each pending job
    for i, job in enumerate(jobs_to_process):
        if not is_career_ops_mode():
            print_lg("[Career-Ops] Mode deactivated during evaluation. Stopping loop.")
            save_remaining_pipeline(pipeline_path, new_pending_lines, jobs_to_process[i:], processed_section)
            return

        ui_update_status("Career-Ops: Fetching", f"{job['title']} at {job['company']}")
        print_lg(f"[Career-Ops] Loading page: {job['url']}")

        jd_text = ""
        try:
            driver.get(job['url'])
            sleep(3)
            ui_pause_check()
            body_elem = driver.find_element(By.TAG_NAME, "body")
            jd_text = body_elem.text.strip()
        except Exception as e:
            print_lg(f"[Career-Ops] Failed to fetch content via Selenium for {job['url']}: {e}")
            new_pending_lines.append(f"- [!] {job['url']} | {job['company']} | {job['title']} — Error: Scrape failed ({str(e)})")
            save_remaining_pipeline(pipeline_path, new_pending_lines, jobs_to_process[i+1:], processed_section)
            continue

        if not jd_text:
            print_lg(f"[Career-Ops] Page text is empty for {job['url']}. Skipping.")
            new_pending_lines.append(f"- [!] {job['url']} | {job['company']} | {job['title']} — Error: Empty content")
            save_remaining_pipeline(pipeline_path, new_pending_lines, jobs_to_process[i+1:], processed_section)
            continue

        jds_dir = os.path.join(career_ops_dir, "jds")
        os.makedirs(jds_dir, exist_ok=True)
        temp_jd_file = os.path.join(jds_dir, "temp_jd.txt")
        with open(temp_jd_file, "w", encoding="utf-8") as tf:
            tf.write(jd_text)

        ui_update_status("Career-Ops: AI Eval", f"{job['title']} at {job['company']}")
        print_lg(f"[Career-Ops] Evaluating job description...")

        eval_score = 0.0
        eval_legitimacy = "unknown"
        eval_archetype = "unknown"
        eval_report_file = ""

        try:
            eval_res = subprocess.run(
                ["node", "gemini-eval.mjs", "--file", "jds/temp_jd.txt"],
                cwd=career_ops_dir,
                capture_output=True,
                text=True,
                encoding="utf-8"
            )
            stdout_content = eval_res.stdout
            print_lg(stdout_content)

            summary_match = re.search(r'---SCORE_SUMMARY---(.*?)---END_SUMMARY---', stdout_content, re.DOTALL)
            if summary_match:
                summary_text = summary_match.group(1)
                for s_line in summary_text.split("\n"):
                    s_line = s_line.strip()
                    if s_line.startswith("SCORE:"):
                        try:
                            eval_score = float(s_line.split(":", 1)[1].strip())
                        except:
                            pass
                    elif s_line.startswith("LEGITIMACY:"):
                        eval_legitimacy = s_line.split(":", 1)[1].strip()
                    elif s_line.startswith("ARCHETYPE:"):
                        eval_archetype = s_line.split(":", 1)[1].strip()

            report_match = re.search(r'reports/\d{3}-[a-zA-Z0-9\-]+\-\d{4}-\d{2}-\d{2}\.md', stdout_content)
            if report_match:
                eval_report_file = report_match.group(0)

        except Exception as eval_ex:
            print_lg(f"[Career-Ops] Subprocess gemini-eval failed for {job['url']}: {eval_ex}")
            new_pending_lines.append(f"- [!] {job['url']} | {job['company']} | {job['title']} — AI Eval error: {str(eval_ex)}")
            save_remaining_pipeline(pipeline_path, new_pending_lines, jobs_to_process[i+1:], processed_section)
            continue

        report_num_str = ""
        if eval_report_file:
            base_rep = os.path.basename(eval_report_file)
            rep_num = base_rep.split("-")[0]
            report_num_str = f"#{rep_num} | "

        processed_line = f"- [x] {report_num_str}{job['url']} | {job['company']} | {job['title']} | {eval_score}/5 | PDF ❌"

        processed_lines_list = processed_section.split("\n")
        processed_lines_list = [l for l in processed_lines_list if l.strip() and not l.startswith("Procesadas") and not l.startswith("Processed")]
        processed_lines_list.insert(0, processed_line)
        processed_section = "Procesadas\n\n" + "\n".join(processed_lines_list)

        save_remaining_pipeline(pipeline_path, new_pending_lines, jobs_to_process[i+1:], processed_section)

        try:
            subprocess.run(["node", "merge-tracker.mjs"], cwd=career_ops_dir, capture_output=True)
        except Exception as merge_ex:
            print_lg(f"[Career-Ops] Failed to run merge-tracker: {merge_ex}")

        if eval_score >= 4.0:
            add_to_manual_jobs(
                job_id=job['url'].split("/")[-1] or "external",
                title=job['title'],
                company=job['company'],
                score=eval_score,
                reason=f"Archetype: {eval_archetype} | Legitimacy: {eval_legitimacy}",
                link=job['url']
            )
            ui_update_status("Collected Career-Ops Job", f"{job['title']} at {job['company']} (Score: {eval_score}) ({len(top_manual_jobs)}/5 matches)")

        if not check_and_prompt_career_ops():
            break

    if len(top_manual_jobs) > 0:
        prompt_open_remaining()


def save_remaining_pipeline(pipeline_path, new_pending_lines, remaining_jobs, processed_section):
    new_content = "## Pendientes\n\n"
    for l in new_pending_lines:
        new_content += l + "\n"
    for r_job in remaining_jobs:
        new_content += r_job['line'] + "\n"

    new_content += f"\n## {processed_section.strip()}\n"

    with open(pipeline_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def prompt_open_remaining():
    global top_manual_jobs
    decision = ui_confirm("Career-Ops", f"Se completó la evaluación. ¿Quieres abrir las {len(top_manual_jobs)} ofertas encontradas para aplicar?", ["Yes", "No"])
    if decision == "Yes":
        for job in top_manual_jobs:
            try:
                driver.execute_script("window.open(arguments[0], '_blank');", job['link'])
            except Exception as ex:
                print_lg(f"Failed to open link: {job['link']}", ex)
        applied_decision = "No"
        while applied_decision != "Yes":
            applied_decision = ui_confirm("Career-Ops", "¿Ya aplicaste?", ["Yes", "No"])
            if applied_decision == "No":
                time.sleep(2)
                ui_pause_check()
    top_manual_jobs.clear()


def run(total_runs: int) -> int:
    if dailyEasyApplyLimitReached and not is_career_ops_mode():
        return total_runs
    print_lg("\n########################################################################################################################\n")
    print_lg(f"Date and Time: {datetime.now()}")
    print_lg(f"Cycle number: {total_runs}")

    if is_career_ops_mode():
        run_career_ops_cycle()
    else:
        print_lg(f"Currently looking for jobs posted within '{date_posted}' and sorting them by '{sort_by}'")
        apply_to_jobs(search_terms)

    print_lg("########################################################################################################################\n")
    if not dailyEasyApplyLimitReached and not is_career_ops_mode():
        print_lg("Sleeping for 10 min...")
        interruptible_sleep(300)
        print_lg("Few more min... Gonna start with in next 5 min...")
        interruptible_sleep(300)
    buffer(3)
    return total_runs + 1



chatGPT_tab = False
linkedIn_tab = False

def main() -> None:
    total_runs = 1
    global driver
    try:
        global linkedIn_tab, tabs_count, useNewResume, aiClient
        alert_title = "Error Occurred. Closing Browser!"

        # Reload config from disk — wizard may have written values after module load
        import importlib, sys as _sys
        for _mod_name in ['config.personals', 'config.questions', 'config.search',
                          'config.secrets', 'config.settings']:
            if _mod_name in _sys.modules:
                _m = importlib.reload(_sys.modules[_mod_name])
                for _k, _v in vars(_m).items():
                    if not _k.startswith('_'):
                        globals()[_k] = _v
        global first_name, middle_name, last_name, full_name
        first_name  = first_name.strip()
        middle_name = middle_name.strip()
        last_name   = last_name.strip()
        full_name   = (first_name + " " + middle_name + " " + last_name
                       if middle_name else first_name + " " + last_name)

        validate_config()
        
        if not os.path.exists(default_resume_path):
            ui_alert("Missing Resume", 'Your default resume "{}" is missing! Please update it\'s folder path "default_resume_path" in config.py\n\nOR\n\nAdd a resume with exact name and path (check for spelling mistakes including cases).\n\n\nFor now the bot will continue using your previous upload from LinkedIn!'.format(default_resume_path))
            useNewResume = False
        
        # Login to LinkedIn
        ui_update_status("Logging In", "Navigating to LinkedIn login page...")
        tabs_count = len(driver.window_handles)
        driver.get("https://www.linkedin.com/login")
        sleep(5)
        if not is_logged_in_LN(): login_LN()
        
        linkedIn_tab = driver.current_window_handle

        # # Login to ChatGPT in a new tab for resume customization
        # if use_resume_generator:
        #     try:
        #         driver.switch_to.new_window('tab')
        #         driver.get("https://chat.openai.com/")
        #         if not is_logged_in_GPT(): login_GPT()
        #         open_resume_chat()
        #         global chatGPT_tab
        #         chatGPT_tab = driver.current_window_handle
        #     except Exception as e:
        #         print_lg("Opening OpenAI chatGPT tab failed!")
        if use_AI:
            if ai_provider in ("openai", "groq"):
                aiClient = ai_create_openai_client()
            ##> ------ Yang Li : MARKYangL - Feature ------
            # Create DeepSeek client
            elif ai_provider == "deepseek":
                aiClient = deepseek_create_client()
            elif ai_provider == "gemini":
                aiClient = gemini_create_client()
            ##<

            try:
                about_company_for_ai = " ".join([word for word in (first_name+" "+last_name).split() if len(word) > 3])
                print_lg(f"Extracted about company info for AI: '{about_company_for_ai}'")
            except Exception as e:
                print_lg("Failed to extract about company info!", e)
        
        # Start applying to jobs
        driver.switch_to.window(linkedIn_tab)
        total_runs = run(total_runs)
        while(run_non_stop):
            if cycle_date_posted:
                date_options = ["Any time", "Past month", "Past week", "Past 24 hours"]
                global date_posted
                date_posted = date_options[date_options.index(date_posted)+1 if date_options.index(date_posted)+1 > len(date_options) else -1] if stop_date_cycle_at_24hr else date_options[0 if date_options.index(date_posted)+1 >= len(date_options) else date_options.index(date_posted)+1]
            if alternate_sortby:
                global sort_by
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
                total_runs = run(total_runs)
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
            total_runs = run(total_runs)
            if dailyEasyApplyLimitReached and not is_career_ops_mode():
                break
        

    except (NoSuchWindowException, WebDriverException) as e:
        print_lg("Browser window closed or session is invalid. Exiting.", e)
    except Exception as e:
        critical_error_log("In Applier Main", e)
        ui_alert(alert_title, str(e))
    finally:
        summary = "Total runs: {}\nJobs Easy Applied: {}\nExternal job links collected: {}\nTotal applied or collected: {}\nFailed jobs: {}\nIrrelevant jobs skipped: {}\n".format(total_runs,easy_applied_count,external_jobs_count,easy_applied_count + external_jobs_count,failed_count,skip_count)
        print_lg(summary)
        print_lg("\n\nTotal runs:                     {}".format(total_runs))
        print_lg("Jobs Easy Applied:              {}".format(easy_applied_count))
        print_lg("External job links collected:   {}".format(external_jobs_count))
        print_lg("                              ----------")
        print_lg("Total applied or collected:     {}".format(easy_applied_count + external_jobs_count))
        print_lg("\nFailed jobs:                    {}".format(failed_count))
        print_lg("Irrelevant jobs skipped:        {}\n".format(skip_count))
        if randomly_answered_questions: print_lg("\n\nQuestions randomly answered:\n  {}  \n\n".format(";\n".join(str(question) for question in randomly_answered_questions)))
        quotes = choice([
            "Success is not final, failure is not fatal, It is the courage to continue that counts. - Winston Churchill",
            "Believe in yourself and all that you are. Know that there is something inside you that is greater than any obstacle. - Christian D. Larson",
            "Every job is a self-portrait of the person who does it. Autograph your work with excellence. - Jessica Guidobono",
            "The only way to do great work is to love what you do. If you haven't found it yet, keep looking. Don't settle. - Steve Jobs",
            "Opportunities don't happen, you create them. - Chris Grosser",
            "The road to success and the road to failure are almost exactly the same. The difference is perseverance. - Colin R. Davis",
            "Obstacles are those frightful things you see when you take your eyes off your goal. - Henry Ford",
            "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt",
            ])
        timeSaved = (easy_applied_count * 80) + (external_jobs_count * 20) + (skip_count * 10)
        timeSavedMsg = ""
        if timeSaved > 0:
            timeSaved += 60
            timeSavedMsg = f"In this run, you saved approx {round(timeSaved/60)} mins ({timeSaved} secs)."
        msg = f"{quotes}\n\n{timeSavedMsg}\n\nSummary:\n{summary}"
        print_lg(msg,"Closing the browser...")
        if tabs_count >= 10:
            msg = "NOTE: IF YOU HAVE MORE THAN 10 TABS OPENED, PLEASE CLOSE OR BOOKMARK THEM!\n\nOr it's highly likely that application will just open browser and not do anything next time!" 
            print_lg("\n"+msg)
        ##> ------ Yang Li : MARKYangL - Feature ------
        if use_AI and aiClient:
            try:
                if ai_provider.lower() in ("openai", "groq"):
                    ai_close_openai_client(aiClient)
                elif ai_provider.lower() == "deepseek":
                    ai_close_openai_client(aiClient)
                elif ai_provider.lower() == "gemini":
                    pass # Gemini client does not need to be closed
                print_lg(f"Closed {ai_provider} AI client.")
            except Exception as e:
                print_lg("Failed to close AI client:", e)
        ##<
        ##> ------ Orchestration to open manual jobs ------
        if top_manual_jobs:
            # Sort top manual jobs descending by score
            top_manual_jobs.sort(key=lambda x: x.get('score', 5), reverse=True)
            jobs_to_open = top_manual_jobs[:5]
            
            print_lg(f"\n--- TOP {len(jobs_to_open)} MANUAL JOBS TO OPEN ---")
            for job in jobs_to_open:
                print_lg(f"Score: {job['score']} | {job['title']} at {job['company']} | Link: {job['link']}")
            
            if driver:
                try:
                    try:
                        driver.switch_to.window(linkedIn_tab)
                    except:
                        try:
                            driver.switch_to.window(driver.window_handles[0])
                        except:
                            pass
                    
                    for job in jobs_to_open:
                        driver.execute_script("window.open(arguments[0], '_blank');", job['link'])
                    
                    # Notify the user with ui_alert
                    links_msg = "\n".join([f"- {j['title']} at {j['company']} (Score: {j['score']})" for j in jobs_to_open])
                    ui_alert("Manual Applications Opened", f"The daily application limit was reached or search ended. The top {len(jobs_to_open)} matching jobs have been opened in your browser for manual review:\n\n{links_msg}")
                    
                    # Bypass quitting the driver
                    driver = None
                except Exception as ex:
                    print_lg("Failed to open manual jobs in browser:", ex)
        ##<
        try:
            if driver:
                driver.quit()
        except WebDriverException as e:
            print_lg("Browser already closed.", e)
        except Exception as e: 
            critical_error_log("When quitting...", e)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_lg("\nExiting bot cleanly...")
        import os
        os._exit(0)
