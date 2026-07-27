"""
Unified AI provider abstraction for CVSniper.

All provider-specific dispatch logic is centralised here.
Callers obtain a provider via get_ai_client() and call its methods directly,
with no need to branch on ai_provider/llm_spec themselves.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Literal

from modules.helpers import print_lg, critical_error_log, convert_to_json
from modules.ai.prompts import (
    extract_skills_prompt, extract_skills_response_format,
    deepseek_extract_skills_prompt,
    ai_answer_prompt, evaluate_job_prompt,
)
from modules.ai.qa_database import get_answer_from_database, save_to_qa_database


# ── Shared helpers ─────────────────────────────────────────────────────────────

_API_INSTRUCTIONS = """
1. Make sure your AI API connection details (url, key, model) are correct.
2. If using a local LLM, check that the server is running.
Open config/secrets.py to configure AI settings.
ERROR:
"""

def _ai_error_alert(message: str, exc, title: str = "AI Connection Error") -> None:
    from config.settings import showAiErrorAlerts
    from pyautogui import confirm
    if showAiErrorAlerts:
        confirm(f"{message}\n{exc}\n", title, ["Pause AI error alerts", "Okay Continue"])
    critical_error_log(message, exc)


# ── Abstract base ──────────────────────────────────────────────────────────────

class AIProvider(ABC):
    """Common interface every AI provider must implement."""

    @abstractmethod
    def answer_question(
        self,
        question: str,
        options: list[str] | None = None,
        question_type: Literal['text', 'textarea', 'single_select', 'multiple_select'] = 'text',
        job_description: str | None = None,
        about_company: str | None = None,
        user_information_all: str | None = None,
        error_message: str | None = None,
        stream: bool = None,
    ) -> str | dict:
        """Answer a form question, checking the QA cache first."""

    @abstractmethod
    def evaluate_job(self, job_description: str, user_information_all: str) -> dict:
        """Return a dict indicating whether the user matches this job."""

    @abstractmethod
    def extract_skills(self, job_description: str, stream: bool = None) -> dict:
        """Extract required skills from the job description."""

    def close(self) -> None:
        """Release any provider resources (override if needed)."""


# ── OpenAI-compatible provider ─────────────────────────────────────────────────
# Covers openai, groq, deepseek, ollama — any llm_spec="openai-like" endpoint.

_TEMP_SUPPORTED_MODELS = frozenset({
    "gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini",
    "deepseek-chat", "deepseek-reasoner",
})


class OpenAILikeProvider(AIProvider):

    def __init__(self, client, model: str, provider_name: str, stream_output: bool):
        self.client = client
        self.model = model
        self.provider_name = provider_name
        self.stream_output = stream_output

    def _completion(
        self,
        messages: list[dict],
        response_format: dict = None,
        temperature: float = 0,
        stream: bool = None,
    ) -> dict | str:
        from config.secrets import llm_spec
        if not self.client:
            raise ValueError("Client is not available!")
        if stream is None:
            stream = self.stream_output

        params: dict = {"model": self.model, "messages": messages, "stream": stream}

        if self.model in _TEMP_SUPPORTED_MODELS:
            params["temperature"] = temperature

        if response_format and llm_spec in ("openai", "openai-like"):
            # Groq doesn't support json_schema strict mode — downgrade to json_object
            if (self.provider_name.lower() == "groq"
                    and isinstance(response_format, dict)
                    and response_format.get("type") == "json_schema"):
                params["response_format"] = {"type": "json_object"}
            else:
                params["response_format"] = response_format

        completion = self.client.chat.completions.create(**params)
        result = ""

        if stream:
            print_lg("--STREAMING STARTED")
            for chunk in completion:
                if chunk.model_extra and chunk.model_extra.get("error"):
                    raise ValueError(f'API error: "{chunk.model_extra.get("error")}"')
                msg = chunk.choices[0].delta.content
                if msg is not None:
                    result += msg
                print_lg(msg, end="", flush=True)
            print_lg("\n--STREAMING COMPLETE")
        else:
            if completion.model_extra and completion.model_extra.get("error"):
                raise ValueError(f'API error: "{completion.model_extra.get("error")}"')
            result = completion.choices[0].message.content
            try:
                if completion.usage and completion.usage.total_tokens:
                    from modules.bot_ui import update_api_usage
                    update_api_usage(completion.usage.total_tokens)
            except Exception:
                pass

        if response_format:
            result = convert_to_json(result)

        print_lg("\nAI Answer:\n")
        print_lg(result, pretty=bool(response_format))
        return result

    def answer_question(
        self, question, options=None, question_type='text',
        job_description=None, about_company=None,
        user_information_all=None, error_message=None, stream=None,
    ) -> str | dict:
        try:
            if not error_message:
                cached = get_answer_from_database(question, options=options)
                if cached:
                    print_lg(f"Found answer in QA Database: {cached}")
                    return cached

            print_lg(f"Answering question using {self.provider_name} AI: {question}")
            user_info = user_information_all or ""
            prompt = ""
            if error_message:
                prompt += (
                    f"IMPORTANT: The previous answer resulted in a validation error: "
                    f"'{error_message}'. Please provide a NEW answer that fixes this error.\n\n"
                )
            prompt += ai_answer_prompt.format(user_info, question)

            if options and question_type in ('single_select', 'multiple_select'):
                prompt += "\n\nOPTIONS:\n" + "\n".join(f"- {o}" for o in options)
                if question_type == 'single_select':
                    prompt += "\n\nPlease select exactly ONE option from the list above."
                else:
                    prompt += "\n\nYou may select MULTIPLE options from the list above if appropriate."

            if job_description and job_description != "Unknown":
                prompt += f"\nJob Description:\n{job_description}"
            if about_company and about_company != "Unknown":
                prompt += f"\nAbout the Company:\n{about_company}"

            print_lg("Prompt we are passing to AI: ", prompt)
            response = self._completion([{"role": "user", "content": prompt}], stream=stream)
            if isinstance(response, str) and not response.startswith("{'error'"):
                save_to_qa_database(question, response, options=options)
            return response
        except Exception as e:
            _ai_error_alert(f"Error answering question. {_API_INSTRUCTIONS}", e)
            return {"error": str(e)}

    def evaluate_job(self, job_description: str, user_information_all: str) -> dict:
        try:
            print_lg(f"Evaluating job using {self.provider_name} AI...")
            user_info = user_information_all or ""
            prompt = evaluate_job_prompt.format(user_info, job_description)
            return self._completion(
                [{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
        except Exception as e:
            _ai_error_alert(f"Error evaluating job. {_API_INSTRUCTIONS}", e)
            return {"error": str(e)}

    def extract_skills(self, job_description: str, stream: bool = None) -> dict:
        try:
            print_lg(f"Extracting skills using {self.provider_name} AI...")
            if self.provider_name.lower() == "deepseek":
                prompt = deepseek_extract_skills_prompt.format(job_description)
                rf = {"type": "json_object"}
            else:
                prompt = extract_skills_prompt.format(job_description)
                rf = extract_skills_response_format
            
            try:
                return self._completion(
                    [{"role": "user", "content": prompt}],
                    response_format=rf,
                    stream=stream,
                )
            except Exception as inner_e:
                # If json_schema is not supported (e.g. Groq via OpenAI endpoint), fallback to json_object
                if "response_format" in str(inner_e).lower() or "json_schema" in str(inner_e).lower():
                    print_lg("Provider does not support json_schema, falling back to json_object...")
                    return self._completion(
                        [{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                        stream=stream,
                    )
                raise inner_e
        except Exception as e:
            _ai_error_alert(f"Error extracting skills. {_API_INSTRUCTIONS}", e)
            return {"error": str(e)}

    def close(self) -> None:
        try:
            if self.client:
                print_lg(f"Closing {self.provider_name} client...")
                self.client.close()
        except Exception as e:
            _ai_error_alert("Error closing client.", e)


# ── Gemini provider ────────────────────────────────────────────────────────────

class GeminiProvider(AIProvider):
    """Covers llm_spec='gemini' (google.generativeai)."""

    def __init__(self, model):
        self.model = model

    def _completion(self, prompt: str, is_json: bool = False) -> str | dict:
        import google.generativeai as genai
        if not self.model:
            raise ValueError("Gemini client is not available!")

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        generation_config = genai.types.GenerationConfig(temperature=0.3, max_output_tokens=8192)

        print_lg("Calling Gemini API...")
        response = self.model.generate_content(
            prompt,
            safety_settings=safety_settings,
            generation_config=generation_config,
            request_options={"timeout": 45},
        )
        if not response.parts:
            raise ValueError("Gemini response was empty (safety filter or empty content).")

        result = response.text
        try:
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                total = getattr(response.usage_metadata, 'total_token_count', 0) or 0
                if total:
                    from modules.bot_ui import update_api_usage
                    update_api_usage(total)
        except Exception:
            pass

        if is_json:
            clean = result.strip().strip('`')
            if clean.startswith('json'):
                clean = clean[4:].strip()
            return convert_to_json(clean)
        return result

    def answer_question(
        self, question, options=None, question_type='text',
        job_description=None, about_company=None,
        user_information_all=None, error_message=None, stream=None,
    ) -> str | dict:
        try:
            if not error_message:
                cached = get_answer_from_database(question, options=options)
                if cached:
                    print_lg(f"Found answer in QA Database: {cached}")
                    return cached

            print_lg(f"Answering question using Gemini AI: {question}")
            user_info = user_information_all or ""
            prompt = ""
            if error_message:
                prompt += (
                    f"IMPORTANT: The previous answer resulted in a validation error: "
                    f"'{error_message}'. Please provide a NEW answer.\n\n"
                )
            prompt += ai_answer_prompt.format(user_info, question)

            if options and question_type in ('single_select', 'multiple_select'):
                prompt += "\n\nOPTIONS:\n" + "\n".join(f"- {o}" for o in options)
                if question_type == 'single_select':
                    prompt += "\n\nPlease select exactly ONE option from the list above."
                else:
                    prompt += "\n\nYou may select MULTIPLE options from the list above if appropriate."

            if job_description:
                prompt += f"\n\nJOB DESCRIPTION:\n{job_description}"
            if about_company:
                prompt += f"\n\nABOUT COMPANY:\n{about_company}"

            answer = self._completion(prompt)
            if isinstance(answer, str) and not answer.startswith("{'error'"):
                save_to_qa_database(question, answer, options=options)
            return answer
        except Exception as e:
            critical_error_log("Error answering question with Gemini!", e)
            return {"error": str(e)}

    def evaluate_job(self, job_description: str, user_information_all: str) -> dict:
        try:
            print_lg("Evaluating job using Gemini AI...")
            user_info = user_information_all or ""
            prompt = evaluate_job_prompt.format(user_info, job_description)
            return self._completion(prompt, is_json=True)
        except Exception as e:
            critical_error_log("Error evaluating job with Gemini!", e)
            return {"error": str(e)}

    def extract_skills(self, job_description: str, stream: bool = None) -> dict:
        try:
            print_lg("Extracting skills using Gemini AI...")
            prompt = (
                extract_skills_prompt.format(job_description)
                + "\n\nImportant: Respond with only the JSON object, without any markdown formatting."
            )
            return self._completion(prompt, is_json=True)
        except Exception as e:
            critical_error_log("Error extracting skills with Gemini!", e)
            return {"error": str(e)}

    def close(self) -> None:
        pass  # Gemini client does not need explicit closing


# ── Factory ────────────────────────────────────────────────────────────────────

def get_ai_client() -> AIProvider | None:
    """
    Read config/secrets.py and return the matching AIProvider instance.
    Returns None (and logs the error) if configuration or connection fails.
    """
    from config.secrets import (
        use_AI, ai_provider, llm_api_url, llm_api_key,
        llm_model, llm_spec, stream_output,
    )

    if not use_AI:
        raise ValueError("AI is not enabled. Set use_AI = True in config/secrets.py.")

    if llm_spec == "gemini" or ai_provider.lower() == "gemini":
        try:
            import google.generativeai as genai
            print_lg("Configuring Gemini client...")
            if not llm_api_key or "YOUR_API_KEY" in llm_api_key:
                raise ValueError("Gemini API key is not set in config/secrets.py.")
            genai.configure(api_key=llm_api_key)

            available = [
                m.name for m in genai.list_models()
                if 'generateContent' in m.supported_generation_methods
            ]
            if not any(llm_model in m for m in available):
                raise ValueError(f"Gemini model '{llm_model}' not found or unavailable.")

            model = genai.GenerativeModel(llm_model)
            print_lg(f"---- SUCCESSFULLY CONFIGURED GEMINI CLIENT (model: {llm_model}) ----")
            return GeminiProvider(model)
        except Exception as e:
            _ai_error_alert("Error configuring Gemini client.", e, "Gemini Connection Error")
            return None

    else:  # openai-like: openai, groq, deepseek, ollama, or any custom endpoint
        try:
            from openai import OpenAI
            print_lg(f"Creating {ai_provider} client...")
            base_url = llm_api_url.rstrip('/')
            client = OpenAI(base_url=base_url, api_key=llm_api_key)

            # Validate model availability (some providers don't expose /models — skip gracefully)
            try:
                models = client.models.list()
                ids = [m.id for m in models.data]
                if ids and llm_model not in ids:
                    raise ValueError(f"Model '{llm_model}' not found. Available: {ids}")
            except Exception as model_err:
                print_lg(f"Model validation skipped or failed ({model_err}). Continuing.")

            print_lg(f"---- SUCCESSFULLY CREATED {ai_provider.upper()} CLIENT ----")
            print_lg(f"URL: {base_url}  |  Model: {llm_model}")
            return OpenAILikeProvider(client, llm_model, ai_provider, stream_output)
        except Exception as e:
            _ai_error_alert(f"Error creating {ai_provider} client. {_API_INSTRUCTIONS}", e)
            return None
