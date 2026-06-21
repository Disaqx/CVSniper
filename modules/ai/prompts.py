"""
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

Support me: https://github.com/sponsors/GodsScion

version:    26.01.20.5.08
"""


##> Common Response Formats
array_of_strings = {"type": "array", "items": {"type": "string"}}
"""
Response schema to represent array of strings `["string1", "string2"]`
"""
#<


##> Extract Skills

# Structure of messages = `[{"role": "user", "content": extract_skills_prompt}]`

extract_skills_prompt = """
You are a job requirements extractor and classifier. Your task is to extract all skills mentioned in a job description and classify them into five categories:
1. "tech_stack": Identify all skills related to programming languages, frameworks, libraries, databases, and other technologies used in software development. Examples include Python, React.js, Node.js, Elasticsearch, Algolia, MongoDB, Spring Boot, .NET, etc.
2. "technical_skills": Capture skills related to technical expertise beyond specific tools, such as architectural design or specialized fields within engineering. Examples include System Architecture, Data Engineering, System Design, Microservices, Distributed Systems, etc.
3. "other_skills": Include non-technical skills like interpersonal, leadership, and teamwork abilities. Examples include Communication skills, Managerial roles, Cross-team collaboration, etc.
4. "required_skills": All skills specifically listed as required or expected from an ideal candidate. Include both technical and non-technical skills.
5. "nice_to_have": Any skills or qualifications listed as preferred or beneficial for the role but not mandatory.
Return the output in the following JSON format with no additional commentary:
{{
    "tech_stack": [],
    "technical_skills": [],
    "other_skills": [],
    "required_skills": [],
    "nice_to_have": []
}}

JOB DESCRIPTION:
{}
"""
"""
Use `extract_skills_prompt.format(job_description)` to insert `job_description`.
"""

# DeepSeek-specific optimized prompt, emphasis on returning only JSON without using json_schema
deepseek_extract_skills_prompt = """
You are a job requirements extractor and classifier. Your task is to extract all skills mentioned in a job description and classify them into five categories:
1. "tech_stack": Identify all skills related to programming languages, frameworks, libraries, databases, and other technologies used in software development. Examples include Python, React.js, Node.js, Elasticsearch, Algolia, MongoDB, Spring Boot, .NET, etc.
2. "technical_skills": Capture skills related to technical expertise beyond specific tools, such as architectural design or specialized fields within engineering. Examples include System Architecture, Data Engineering, System Design, Microservices, Distributed Systems, etc.
3. "other_skills": Include non-technical skills like interpersonal, leadership, and teamwork abilities. Examples include Communication skills, Managerial roles, Cross-team collaboration, etc.
4. "required_skills": All skills specifically listed as required or expected from an ideal candidate. Include both technical and non-technical skills.
5. "nice_to_have": Any skills or qualifications listed as preferred or beneficial for the role but not mandatory.

IMPORTANT: You must ONLY return valid JSON object in the exact format shown below - no additional text, explanations, or commentary.
Each category should contain an array of strings, even if empty.

{{
    "tech_stack": ["Example Skill 1", "Example Skill 2"],
    "technical_skills": ["Example Skill 1", "Example Skill 2"],
    "other_skills": ["Example Skill 1", "Example Skill 2"],
    "required_skills": ["Example Skill 1", "Example Skill 2"],
    "nice_to_have": ["Example Skill 1", "Example Skill 2"]
}}

JOB DESCRIPTION:
{}
"""
"""
DeepSeek optimized version, use `deepseek_extract_skills_prompt.format(job_description)` to insert `job_description`.
"""


extract_skills_response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "Skills_Extraction_Response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "tech_stack": array_of_strings,
                "technical_skills": array_of_strings,
                "other_skills": array_of_strings,
                "required_skills": array_of_strings,
                "nice_to_have": array_of_strings,
            },
            "required": [
                "tech_stack",
                "technical_skills",
                "other_skills",
                "required_skills",
                "nice_to_have",
            ],
            "additionalProperties": False
        },
    },
}
"""
Response schema for `extract_skills` function
"""
#<

##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
##> Answer Questions
# Structure of messages = `[{"role": "user", "content": answer_questions_prompt}]`

ai_answer_prompt = """
You are an intelligent AI assistant filling out a job application form on behalf of the user.
Respond concisely based on the type of question:

1. If the question asks for **years of experience, duration, or numeric value**, return **only a number** (e.g., "0", "2", "5").
2. If the question is **a Yes/No question**, return **only "Yes" or "No"** (or "Sí" or "No" if the options are in Spanish).
3. If the question provides specific OPTIONS, your answer MUST EXACTLY match one of the options character-by-character. Do not translate it.
4. Do **not** repeat the question in your answer.

CRITICAL INSTRUCTIONS ON ANSWERING STRATEGY:
- Answer truthfully according to the user's information.
- If the question asks if the user has a specific technical skill, certification, or years of experience that is NOT explicitly supported by the user's CV, you MUST answer "No" or "0". Do not lie, exaggerate, or hallucinate experience.
- If the user is a student, their years of professional experience in specialized fields (like cybersecurity) is "0" unless stated otherwise.
- If the question asks about a generic soft-skill or an evident requirement (e.g., "Are you willing to work hybrid?", "Do you speak fluent English?", "Are you authorized to work in this country?"), default to the positive answer (e.g., "Yes") unless the CV contradicts it.
- SENSITIVE QUESTIONS — ALWAYS answer "No" for these categories unless the user's information EXPLICITLY states otherwise:
  * Criminal history: felony, misdemeanor, conviction, arrested, criminal charges, crime, criminal record, background check disclosure
  * Previous employment at THIS specific company: "Have you worked here before?", "Are you a former employee?", "Previously employed by us?" — ONLY answer "Yes" if that exact company is in the user's work history
  * Previous applications: "Have you applied here before?", "Have you interviewed with us?" — default "No"
  * Lawsuits or legal disputes involving the company
  * Any question framed as a negative disclosure (drug use, misconduct, termination for cause)

**User Information:** 
{}

**QUESTION Start from here:**  
{}
"""
#<

##> Evaluate Job Requirements
# Structure of messages = `[{"role": "user", "content": evaluate_job_prompt}]`

evaluate_job_prompt = """
You are a pragmatic career assistant deciding if a job is worth applying to.
Your task is to analyze the user's profile/CV and the job description.

INSTRUCTIONS:
- Return ONLY a valid JSON object in the exact format shown below — no extra text.
- GOAL: Cast a wide net. Job descriptions are wish lists. Candidates rarely meet 100% of requirements and still get hired.
- Set "meets_requirements" to FALSE only when the candidate is CLEARLY disqualified:
  * Experience gap is large: role requires 5+ years and candidate has under 2 years
  * Completely different domain (e.g., nurse applying for software architect)
  * Hard legal/location requirement the candidate cannot meet (e.g., must be on-site in a country they are not in)
  * Role is senior/director/executive level and candidate is junior
- Set "meets_requirements" to TRUE when:
  * The candidate works in the same field or a closely adjacent one
  * The candidate meets at least 60% of core requirements
  * Missing items are specific tools or certifications — these are learnable and not disqualifiers
  * Experience years are close (within 1-2 years of the requirement)
- Do NOT reject because the candidate lacks 1-2 specific tools (e.g., a specific MDM platform, a specific ticketing system). If they have the fundamentals, they can learn the tool.
- Assign a "score" from 1 to 10 based on overall match quality (7+ = strong match, 5-6 = reasonable match, below 5 = poor match).

Output Format:
{{
    "meets_requirements": true/false,
    "score": 1-10,
    "reason": "Brief 1-sentence reason for your decision."
}}

**User Information:**
{}

**Job Description:**
{}
"""
#<
#<