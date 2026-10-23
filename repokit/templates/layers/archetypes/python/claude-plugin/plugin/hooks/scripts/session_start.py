"""SessionStart hook for __RK_PROJECT__.

Claude Code runs this (through run-hook.mjs) when a session starts and passes
the event as JSON on stdin. Anything printed to stdout as JSON with
"additionalContext" reaches the session; an empty object is a no-op. Replace
the body with the plugin's work; keep it quick (the hooks.json timeout is 10
seconds).
"""
import json
import os
import sys


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        event = {}
    output = {}
    if os.environ.get("__RK_MACRO___DEBUG"):
        output["additionalContext"] = (
            f"__RK_PROJECT__ saw a {event.get('hook_event_name', 'SessionStart')} event "
            f"(source: {event.get('source', 'unknown')})."
        )
    sys.stdout.write(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
