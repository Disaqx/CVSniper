# Tests

```
py -3 tests/test_filtros.py
py -3 tests/test_modo.py
```

No need for pytest, and no need to be in the project folder — they locate it
from their own path.

## Why they are written this way

Almost nothing here can be imported normally. `modules/job_search.py` imports
`modules/open_chrome.py`, which **launches Chrome at import time**; `bot_ui.py`
opens a Tkinter window. Importing either one to test a string comparison would
start a browser.

So these read the source with `ast`, pull out the individual functions and the
module-level constants they depend on, and run those in a namespace built from
the real `config/`. What gets tested is the actual shipped code, not a copy of
it — edit `job_search.py` and the test follows.

The trade-off: only pure predicates are covered. Anything that touches the
driver is not, and never will be by these.

## What they cover

`test_filtros.py` — everything that decides whether a job is worth applying to:

- the clearance check, which used to match `secret` inside the Spanish words
  *secreto* and *Secretaría* and silently threw those jobs away
- whole-word matching for `bad_words` and `title_bad_words`, so `PHP` does not
  fire inside `index.php` and `.NET` does not fire inside `careers.example.net`
- the focus filter, accent-insensitive
- the experience ceiling and its tolerance
- the residency detector: a remote job in Mexico that requires living in Mexico
  is dropped, one open to Latin America or to the user's own country is kept
- the remote sweep URL: `geoId`, `f_WT=2`, `f_JT`

`test_modo.py` — the application mode, the external applier and the form
answers:

- the three-position switch: its left-to-right order (easy · both · external,
  which is deliberately not the order of `APPLICATION_MODES`), which mode each
  third of a click lands on, and its i18n keys in both languages — including
  that the short labels stay at five characters or fewer, since longer ones
  overlap inside the switch
- that the header packs the switch before the title, so the title is what gives
  up space. Packed the other way round, the switch was squeezed to a sliver
- when `f_LF=f_AL` belongs in the URL, and `ensure_easy_apply_state()` run for
  real against a fake driver: it removes the filter when LinkedIn puts it back,
  restores it when it falls off, reloads nothing when the URL already agrees,
  and does not mangle the URL when the filter was its first parameter
- that Apply is clicked exactly once: `probe_apply_button()` is the only thing
  that clicks the generic apply button, and when it finds nothing the job is
  skipped instead of handed to `external_apply()` to click it again
- the ATS triage, the consent-checkbox detector, and `_xp_literal()` for the
  ids ATS platforms invent
- that the action button row still holds four buttons — five overflowed the
  panel and pushed STOP off the edge
- agreement questions: *"¿Está de acuerdo con ocupar el rol?"* must answer Yes.
  Answering No there is an instant rejection, and it is what the bot was doing.

## Adding a case

Use `check(name, actual, expected)`. It records the failure and keeps going, so
one run shows you everything that broke rather than the first thing.
