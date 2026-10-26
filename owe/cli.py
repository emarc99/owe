"""Command line for Owe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from owe.draft import draft_reply


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Draft the reply you have been avoiding. Gemma writes it. A local check decides if you can send it."
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="The message text, or a path to a text file. Reads stdin when omitted.",
    )
    parser.add_argument(
        "--note",
        default="",
        help="What you already decided, if anything. Facts in this note are allowed in the reply.",
    )
    parser.add_argument("--json", action="store_true", help="Print the reviewed JSON only.")
    args = parser.parse_args(argv)

    try:
        message = _read_message(args.message)
        result = draft_reply(message, args.note)
    except (ValueError, RuntimeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    send = "Yes" if result["can_send"] else "No"
    print(f"Reply ({result['word_count']} words)")
    print(result["reply"])
    print()
    print("Do not invent")
    print(result["must_not_invent"])
    print()
    print(f"Send? {send}")
    if result["why"]:
        print(result["why"])
    if result["blocked"]:
        print()
        print("Held back")
        for issue in result["blocked"]:
            print(f"- {issue}")
    print()
    print(f"{result['model']} in {result['seconds']}s")
    return 0


def _read_message(raw: str | None) -> str:
    if raw:
        path = Path(raw)
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return raw
    if sys.stdin.isatty():
        raise ValueError("Paste a message, pass a text file, or pipe text on stdin.")
    return sys.stdin.read()


if __name__ == "__main__":
    raise SystemExit(main())
