'''
Module: qa_database.py

Stores question-answer pairs to a local JSON file so the bot can
"remember" answers it has already given and reuse them in future sessions.

File location: modules/ai/qa_database.py
'''

import os
import json
from datetime import datetime

# Path to the QA database file
_QA_DB_PATH = os.path.join("all excels", "qa_database.json")


def _load_db() -> dict:
    """Loads the QA database from disk. Returns an empty dict if not found."""
    try:
        if os.path.exists(_QA_DB_PATH):
            with open(_QA_DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def _save_db(db: dict) -> None:
    """Persists the QA database to disk."""
    try:
        os.makedirs(os.path.dirname(_QA_DB_PATH), exist_ok=True)
        with open(_QA_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[qa_database] Warning: could not save QA database – {e}")


def save_to_qa_database(question: str, answer: str) -> None:
    """
    Saves a question-answer pair to the local QA database.

    Args:
        question (str): The question label (e.g. field label from the form).
        answer   (str): The answer the bot gave or the user provided.
    """
    if not question or answer is None:
        return

    db = _load_db()

    key = question.strip().lower()
    db[key] = {
        "question": question.strip(),
        "answer": str(answer).strip(),
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    _save_db(db)


def get_from_qa_database(question: str) -> str | None:
    """
    Retrieves a previously saved answer for a question.

    Args:
        question (str): The question label to look up.

    Returns:
        str | None: The saved answer, or None if not found.
    """
    if not question:
        return None

    db = _load_db()
    key = question.strip().lower()
    entry = db.get(key)
    return entry["answer"] if entry else None