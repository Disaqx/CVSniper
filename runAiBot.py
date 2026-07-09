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
    from modules.ai.providers import get_ai_client

from typing import Literal
from modules.ai.qa_database import save_to_qa_database

from modules.linkedin_login import is_logged_in_LN, login_LN
from modules.job_search import (
    re_experience, is_job_relevant, set_search_location, apply_filters,
    get_page_info, get_job_main_details, check_blacklist,
    extract_years_of_experience, get_job_description
)
from modules.easy_apply import (
    CareerOpsActivatedException, upload_resume, resolve_value_for_category,
    find_matching_option, answer_language_question, resolve_salary_expectation,
    is_sensitive_question, answer_common_questions, answer_questions,
    follow_company, discard_job, randomly_answered_questions
)
from modules.external_apply import external_apply


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

tabs_count = 1
easy_applied_count = 0
external_jobs_count = 0
failed_count = 0
skip_count = 0
dailyEasyApplyLimitReached = False

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
    global current_city, failed_count, skip_count, easy_applied_count, external_jobs_count, tabs_count, pause_before_submit, pause_at_failed_question, useNewResume, top_manual_jobs, pause_after_filters
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

        pause_after_filters = apply_filters(location, sort_by, date_posted, pause_after_filters)
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
                        time_posted_text = jobs_top_card.find_element(By.XPATH, './/span[contains(normalize-space(), " ago") or contains(normalize-space(), "hace ")]').text
                        print("Time Posted: " + time_posted_text)
                        if "Reposted" in time_posted_text or "Republicado" in time_posted_text:
                            reposted = True
                            time_posted_text = time_posted_text.replace("Reposted", "").replace("Republicado", "")
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
                            
                            eval_result = aiClient.evaluate_job(description, user_information_all)
                                
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
                            skills = aiClient.extract_skills(description)
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
                                if not wait_span_click(modal, "Next", 1):
                                    wait_span_click(modal, "Siguiente", 1)
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
                                    questions_list = answer_questions(modal, questions_list, work_location, job_description=description, ai_client=aiClient)
                                    if useNewResume and not uploaded: uploaded, resume = upload_resume(modal, default_resume_path)
                                    try: next_button = modal.find_element(By.XPATH, './/button[contains(normalize-space(.), "Review") or contains(@aria-label, "Review") or contains(normalize-space(.), "Revisar") or contains(@aria-label, "Revisar")]')
                                    except NoSuchElementException:  next_button = modal.find_element(By.XPATH, './/button[contains(normalize-space(.), "Next") or contains(@aria-label, "next") or contains(@aria-label, "Next") or contains(normalize-space(.), "Siguiente") or contains(@aria-label, "Siguiente")]')
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
                                    wait_button_click(driver, ["Review", "Revisar solicitud", "Revisar"], 3, scrollTop=True)
                                    cur_pause_before_submit = pause_before_submit
                                    if errored != "stuck" and cur_pause_before_submit:
                                        decision = ui_confirm("Confirm your information", '1. Please verify your information.\n2. If you edited something, please return to this final screen.\n3. DO NOT CLICK "Submit Application".\n\n\n\n\nYou can turn off "Pause before submit" setting in config.py\nTo TEMPORARILY disable pausing, click "Disable Pause"', ["Disable Pause", "Discard Application", "Submit Application"])
                                        if decision == "Discard Application": raise Exception("Job application discarded by user!")
                                        pause_before_submit = False if "Disable Pause" == decision else True
                                        # try_xp(modal, ".//span[normalize-space(.)='Review']")
                                    follow_company(modal)
                                    if wait_button_click(driver, ["Submit application", "Submit", "Enviar solicitud", "Enviar"], 8, scrollTop=True):
                                        date_applied = datetime.now()
                                        if not wait_button_click(driver, ["Done", "Listo", "Hecho"], 4):
                                            actions.send_keys(Keys.ESCAPE).perform()
                                    elif errored != "stuck" and cur_pause_before_submit and "Yes" in ui_confirm("Failed to find Submit Application!", "You submitted the application, didn't you?", ["Yes", "No"]):
                                        date_applied = datetime.now()
                                        wait_button_click(driver, ["Done", "Listo", "Hecho"], 4)
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
                        skip, application_link, tabs_count = external_apply(job_id, job_link, resume, date_listed, application_link, screenshot_name, tabs_count=tabs_count, ai_client=aiClient, job_description=description)
                        if not skip:
                            date_applied = datetime.now()
                            external_jobs_count += 1
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
            aiClient = get_ai_client()

            try:
                about_company_for_ai = None  # TODO: extract real "About Company" info from LinkedIn job page
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
                aiClient.close()
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
