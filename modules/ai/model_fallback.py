"""Swap a retired model for one the endpoint still serves.

Providers retire models on their own schedule (Groq shut down
llama-3.1-8b-instant in August 2026), and a stale `llm_model` in
config/secrets.py then fails every call with a 404 that looks like a bad key.
Instead of failing, ask the endpoint what it serves and pick the best match.
"""

from __future__ import annotations

# Best first. Only used when the configured model is not served.
_PREFERRED = (
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
)

_NOT_CHAT = ("whisper", "tts", "orpheus", "guard", "embed", "playai", "moderation")


def resolve_model(client, wanted: str) -> str:
    """Return `wanted` if the endpoint serves it, else the best available chat
    model. Returns `wanted` unchanged when /models cannot be listed."""
    try:
        ids = [m.id for m in client.models.list().data]
    except Exception:
        return wanted
    if not ids or wanted in ids:
        return wanted
    for candidate in _PREFERRED:
        if candidate in ids:
            return candidate
    chat = [i for i in ids if not any(w in i.lower() for w in _NOT_CHAT)]
    return chat[0] if chat else wanted
