# Owe

https://github.com/emarc99/owe

Paste the message you have been avoiding. [Gemma 4](https://ai.google.dev/gemma) (`gemma-4-26b-a4b-it`, via the Gemini API) drafts a reply of at most 60 words, names the one fact it must not invent, and says whether you can send it. A local check then blocks the send if the reply is too long or contains a number, email, or name that was not in the message (or in a note you passed in).

The lazy payoff is the blank box. You do not stare at it. You either get a reply that is safe to send, or one sentence about the decision that is still yours.

## Run

```powershell
python -m pip install -r requirements.txt
copy .env.example .env
# set GEMINI_API_KEY in .env — the file is gitignored

python -m owe examples/saturday.txt
python -m owe examples/saturday.txt --note "I can't come Saturday, but I can drop the speaker with Priya tonight."
python -m owe examples/saturday.txt --json
```

Text is sent to the Gemini API. It does not stay on the machine. The guard that decides `can_send` does stay local: it runs in `owe/guard.py` after the model returns, and it can override a confident "yes".

## What the model is for

Gemma writes the draft and names the missing fact. It does not get to mark the reply sendable on its own. `owe/guard.py` checks:

- the reply is 1–60 words
- every number and email in the reply appears in the message or your `--note`
- every capitalized name in the reply appears there too
- `must_not_invent` is not empty

If any check fails, `can_send` is forced to false.

## Tests

```powershell
python -m unittest tests.test_guard
```

The tests do not call the API.
