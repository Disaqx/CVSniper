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

> Screening logic is covered by `tests/` — run `py -3 tests/test_filtros.py`
> after changing a filter. See `tests/README.md` for why they are written the
> way they are.

### The mode switch

Top-right of the control panel is a three-position switch. Left is Easy Apply
only, the middle is both, right is external only. It writes itself back to
`application_mode` in `settings.py`, so it survives a restart, and the bot
re-reads it between jobs — flipping it mid-run takes effect on the next listing.

| Position | What it does |
|---|---|
| **EASY** (left) | Adds `f_LF=f_AL` to the search URL, so LinkedIn returns nothing else. The fastest mode |
| **BOTH** (middle) | No Easy Apply filter at all |
| **EXT** (right) | LinkedIn has no "not Easy Apply" filter, so the bot walks every result and skips the Easy Apply ones itself. Slower by design |

The filter is re-checked on every page of results, not just once after the
filter panel. LinkedIn puts `f_LF=f_AL` back by itself on some navigations, and
that drift is what used to turn an external-only run into an Easy Apply one
halfway through.

### External applications

An external job is one whose Apply button leaves LinkedIn. The bot clicks Apply
**once** and works out what happened — an Easy Apply modal, a new tab, or this
tab navigating away — then reopens the application page in a tab of its own.

With `external_apply_enabled = False` nothing is filled in: the link is just
recorded in the CSV. That is a cheap way to find out which ATS platforms your
searches actually turn up before trusting the auto-fill with any of them.

With it True, the platform decides what happens next:

| | Platforms | Behaviour |
|---|---|---|
| Auto-filled | Greenhouse, Lever, Ashby, Workable, Recruitee, SmartRecruiters, Breezy, Teamtailor, and any unrecognised single-page form | CV uploaded first (many parse it and prefill the rest), then text fields, dropdowns, React comboboxes, radio groups and consent checkboxes |
| Manual | Workday, iCIMS, SuccessFactors, Taleo/Oracle, BrassRing, Eightfold | Account creation, email verification and usually CAPTCHA. The link is recorded and nothing is touched |

Submitting is conservative. It happens only when every **required** field could
be answered — one unanswered required field and the application is left alone,
with the field names in the log. `pause_before_submit_external = True` asks for
confirmation first; False fills, submits, verifies and moves on unattended.

A submitted application always closes its tab. `close_tabs` decides the rest:
True closes the unfinished ones too (the link is still in the CSV), False leaves
them open to finish by hand.

"Submitted" means a confirmation message appeared, or the form vanished *and*
the URL changed. A URL change on its own is not enough — a validation error that
scrolls the page also changes it, and that used to count as an application sent.

**Known limit:** if LinkedIn navigates the results tab itself instead of opening
one (rare — apply links are forced to `target=_blank`), coming back re-renders
the page and the bot may lose the rest of that page of results before moving to
the next search term.

**Pause** blocks the bot at the next checkpoint. Checkpoints sit before every AI
call, on each page of the Easy Apply modal, and on each field of an external
form — but a request already in flight to the LLM cannot be cancelled, so
expect a few seconds before it settles.

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

**Remote jobs anywhere.** `search_location` only ever finds jobs tied to that one
place. Set `remote_worldwide = True` and every search term is also run against
each entry in `remote_search_locations` with LinkedIn's Remote filter forced on,
which is how you reach markets that pay better than your own. It multiplies the
run time by the number of locations, so keep the list short.

Know what that filter actually does, though. **LinkedIn's "Remote" means "you
don't come to an office" — not "we hire from anywhere".** A job listed Remote in
Mexico can still require you to live in Mexico, and LinkedIn has no filter for
that; the restriction only ever appears in the description. There is also no
freelance filter — `remote_job_types = ["C"]` (Contract) is the closest thing,
and it is where most hire-from-anywhere work sits.

So the location list is only half of it. `work_authorized_countries` is the
other half: list the countries you can work from without the employer
sponsoring anything, and postings that demand residency somewhere else get
dropped after their description is read. `Worldwide` is the entry that actually
surfaces globally-open roles — it carries LinkedIn's `geoId=92000000`. Any other
location can be pinned by writing it as `Name|geoId`.

**How picky the bot is.** Five settings decide how many listings survive
screening. Loosen them if the bot is skipping jobs you would have applied to;
tighten them if it is applying to junk.

| Setting | Effect |
|---|---|
| `ai_min_score` | The main knob. The AI scores each posting 0-100 and anything below this is skipped. `0` never skips, `25` skips only a different profession, `70` applies only where you meet every stated requirement |
| `ai_prescreen_strict` | Also honour the AI's own pass/fail verdict on hard requirements. Off by default — that verdict fails a candidate for missing any listed skill |
| `experience_tolerance` | Years above `current_experience` you will still apply to. Postings list the ceiling of a range and settle for less |
| `enable_job_focus_filter` | Off by default. When on, a job is dropped unless its title matches `primary_focus_keywords` — precise, but it silently discards every title you did not anticipate |
| `title_bad_words` | The cheap alternative: instead of listing every title you want, list the few you don't. Runs either way |
| `work_authorized_countries` | Drops the "remote" job that still wants you living in another country. Defaults to your `country` from `personals.py` |

`bad_words` and `title_bad_words` are matched as whole words, case- and
accent-insensitive. Keep them short — every entry is a job you will never see.

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
   └─ for every term in search_terms, in search_location:
       ├─ apply the configured filters
       └─ walk the results page by page
   └─ then again in each remote_search_locations, Remote only

4. SCREEN EACH LISTING
   ├─ already applied?              -> skip
   ├─ wrong kind for the mode
   │  (Easy Apply vs external)?     -> skip
   ├─ title in title_bad_words?     -> skip
   ├─ matches bad_words?            -> skip
   ├─ years required above your
   │  experience + tolerance?       -> skip
   ├─ "remote" but requires living
   │  somewhere you cannot work?    -> skip
   ├─ outside the focus filter?     -> skip (only if it is enabled)
   └─ AI scores it against your profile
      └─ below ai_min_score?        -> skip, with a reason

5. APPLY
   └─ click Apply ONCE and see where it goes:
       ├─ Easy Apply modal -> walk its pages
       │   ├─ personal details from your config
       │   ├─ questions already answered before, from qa_database.json
       │   ├─ new questions -> the AI answers and the answer is cached
       │   ├─ optional manual review (pause_before_submit)
       │   └─ submit
       ├─ a page outside LinkedIn -> reopen it in its own tab
       │   ├─ walled ATS (Workday, iCIMS...)? -> record the link, done
       │   ├─ upload the CV, fill the form, tick the consent boxes
       │   ├─ any required field unanswered? -> record the link, done
       │   ├─ optional manual review (pause_before_submit_external)
       │   └─ submit, verify, close the tab
       └─ nowhere -> skip

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
