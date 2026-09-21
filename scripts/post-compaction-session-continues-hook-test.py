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
    check("the oversized final record itself is not injected",
          context is not None and "TOOLDUMP" not in context,
          "a record wider than the whole ceiling was injected anyway")

    # ---- the ceiling on the injected tail ---------------------------------

    # The floor the extractor clears is 1000 words, and the walk back to the
    # nearest earlier USER turn that follows it is unbounded: a transcript
    # with one prompt and a long agentic stretch behind it has no earlier user
    # turn to stop at, so the tail is the whole stretch. Measured at the
    # commit this one sits on: 40,062 words, 271 KiB, injected into a session
    # that had just compacted to free context. That shape is the one that
    # CAUSES a compaction, so the hook's worst case was its primary case.

    def dialog_words_of(tail_text):
        """Count a rendered tail's dialog words, not its per-turn headings.

        render_turns writes "## User" or "## Agent" above each turn; those two
        words per turn are rendering, not dialog, and the ceiling does not
        count them. No transcript built here puts that string in its text, so
        subtracting them is exact.
        """
        headings = tail_text.count("## User") + tail_text.count("## Agent")
        return len(tail_text.split()) - 2 * headings

    # Both numbers this section measures against come from the extractor
    # itself -- its floor here, its own selection further down -- so neither
    # is a remembered constant that can drift when the extractor changes.
    extractor = hook.sibling_module(hook.EXTRACT_SCRIPT, "handoff_extract_conversation")

    def tail_of(context_text):
        """Return the rendered tail out of an injected context, or ""."""
        if context_text is None or hook.TAIL_HEADING not in context_text:
            return ""
        return context_text.split(hook.TAIL_HEADING, 1)[1].strip()

    agentic_stretch = workspace / "one-prompt-then-a-long-stretch.jsonl"
    agentic_lines = [user_record(
        "the one prompt that started the run " + "planning words " * 40)]
    for turn in range(300):
        agentic_lines.append(assistant_record(
            f"agent turn {turn} " + "tool driven narration words " * 32))
    agentic_stretch.write_text("\n".join(agentic_lines) + "\n", encoding="utf-8")

    result = run_hook({"session_id": "s-stretch", "source": "compact",
                       "transcript_path": str(agentic_stretch)}, home)
    context = injected_context_of(result)
    stretch_tail = tail_of(context)
    check("one prompt and a long agentic stretch inject a tail under the ceiling",
          result.returncode == 0 and stretch_tail
          and dialog_words_of(stretch_tail) <= hook.MAXIMUM_INJECTED_TAIL_WORDS,
          f"code {result.returncode}, tail words {dialog_words_of(stretch_tail)}"
          f" against a ceiling of {hook.MAXIMUM_INJECTED_TAIL_WORDS}")
    check("the trimmed tail keeps the most recent turn",
          "agent turn 299 " in stretch_tail,
          "the newest turn was trimmed away")
    check("the trimmed tail drops the oldest turns",
          "agent turn 0 " not in stretch_tail
          and "the one prompt that started the run" not in stretch_tail,
          "the oldest turns survived a tail that should have been trimmed")
    check("the trimmed tail still clears the extractor's word floor",
          dialog_words_of(stretch_tail) >= extractor.MINIMUM_DIALOG_WORDS,
          f"tail words {dialog_words_of(stretch_tail)}, under the"
          f" {extractor.MINIMUM_DIALOG_WORDS}-word floor")

    # The ceiling must do nothing at all to a selection that already fits: the
    # floor rule is correct, and this only bounds it. The comparison is against
    # the extractor's own selection rather than a remembered number, so it
    # cannot drift when the floor changes.
    untrimmed_turns, _skipped = extractor.read_dialog_turns(ordinary)
    untrimmed_selection, _index = extractor.select_tail_clearing_floor(untrimmed_turns)
    result = run_hook({"session_id": "s-under-ceiling", "source": "compact",
                       "transcript_path": str(ordinary)}, home)
    check("a floor selection already under the ceiling is injected untrimmed",
          tail_of(injected_context_of(result))
          == hook.render_turns(untrimmed_selection).strip(),
          "the ceiling trimmed a selection that already fitted")

    # ---- the ceiling's own edges, called directly -------------------------

    def turn_of(name, words, voice="assistant"):
        return {"voice": voice, "text": f"{name} " + "word " * (words - 1)}

    trailing_dump = [turn_of("older", 30), turn_of("newer", 30),
                     turn_of("dump", 500)]
    check("the ceiling steps over a final turn wider than the whole ceiling",
          hook.turns_within_injected_tail_ceiling(trailing_dump, 100)
          == trailing_dump[0:2],
          "a turn that can never fit cost the dialog behind it")

    middle_dump = [turn_of("oldest", 10), turn_of("dump", 500),
                   turn_of("newer", 30), turn_of("newest", 30)]
    check("an oversized turn earlier in the run stops the fill, leaving no gap",
          hook.turns_within_injected_tail_ceiling(middle_dump, 100)
          == middle_dump[2:4],
          "the fill jumped an oversized turn and left a gap in the dialog")

    check("a run of nothing but oversized turns leaves no tail at all",
          hook.turns_within_injected_tail_ceiling(
              [turn_of("dump-one", 500), turn_of("dump-two", 500)], 100) == [],
          "an oversized turn was injected because it was the only one")

    boundary = [turn_of("too-far-back", 60), turn_of("fits", 50),
                turn_of("newest", 40)]
    check("the fill stops at the ceiling rather than crossing it",
          hook.turns_within_injected_tail_ceiling(boundary, 100) == boundary[1:3],
          "the fill crossed the ceiling to take one more turn")

    under_ceiling = [turn_of("first", 10), turn_of("second", 20)]
    kept = hook.turns_within_injected_tail_ceiling(under_ceiling, 100)
    check("a run already under the ceiling is returned whole and untruncated",
          len(kept) == len(under_ceiling)
          and all(kept[i] is under_ceiling[i] for i in range(len(kept))),
          f"{len(kept)} of {len(under_ceiling)} turns returned, or a turn was rebuilt")

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

    original_ceiling = hook.turns_within_injected_tail_ceiling
    try:
        hook.turns_within_injected_tail_ceiling = raise_instead
        tail = hook.recovered_tail(str(ordinary))
        check("a ceiling that fails costs the tail, not the instruction",
              tail == "" and hook.TAIL_HEADING not in hook.injected_context(tail)
              and hook.CONTINUE_INSTRUCTION_LINES[0] in hook.injected_context(tail),
              f"the recovered tail was {tail[:120]!r}")
    finally:
        hook.turns_within_injected_tail_ceiling = original_ceiling

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
