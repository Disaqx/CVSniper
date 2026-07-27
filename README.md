# CVSniper — LinkedIn Easy Apply bot

CVSniper applies to LinkedIn jobs for you. Selenium drives the browser, an LLM
answers the application questions and screens listings against your profile,
and a floating control panel lets you watch, pause or stop it at any point.

**You never edit a config file by hand.** Everything is configured from the
settings window, and the first run walks you through it.

---

## Table of contents

- [Requirements](#requirements)
- [Install](#install)
- [First run](#first-run)
- [Configuration reference](#configuration-reference)
- [Project layout](#project-layout)
- [How a run works](#how-a-run-works)
- [AI providers](#ai-providers)
- [Control panel](#control-panel)
- [Output files](#output-files)
- [Common problems](#common-problems)
- [Privacy](#privacy)

---

## Requirements

| | |
|---|---|
| Python | 3.10 or newer (3.14 recommended) |
| Browser | Google Chrome, any recent version |
| LinkedIn | An account, ideally with a complete profile |
| LLM API key | Optional but strongly recommended — see [AI providers](#ai-providers) |

A free Groq key is enough to run the whole thing.

---

## Install

```bash
git clone https://github.com/Disaqx/CVSniper.git
cd CVSniper
```

Then run the setup script for your platform:

```bash
# Windows
setup\windows-setup.bat

# Linux / macOS
bash setup/setup.sh
```

It checks your Python version, installs the dependencies and creates your
config files from the templates. Or do it by hand:

```bash
pip install -r requirements.txt
python runAiBot.py
```

---

## First run

Launch the bot and it guides you through three steps:

**1. CV Wizard (optional).** Point it at your PDF resume and it fills in your
name, contact details, skills and experience automatically. Skip it and type
everything yourself if you prefer.

**2. Settings panel.** Review what the wizard extracted, add your LinkedIn
credentials and your LLM key, and set your search terms and filters.

**3. It starts.** The bot logs in, searches, and begins applying. The control
panel shows every action as it happens.

> Your resume goes in `all resumes/` and the path is set in the settings panel.

---

## Configuration reference

Five files under `config/`, all managed from the settings window. They are
**gitignored** — they hold your personal data and your API keys, and never
leave your machine.

### `personals.py` — who you are

`first_name` · `middle_name` · `last_name` · `phone_number` · `current_city` ·
`street` · `state` · `zipcode` · `country` · `university` · `degree` ·
`graduation_year` · `field_of_study` · `ethnicity` · `gender` ·
`disability_status` · `veteran_status`

### `secrets.py` — credentials and AI

| Field | What it is |
|---|---|
| `username` / `password` | LinkedIn login. Optional if Chrome already has a session |
| `use_AI` | Turn the LLM on or off |
| `ai_provider` | `groq`, `openai`, `deepseek`, `gemini`, `ollama` |
| `llm_api_url` | Endpoint. This is what makes any OpenAI-compatible provider work |
| `llm_api_key` | Your key |
| `llm_model` | Model name, e.g. `llama-3.3-70b-versatile` |

### `search.py` — what to look for

`search_terms` · `search_location` · `date_posted` · `sort_by` ·
`experience_level` · `job_type` · `on_site` · `easy_apply_only` · `companies` ·
`industry` · `bad_words` · `about_company_bad_words` ·
`primary_focus_keywords` · `secondary_focus_keywords` · `switch_number`

`bad_words` and the focus keywords are what stop the bot wasting applications
on listings that were never a fit.

### `questions.py` — answers and resume

| Field | Notes |
|---|---|
| `default_resume_path` | Relative to the project folder |
| `years_of_experience` | |
| `notice_period` | **Availability to start, in days. 0 = immediately** |
| `desired_salary` / `current_ctc` | |
| `us_citizenship` / `require_visa` | |
| `linkedin_headline` / `linkedin_summary` | |
| `user_information_all` | 200-300 words about you. The LLM uses this to answer screening questions — the better it is, the better the answers |
| `confidence_level` | 1-10. How willing the bot is to answer a question it is unsure about |
| `pause_before_submit` | Review each application before it goes out |

### `settings.py` — behaviour

`ui_language` · `run_non_stop` · `alternate_sortby` · `cycle_date_posted` ·
`click_gap` · `run_in_background` · `safe_mode` · `stealth_mode` ·
`smooth_scroll` · `keep_screen_awake` · `close_tabs`

> `click_gap` is the minimum pause between actions, in seconds. Lowering it
> makes the bot faster and easier for LinkedIn to spot.

---

## Project layout

```
CVSniper/
│
├── runAiBot.py                  <- entry point
├── app.py                       <- read-only Flask dashboard for the results
│
├── config/                      <- created on first run, gitignored
│   ├── personals.py             questions.py    search.py
│   ├── settings.py              secrets.py
│   └── *.default.py             <- the versioned templates
│
├── modules/
│   ├── bot_ui.py                <- floating control panel + settings window
│   ├── easy_apply.py            <- the Easy Apply modal: reads and answers every question
│   ├── job_search.py            <- search and filters
│   ├── linkedin_login.py        <- login and session reuse
│   ├── cv_wizard.py             <- config extraction from a PDF resume
│   ├── validator.py             <- checks the config before the browser opens
│   ├── helpers.py               <- logging, pacing, JSON, paths
│   ├── open_chrome.py           <- Chrome startup (importing this opens the browser)
│   ├── clickers_and_finders.py  <- Selenium wrappers for LinkedIn's DOM
│   ├── i18n.py                  <- interface strings, English and Spanish
│   │
│   └── ai/
│       ├── providers.py            <- provider abstraction, one interface for all
│       ├── prompts.py              <- prompt templates
│       ├── openaiConnections.py    <- CV Optimizer
│       ├── geminiConnections.py    <- Gemini client for the CV tools
│       ├── deepseekConnections.py
│       └── qa_database.py          <- local cache of questions and answers
│
├── all resumes/                 <- your PDF resume goes here
├── all excels/                  <- CSV history and the QA database
├── logs/                        <- one log file per day, plus screenshots
├── scripts/                     <- CV generation and release packaging
└── setup/                       <- install scripts
```

---

## How a run works

```
1. START
   ├─ create config files from the templates if this is the first run
   ├─ validate the config and stop early if anything is wrong
   ├─ open Chrome
   └─ show the control panel (and the wizard, if there is no config yet)

2. LOG IN
   └─ reuse the Chrome session if there is one, otherwise sign in

3. SEARCH
   └─ for every term in search_terms:
       ├─ apply the configured filters
       └─ walk the results page by page

4. SCREEN EACH LISTING
   ├─ already applied?           -> skip
   ├─ matches bad_words?         -> skip
   ├─ outside the focus filter?  -> skip
   └─ AI checks it against your profile -> apply or skip, with a reason

5. APPLY
   ├─ personal details from your config
   ├─ questions already answered before, from qa_database.json
   ├─ new questions -> the AI answers and the answer is cached
   ├─ optional manual review (pause_before_submit)
   └─ submit

6. RECORD
   ├─ applied -> all excels/all_applied_applications_history.csv
   └─ failed  -> all excels/all_failed_applications_history.csv
                 plus a screenshot in logs/screenshots/
```

---

## AI providers

Everything the bot does while applying goes through `modules/ai/providers.py`,
which exposes one interface:

| Method | What it does |
|---|---|
| `answer_question(...)` | Answers a form field: text, single select or yes/no |
| `evaluate_job(...)` | Scores the listing against your profile and says why |
| `extract_skills(...)` | Pulls the required and nice-to-have skills out as JSON |

Any **OpenAI-compatible** endpoint works — only `llm_api_url` changes. That
covers Groq, OpenAI, DeepSeek, Ollama and most hosted providers. Gemini has its
own path because its SDK is different.

Providers that support structured output get a strict JSON schema, so the model
cannot drift off-format. The rest get the contract spelled out in the prompt.

Every answer is cached in `all excels/qa_database.json`, so the same question is
never paid for twice.

**The prompts are built to refuse invention.** An answer the bot makes up is
submitted under your real name, so when your profile does not contain the
answer the model is told to give the most conservative truthful response rather
than guess.

---

## Control panel

A floating window sits in the corner of the screen while the bot runs:

- **Live log** of every action
- **Settings** — opens the configuration panel
- **Optimize CV** — rewrites your resume with the AI and renders a new PDF
- **Pause** — stops at the next checkpoint, including before each AI call
- **Stop** — ends the run. Needs a second click to confirm, and force-exits
  after 5 seconds if Chrome has hung

Keyboard: `Ctrl+P` pause/resume · `Ctrl+Q` or `Ctrl+C` stop.

---

## Output files

| File | Contents |
|---|---|
| `all excels/all_applied_applications_history.csv` | Every application: job id, title, company, link, questions found, date |
| `all excels/all_failed_applications_history.csv` | Failures with the reason, the stack trace and the screenshot name |
| `all excels/qa_database.json` | Cached questions and answers |
| `logs/YYYY-MM-DD.log` | Everything the bot did that day |
| `logs/screenshots/` | Page captures from the moment each failure happened |

---

## Common problems

| Symptom | Cause | Fix |
|---|---|---|
| Config errors listed on startup | Something invalid in `config/` | The validator names every problem at once — fix them and rerun |
| Browser opens and nothing happens | Chrome is already running with the same profile | Close Chrome, or set `safe_mode = True` to use a separate profile |
| LinkedIn asks for verification | It spotted the automation | Keep `stealth_mode = True` and raise `click_gap` |
| A location field is left empty | The autocomplete list was never opened | Fixed — the bot now picks the first suggestion. Check the log for `[Typeahead]` |
| Pause seems to do nothing | An AI call was already in flight | It stops at the next checkpoint, at most one call later |
| CV Wizard extracts nothing | The PDF is a scan with no text layer | Use a PDF with real text |
| "Failed to update the excel" | The CSV is open in Excel | Close it and press Resume |

---

## Privacy

Everything stays on your machine. There is no server, no telemetry and no
account.

- `config/*.py` hold your data and keys and are **gitignored** — only the
  `*.default.py` templates are versioned
- Your resume, your CSV history and your logs never leave the folder
- The only outbound traffic is LinkedIn itself and the LLM provider you chose

> Automating LinkedIn is against their terms of service. Your account is yours
> to risk. `stealth_mode` and `click_gap` exist to reduce the odds, not to
> remove them.

---

## License

MIT — see [LICENSE](LICENSE).
