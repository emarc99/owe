"""Local checks that run after Gemma replies. The model does not get the last word."""

from __future__ import annotations

import re

WORD_LIMIT = 60

_PLACEHOLDER_MISSING = {
    "none",
    "n/a",
    "na",
    "nothing",
    "null",
    "nil",
    "-",
    "no",
}

# The model sometimes copies the instruction instead of naming a fact.
_INSTRUCTION_ECHOES = (
    "uses only facts",
    "already written above",
    "facts already written",
    "do not invent",
    "json only",
)

_SKIP_CAPS = {
    "i",
    "i'm",
    "i'll",
    "i've",
    "i'd",
    "hi",
    "hey",
    "hello",
    "thanks",
    "thank",
    "sorry",
    "please",
    "ok",
    "okay",
    "yes",
    "no",
}


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text or ""))


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d[\d,]*(?:\.\d+)?", text or ""))


def _emails(text: str) -> set[str]:
    return {match.lower() for match in re.findall(r"[\w.+-]+@[\w.-]+\.\w+", text or "")}


def invented_facts(reply: str, source: str) -> list[str]:
    """Facts in the reply that the message never stated.

    Numbers, email addresses, and capitalized names are checked. Ordinary
    sentence words are left alone so a holding reply can still say hello.
    """
    found: list[str] = []
    source_numbers = _numbers(source)
    for number in _numbers(reply):
        if number not in source_numbers:
            found.append(number)

    source_emails = _emails(source)
    for email in _emails(reply):
        if email not in source_emails:
            found.append(email)

    source_words = {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z']+", source or "")}
    for word in re.findall(r"\b[A-Z][a-zA-Z']{1,}\b", reply or ""):
        lowered = word.lower()
        if lowered in _SKIP_CAPS or lowered in source_words:
            continue
        found.append(word)
    return found


def review(draft: dict, source: str) -> dict:
    """Force can_send off when the reply is too long, empty, or inventive."""
    reply = str(draft.get("reply") or "").strip()
    missing = str(draft.get("must_not_invent") or "").strip()
    why = str(draft.get("why") or "").strip()
    issues: list[str] = []

    count = word_count(reply)
    if count == 0:
        issues.append("reply is empty")
    elif count > WORD_LIMIT:
        issues.append(f"reply is {count} words, over the {WORD_LIMIT}-word limit")

    invented = invented_facts(reply, source)
    if invented:
        shown = ", ".join(invented)
        issues.append(f"reply contains {shown}, which is not in the message")

    if _is_placeholder(missing) or _echoes_instructions(missing):
        if count and count <= WORD_LIMIT and not invented and _as_bool(draft.get("can_send")):
            missing = "Nothing beyond the message and your note. The reply does not add a fact."
        else:
            issues.append("must_not_invent is empty")
            missing = ""
    elif not missing:
        issues.append("must_not_invent is empty")

    model_says_send = _as_bool(draft.get("can_send"))
    can_send = model_says_send and not issues
    if model_says_send and issues:
        why = (why + " " if why else "") + "Held back locally: " + "; ".join(issues)

    return {
        "reply": reply,
        "must_not_invent": missing,
        "can_send": can_send,
        "why": why.strip(),
        "word_count": count,
        "blocked": issues,
    }


def _is_placeholder(text: str) -> bool:
    return text.strip().lower().strip(".") in _PLACEHOLDER_MISSING


def _echoes_instructions(text: str) -> bool:
    lowered = text.strip().lower()
    return any(echo in lowered for echo in _INSTRUCTION_ECHOES)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return False
