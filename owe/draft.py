"""Ask Gemma 4 for a short reply, then let the local guard decide if it can be sent."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from owe.guard import review

GEMMA_MODEL = "gemma-4-26b-a4b-it"
_RETRY_ATTEMPTS = 4
_RETRY_BASE_SEC = 1.5


def load_env() -> None:
    """Read GEMINI_API_KEY from the environment or a local .env file.

    Existing environment variables win. The key is never printed.
    """
    if os.getenv("GEMINI_API_KEY", "").strip():
        return

    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"]
    extra = os.getenv("OWE_ENV_FILE", "").strip()
    if extra:
        candidates.insert(0, Path(extra))

    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        if os.getenv("GEMINI_API_KEY", "").strip():
            return


def draft_reply(message: str, note: str = "") -> dict[str, Any]:
    """Return the guarded draft for one message the user has been avoiding."""
    message = message.strip()
    if not message:
        raise ValueError("The message is empty. Paste the text you have been avoiding.")

    load_env()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to .env in this folder "
            "(that file is gitignored) or set it in the environment."
        )

    client = genai.Client(api_key=api_key)
    prompt = _prompt(message, note.strip())
    started = time.perf_counter()
    raw_text = _generate(client, prompt)
    elapsed = round(time.perf_counter() - started, 2)
    parsed = _parse_json(raw_text)
    guarded = review(parsed, _source(message, note))
    guarded["model"] = GEMMA_MODEL
    guarded["seconds"] = elapsed
    return guarded


def _source(message: str, note: str) -> str:
    if note.strip():
        return message.strip() + "\n" + note.strip()
    return message.strip()


def _prompt(message: str, note: str) -> str:
    known = note if note else "They have not said what they decided."
    return f"""You help someone answer a message they have been putting off.
You do not decide for them, and you do not add facts.

Message they owe a reply to:
---
{message}
---

What they already know they want, if anything:
---
{known}
---

Return one JSON object and nothing else, with these keys:
- reply: at most 60 words. Use only facts written above. If a decision is missing, write a short holding reply that does not pretend they decided. Do not invent times, amounts, names, places, or promises.
- must_not_invent: the single missing fact that would change the reply, as one full sentence. If nothing is missing, write one sentence that says the reply uses only facts already written above. Never answer with the single word None.
- can_send: true only when the reply needs no missing fact. Otherwise false.
- why: one sentence explaining that choice.

JSON only. No markdown.
"""


def _generate(client: genai.Client, prompt: str) -> str:
    last_error: BaseException | None = None
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=GEMMA_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2),
            )
            text = (response.text or "").strip()
            if not text:
                raise RuntimeError("Gemma returned an empty response.")
            return text
        except Exception as exc:
            last_error = exc
            if attempt == _RETRY_ATTEMPTS or not _is_retryable(exc):
                raise RuntimeError(_friendly_api_error(exc)) from exc
            time.sleep(_RETRY_BASE_SEC * attempt)
    raise RuntimeError(_friendly_api_error(last_error or RuntimeError("Gemma call failed.")))


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", cleaned, re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError(f"Gemma returned non-JSON output: {text[:500]}") from None
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Gemma returned non-JSON output: {text[:500]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Gemma JSON was not an object.")
    return parsed


def _is_retryable(exc: BaseException) -> bool:
    text = str(exc).lower()
    markers = ("500", "503", "429", "internal", "unavailable", "timeout", "temporar", "resource_exhausted", "deadline")
    return any(marker in text for marker in markers)


def _friendly_api_error(exc: BaseException | None) -> str:
    text = str(exc or "")
    if "429" in text or "resource_exhausted" in text.lower():
        return "Gemini API rate limit hit. Wait a moment and run the command again."
    if "API_KEY" in text.upper() or "403" in text or "401" in text:
        return "Gemini API rejected the key. Check GEMINI_API_KEY in .env. The key is not printed here."
    if "500" in text or "INTERNAL" in text:
        return "Gemini API returned a temporary error while calling Gemma 4. Run the command again."
    return f"Gemma API call failed: {text[:400]}"
