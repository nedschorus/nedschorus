#!/usr/bin/env python3
"""Tests for the handoff auto-trigger pair.

Covers handoff-statusline-context-relay.py and
handoff-context-threshold-hook.py together, because the pair only means
anything as a pair: the status line writes what the Stop hook reads.

Run: python3 scripts/handoff-auto-trigger-test.py
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RELAY_SCRIPT = Path(__file__).with_name("handoff-statusline-context-relay.py")
HOOK_SCRIPT = Path(__file__).with_name("handoff-context-threshold-hook.py")

_relay_spec = importlib.util.spec_from_file_location("handoff_statusline_relay", RELAY_SCRIPT)
relay = importlib.util.module_from_spec(_relay_spec)
_relay_spec.loader.exec_module(relay)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_script(script_path, stdin_payload, extra_arguments=()):
    return subprocess.run(
        [sys.executable, str(script_path), *extra_arguments],
        input=json.dumps(stdin_payload), capture_output=True, text=True, check=False,
    )


with tempfile.TemporaryDirectory() as workspace:
    relay_directory = Path(workspace) / "handoffs"
    original_relay_directory = relay.RELAY_DIRECTORY
    relay.RELAY_DIRECTORY = relay_directory

    # --- Status line rendering (in-process, so the patched directory applies)
    payload = {
        "session_id": "test-session",
        "workspace": {"current_dir": "/Users/el/Projects/nedschorus"},
        "model": {"display_name": "Fable 5"},
        "context_window": {"remaining_percentage": 62.4},
    }
    line = relay.status_line_text(payload)
    check("status line names the working directory", "nedschorus" in line, line)
    check("status line names the model", "Fable 5" in line, line)
    check("status line reports context left", "context 62% left" in line, line)

    relay.write_relay(payload)
    written = json.loads((relay_directory / "test-session-context.json").read_text(encoding="utf-8"))
    check("relay records the percentage", written["remaining_percentage"] == 62.4, str(written))

    relay.write_relay({"session_id": "no-context-session"})
    check(
        "relay writes nothing without a percentage",
        not (relay_directory / "no-context-session-context.json").exists(),
    )

    check("status line survives an empty payload", relay.status_line_text({}) == "")
    relay.RELAY_DIRECTORY = original_relay_directory

    # --- The hook, as the harness runs it: a subprocess reading stdin -----
    # The pair shares one directory, so the hook is exercised end to end by
    # writing a relay file where the hook looks for it.
    hook_relay_directory = Path.home() / ".claude" / "handoffs"
    hook_relay_directory.mkdir(parents=True, exist_ok=True)
    PROBE_SESSION_ID = "handoff-auto-trigger-test-session"
    relay_file = hook_relay_directory / f"{PROBE_SESSION_ID}-context.json"
    marker_file = hook_relay_directory / f"{PROBE_SESSION_ID}-handoff-asked"

    try:
        relay_file.write_text(
            json.dumps({"session_id": PROBE_SESSION_ID, "remaining_percentage": 80.0}), encoding="utf-8"
        )
        result = run_script(HOOK_SCRIPT, {"session_id": PROBE_SESSION_ID})
        check("hook stays silent above the threshold", result.returncode == 0 and not result.stderr.strip(),
              f"code {result.returncode}, stderr {result.stderr[:120]}")

        relay_file.write_text(
            json.dumps({"session_id": PROBE_SESSION_ID, "remaining_percentage": 40.0}), encoding="utf-8"
        )
        result = run_script(HOOK_SCRIPT, {"session_id": PROBE_SESSION_ID})
        check("hook fires at the threshold", result.returncode == 2, f"code {result.returncode}")
        check("hook names the handoff skill", "handoff skill" in result.stderr, result.stderr[:160])
        check("hook reports the used percentage", "60% used" in result.stderr, result.stderr[:160])

        result = run_script(HOOK_SCRIPT, {"session_id": PROBE_SESSION_ID})
        check("hook fires only once per session", result.returncode == 0, f"code {result.returncode}")

        marker_file.unlink(missing_ok=True)
        result = run_script(HOOK_SCRIPT, {"session_id": PROBE_SESSION_ID},
                            ("--threshold-used-percentage", "75"))
        check("threshold is configurable", result.returncode == 0, f"code {result.returncode}")

        result = run_script(HOOK_SCRIPT, {})
        check("hook stays silent with no session id", result.returncode == 0)

        result = run_script(HOOK_SCRIPT, {"session_id": "session-that-never-reported"})
        check("hook stays silent before the first status-line report", result.returncode == 0)

        # --- The transcript path: works with no status line at all ---------
        hook_spec = importlib.util.spec_from_file_location("handoff_threshold_hook", HOOK_SCRIPT)
        hook = importlib.util.module_from_spec(hook_spec)
        hook_spec.loader.exec_module(hook)

        check("window lookup knows the million-token models",
              hook.context_window_for("claude-fable-5") == 1_000_000
              and hook.context_window_for("claude-opus-5") == 1_000_000
              and hook.context_window_for("claude-sonnet-5") == 1_000_000)
        check("window lookup knows the 200k model",
              hook.context_window_for("claude-haiku-4-5-20251001") == 200_000)
        check("an unknown model falls back to the default window",
              hook.context_window_for("claude-something-unreleased") == 200_000)

        transcript = Path(workspace) / "probe-transcript.jsonl"
        transcript.write_text(
            "\n".join(
                json.dumps(record)
                for record in (
                    {"type": "user", "message": {"content": "hello"}},
                    {"type": "assistant", "message": {
                        "model": "claude-fable-5",
                        "usage": {"input_tokens": 10, "cache_read_input_tokens": 90,
                                  "cache_creation_input_tokens": 0},
                    }},
                    {"type": "assistant", "message": {
                        "model": "claude-fable-5",
                        "usage": {"input_tokens": 100_000, "cache_read_input_tokens": 500_000,
                                  "cache_creation_input_tokens": 50_000},
                    }},
                )
            ),
            encoding="utf-8",
        )
        used = hook.context_used_percentage_from_transcript(str(transcript))
        check("transcript reports the newest turn's usage as a percentage",
              used is not None and abs(used - 65.0) < 0.01, str(used))
        check("an absent transcript reports nothing",
              hook.context_used_percentage_from_transcript(str(Path(workspace) / "nope.jsonl")) is None)
        check("a transcript with no assistant turn reports nothing",
              hook.context_used_percentage_from_transcript(str(Path(workspace) / "empty.jsonl"))
              is None)

        result = run_script(HOOK_SCRIPT,
                            {"session_id": "no-relay-session", "transcript_path": str(transcript)})
        check("hook fires from the transcript with no relay file at all",
              result.returncode == 2, f"code {result.returncode}: {result.stderr[:120]}")
        (hook_relay_directory / "no-relay-session-handoff-asked").unlink(missing_ok=True)
    finally:
        relay_file.unlink(missing_ok=True)
        marker_file.unlink(missing_ok=True)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
