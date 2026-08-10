"""Prompt templates shared by every LLM provider.

All of these are consumed with `str.format()`, so any literal brace meant for
the model has to be doubled — `{{` and `}}`. A single brace is read as a
placeholder and raises KeyError at runtime, which is the classic way these
files break.

Placeholders, in order:
    ai_answer_prompt                (user_info, question)
    evaluate_job_prompt             (user_info, job_description)
    extract_skills_prompt           (job_description)
    deepseek_extract_skills_prompt  (job_description)

The JSON keys below are a contract with the rest of the codebase. Reword the
instructions freely, but do not rename a key without updating the consumers.
"""

# ---------------------------------------------------------------------------
# Answering application questions
# ---------------------------------------------------------------------------
# The single most damaging failure mode of a job-application bot is inventing
# credentials the candidate does not have. That is why the rules below are
# stated as hard constraints and repeated at the end: a fabricated answer is
# worse than a blank one, because it is submitted under the user's real name.

ai_answer_prompt = """You are filling in a job application form on behalf of a real candidate.

CANDIDATE PROFILE
-----------------
{}

QUESTION ON THE FORM
--------------------
{}

RULES
-----
1. Answer using ONLY the facts in the candidate profile. Never invent
   experience, qualifications, certifications, salaries or dates.
2. If the profile does not contain the answer, give the most conservative
   truthful response instead of guessing.
3. Match the format the field expects:
   - years of experience  -> a plain number, e.g. 3
   - yes / no             -> exactly "Yes" or "No"
   - salary               -> a plain number, no currency symbol or separators
   - free text            -> one or two sentences, first person
4. Return the answer and nothing else. No preamble, no explanation, no
   quotes around it, no markdown.
5. Write in the same language as the question.

A wrong answer is submitted under the candidate's real name and can cost them
the role. When in doubt, be accurate rather than impressive.

ANSWER:"""


# ---------------------------------------------------------------------------
# Judging whether a posting is worth applying to
# ---------------------------------------------------------------------------

evaluate_job_prompt = """You are screening a job posting for a candidate who is
actively job hunting and wants to apply broadly.

CANDIDATE PROFILE
-----------------
{}

JOB POSTING
-----------
{}

Your job is to spot the few postings that are a waste of an application — not to
find reasons to say no. An application costs the candidate almost nothing, and
postings routinely list more than the employer settles for.

Treat as NOT disqualifying, on their own:
  - missing some of the listed skills, tools or certifications
  - asking for a few more years of experience than the candidate has
  - a degree listed as "preferred", "desirable" or "a plus"
  - a remote posting listed in another country that does NOT say where the
    candidate must live
  - unfamiliar industry, product or company size

Treat as genuinely disqualifying:
  - a different profession entirely (e.g. a nurse, a lawyer, a welder)
  - a legal barrier the candidate cannot clear: citizenship or work
    authorisation they do not hold, a licence or clearance they do not have
  - a language the posting requires and the candidate does not speak
  - seniority far beyond the candidate's (a director or head-of role when the
    candidate is early career)
  - on-site work in a city the candidate cannot reach
  - a REMOTE role that still restricts where the candidate may live, to
    somewhere they are not: "must reside in", "must be located in", "must be
    authorised to work in", "residents of X only", "no visa sponsorship" in a
    posting scoped to one country. Remote on a job board means "no office", not
    "hires from anywhere" — read the posting for the real restriction.
    A remote role open to the candidate's own country or region is fine.

Reply with a single JSON object, no markdown fences and no text around it:

{{
  "meets_requirements": true or false,
  "reason": "two or three sentences: what matches, what is missing, and whether anything here is a real barrier",
  "score": 0 to 100,
  "role": "the job title exactly as it appears in the posting"
}}

Scoring guide:
   0-24   a different profession, or a barrier the candidate cannot clear
  25-49   a stretch, but an application is not wasted
  50-74   a reasonable fit with gaps the candidate could be trained on
  75-100  meets the stated requirements

Set "meets_requirements" to false ONLY for the genuinely disqualifying cases
listed above. A gap in skills or years is a lower score, not a false."""


def build_evaluate_job_prompt(user_info: str, job_description: str) -> str:
    '''
    Fills `evaluate_job_prompt`, prepending where the candidate actually lives
    and may legally work.

    Without this the model has only `user_information_all`, a free-text blurb
    that usually never states a country — so it cannot tell a remote job that
    hires from anywhere from one that quietly requires living in the country it
    was posted in. That is the single most common way a worldwide remote sweep
    wastes applications.
    '''
    try:
        from config.personals import country as _pais
    except Exception:
        _pais = ""
    try:
        from config.search import work_authorized_countries as _autorizado
    except Exception:
        _autorizado = []

    cabecera = []
    if _pais:
        cabecera.append(f"Lives in: {_pais}")
    if _autorizado:
        cabecera.append("Can legally work, without the employer sponsoring anything, in: "
                        + ", ".join(str(p) for p in _autorizado))
    if cabecera:
        cabecera.append("Anywhere else would need sponsorship or relocation.")
        user_info = "\n".join(cabecera) + "\n\n" + (user_info or "")

    return evaluate_job_prompt.format(user_info or "", job_description)


# ---------------------------------------------------------------------------
# Pulling the skills out of a posting
# ---------------------------------------------------------------------------

_SKILLS_RULES = """Read the posting and sort every skill it mentions into these buckets:

  tech_stack        languages, frameworks, databases and platforms the team
                    works with day to day (e.g. Python, React, PostgreSQL, AWS)
  technical_skills  technical abilities that are not a named product
                    (e.g. REST API design, CI/CD, unit testing, troubleshooting)
  other_skills      everything non-technical: communication, teamwork,
                    languages spoken, certifications, degrees, licences
  required_skills   the subset that the posting states as mandatory — look for
                    "required", "must have", "essential", "minimum"
  nice_to_have      the subset presented as a plus, bonus, desirable or optional

Rules:
  - Use the exact wording of the posting. Do not translate or normalise names.
  - A skill may appear in both a category bucket and required/nice_to_have.
  - If the posting does not state whether something is mandatory, leave it out
    of required_skills instead of assuming.
  - Never invent a skill that is not in the text.
  - Every field must be present. Use an empty array when there is nothing."""

extract_skills_prompt = (
    "You are parsing a job posting into structured data.\n\n"
    "JOB POSTING\n-----------\n{}\n\n"
    + _SKILLS_RULES
    + "\n\nReturn one JSON object with exactly these five keys: tech_stack, "
      "technical_skills, other_skills, required_skills, nice_to_have. "
      "Each value is an array of strings."
)

# DeepSeek has no structured-output mode, so the JSON contract has to live in
# the prompt itself and be spelled out far more forcefully.
deepseek_extract_skills_prompt = (
    "You are parsing a job posting into structured data.\n\n"
    "JOB POSTING\n-----------\n{}\n\n"
    + _SKILLS_RULES
    + """

OUTPUT FORMAT — follow this exactly:

{{
  "tech_stack": ["..."],
  "technical_skills": ["..."],
  "other_skills": ["..."],
  "required_skills": ["..."],
  "nice_to_have": ["..."]
}}

Output the raw JSON object and nothing else. No ```json fences, no commentary
before or after, no trailing commas. Your entire reply must parse with
json.loads() on the first attempt."""
)


# ---------------------------------------------------------------------------
# Structured-output schema for providers that support it
# ---------------------------------------------------------------------------
# OpenAI-compatible strict mode requires every property to be listed in
# "required" and "additionalProperties" to be false. Groq, OpenAI and any
# other compatible endpoint enforce this, so the model cannot drift off-schema
# and convert_to_json() never has to repair the reply.

_SKILL_ARRAY = {
    "type": "array",
    "items": {"type": "string"},
}

extract_skills_response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "extracted_skills",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "tech_stack": _SKILL_ARRAY,
                "technical_skills": _SKILL_ARRAY,
                "other_skills": _SKILL_ARRAY,
                "required_skills": _SKILL_ARRAY,
                "nice_to_have": _SKILL_ARRAY,
            },
            "required": [
                "tech_stack",
                "technical_skills",
                "other_skills",
                "required_skills",
                "nice_to_have",
            ],
            "additionalProperties": False,
        },
    },
}
