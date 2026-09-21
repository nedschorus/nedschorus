#!/usr/bin/env python3
"""Cases for the hook that restarts a compacted session.

Every case runs the hook as a subprocess under its OWN HOME, so the marker it
deletes is one this suite made and never the real ~/.claude/handoffs (PR
"systemd unit installer: --remove reports a failed disable or reload and exits
1" recorded a suite that wrote into the real handoff directory; this one
cannot). HOME is what decides the directory, because the threshold hook
computes HANDOFF_DIRECTORY from Path.home() at import.

The exit code is asserted on every case, including the malformed ones: exit 2
from a SessionStart hook prevents the session starting at all, so "never 2" is
the property this suite exists to keep. A case that merely checked the text
would pass while the hook bricked the seat.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("post-compaction-session-continues-hook.py")

_hook_spec = importlib.util.spec_from_file_location(
    "post_compaction_session_continues_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_hook(stdin_payload, home, raw_input_text=None):
    """Run the hook as a subprocess under a HOME of this suite's choosing."""
    text = raw_input_text if raw_input_text is not None else json.dumps(stdin_payload)
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=text, capture_output=True, text=True, check=False,
        env={**os.environ, "HOME": str(home)},
    )


def injected_context_of(result):
    """Return the additionalContext the hook emitted, or None."""
    if not result.stdout.strip():
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    specific = payload.get("hookSpecificOutput")
    if not isinstance(specific, dict):
        return None
    return specific.get("additionalContext")


def user_record(text):
    return json.dumps({"type": "user",
                       "message": {"role": "user", "content": text}})


def assistant_record(text):
    return json.dumps({"type": "assistant",
                       "message": {"role": "assistant",
                                   "content": [{"type": "text", "text": text}]}})


def marker_for(home, session_id):
    return Path(home) / ".claude" / "handoffs" / f"{session_id}-handoff-asked"


with tempfile.TemporaryDirectory() as workspace:
    workspace = Path(workspace)
    home = workspace / "home"
    (home / ".claude" / "handoffs").mkdir(parents=True)

    # A transcript with enough real dialog to clear the word floor, plus the
    # harness-injected noise the extractor is supposed to drop.
    ordinary = workspace / "ordinary.jsonl"
    lines = []
    for turn in range(12):
        lines.append(user_record(
            f"user turn {turn} " + "measurable dialog words " * 40))
        lines.append(assistant_record(
            f"agent turn {turn} " + "measurable dialog words " * 40))
    lines.append(user_record(
        "<task-notification>a watcher event nobody typed</task-notification>"))
    ordinary.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- the source gate -------------------------------------------------

    for other_source in ("startup", "resume", "clear", "fork"):
        result = run_hook({"session_id": f"s-{other_source}",
                           "transcript_path": str(ordinary),
                           "source": other_source}, home)
        check(f"source {other_source} is silent and exits 0",
              result.returncode == 0 and not result.stdout.strip(),
              f"code {result.returncode}, stdout {result.stdout[:120]}")

    result = run_hook({"session_id": "s-compact", "transcript_path": str(ordinary),
                       "source": "compact"}, home)
    context = injected_context_of(result)
    check("source compact emits context and exits 0",
          result.returncode == 0 and context is not None,
          f"code {result.returncode}, stdout {result.stdout[:200]}")
    check("the injected text tells the session to continue",
          context is not None and "Continue the work that was underway" in context,
          (context or "")[:200])
    check("the injected text carries the recovered dialog",
          context is not None and "measurable dialog words" in context,
          (context or "")[:200])
    check("the harness-injected record is not carried",
          context is not None and "task-notification" not in context,
          (context or "")[:200])

    result = run_hook({"session_id": "s-reason-fallback",
                       "transcript_path": str(ordinary),
                       "session_start_reason": "compact"}, home)
    check("session_start_reason is read when source is absent",
          result.returncode == 0 and injected_context_of(result) is not None,
          f"code {result.returncode}, stdout {result.stdout[:120]}")

    # ---- the marker ------------------------------------------------------

    marker = marker_for(home, "s-marker")
    marker.write_text("fired\n", encoding="utf-8")
    sibling = marker_for(home, "s-other-session")
    sibling.write_text("fired\n", encoding="utf-8")
    result = run_hook({"session_id": "s-marker", "transcript_path": str(ordinary),
                       "source": "compact"}, home)
    check("the compacted session's fired marker is cleared",
          result.returncode == 0 and not marker.exists(),
          f"code {result.returncode}, marker exists {marker.exists()}")
    check("another session's marker survives",
          sibling.exists(), "the sibling marker was removed")
    sibling.unlink()

    result = run_hook({"session_id": "s-no-marker", "transcript_path": str(ordinary),
                       "source": "compact"}, home)
    check("an absent marker is not an error",
          result.returncode == 0 and injected_context_of(result) is not None,
          f"code {result.returncode}, stderr {result.stderr[:160]}")

    # ---- malformed and missing input, none of which may exit 2 -----------

    result = run_hook(None, home, raw_input_text="")
    check("empty stdin exits 0 in silence",
          result.returncode == 0 and not result.stdout.strip(),
          f"code {result.returncode}")

    result = run_hook(None, home, raw_input_text="{not json at all")
    check("unparseable stdin exits 0 in silence",
          result.returncode == 0 and not result.stdout.strip(),
          f"code {result.returncode}")

    result = run_hook(None, home, raw_input_text='["a list, not an object"]')
    check("a non-object payload exits 0 in silence",
          result.returncode == 0 and not result.stdout.strip(),
          f"code {result.returncode}")

    result = run_hook({"source": "compact"}, home)
    context = injected_context_of(result)
    check("a compaction with no transcript path still says continue",
          result.returncode == 0 and context is not None
          and "Continue the work that was underway" in context,
          f"code {result.returncode}, stdout {result.stdout[:200]}")

    result = run_hook({"session_id": "s-absent", "source": "compact",
                       "transcript_path": str(workspace / "never-written.jsonl")}, home)
    context = injected_context_of(result)
    check("a transcript that does not exist still says continue",
          result.returncode == 0 and context is not None
          and "Continue the work that was underway" in context,
          f"code {result.returncode}, stdout {result.stdout[:200]}")

    unreadable = workspace / "unreadable.jsonl"
    unreadable.write_text(ordinary.read_text(encoding="utf-8"), encoding="utf-8")
    unreadable.chmod(0o000)
    try:
        result = run_hook({"session_id": "s-unreadable", "source": "compact",
                           "transcript_path": str(unreadable)}, home)
        context = injected_context_of(result)
        check("an unreadable transcript still says continue, and never exits 2",
              result.returncode == 0 and context is not None
              and "Continue the work that was underway" in context,
              f"code {result.returncode}, stdout {result.stdout[:200]}")
    finally:
        unreadable.chmod(0o600)

    garbage = workspace / "garbage.jsonl"
    garbage.write_text("not json\n{\"half\": \n\x00\x01\n", encoding="utf-8")
    result = run_hook({"session_id": "s-garbage", "source": "compact",
                       "transcript_path": str(garbage)}, home)
    context = injected_context_of(result)
    check("a malformed transcript still says continue",
          result.returncode == 0 and context is not None
          and "Continue the work that was underway" in context,
          f"code {result.returncode}, stdout {result.stdout[:200]}")

    empty_transcript = workspace / "empty.jsonl"
    empty_transcript.write_text("", encoding="utf-8")
    result = run_hook({"session_id": "s-empty", "source": "compact",
                       "transcript_path": str(empty_transcript)}, home)
    context = injected_context_of(result)
    check("an empty transcript still says continue",
          result.returncode == 0 and context is not None
          and "Continue the work that was underway" in context,
          f"code {result.returncode}, stdout {result.stdout[:200]}")

    # ---- the case a byte tail would fail ---------------------------------

    # One record larger than the whole word budget, sitting at the very end.
    # A tail taken by bytes would land inside it and carry no conversation at
    # all; the record-aware walk steps over it to the dialog behind it.
    giant = workspace / "giant-final-record.jsonl"
    giant_lines = list(lines[:-1])
    giant_lines.append(assistant_record(
        "TOOLDUMP " + "xyzzy " * 30000))
    giant.write_text("\n".join(giant_lines) + "\n", encoding="utf-8")
    result = run_hook({"session_id": "s-giant", "source": "compact",
                       "transcript_path": str(giant)}, home)
    context = injected_context_of(result)
    check("a final record larger than the budget does not crowd out the dialog",
          result.returncode == 0 and context is not None
          and "measurable dialog words" in context,
          f"code {result.returncode}, stdout {result.stdout[:200]}")

    # ---- the emitted shape -----------------------------------------------

    result = run_hook({"session_id": "s-shape", "transcript_path": str(ordinary),
                       "source": "compact"}, home)
    try:
        emitted = json.loads(result.stdout)
    except json.JSONDecodeError:
        emitted = {}
    check("the emitted payload names the SessionStart event",
          emitted.get("hookSpecificOutput", {}).get("hookEventName") == "SessionStart",
          result.stdout[:200])
    check("the emitted payload carries no decision field",
          "decision" not in emitted
          and "decision" not in emitted.get("hookSpecificOutput", {}),
          result.stdout[:200])

    # ---- a sibling that is gone costs the tail, never the instruction ----

    # Loading the siblings at module scope made this case impossible to pass:
    # module scope is outside main()'s guard, so with
    # handoff-extract-conversation.py absent the hook exited 1 on a traceback
    # and emitted NOTHING -- the optional half of the job taking down the
    # essential half. Measured that way on 2026-09-20, before the fix. Files
    # get renamed and moved in this repository, so a missing sibling is a
    # named behaviour rather than a hypothetical. The hook resolves siblings
    # beside its own file, so a copy in a directory holding only some of them
    # reproduces it exactly.

    def hook_copied_beside(directory, siblings):
        """Copy the hook into `directory` beside `siblings` only."""
        directory.mkdir(parents=True, exist_ok=True)
        copied = directory / HOOK_SCRIPT.name
        copied.write_bytes(HOOK_SCRIPT.read_bytes())
        for sibling in siblings:
            (directory / sibling).write_bytes(
                HOOK_SCRIPT.with_name(sibling).read_bytes())
        return copied

    def run_copied_hook(copied, payload):
        return subprocess.run(
            [sys.executable, str(copied)],
            input=json.dumps(payload), capture_output=True, text=True,
            check=False, env={**os.environ, "HOME": str(home)})

    sibling_payload = {"session_id": "s-siblings", "source": "compact",
                       "hook_event_name": "SessionStart",
                       "transcript_path": str(ordinary)}

    no_extractor = hook_copied_beside(
        workspace / "no-extractor", [hook.THRESHOLD_SCRIPT])
    result = run_copied_hook(no_extractor, sibling_payload)
    context = injected_context_of(result)
    check("an absent extractor exits 0, not 1 on a traceback",
          result.returncode == 0,
          f"rc={result.returncode}; stderr={result.stderr[:200]!r}")
    check("an absent extractor still tells the session to continue",
          context is not None and hook.CONTINUE_INSTRUCTION_LINES[0] in context,
          f"injected context was {context!r}")
    check("an absent extractor claims no tail it could not build",
          context is not None and hook.TAIL_HEADING not in context,
          "the tail heading was emitted with no extractor to fill it")

    no_threshold = hook_copied_beside(
        workspace / "no-threshold", [hook.EXTRACT_SCRIPT])
    result = run_copied_hook(no_threshold, sibling_payload)
    context = injected_context_of(result)
    check("an absent threshold hook exits 0, not 1 on a traceback",
          result.returncode == 0,
          f"rc={result.returncode}; stderr={result.stderr[:200]!r}")
    check("an absent threshold hook still tells the session to continue",
          context is not None and hook.CONTINUE_INSTRUCTION_LINES[0] in context,
          f"injected context was {context!r}")
    check("an absent threshold hook still recovers the tail",
          context is not None and hook.TAIL_HEADING in context,
          "the tail was lost to an unrelated sibling going missing")

    # ---- the last-resort handler, which no end-to-end case can reach -----

    # Every inner read already swallows its own failures, so main()'s outer
    # handler is unreachable from outside the process: an end-to-end case
    # asserting "never exits 2" passes whether that handler returns 0 or 2,
    # and a mutation to it changed nothing measurable until this case existed.
    # Calling main() here, with a collaborator replaced by one that raises, is
    # what puts it in front of the condition it exists for. Same shape as
    # run_hook_in_process() in handoff-context-threshold-hook-test.py, and for
    # the same reason.
    def raise_instead(*_arguments, **_keywords):
        raise RuntimeError("a collaborator failed in a way nothing anticipated")

    original_injected_context = hook.injected_context
    original_payload_reader = hook.hook_payload_from_stdin
    try:
        hook.hook_payload_from_stdin = lambda: {
            "session_id": "s-in-process", "source": "compact",
            "transcript_path": str(ordinary)}
        hook.injected_context = raise_instead
        returned = hook.main()
        check("an unanticipated failure inside main still returns 0, never 2",
              returned == 0, f"main() returned {returned}")
    finally:
        hook.injected_context = original_injected_context
        hook.hook_payload_from_stdin = original_payload_reader

    # ---- the marker name has one definition ------------------------------

    threshold_source = HOOK_SCRIPT.with_name(
        "handoff-context-threshold-hook.py").read_text(encoding="utf-8")
    check("the threshold hook defines the fired-marker suffix exactly once",
          threshold_source.count('FIRED_MARKER_SUFFIX = "-handoff-asked"') == 1,
          "definition count is not 1")
    check("this hook carries no second copy of the marker name",
          "-handoff-asked" not in HOOK_SCRIPT.read_text(encoding="utf-8").replace(
              "post-compaction-session-continues-hook.py", ""),
          "the hook hardcodes the marker suffix instead of importing it")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
