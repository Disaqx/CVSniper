'''
Module: qa_database.py

Stores question-answer pairs to a local JSON file so the bot can
"remember" answers it has already given and reuse them in future sessions.

Matching strategy (in order):
1. Exact match on the normalized question.
2. Token-set match — same words after removing accents, punctuation and
   stopwords, regardless of order ("years of experience with Python?" ==
   "Years of experience with python").
3. Fuzzy match (difflib) with a high cutoff, but ONLY if the distinguishing
   content tokens are identical — this prevents "experience with Python"
   from matching "experience with Java".

When `options` are provided (select questions), a cached answer is returned
only if it actually matches one of the current options; otherwise the caller
falls through to the AI with full options context.

File location: modules/ai/qa_database.py
'''

import os
import json
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

# Path to the QA database file
_QA_DB_PATH = os.path.join("all excels", "qa_database.json")
# Old flat-format database ({question: answer}) from earlier versions;
# merged into the main DB on first load, then renamed.
_LEGACY_DB_PATH = "qa_database.json"

_FUZZY_CUTOFF = 0.90

# Words that never distinguish one question from another
_STOPWORDS = frozenset("""
a an the of in on at to for with do you your does are is have has how many
much what which please select if any and or
el la los las un una de del en con para por que cual cuales cuantos cuantas
como tienes tiene eres es hay tu su y o si
""".split())

# ── In-memory cache ────────────────────────────────────────────────────────────

_cache: dict | None = None
_cache_mtime: float | None = None


def _normalize(text: str) -> str:
    """Lowercase, strip accents/punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _content_tokens(normalized: str) -> frozenset:
    return frozenset(t for t in normalized.split() if t not in _STOPWORDS)


def _migrate_legacy() -> None:
    """One-time merge of the old flat root-level DB into the current one."""
    if not os.path.exists(_LEGACY_DB_PATH):
        return
    try:
        with open(_LEGACY_DB_PATH, "r", encoding="utf-8") as f:
            legacy = json.load(f)
        db = _load_db(migrate=False)
        added = 0
        for question, answer in legacy.items():
            if not isinstance(answer, str):
                continue
            key = _normalize(question)
            if key and key not in db:
                db[key] = {
                    "question": question.strip(),
                    "answer": answer.strip(),
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "use_count": 0,
                }
                added += 1
        _save_db(db)
        os.replace(_LEGACY_DB_PATH, _LEGACY_DB_PATH + ".migrated")
        print(f"[qa_database] Migrated {added} legacy answers into {_QA_DB_PATH}")
    except (json.JSONDecodeError, IOError, OSError) as e:
        print(f"[qa_database] Warning: legacy migration failed – {e}")


def _load_db(migrate: bool = True) -> dict:
    """Loads the QA database, re-reading from disk only when the file changed."""
    global _cache, _cache_mtime
    if migrate:
        _migrate_legacy()
    try:
        mtime = os.path.getmtime(_QA_DB_PATH) if os.path.exists(_QA_DB_PATH) else None
        if _cache is not None and mtime == _cache_mtime:
            return _cache
        db = {}
        if mtime is not None:
            with open(_QA_DB_PATH, "r", encoding="utf-8") as f:
                db = json.load(f)
        # Re-key old entries whose key was plain strip().lower()
        db = {_normalize(k): v for k, v in db.items()}
        _cache, _cache_mtime = db, mtime
        return db
    except (json.JSONDecodeError, IOError):
        return _cache or {}


def _save_db(db: dict) -> None:
    """Persists the QA database to disk."""
    global _cache, _cache_mtime
    try:
        os.makedirs(os.path.dirname(_QA_DB_PATH), exist_ok=True)
        with open(_QA_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        _cache = db
        _cache_mtime = os.path.getmtime(_QA_DB_PATH)
    except IOError as e:
        print(f"[qa_database] Warning: could not save QA database – {e}")


def _answer_matches_options(answer: str, options: list[str]) -> bool:
    """True if a cached answer can be applied to one of the current options."""
    ans = _normalize(answer)
    if not ans:
        return False
    for opt in options:
        o = _normalize(opt)
        if ans == o or ans in o or o in ans:
            return True
    return False


def _find_entry(db: dict, question: str) -> tuple[str, dict] | None:
    key = _normalize(question)
    if not key:
        return None

    # 1. Exact normalized match
    if key in db:
        return key, db[key]

    tokens = _content_tokens(key)
    if not tokens:
        return None

    best = None
    for k, entry in db.items():
        k_tokens = _content_tokens(k)
        # 2. Same content tokens (word order / stopwords / punctuation differ)
        if k_tokens == tokens:
            return k, entry
        # 3. Fuzzy — only when distinguishing tokens agree, so questions that
        #    differ in a skill/company name never cross-match
        if k_tokens and (k_tokens <= tokens or tokens <= k_tokens):
            ratio = SequenceMatcher(None, key, k).ratio()
            if ratio >= _FUZZY_CUTOFF and (best is None or ratio > best[0]):
                best = (ratio, k, entry)
    if best:
        return best[1], best[2]
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

def save_to_qa_database(question: str, answer: str, options: list[str] | None = None) -> None:
    """
    Saves a question-answer pair to the local QA database.

    Args:
        question: The question label (e.g. field label from the form).
        answer:   The answer the bot gave or the user provided.
        options:  The select options shown when this answer was given, if any.
    """
    if not question or answer is None:
        return
    answer = str(answer).strip()
    if not answer or answer.startswith("{'error'") or answer.startswith('{"error"'):
        return

    db = _load_db()
    key = _normalize(question)
    if not key:
        return
    prev = db.get(key, {})
    db[key] = {
        "question": question.strip(),
        "answer": answer,
        "options": options if options else prev.get("options"),
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "use_count": prev.get("use_count", 0),
    }
    _save_db(db)


def get_from_qa_database(question: str, options: list[str] | None = None) -> str | None:
    """
    Retrieves a previously saved answer for a question.

    Args:
        question: The question label to look up.
        options:  Current select options; if given, the cached answer is only
                  returned when it matches one of them.

    Returns:
        The saved answer, or None if not found / not applicable.
    """
    if not question:
        return None

    db = _load_db()
    found = _find_entry(db, question)
    if not found:
        return None
    key, entry = found

    answer = entry.get("answer")
    if not answer:
        return None
    if options and not _answer_matches_options(answer, options):
        return None

    entry["use_count"] = entry.get("use_count", 0) + 1
    entry["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_db(db)
    return answer


def qa_database_stats() -> dict:
    """Returns simple stats for display: entries and total cache hits."""
    db = _load_db()
    return {
        "entries": len(db),
        "total_hits": sum(e.get("use_count", 0) for e in db.values() if isinstance(e, dict)),
    }


# Aliases for backwards compatibility
get_answer_from_database = get_from_qa_database
