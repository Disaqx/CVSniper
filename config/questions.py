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


###################################################### APPLICATION INPUTS ######################################################


# >>>>>>>>>>> Easy Apply Questions & Inputs <<<<<<<<<<<

# Give an relative path of your default resume to be uploaded. If file in not found, will continue using your previously uploaded resume in LinkedIn.
default_resume_path = "all resumes/Cesar_Jimenez_CV.pdf"

# What do you want to answer for questions that ask about years of experience you have, this is different from current_experience?
years_of_experience = 3

# Do you need visa sponsorship now or in future?
require_visa = "No"

# What is the link to your portfolio website, leave it empty as "", if you want to leave this question unanswered
website = ""

# Please provide the link to your LinkedIn profile.
linkedIn = "https://www.linkedin.com/in/caesarjimez/"

# What is the status of your citizenship? # If left empty as "", tool will not answer the question. However, note that some companies make it compulsory to be answered
# Valid options are: "U.S. Citizen/Permanent Resident", "Non-citizen allowed to work for any employer", "Non-citizen allowed to work for current employer", "Non-citizen seeking work authorization", "Canadian Citizen/Permanent Resident" or "Other"
us_citizenship = "Other"



## SOME ANNOYING QUESTIONS BY COMPANIES 🫠 ##

# What to enter in your desired salary question (American and European), What is your expected CTC (South Asian and others)?, only enter in numbers as some companies only allow numbers,
desired_salary = 4000000
'''
Note: If question has the word "lakhs" in it (Example: What is your expected CTC in lakhs),
then it will add '.' before last 5 digits and answer. Examples:
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
And if asked in months, then it will divide by 12 and answer. Examples:
* 2400000 will be answered as "200000"
* 850000 will be answered as "70833"
'''

# What is your current CTC? Some companies make it compulsory to be answered in numbers...
current_ctc = 1200
'''
Note: If question has the word "lakhs" in it (Example: What is your current CTC in lakhs),
then it will add '.' before last 5 digits and answer. Examples:
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
# And if asked in months, then it will divide by 12 and answer. Examples:
# * 2400000 will be answered as "200000"
# * 850000 will be answered as "70833"
'''

# (In Development) # Currency of salaries you mentioned. Companies that allow string inputs will add this tag to the end of numbers. Eg:
# currency = "USD"                 # "USD", "INR", "EUR", etc.

# What is your notice period in days?
notice_period = 0
'''
Note: If question has 'month' or 'week' in it (Example: What is your notice period in months),
then it will divide by 30 or 7 and answer respectively. Examples:
* For notice_period = 66:
  - "66" OR "2" if asked in months OR "9" if asked in weeks
* For notice_period = 15:"
  - "15" OR "0" if asked in months OR "2" if asked in weeks
* For notice_period = 0:
  - "0" OR "0" if asked in months OR "0" if asked in weeks
'''

# Your LinkedIn headline in quotes Eg: "Software Engineer @ Google, Masters in Computer Science", "Recent Grad Student @ MIT, Computer Science"
linkedin_headline = "IT Support Specialist | Active Directory & Microsoft 365 | Help Desk & Operational Support"

# Your summary in quotes, use \n to add line breaks if using single quotes "Summary".You can skip \n if using triple quotes """Summary"""
linkedin_summary = "Technical Support professional with a \"Builder\" mindset and a strong foundation in IT infrastructure. Expert in managing complex systems, including Active Directory, Microsoft 365, and Linux environments. Proven track record in high-stakes environments (Airbnb, Uber) combining bilingual communication with deep technical troubleshooting and Python automation."

'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Your cover letter in quotes, use \n to add line breaks if using single quotes "Cover Letter".You can skip \n if using triple quotes """Cover Letter""" (This question makes sense though)
cover_letter = """
To whom it may concern,

I am writing to express my interest in the IT Support / Operational Support position. With a strong background in managing digital infrastructure, user permissions (Active Directory/M365), and executive communications at companies like Keller Williams, Airbnb, and Uber, I am confident in my ability to contribute effectively to your team.

What sets me apart is my technical versatility. Beyond high-level support, I possess a deep "Builder" mindset with hands-on experience in Python scripting for automation, advanced terminal proficiency, and system administration. I have also developed a "Proof of Tech Portfolio" showcasing my work in hardware hacking, Linux system modding, and 3D Engineering.

Throughout my career, I have excelled in resolving complex issues and providing high-quality support in fast-paced environments. I am a bilingual professional with a proactive approach to problem-solving and a dedication to operational excellence.

Thank you for considering my application. I look forward to the possibility of discussing how my skills and experience align with your needs.

Sincerely,
Cesar Jimenez
"""
##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------

# Your user_information_all letter in quotes, use \n to add line breaks if using single quotes "user_information_all".You can skip \n if using triple quotes """user_information_all""" (This question makes sense though)
# We use this to pass to AI to generate answer from information , Assuing Information contians eg: resume  all the information like name, experience, skills, Country, any illness etc. 
user_information_all = """
Name: Cesar Jimenez
Location: Bogotá, Colombia
Phone: +57 323 9301232
Email: Cesardjm2003@gmail.com
LinkedIn: linkedin.com/in/caesarjimez/

Technical Expertise:
- Systems Administration: Active Directory (user management, group policies), Microsoft 365 Admin Center (Outlook, Teams, SharePoint).
- Support: Help Desk, Executive Support, Troubleshooting (Zendesk, JIRA).
- Programming & Automation: Python scripting for process optimization and automation. 
- Terminal: Advanced proficiency in Bash and PowerShell.
- Infrastructure: Linux (Ubuntu/Debian), Windows Server, PostgreSQL, Hadoop.
- Security: Secure Boot (EFI), Privilege Management, Network Auditing.
- Hardware: PC Building, Modding, Precision Soldering.

Experience Summary:
- Keller Williams | Tech Support Specialist (Feb 2025 – March 2026)
- Airbnb | Executive Support (May 2023 – Nov 2024)
- Uber | Support Representative (Dec 2022 – April 2023)

Education:
- CSA (Colegio San Agustin) en Bogota
- Google IT Support Professional Certificate (June 2025)

Relocation & International Roles:
- Open to international opportunities: Yes
- Willing to relocate to another country if supported by employer: Yes
"""
##<
'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Name of your most recent employer
recent_employer = "Keller Williams"

# Example question: "On a scale of 1-10 how much experience do you have building web or mobile applications? 1 being very little or only in school, 10 being that you have built and launched applications to real users"
confidence_level = 9
##



# >>>>>>>>>>> RELATED SETTINGS <<<<<<<<<<<

## Allow Manual Inputs
# Should the tool pause before every submit application during easy apply to let you check the information?
pause_before_submit = False
'''
Note: Will be treated as False if `run_in_background = True`
'''

# Should the tool pause if it needs help in answering questions during easy apply?
# Note: If set as False will answer randomly...
pause_at_failed_question = True
'''
Note: Will be treated as False if `run_in_background = True`
'''
##

# Do you want to overwrite previous answers?
overwrite_previous_answers = False
