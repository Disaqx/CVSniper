import json
import os
import re
import time
import unicodedata
from random import randint
from typing import Literal
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import NoSuchElementException
from modules.open_chrome import driver, wait, actions
from modules.helpers import print_lg, buffer, sleep
from modules.bot_ui import is_career_ops_mode, ui_pause_check, ui_alert, ui_confirm, ui_update_status
from modules.clickers_and_finders import try_xp, find_by_class, try_find_by_classes, wait_span_click, text_input_by_ID
from modules.ai.qa_database import save_to_qa_database
from modules.ai.openaiConnections import ai_answer_question
from modules.ai.deepseekConnections import deepseek_answer_question
from modules.ai.geminiConnections import gemini_answer_question
from config.personals import *
from config.questions import *
from config.secrets import use_AI, ai_provider
from config.settings import *

# Derived values (computed from config; mirroring runAiBot.py module-level logic)
first_name = first_name.strip()
middle_name = middle_name.strip()
last_name = last_name.strip()
full_name = first_name + " " + middle_name + " " + last_name if middle_name else first_name + " " + last_name
notice_period_months = str(notice_period // 30)
notice_period_weeks = str(notice_period // 7)
notice_period = str(notice_period)
desired_salary = str(desired_salary)
current_ctc = str(current_ctc)

# Module-level mutable state shared with runAiBot.py
randomly_answered_questions = set()


class CareerOpsActivatedException(Exception):
    pass


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
        # Load user's configured English level
        try:
            from config.questions import english_level as _eng_lvl
        except Exception:
            _eng_lvl = ""
        _el = (_eng_lvl or "").lower().strip()

        # Map level to keyword sets for matching options
        _level_kw = {
            "none":   ["none", "no proficiency", "ninguno", "sin conocimiento", "don't speak", "do not speak", "no hablo", "0", "n/a"],
            "a1":     ["a1", "beginner", "principiante", "elementary", "basic"],
            "a2":     ["a2", "pre-intermediate", "pre intermediate", "elementary", "basic", "limited"],
            "b1":     ["b1", "intermediate", "intermedio"],
            "b2":     ["b2", "upper intermediate", "upper-intermediate", "upper", "conversational", "working proficiency"],
            "c1":     ["c1", "advanced", "avanzado", "professional", "proficient", "fluent"],
            "c2":     ["c2", "proficient", "mastery", "superior", "full professional", "native or bilingual"],
            "native": ["native", "nativo", "bilingual", "bilingue", "c2"],
        }

        if _el == "none":
            # User has no English — treat like an unknown language
            if question_type in ["select", "radio", "combobox"] and options_text:
                no_idx = find_matching_option(options_text, "No")
                if no_idx is not None:
                    return options_text[no_idx]
                for opt in options_text:
                    if any(w in opt.lower() for w in _level_kw["none"]):
                        return opt
                return options_text[0]
            return "No"

        if _el in _level_kw and question_type in ["select", "radio", "combobox"] and options_text:
            kws = _level_kw[_el]
            for opt in options_text:
                if any(w in opt.lower() for w in kws):
                    return opt
            # Fallback: pick any Yes option
            yes_idx = find_matching_option(options_text, "Yes")
            if yes_idx is not None:
                return options_text[yes_idx]

        if not _el:
            # Old behaviour: pick highest available option
            if question_type in ["select", "radio", "combobox"] and options_text:
                for opt in options_text:
                    opt_lower = opt.lower()
                    if any(w in opt_lower for w in ["advanced", "avanzado", "fluent", "proficient", "c1", "c2", "professional", "professional working"]):
                        return opt
                yes_idx = find_matching_option(options_text, "Yes")
                if yes_idx is not None:
                    return options_text[yes_idx]

        return _el.upper() if _el else "C1/Advanced"

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
    db_path = os.path.join(script_dir, "..", "config", "questions_db.json")
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
def answer_questions(modal: WebElement, questions_list: set, work_location: str, job_description: str | None = None, ai_client=None) -> set:
    import json
    import os
    import unicodedata

    def normalize_label(label_str: str) -> str:
        if not label_str:
            return ""
        return "".join(c for c in unicodedata.normalize('NFD', label_str) if unicodedata.category(c) != 'Mn').lower().strip()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "..", "config", "questions_db.json")
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
                    if use_AI and ai_client and optionsText and not _skip_ai_education:
                        if is_career_ops_mode():
                            raise CareerOpsActivatedException()
                        try:
                            print_lg(f"Asking AI to select an option for: {label_org}")
                            ai_answer = None
                            if ai_provider.lower() in ("openai", "groq"):
                                ai_answer = ai_answer_question(ai_client, label_org, options=optionsText, question_type="single_select", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                ai_answer = deepseek_answer_question(ai_client, label_org, options=optionsText, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                ai_answer = gemini_answer_question(ai_client, label_org, options=optionsText, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)

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
                    if use_AI and ai_client:
                        if is_career_ops_mode():
                            raise CareerOpsActivatedException()
                        try:
                            print_lg(f"Asking AI to answer Radio question: {label_org}")
                            ai_answer = None
                            if ai_provider.lower() in ("openai", "groq"):
                                ai_answer = ai_answer_question(ai_client, label_org, options=options_text_list, question_type="single_select", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                ai_answer = deepseek_answer_question(ai_client, label_org, options=options_text_list, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                ai_answer = gemini_answer_question(ai_client, label_org, options=options_text_list, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)

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
                    if use_AI and ai_client:
                        if is_career_ops_mode():
                            raise CareerOpsActivatedException()
                        try:
                            # Pass full question block text when it adds context beyond just the label
                            ai_question = label_org
                            if question_full_text and question_full_text.lower() != label_org.lower() and len(question_full_text) > len(label_org) + 5:
                                ai_question = f"{label_org}\n\n[Full question context: {question_full_text}]"
                            if ai_provider.lower() in ("openai", "groq"):
                                ai_answer = ai_answer_question(ai_client, ai_question, question_type="text", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                ai_answer = deepseek_answer_question(ai_client, ai_question, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                ai_answer = gemini_answer_question(ai_client, ai_question, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all, error_message=error_msg if has_error else None)

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
                                if use_AI and ai_client:
                                    if is_career_ops_mode():
                                        raise CareerOpsActivatedException()
                                    try:
                                        if ai_provider.lower() in ("openai", "groq"):
                                            answer = ai_answer_question(ai_client, label_org, question_type="text", job_description=job_description, user_information_all=user_information_all)
                                        elif ai_provider.lower() == "deepseek":
                                            answer = deepseek_answer_question(ai_client, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                                        elif ai_provider.lower() == "gemini":
                                            answer = gemini_answer_question(ai_client, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
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
                        if use_AI and ai_client and optionsText:
                            if is_career_ops_mode():
                                raise CareerOpsActivatedException()
                            try:
                                print_lg(f"Asking AI to select an option for combobox: {label_org}")
                                ai_answer = None
                                if ai_provider.lower() in ("openai", "groq"):
                                    ai_answer = ai_answer_question(ai_client, label_org, options=optionsText, question_type="single_select", job_description=job_description, user_information_all=user_information_all)
                                elif ai_provider.lower() == "deepseek":
                                    ai_answer = deepseek_answer_question(ai_client, label_org, options=optionsText, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                                elif ai_provider.lower() == "gemini":
                                    ai_answer = gemini_answer_question(ai_client, label_org, options=optionsText, question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)

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
                    if use_AI and ai_client:
                        if is_career_ops_mode():
                            raise CareerOpsActivatedException()
                        try:
                            if ai_provider.lower() in ("openai", "groq"):
                                answer = ai_answer_question(ai_client, label_org, question_type="textarea", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                answer = deepseek_answer_question(ai_client, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                answer = gemini_answer_question(ai_client, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)

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

                    if use_AI and ai_client:
                        if is_career_ops_mode():
                            raise CareerOpsActivatedException()
                        try:
                            ai_ans = None
                            if ai_provider.lower() in ("openai", "groq"):
                                ai_ans = ai_answer_question(ai_client, label_org, options=["Yes", "No"], question_type="single_select", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                ai_ans = deepseek_answer_question(ai_client, label_org, options=["Yes", "No"], question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                ai_ans = gemini_answer_question(ai_client, label_org, options=["Yes", "No"], question_type="single_select", job_description=job_description, about_company=None, user_information_all=user_information_all)
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



# Function to discard the job application
def discard_job() -> None:
    actions.send_keys(Keys.ESCAPE).perform()
    wait_span_click(driver, 'Discard', 2) or wait_span_click(driver, 'Descartar', 2)
