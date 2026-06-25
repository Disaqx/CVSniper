'''
CVSniper - Template de Respuestas / Answers Template

Rellena tus datos aqui / Fill in your data here.
Este archivo es tuyo - NUNCA se sube al repositorio.
This file is yours - it is NEVER uploaded to the repository.
'''

# Ruta de tu CV por defecto (PDF) / Default resume path (PDF)
default_resume_path = ""
'''
Example (Windows): "C:\\Users\\YourName\\Documents\\MyResume.pdf"
Example (Mac/Linux): "/home/yourname/Documents/MyResume.pdf"
'''

# Anios de experiencia a reportar / Years of experience to report
years_of_experience = "1"

# Necesitas visa de trabajo? / Do you need work visa sponsorship?
require_visa = "No"   # "Yes" or "No"

# Link de tu portfolio / website
website = ""

# Link de tu perfil de LinkedIn / Your LinkedIn profile URL
linkedIn = ""

# Ciudadania / Citizenship status
us_citizenship = "Other"
'''
Valid: "U.S. Citizen/Permanent Resident", "Non-citizen allowed to work for any employer",
       "Non-citizen allowed to work for current employer",
       "Non-citizen seeking work authorization", "Canadian Citizen/Permanent Resident", "Other"
'''

# Salario deseado (solo numeros) / Desired salary (numbers only)
desired_salary = 0

# Salario actual / Current salary (CTC)
current_ctc = 0

# Periodo de aviso en dias / Notice period in days
notice_period = 30

# Empleador reciente / Most recent employer
recent_employer = ""

# Nivel de confianza 1-10 / Confidence level 1-10
confidence_level = 8

# Nivel de inglés / English proficiency level
# Opciones: "none", "a1", "a2", "b1", "b2", "c1", "c2", "native"
# Deja "" si no aplicas a trabajos en inglés
english_level = ""

# Titular de LinkedIn / LinkedIn headline
linkedin_headline = ""

# Resumen de LinkedIn / LinkedIn summary
linkedin_summary = ""

# Carta de presentacion / Cover letter
cover_letter = ""

# Informacion completa para IA / Complete info for AI (to answer questions)
user_information_all = """
[FILL IN YOUR PROFESSIONAL SUMMARY HERE]
Include: your name, skills, work experience, education, achievements, and anything relevant to job applications.
The AI will use this information to answer screening questions on your behalf.
"""

# Opciones de comportamiento / Behavior options
pause_before_submit = False      # True: revisa antes de enviar / review before submit
pause_at_failed_question = False # True: pausa si no puede responder / pause if can't answer
overwrite_previous_answers = False
