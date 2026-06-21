'''
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

Support me: https://github.com/sponsors/GodsScion

version:    26.01.20.5.08
'''


from config.secrets import *
from config.settings import showAiErrorAlerts
from config.personals import ethnicity, gender, disability_status, veteran_status
from config.questions import *
from config.search import security_clearance, did_masters

from modules.helpers import print_lg, critical_error_log, convert_to_json
from modules.ai.prompts import *

from pyautogui import confirm
from openai import OpenAI
from openai.types.model import Model
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from typing import Iterator, Literal


apiCheckInstructions = """

1. Make sure your AI API connection details like url, key, model names, etc are correct.
2. If you're using an local LLM, please check if the server is running.
3. Check if appropriate LLM and Embedding models are loaded and running.

Open `secret.py` in `/config` folder to configure your AI API connections.

ERROR:
"""

# Function to show an AI error alert
def ai_error_alert(message: str, stackTrace: str, title: str = "AI Connection Error") -> None:
    """
    Function to show an AI error alert and log it.
    """
    global showAiErrorAlerts
    if showAiErrorAlerts:
        if "Pause AI error alerts" == confirm(f"{message}{stackTrace}\n", title, ["Pause AI error alerts", "Okay Continue"]):
            showAiErrorAlerts = False
    critical_error_log(message, stackTrace)


# Function to check if an error occurred
def ai_check_error(response: ChatCompletion | ChatCompletionChunk) -> None:
    """
    Function to check if an error occurred.
    * Takes in `response` of type `ChatCompletion` or `ChatCompletionChunk`
    * Raises a `ValueError` if an error is found
    """
    if response.model_extra.get("error"):
        raise ValueError(
            f'Error occurred with API: "{response.model_extra.get("error")}"'
        )


# Function to create an OpenAI client
def ai_create_openai_client() -> OpenAI:
    """
    Function to create an OpenAI client.
    * Takes no arguments
    * Returns an `OpenAI` object
    """
    try:
        print_lg("Creating OpenAI client...")
        if not use_AI:
            raise ValueError("AI is not enabled! Please enable it by setting `use_AI = True` in `secrets.py` in `config` folder.")
        
        client = OpenAI(base_url=llm_api_url, api_key=llm_api_key)

        models = ai_get_models_list(client)
        if "error" in models:
            raise ValueError(models[1])
        if len(models) == 0:
            raise ValueError("No models are available!")
        if llm_model not in [model.id for model in models]:
            raise ValueError(f"Model `{llm_model}` is not found!")
        
        print_lg("---- SUCCESSFULLY CREATED OPENAI CLIENT! ----")
        print_lg(f"Using API URL: {llm_api_url}")
        print_lg(f"Using Model: {llm_model}")
        print_lg("Check './config/secrets.py' for more details.\n")
        print_lg("---------------------------------------------")

        return client
    except Exception as e:
        ai_error_alert(f"Error occurred while creating OpenAI client. {apiCheckInstructions}", e)


# Function to close an OpenAI client
def ai_close_openai_client(client: OpenAI) -> None:
    """
    Function to close an OpenAI client.
    * Takes in `client` of type `OpenAI`
    * Returns no value
    """
    try:
        if client:
            print_lg("Closing OpenAI client...")
            client.close()
    except Exception as e:
        ai_error_alert("Error occurred while closing OpenAI client.", e)



# Function to get list of models available in OpenAI API
def ai_get_models_list(client: OpenAI) -> list[ Model | str]:
    """
    Function to get list of models available in OpenAI API.
    * Takes in `client` of type `OpenAI`
    * Returns a `list` object
    """
    try:
        print_lg("Getting AI models list...")
        if not client: raise ValueError("Client is not available!")
        models = client.models.list()
        ai_check_error(models)
        print_lg("Available models:")
        print_lg(models.data, pretty=True)
        return models.data
    except Exception as e:
        critical_error_log("Error occurred while getting models list!", e)
        return ["error", e]

def model_supports_temperature(model_name: str) -> bool:
    """
    Checks if the specified model supports the temperature parameter.
    
    Args:
        model_name (str): The name of the AI model.
    
    Returns:
        bool: True if the model supports temperature adjustments, otherwise False.
    """
    return model_name in ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini"]

# Function to get chat completion from OpenAI API
def ai_completion(client: OpenAI, messages: list[dict], response_format: dict = None, temperature: float = 0, stream: bool = stream_output) -> dict | ValueError:
    """
    Function that completes a chat and prints and formats the results of the OpenAI API calls.
    * Takes in `client` of type `OpenAI`
    * Takes in `messages` of type `list[dict]`. Example: `[{"role": "user", "content": "Hello"}]`
    * Takes in `response_format` of type `dict` for JSON representation, default is `None`
    * Takes in `temperature` of type `float` for temperature, default is `0`
    * Takes in `stream` of type `bool` to indicate if it's a streaming call or not
    * Returns a `dict` object representing JSON response, will try to convert to JSON if `response_format` is given
    """
    if not client: raise ValueError("Client is not available!")

    params = {"model": llm_model, "messages": messages, "stream": stream}

    if model_supports_temperature(llm_model):
        params["temperature"] = temperature
    if response_format and llm_spec in ["openai", "openai-like"]:
        params["response_format"] = response_format

    completion = client.chat.completions.create(**params)

    result = ""
    
    # Log response
    if stream:
        print_lg("--STREAMING STARTED")
        for chunk in completion:
            ai_check_error(chunk)
            chunkMessage = chunk.choices[0].delta.content
            if chunkMessage != None:
                result += chunkMessage
            print_lg(chunkMessage, end="", flush=True)
        print_lg("\n--STREAMING COMPLETE")
    else:
        ai_check_error(completion)
        result = completion.choices[0].message.content
    
    if response_format:
        result = convert_to_json(result)
    
    print_lg("\nAI Answer to Question:\n")
    print_lg(result, pretty=response_format)
    return result


def ai_extract_skills(client: OpenAI, job_description: str, stream: bool = stream_output) -> dict | ValueError:
    """
    Function to extract skills from job description using OpenAI API.
    * Takes in `client` of type `OpenAI`
    * Takes in `job_description` of type `str`
    * Takes in `stream` of type `bool` to indicate if it's a streaming call
    * Returns a `dict` object representing JSON response
    """
    print_lg("-- EXTRACTING SKILLS FROM JOB DESCRIPTION")
    try:        
        prompt = extract_skills_prompt.format(job_description)

        messages = [{"role": "user", "content": prompt}]
        ##> ------ Dheeraj Deshwal : dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Bug fix ------
        return ai_completion(client, messages, response_format=extract_skills_response_format, stream=stream)
    ##<
    except Exception as e:
        ai_error_alert(f"Error occurred while extracting skills from job description. {apiCheckInstructions}", e)


##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
from modules.ai.qa_database import get_answer_from_database, save_to_qa_database

def ai_answer_question(
    client: OpenAI,
    question: str, options: list[str] | None = None, 
    question_type: Literal['text', 'textarea', 'single_select', 'multiple_select'] = 'text', 
    job_description: str = None, about_company: str = None, user_information_all: str = None,
    error_message: str = None,
    stream: bool = stream_output
) -> str | dict | ValueError:
    """
    Answers a question using the OpenAI API.
    """
    try:
        # Check QA Database first
        if not error_message:
            cached_answer = get_answer_from_database(question)
            if cached_answer:
                print_lg(f"Found answer in QA Database: {cached_answer}")
                return cached_answer
                
        print_lg(f"Answering question using AI: {question}")
        user_info = user_information_all or ""
        
        prompt = ""
        if error_message:
            prompt += f"IMPORTANT: The previous answer to this question resulted in a validation error: '{error_message}'. Please provide a NEW answer that fixes this error.\n\n"
        prompt += ai_answer_prompt.format(user_info, question)
        
        # Append optional details if provided
        if options and (question_type in ['single_select', 'multiple_select']):
            options_str = "OPTIONS:\n" + "\n".join([f"- {option}" for option in options])
            prompt += f"\n\n{options_str}"
            if question_type == 'single_select':
                prompt += "\n\nPlease select exactly ONE option from the list above."
            else:
                prompt += "\n\nYou may select MULTIPLE options from the list above if appropriate."
                
        if job_description and job_description != "Unknown":
            prompt += f"\nJob Description:\n{job_description}"
        if about_company and about_company != "Unknown":
            prompt += f"\nAbout the Company:\n{about_company}"

        messages = [{"role": "user", "content": prompt}]
        print_lg("Prompt we are passing to AI: ", prompt)
        response = ai_completion(client, messages, stream=stream)
        
        # Save valid answers to QA Database
        if isinstance(response, str) and not response.startswith("{'error'"):
            save_to_qa_database(question, response)
            
        return response
    except Exception as e:
        ai_error_alert(f"Error occurred while answering question. {apiCheckInstructions}", e)
        return {"error": str(e)}

def ai_evaluate_job(client: OpenAI, job_description: str, user_information_all: str) -> dict:
    """
    Evaluates if the user meets the core requirements of the job.
    """
    try:
        print_lg("Evaluating if job matches user's CV using OpenAI...")
        user_info = user_information_all or ""
        prompt = evaluate_job_prompt.format(user_info, job_description)
        messages = [{"role": "user", "content": prompt}]
        return ai_completion(client, messages, response_format={"type": "json_object"})
    except Exception as e:
        ai_error_alert(f"Error occurred while evaluating job. {apiCheckInstructions}", e)
        return {"error": str(e)}


def ai_gen_experience(
    client: OpenAI, 
    job_description: str, about_company: str, 
    required_skills: dict, user_experience: dict,
    stream: bool = stream_output
) -> dict | ValueError:
    pass



def ai_generate_resume(
    client: OpenAI, 
    job_description: str, about_company: str, required_skills: dict,
    stream: bool = stream_output
) -> dict | ValueError:
    '''
    Function to generate resume. Takes in user experience and template info from config.
    '''
    pass



def ai_generate_coverletter(
    client: OpenAI, 
    job_description: str, about_company: str, required_skills: dict,
    stream: bool = stream_output
) -> dict | ValueError:
    '''
    Function to generate resume. Takes in user experience and template info from config.
    '''
    pass



##< Evaluation Agents
def ai_evaluate_resume(
    client: OpenAI, 
    job_description: str, about_company: str, required_skills: dict,
    resume: str,
    stream: bool = stream_output
) -> dict | ValueError:
    pass



def ai_evaluate_resume(
    client: OpenAI, 
    job_description: str, about_company: str, required_skills: dict,
    resume: str,
    stream: bool = stream_output
) -> dict | ValueError:
    pass



def ai_check_job_relevance(
    client: OpenAI, 
    job_description: str, about_company: str,
    stream: bool = stream_output
) -> dict:
    pass

def ai_optimize_existing_cv(file_path: str, include_portfolio: bool = False) -> bool:
    try:
        import fitz
        import traceback
        from modules.helpers import convert_to_json
        from generate_cv_fullportfolio import generate_full_portfolio, default_projects, images_dir_default
        from config.secrets import ai_provider as _ai_provider
        
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
        print(f"[CV Optimizer] Extracted {len(text)} chars from PDF")

        prompt = f"""\
Act as an expert resume writer. Optimize the CV text below: be impactful, metric-driven, and modern.
Return ONLY a JSON object (no markdown) with this exact structure:
{{
    "name": "Full Name",
    "title": "Professional Title",
    "contact": ["Email: x@y.com", "Phone: +123"],
    "sections": [
        {{
            "title": "EXPERIENCE",
            "subsections": [
                {{
                    "title": "Job Title at Company",
                    "date": "Jan 2020 - Present",
                    "bullets": ["Achievement 1", "Achievement 2"]
                }}
            ],
            "bullets": []
        }},
        {{
            "title": "SKILLS",
            "subsections": [],
            "bullets": ["Skill A", "Skill B"]
        }}
    ]
}}

RAW CV TEXT:
{text}"""

        response_text = None

        if _ai_provider.lower() == "gemini":
            from modules.ai.geminiConnections import gemini_create_client, gemini_completion
            client = gemini_create_client()
            if not client:
                print("[CV Optimizer] ERROR: Gemini client is None.")
                return False
            response_text = gemini_completion(client, prompt, is_json=True)
        else:
            client = ai_create_openai_client()
            if not client:
                print("[CV Optimizer] ERROR: OpenAI/DeepSeek client is None. Check API key.")
                return False
            messages = [{"role": "user", "content": prompt}]
            response_text = ai_completion(client, messages, response_format={"type": "json_object"})

        if isinstance(response_text, str):
            import json
            # Strip markdown code fences if present
            clean = response_text.strip().strip('`')
            if clean.startswith('json'):
                clean = clean[4:].strip()
            cv_data = json.loads(clean)
        else:
            cv_data = response_text

        print(f"[CV Optimizer] Raw AI response keys: {list(cv_data.keys()) if isinstance(cv_data, dict) else type(cv_data)}")

        # Normalize: Gemini sometimes returns different key names
        def _normalize_cv(raw: dict) -> dict:
            # If data is nested inside a wrapper key, unwrap it
            for wrapper_key in ("cv", "resume", "candidate", "data", "result"):
                if wrapper_key in raw and isinstance(raw[wrapper_key], dict):
                    raw = raw[wrapper_key]
                    break
            # Map common name aliases
            if "name" not in raw:
                for alias in ("full_name", "candidate_name", "applicant_name", "firstName"):
                    if alias in raw:
                        raw["name"] = raw[alias]
                        break
                else:
                    raw["name"] = "Candidate"
            if "title" not in raw:
                for alias in ("professional_title", "job_title", "headline", "position"):
                    if alias in raw:
                        raw["title"] = raw[alias]
                        break
                else:
                    raw["title"] = ""
            if "contact" not in raw:
                for alias in ("contact_info", "contacts", "contact_details"):
                    if alias in raw:
                        raw["contact"] = raw[alias]
                        break
                else:
                    raw["contact"] = []
            if "sections" not in raw:
                for alias in ("experience", "experiences", "resume_sections"):
                    if alias in raw and isinstance(raw[alias], list):
                        raw["sections"] = raw[alias]
                        break
                else:
                    raw["sections"] = []
            return raw

        cv_data = _normalize_cv(cv_data)
        print(f"[CV Optimizer] Normalized: name={cv_data.get('name')}, sections={len(cv_data.get('sections', []))}")

        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        safe_name = cv_data.get("name", "Optimized").replace(" ", "_")
        output_path = os.path.join(base_dir, "all resumes", f"{safe_name}_CV_Optimized.pdf")

        generate_full_portfolio(cv_data, output_path, include_portfolio=include_portfolio, projects=default_projects, images_dir=images_dir_default)
        print(f"[CV Optimizer] SUCCESS: Saved to {output_path}")
        return True
    except Exception as e:
        import traceback
        print(f"[CV Optimizer] EXCEPTION in ai_optimize_existing_cv:")
        traceback.print_exc()
        return False

def ai_generate_cv_from_config(include_portfolio: bool = False) -> bool:
    try:
        from generate_cv_fullportfolio import generate_cv_from_basic_info, default_projects, images_dir_default
        import os
        from modules.bot_ui import _read_py_var

        _BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _PERS = os.path.join(_BASE, "config", "personals.py")
        _QUEST = os.path.join(_BASE, "config", "questions.py")

        fn = _read_py_var(_PERS, "first_name") or "John"
        ln = _read_py_var(_PERS, "last_name") or "Doe"
        ph = _read_py_var(_PERS, "phone_number") or ""
        city = _read_py_var(_PERS, "current_city") or ""
        st = _read_py_var(_PERS, "state") or ""
        title = _read_py_var(_QUEST, "linkedin_headline") or "Professional"

        output_path = os.path.join(_BASE, "all resumes", f"{fn}_{ln}_CV_Generado.pdf")

        generate_cv_from_basic_info(fn, ln, ph, f"{city}, {st}", title, output_path, include_portfolio=include_portfolio, projects=default_projects, images_dir=images_dir_default)
        print(f"[CV Optimizer] SUCCESS: Saved to {output_path}")
        return True
    except Exception as e:
        import traceback
        print(f"[CV Optimizer] EXCEPTION in ai_generate_cv_from_config:")
        traceback.print_exc()
        return False
#>