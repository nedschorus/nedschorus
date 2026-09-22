#!/usr/bin/env python3
"""Tests for ghi-info-ask.py (nedschorus#46).

Nothing real runs: mirror_refresh.refresh and run_claude are both
monkeypatched with queue-based fakes, so no gh call, no ssh, and no claude
invocation happens anywhere in this file. The fake refresh writes a real
cache file to disk (mirroring what the real one does) so read_cache — used,
un-mocked, by the post-check — is genuinely exercised. Every case runs
against a throwaway seat directory under a TemporaryDirectory.

Run: python3 scripts/ghi-info-ask-test.py
"""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("ghi-info-ask.py")

_spec = importlib.util.spec_from_file_location("ghi_info_ask", SCRIPT_PATH)
ghi_ask = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ghi_ask)
# The real run_claude, captured before any case installs a fake over it.
run_claude_real = ghi_ask.run_claude

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def patch(monkey_target, value):
    setattr(ghi_ask, monkey_target, value)


def issue(number, state="OPEN", closed_at=None):
    return {"number": number, "state": state, "closedAt": closed_at}


def fake_refresh_queue(responses):
    """responses: list of (changed_numbers, cache_issues_dict, error) popped
    in call order, one per refresh call — an extra call empties the queue
    and fails loudly rather than passing quietly. Writes a real cache file
    each time, like the genuine refresh does, so read_cache — used
    un-mocked by the post-check — is genuinely exercised."""
    calls = []

    def fake_refresh(mirror_dir, repo, full):
        calls.append({"mirror_dir": mirror_dir, "repo": repo, "full": full})
        changed, cache_issues, error = responses.pop(0)
        if error:
            return None, error
        mirror_dir.mkdir(parents=True, exist_ok=True)
        cache = {"last_refresh_at": "2026-08-23T00:00:00Z", "issues": cache_issues}
        (mirror_dir / ghi_ask.mirror_refresh.CACHE_FILE_NAME).write_text(
            json.dumps(cache), encoding="utf-8")
        (mirror_dir / "issues-open.md").write_text("open", encoding="utf-8")
        return {
            "changed": changed, "full_refresh": full, "mirror_dir": str(mirror_dir),
            "open_path": str(mirror_dir / "issues-open.md"),
            "closed_path": str(mirror_dir / "issues-closed.md"),
        }, None
    patch_module_function(ghi_ask.mirror_refresh, "refresh", fake_refresh)
    return calls


def patch_module_function(module, name, value):
    setattr(module, name, value)


def fake_claude_queue(responses):
    """responses: list of (result_dict_or_None, error_or_None) popped in
    call order. Each call is recorded as (prompt, resume_session_id)."""
    calls = []

    def fake_run_claude(prompt, resume_session_id, seat_dir, timeout_seconds):
        calls.append((prompt, resume_session_id))
        return responses.pop(0)
    patch("run_claude", fake_run_claude)
    return calls


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)

    # --- cold start: no state file -> two claude calls, session persisted --
    seat = root / "seat1"
    seat.mkdir()
    refresh_calls = fake_refresh_queue([
        ([1], {"1": issue(1)}, None),           # the single full refresh
    ])
    claude_calls = fake_claude_queue([
        ({"session_id": "sess-A", "result": "(ack)"}, None),   # cold-start turn
        ({"session_id": "sess-A", "result": "read #1"}, None),  # actual ask
    ])
    answer, error = ghi_ask.ask("what covers X?", False, seat, "x/y")
    check("cold start (no state file) succeeds and returns the answer",
          answer == "read #1" and error is None, (answer, error))
    check("cold start makes exactly two claude calls (cold-start turn, then ask)",
          len(claude_calls) == 2, claude_calls)
    check("cold-start's second call resumes the session the first call opened",
          claude_calls[1][1] == "sess-A", claude_calls)
    # With no session to resume there is nothing a delta could inform: the
    # delta would itself be a full fetch (no cache, so no cutoff to search
    # from), so running one first fetched the whole corpus TWICE per first ask.
    check("a cold start fetches the corpus ONCE — one refresh call, full",
          len(refresh_calls) == 1 and refresh_calls[0]["full"] is True, refresh_calls)
    state = json.loads((seat / ghi_ask.STATE_FILE_NAME).read_text(encoding="utf-8"))
    check("state persists the new session id after a cold start",
          state[ghi_ask.GHI_INFO_SESSION_ID_STATE_KEY] == "sess-A", state)
    check("state resets counters on a cold start",
          state["closes_since_birth"] == 0 and state["recent_matches"] == [False], state)

    # --- resume: existing session, no reincarnation trigger -> one claude call ---
    seat2 = root / "seat2"
    seat2.mkdir()
    ghi_ask.save_state(seat2 / ghi_ask.STATE_FILE_NAME,
                       {ghi_ask.GHI_INFO_SESSION_ID_STATE_KEY: "sess-B", "closes_since_birth": 0, "recent_matches": []})
    refresh_calls = fake_refresh_queue([([7], {"7": issue(7)}, None)])
    claude_calls = fake_claude_queue([({"session_id": "sess-B", "result": "read #7"}, None)])
    answer, error = ghi_ask.ask("about #7?", False, seat2, "x/y")
    check("a resumed ask makes exactly one claude call",
          len(claude_calls) == 1, claude_calls)
    check("the resume call carries the stored session id",
          claude_calls[0][1] == "sess-B", claude_calls)
    check("the resume prompt names the changed entry",
          "#7" in claude_calls[0][0] and "changed" in claude_calls[0][0], claude_calls)
    check("only a delta refresh runs on an ordinary resume (no full refresh)",
          len(refresh_calls) == 1 and refresh_calls[0]["full"] is False, refresh_calls)

    # --- reincarnation: closes-since-birth over threshold forces a cold start ----
    seat3 = root / "seat3"
    seat3.mkdir()
    ghi_ask.save_state(seat3 / ghi_ask.STATE_FILE_NAME, {
        ghi_ask.GHI_INFO_SESSION_ID_STATE_KEY: "sess-OLD",
        "closes_since_birth": ghi_ask.CLOSES_SINCE_BIRTH_THRESHOLD,
        "recent_matches": [],
    })
    refresh_calls = fake_refresh_queue([
        ([], {}, None),
        ([], {}, None),
    ])
    claude_calls = fake_claude_queue([
        ({"session_id": "sess-NEW", "result": "(ack)"}, None),
        ({"session_id": "sess-NEW", "result": "read #3"}, None),
    ])
    answer, error = ghi_ask.ask("q", False, seat3, "x/y")
    check("closes-since-birth at threshold forces a cold start (fresh session id)",
          answer == "read #3", (answer, error))
    state3 = json.loads((seat3 / ghi_ask.STATE_FILE_NAME).read_text(encoding="utf-8"))
    check("reincarnation replaces the old session id with the new one",
          state3[ghi_ask.GHI_INFO_SESSION_ID_STATE_KEY] == "sess-NEW", state3)

    # --- a state file written before the 2026-09-22 rename still resumes ---
    # The key moved from `session_id` to `ghi_info_session_id`; a seat whose
    # `.ghi-info-state.json` predates the rename must resume its ghi-info
    # session rather than silently cold-start, which would rebuild the whole
    # mirror and lose the session's accumulated reading.
    seat_legacy = root / "seat-legacy"
    seat_legacy.mkdir()
    (seat_legacy / ghi_ask.STATE_FILE_NAME).write_text(
        json.dumps({"session_id": "sess-LEGACY", "closes_since_birth": 0,
                    "recent_matches": []}) + "\n", encoding="utf-8")
    refresh_calls = fake_refresh_queue([([], {}, None)])
    claude_calls = fake_claude_queue([({"session_id": "sess-LEGACY", "result": "read #5"}, None)])
    answer, error = ghi_ask.ask("about #5?", False, seat_legacy, "x/y")
    check("a pre-rename state file resumes rather than cold-starting",
          len(claude_calls) == 1 and claude_calls[0][1] == "sess-LEGACY",
          (claude_calls, answer, error))
    state_legacy = json.loads(
        (seat_legacy / ghi_ask.STATE_FILE_NAME).read_text(encoding="utf-8"))
    check("the first write after a migrated read uses the new key alone",
          state_legacy.get(ghi_ask.GHI_INFO_SESSION_ID_STATE_KEY) == "sess-LEGACY"
          and "session_id" not in state_legacy, state_legacy)

    # --- lock contention: throwaway session, nothing persisted -------------
    seat4 = root / "seat4"
    seat4.mkdir()
    ghi_ask.save_state(seat4 / ghi_ask.STATE_FILE_NAME,
                       {ghi_ask.GHI_INFO_SESSION_ID_STATE_KEY: "sess-HELD", "closes_since_birth": 0, "recent_matches": []})
    before_state_text = (seat4 / ghi_ask.STATE_FILE_NAME).read_text(encoding="utf-8")
    refresh_calls = fake_refresh_queue([([], {}, None)])
    claude_calls = fake_claude_queue([
        ({"session_id": "sess-THROWAWAY", "result": "(ack)"}, None),
        ({"session_id": "sess-THROWAWAY", "result": "read #9"}, None),
    ])
    lock_path = seat4 / ghi_ask.LOCK_FILE_NAME
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    held_handle = open(lock_path, "a+")
    fcntl.flock(held_handle.fileno(), fcntl.LOCK_EX)
    try:
        answer, error = ghi_ask.ask("q", False, seat4, "x/y")
    finally:
        fcntl.flock(held_handle.fileno(), fcntl.LOCK_UN)
        held_handle.close()
    check("a contended lock still returns an answer (a throwaway session)",
          answer == "read #9", (answer, error))
    check("a contended lock cold-starts (never resumes the held session)",
          claude_calls[0][1] is None, claude_calls)
    check("a contended lock never writes the state file",
          (seat4 / ghi_ask.STATE_FILE_NAME).read_text(encoding="utf-8") == before_state_text,
          "state file changed under contention")
    # PR #143 review, Codex P2: the shared mirror is three files renamed
    # independently, so a contended ask publishing into it alongside the lock
    # holder could leave a reader with a new open file beside an old closed
    # one, or roll the cache cutoff backward. A contended ask therefore gets
    # a private mirror and never touches the shared one.
    check("a contended ask never publishes into the shared mirror",
          not (seat4 / ghi_ask.mirror_refresh.DEFAULT_MIRROR_DIR).exists(),
          list(seat4.iterdir()))
    check("a contended ask leaves no throwaway mirror behind",
          not list(seat4.glob(".ghi-mirror-throwaway-*")),
          list(seat4.glob(".ghi-mirror-throwaway-*")))
    check("the lock HOLDER does publish into the shared mirror",
          (seat2 / ghi_ask.mirror_refresh.DEFAULT_MIRROR_DIR).exists(),
          list(seat2.iterdir()))

    # --- post-check: unexpected closed pointer triggers one drift recheck --
    seat5 = root / "seat5"
    seat5.mkdir()
    refresh_calls = fake_refresh_queue([
        ([13], {"13": issue(13, state="CLOSED", closed_at="2026-08-08T00:00:00Z")}, None),
    ])
    claude_calls = fake_claude_queue([
        ({"session_id": "sess-C", "result": "(ack)"}, None),               # cold-start
        ({"session_id": "sess-C", "result": "read #13"}, None),            # stale answer
        ({"session_id": "sess-C", "result": "read #24 instead"}, None),    # drift recheck
    ])
    answer, error = ghi_ask.ask("q", False, seat5, "x/y")
    check("a closed pointer (not --include-closed) triggers a third claude call",
          len(claude_calls) == 3, claude_calls)
    check("the drift notice names the issue and its close date",
          "#13" in claude_calls[2][0] and "2026-08-08" in claude_calls[2][0], claude_calls)
    check("the corrected reply from the recheck is the final answer",
          answer == "read #24 instead", answer)
    state5 = json.loads((seat5 / ghi_ask.STATE_FILE_NAME).read_text(encoding="utf-8"))
    check("a drift recheck counts as a stale match in state",
          state5["recent_matches"] == [True], state5)

    # --- --include-closed: closed pointers are expected, no recheck --------
    seat6 = root / "seat6"
    seat6.mkdir()
    refresh_calls = fake_refresh_queue([
        ([13], {"13": issue(13, state="CLOSED", closed_at="2026-08-08T00:00:00Z")}, None),
    ])
    claude_calls = fake_claude_queue([
        ({"session_id": "sess-D", "result": "(ack)"}, None),
        ({"session_id": "sess-D", "result": "#13 (closed 2026-08-08)"}, None),
    ])
    answer, error = ghi_ask.ask("q", True, seat6, "x/y")
    check("--include-closed makes a closed pointer expected: no third call",
          len(claude_calls) == 2, claude_calls)
    state6 = json.loads((seat6 / ghi_ask.STATE_FILE_NAME).read_text(encoding="utf-8"))
    check("an expected closed pointer is not counted as a stale match",
          state6["recent_matches"] == [False], state6)

    # --- escalate:/out-of-scope pass through, no post-check -----------------
    seat7 = root / "seat7"
    seat7.mkdir()
    refresh_calls = fake_refresh_queue([
        ([13], {"13": issue(13, state="CLOSED", closed_at="2026-08-08T00:00:00Z")}, None),
    ])
    claude_calls = fake_claude_queue([
        ({"session_id": "sess-E", "result": "(ack)"}, None),
        ({"session_id": "sess-E", "result": "escalate: does the 2026-08-01 ruling on #13 still bind?"}, None),
    ])
    answer, error = ghi_ask.ask("q", False, seat7, "x/y")
    check("an escalate: reply passes through verbatim, even mentioning #13",
          answer.startswith("escalate:"), answer)
    check("a passthrough reply triggers no drift recheck",
          len(claude_calls) == 2, claude_calls)

    # --- mirror refresh failure surfaces as an ask failure ------------------
    seat8 = root / "seat8"
    seat8.mkdir()
    fake_refresh_queue([(None, None, "gh rate limited")])
    answer, error = ghi_ask.ask("q", False, seat8, "x/y")
    check("a mirror refresh failure fails the ask cleanly",
          answer is None and "gh rate limited" in error, (answer, error))

    # --- claude failure on the ask turn surfaces as an ask failure ---------
    seat9 = root / "seat9"
    seat9.mkdir()
    fake_refresh_queue([([1], {"1": issue(1)}, None)])
    fake_claude_queue([
        ({"session_id": "sess-F", "result": "(ack)"}, None),
        (None, "claude exited 1: boom"),
    ])
    answer, error = ghi_ask.ask("q", False, seat9, "x/y")
    check("a claude failure on the ask turn fails cleanly",
          answer is None and "boom" in error, (answer, error))

    # --- transcript-size reincarnation trigger (real project-dir mangling) -------
    seat10 = root / "seat10"
    seat10.mkdir()
    ghi_ask.save_state(seat10 / ghi_ask.STATE_FILE_NAME,
                       {"session_id": "sess-BIG", "closes_since_birth": 0, "recent_matches": []})
    projects_root = root / "projects"
    project_directory = ghi_ask.watcher.project_directory_for_seat(seat10, projects_root)
    project_directory.mkdir(parents=True)
    (project_directory / "sess-BIG.jsonl").write_bytes(
        b"x" * (ghi_ask.TRANSCRIPT_SIZE_THRESHOLD_BYTES + 1))
    refresh_calls = fake_refresh_queue([([], {}, None), ([], {}, None)])
    claude_calls = fake_claude_queue([
        ({"session_id": "sess-BIGGER", "result": "(ack)"}, None),
        ({"session_id": "sess-BIGGER", "result": "read #1"}, None),
    ])
    answer, error = ghi_ask.ask("q", False, seat10, "x/y", projects_root=projects_root)
    check("an oversized transcript forces a cold start",
          claude_calls[0][1] is None and answer == "read #1", (claude_calls, answer))

    # --- context-share reincarnation trigger ---------------------------------
    # 2026-09-16: ghi-info's session stood at 521,343 tokens of claude-sonnet-5's
    # 1M window with a 3.7 MB transcript, under the size trigger, and the handoff
    # hook's notice came back in place of the answer. That hook is silent in
    # these sessions now, so this trigger is what bounds them.
    def transcript_at_context_tokens(seat, session_id, tokens):
        project_directory = ghi_ask.watcher.project_directory_for_seat(seat, projects_root)
        project_directory.mkdir(parents=True, exist_ok=True)
        record = {"type": "assistant", "message": {
            "model": "claude-sonnet-5",
            "usage": {"input_tokens": 1_000, "cache_read_input_tokens": tokens - 1_000,
                      "cache_creation_input_tokens": 0}}}
        (project_directory / f"{session_id}.jsonl").write_text(
            json.dumps(record) + "\n", encoding="utf-8")

    seat10b = root / "seat10b"
    seat10b.mkdir()
    ghi_ask.save_state(seat10b / ghi_ask.STATE_FILE_NAME,
                       {"session_id": "sess-FULL", "closes_since_birth": 0, "recent_matches": []})
    transcript_at_context_tokens(seat10b, "sess-FULL", 521_343)
    fake_refresh_queue([([], {}, None), ([], {}, None)])
    claude_calls = fake_claude_queue([
        ({"session_id": "sess-FRESH", "result": "(ack)"}, None),
        ({"session_id": "sess-FRESH", "result": "read #1"}, None),
    ])
    answer, error = ghi_ask.ask("q", False, seat10b, "x/y", projects_root=projects_root)
    check("a session past the context threshold is reincarnated, not resumed",
          claude_calls[0][1] is None and answer == "read #1", (claude_calls, answer))

    seat10c = root / "seat10c"
    seat10c.mkdir()
    ghi_ask.save_state(seat10c / ghi_ask.STATE_FILE_NAME,
                       {"session_id": "sess-ROOM", "closes_since_birth": 0, "recent_matches": []})
    transcript_at_context_tokens(seat10c, "sess-ROOM", 390_000)
    fake_refresh_queue([([], {}, None)])
    claude_calls = fake_claude_queue([
        ({"session_id": "sess-ROOM", "result": "read #1"}, None),
    ])
    answer, error = ghi_ask.ask("q", False, seat10c, "x/y", projects_root=projects_root)
    check("a session under the context threshold is resumed",
          claude_calls == [(claude_calls[0][0], "sess-ROOM")] and answer == "read #1",
          (claude_calls, answer))


    # --- one deadline for the whole ask, not one per turn ------------------
    # PR #143 review, Codex P2: an ask can spend three turns (a cold start's
    # two, plus a drift recheck). Giving each the full allowance made a
    # nominal five-minute ask a possible fifteen-minute one, against the
    # design's "one overall timeout (inside the hook budget)".
    seat11 = root / "seat11"
    seat11.mkdir()
    fake_refresh_queue([([13], {"13": issue(13, state="CLOSED",
                                            closed_at="2026-08-08T00:00:00Z")}, None)])
    budgets = []

    def recording_run_claude(prompt, resume_session_id, seat_dir, timeout_seconds):
        budgets.append(timeout_seconds)
        replies = [
            {"session_id": "sess-T", "result": "(ack)"},
            {"session_id": "sess-T", "result": "read #13"},   # cites a closed issue
            {"session_id": "sess-T", "result": "read #24"},   # the drift recheck
        ]
        return replies[len(budgets) - 1], None
    patch("run_claude", recording_run_claude)
    answer, error = ghi_ask.ask("q", False, seat11, "x/y", timeout_seconds=300)
    check("all three turns of one ask draw on a single budget",
          len(budgets) == 3, budgets)
    check("each turn is handed only what the ask has left, never the full budget again",
          budgets == sorted(budgets, reverse=True) and budgets[0] <= 300
          and budgets[-1] < budgets[0],
          budgets)

    # An ask whose budget is already gone fails saying so, rather than
    # starting a turn it cannot afford.
    seat12 = root / "seat12"
    seat12.mkdir()
    fake_refresh_queue([([1], {"1": issue(1)}, None)])
    spent_calls = fake_claude_queue([])
    answer, error = ghi_ask.ask("q", False, seat12, "x/y", timeout_seconds=0)
    check("an ask with no budget left fails cleanly and starts no turn",
          answer is None and "budget was already spent" in error and not spent_calls,
          (answer, error, spent_calls))


# --- an unusable seat directory is one line, not a traceback ---------------
# PR #143 review question: the module docstring promises "one line to stderr
# and exits 1" on any failure, and an unwritable seat raised a traceback.
with tempfile.TemporaryDirectory() as temporary:
    readonly_seat = Path(temporary) / "readonly-seat"
    readonly_seat.mkdir()
    os.chmod(readonly_seat, 0o500)
    try:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            exit_code = ghi_ask.main(["q", "--seat-dir", str(readonly_seat)])
        check("an unwritable seat directory exits 1 with one line, no traceback",
              exit_code == 1 and "Traceback" not in err.getvalue()
              and "not usable" in err.getvalue(),
              err.getvalue())
    finally:
        os.chmod(readonly_seat, 0o700)


# --- the cold-start prompt names the mirror DIRECTORY ----------------------
# PR #143 review, P3: the slot was filled with issues-open.md, which left
# issues-closed.md — named in the very next bullet — with no stated location.
with tempfile.TemporaryDirectory() as temporary:
    seat_cs = Path(temporary) / "seat-coldstart"
    seat_cs.mkdir()
    fake_refresh_queue([([1], {"1": issue(1)}, None)])
    cs_calls = fake_claude_queue([
        ({"session_id": "sess-CS", "result": "(ack)"}, None),
        ({"session_id": "sess-CS", "result": "read #1"}, None),
    ])
    ghi_ask.ask("q", False, seat_cs, "x/y")
    cold_prompt = cs_calls[0][0]
    check("the cold-start prompt names the mirror directory, not one of its files",
          "issues-open.md:" not in cold_prompt
          and str(seat_cs / ghi_ask.mirror_refresh.DEFAULT_MIRROR_DIR) in cold_prompt,
          cold_prompt[:400])


# --- build_remote_command --------------------------------------------------
# The first live Mac->box run failed here: the command spliced in THIS
# machine's expanded seat path (/Users/el/agents/ghi-info), which does not
# exist on the box. The seat must be resolved by the box's own shell.
DANGEROUS = 'what about $(rm -rf /) and "quotes" and \'apostrophes\'?'
command = ghi_ask.build_remote_command(DANGEROUS, False, "x/y")

check("the remote command carries NO path from this machine",
      str(ghi_ask.DEFAULT_SEAT_DIR) not in command
      and str(Path.home()) not in command,
      command)
check("the seat is resolved box-side by the launcher's own agents-root rule",
      '"${NEDSCHORUS_AGENTS_ROOT:-$HOME/agents}/ghi-info"' in command, command)
check("the box-side run is pinned to --seat-dir \"$PWD\", so it can never "
      "re-delegate to itself (an infinite ssh loop)",
      '--seat-dir "$PWD"' in command, command)
check("--repo rides the remote command (it was silently dropped before)",
      "--repo x/y" in command, command)

command_closed = ghi_ask.build_remote_command("q", True, "x/y")
check("--include-closed rides the remote command when requested",
      "--include-closed" in command_closed, command_closed)
check("--include-closed is absent when not requested",
      "--include-closed" not in command, command)

# Quoting is measured by a real POSIX shell, not derived: the question is an
# operator value crossing one shell parse, and this project has been bitten
# by hand-derived quoting before (PR #134's review arc). The launcher's
# suite replays its layers the same way.
with tempfile.TemporaryDirectory() as temporary:
    probe_root = Path(temporary)
    recorder = probe_root / "record-argv"
    recorder.write_text(
        '#!/bin/sh\nfor a in "$@"; do printf "ARG:[%s]\\n" "$a"; done\n',
        encoding="utf-8")
    recorder.chmod(0o755)
    seat_home = probe_root / "agents" / "ghi-info"
    seat_home.mkdir(parents=True)
    replayed = ghi_ask.build_remote_command(DANGEROUS, True, "o/n").replace(
        "python3 scripts/ghi-info-ask.py", str(recorder))
    import subprocess as real_subprocess
    result = real_subprocess.run(
        ["/bin/sh", "-c", replayed], capture_output=True, text=True,
        env={"HOME": str(probe_root), "PATH": "/usr/bin:/bin"})
    recorded = result.stdout.splitlines()
    check("a real /bin/sh cds into the box-side seat and runs the ask there",
          result.returncode == 0, (result.returncode, result.stderr))
    check("the question survives one shell parse as ONE inert argument",
          f"ARG:[{DANGEROUS}]" in recorded, recorded)
    check("the shell resolved --seat-dir to the seat it actually cd'd into",
          f"ARG:[{seat_home}]" in recorded, recorded)

    # A box with no seat must say where it looked, not emit the shell's bare
    # "No such file or directory" — and must not run the ask anyway.
    empty_home = probe_root / "empty"
    empty_home.mkdir()
    missing_result = real_subprocess.run(
        ["/bin/sh", "-c", replayed], capture_output=True, text=True,
        env={"HOME": str(empty_home), "PATH": "/usr/bin:/bin"})
    check("a box with no seat exits 1, names the path, and runs no ask",
          missing_result.returncode == 1
          and "could not enter the ghi-info seat at" in missing_result.stderr
          and str(empty_home / "agents" / "ghi-info") in missing_result.stderr
          and "ARG:[" not in missing_result.stdout,
          (missing_result.returncode, missing_result.stderr, missing_result.stdout))


# --- main(): explicit --seat-dir skips SSH, missing seat-dir errors clean --
mirror_orig = ghi_ask.mirror_refresh.refresh
run_claude_orig = ghi_ask.run_claude
try:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        seat = root / "explicit-seat"
        seat.mkdir()
        fake_refresh_queue([([1], {"1": issue(1)}, None)])
        fake_claude_queue([
            ({"session_id": "sess-M", "result": "(ack)"}, None),
            ({"session_id": "sess-M", "result": "read #1"}, None),
        ])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exit_code = ghi_ask.main(["q", "--seat-dir", str(seat), "--repo", "x/y"])
        check("main() with an explicit --seat-dir runs locally and exits 0",
              exit_code == 0 and out.getvalue().strip() == "read #1", out.getvalue())

        missing = root / "no-such-seat"
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            exit_code = ghi_ask.main(["q", "--seat-dir", str(missing)])
        check("main() with a missing explicit --seat-dir errors cleanly, no traceback",
              exit_code == 1 and "bootstrap" in err.getvalue()
              and str(missing) in err.getvalue(),
              err.getvalue())
finally:
    patch_module_function(ghi_ask.mirror_refresh, "refresh", mirror_orig)
    patch("run_claude", run_claude_orig)


# --- run_claude(): a failing claude's diagnosis is reported, not a truncated blob --
# Behavior this pins, seen 2026-09-11: the box's claude login had expired. claude
# exited 1 AND wrote a complete JSON result whose `result` field carried the
# diagnosis ("Failed to authenticate: OAuth session expired ..."), ~1100 bytes in.
# run_claude checked the exit code first and reported the raw blob cut at 500
# characters, so the caller saw usage counters and never the cause.
LOGGED_OUT_STDOUT = json.dumps({
    "duration_api_ms": 0, "stop_reason": "stop_sequence", "session_id": "c637480c",
    "total_cost_usd": 0,
    "usage": {"input_tokens": 0, "output_tokens": 0, "server_tool_use": {},
              "cache_creation": {"ephemeral_1h_input_tokens": 0,
                                 "ephemeral_5m_input_tokens": 0},
              "padding": "x" * 700},
    "modelUsage": {}, "permission_denials": [], "terminal_reason": "api_error",
    "is_error": True, "num_turns": 1, "subtype": "success", "api_error_status": None,
    "result": "Failed to authenticate: OAuth session expired and could not be refreshed",
    "type": "result", "duration_ms": 133,
})
assert LOGGED_OUT_STDOUT.index('"result"') > 500, "the fixture must put the diagnosis past the old cut"


class FakeCompletedProcess:
    def __init__(self, returncode, stdout, stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def fake_subprocess_run_returning(completed):
    def fake_run(command, **kwargs):
        return completed
    return fake_run


subprocess_run_orig = ghi_ask.subprocess.run
try:
    with tempfile.TemporaryDirectory() as temporary:
        seat = Path(temporary)
        ghi_ask.subprocess.run = fake_subprocess_run_returning(
            FakeCompletedProcess(1, LOGGED_OUT_STDOUT))
        result, error = run_claude_real("q", None, seat, 5)
        check("run_claude: exit 1 with a JSON result reports the result text, not the blob",
              result is None and "OAuth session expired" in error
              and "duration_api_ms" not in error, (result, error))
        check("run_claude: a logged-out box names the login command and the machine",
              error is not None and "claude auth login" in error
              and ghi_ask.AGENT_BOX in error, error)

        ghi_ask.subprocess.run = fake_subprocess_run_returning(
            FakeCompletedProcess(1, "", stderr="boom"))
        result, error = run_claude_real("q", None, seat, 5)
        check("run_claude: exit 1 without JSON keeps the exit-code message",
              result is None and error == "claude exited 1: boom", (result, error))

        ghi_ask.subprocess.run = fake_subprocess_run_returning(
            FakeCompletedProcess(0, json.dumps({"is_error": True, "result": "rate limited"})))
        result, error = run_claude_real("q", None, seat, 5)
        check("run_claude: exit 0 with is_error reports the result, and no login remedy",
              result is None and "rate limited" in error and "auth login" not in error,
              (result, error))

        ghi_ask.subprocess.run = fake_subprocess_run_returning(
            FakeCompletedProcess(0, json.dumps({"session_id": "s", "result": "read #1"})))
        result, error = run_claude_real("q", None, seat, 5)
        check("run_claude: a clean result is returned unchanged",
              error is None and result["result"] == "read #1", (result, error))

        # The handoff hook reads this variable in the claude it launches and
        # stays silent, so a handoff notice never comes back as the answer.
        recorded_keyword_arguments = []

        def recording_run(command, **kwargs):
            recorded_keyword_arguments.append(kwargs)
            return FakeCompletedProcess(0, json.dumps({"session_id": "s", "result": "read #1"}))
        ghi_ask.subprocess.run = recording_run
        run_claude_real("q", "sess-RESUMED", seat, 5)
        launched_environment = (recorded_keyword_arguments[0].get("env") or {}
                                if recorded_keyword_arguments else {})
        check("run_claude: claude's environment tells the handoff hook this script "
              "reincarnates the session",
              launched_environment.get("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER")
              and launched_environment.get("PATH") == os.environ.get("PATH"),
              recorded_keyword_arguments)
finally:
    ghi_ask.subprocess.run = subprocess_run_orig

# --- the seat checkout is fast-forwarded before each ask -------------------
# Ruled 2026-09-15 (nedschorus#324/#334). The freshness hook's merge used to
# be the only thing keeping this checkout current, and that merge is gone; it
# is this caller's job now. ghi-info reads the pair documents and wiki pages
# from this disk, so a stale checkout is stale ANSWERS about the designs the
# issues point at. Real git repositories here: the whole value is in what git
# actually refuses.

import subprocess as _subprocess


def _git(arguments, cwd):
    return _subprocess.run(["git", *arguments], cwd=str(cwd),
                           capture_output=True, text=True, check=False)


def _commit(repository, name, content, message):
    (repository / name).write_text(content, encoding="utf-8")
    _git(["add", name], repository)
    _git(["commit", "-q", "-m", message], repository)


def _make_origin_and_seat(root, seat_name):
    """An origin repository and a seat checkout of it on its own branch —
    the box's layout: ghi-info sits on a branch named `ghi-info`, never main."""
    origin = root / f"{seat_name}-origin"
    origin.mkdir()
    _git(["init", "-q", "-b", "main"], origin)
    _git(["config", "user.email", "test@example.invalid"], origin)
    _git(["config", "user.name", "ghi test"], origin)
    _commit(origin, "shared.txt", "first\n", "first commit")
    seat = root / seat_name
    _git(["clone", "-q", str(origin), str(seat)], root)
    _git(["config", "user.email", "test@example.invalid"], seat)
    _git(["config", "user.name", "ghi test"], seat)
    _git(["checkout", "-q", "-b", "ghi-info"], seat)
    return origin, seat


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)

    origin, seat = _make_origin_and_seat(root, "ff-behind")
    _commit(origin, "design.md", "new design\n", "a design lands on main")
    line = ghi_ask.fast_forward_seat_checkout(seat)
    check("a behind seat checkout is fast-forwarded before the ask",
          (seat / "design.md").exists(), line)
    check("and it says how far it moved",
          "refreshed the seat checkout 1 commit(s)" in line, line)
    check("on its own branch, not main — the reference-checkout rule does not apply here",
          _git(["rev-parse", "--abbrev-ref", "HEAD"], seat).stdout.strip() == "ghi-info")

    check("a checkout already level with main says nothing",
          ghi_ask.fast_forward_seat_checkout(seat) == "",
          ghi_ask.fast_forward_seat_checkout(seat))

    # Freshness must never cost work. Each of the next three leaves the
    # checkout exactly as it was and lets the ask proceed.
    origin, seat = _make_origin_and_seat(root, "ff-dirty")
    _commit(origin, "design.md", "new design\n", "a design lands on main")
    (seat / "shared.txt").write_text("edit in progress\n", encoding="utf-8")
    line = ghi_ask.fast_forward_seat_checkout(seat)
    check("a checkout with uncommitted tracked work is not refreshed",
          "uncommitted tracked change(s)" in line and not (seat / "design.md").exists(), line)
    check("and that work is untouched",
          (seat / "shared.txt").read_text(encoding="utf-8") == "edit in progress\n")

    # ghi-info commits its own document-side link repairs, so a checkout
    # carrying a commit main does not have is a real state, not debris.
    origin, seat = _make_origin_and_seat(root, "ff-diverged")
    _commit(seat, "repair.md", "a link repair\n", "ghi-info repairs a link")
    _commit(origin, "design.md", "new design\n", "a design lands on main")
    head_before = _git(["rev-parse", "HEAD"], seat).stdout.strip()
    line = ghi_ask.fast_forward_seat_checkout(seat)
    check("a diverged checkout is reported and left alone, never merged",
          "would not fast-forward" in line
          and _git(["rev-parse", "HEAD"], seat).stdout.strip() == head_before, line)
    check("no merge state is left behind",
          not (seat / ".git" / "MERGE_HEAD").exists())

    not_a_checkout = root / "not-a-checkout"
    not_a_checkout.mkdir()
    line = ghi_ask.fast_forward_seat_checkout(not_a_checkout)
    check("a seat that is not a git checkout is one line, not a traceback",
          "not a git checkout" in line, line)

    # The mirror and the state file live in the seat directory untracked;
    # they must not read as work in progress and stop the refresh.
    origin, seat = _make_origin_and_seat(root, "ff-untracked")
    (seat / ghi_ask.mirror_refresh.DEFAULT_MIRROR_DIR).mkdir(parents=True, exist_ok=True)
    (seat / ghi_ask.mirror_refresh.DEFAULT_MIRROR_DIR / "issues-open.md").write_text(
        "open", encoding="utf-8")
    ghi_ask.save_state(seat / ghi_ask.STATE_FILE_NAME,
                       {"session_id": "s", "closes_since_birth": 0, "recent_matches": []})
    _commit(origin, "design.md", "new design\n", "a design lands on main")
    line = ghi_ask.fast_forward_seat_checkout(seat)
    check("the mirror and state file do not read as work in progress",
          (seat / "design.md").exists(), line)

    # --- the wiring: under the lock, and only under the lock ---------------
    origin, seat = _make_origin_and_seat(root, "ff-wired")
    _commit(origin, "design.md", "new design\n", "a design lands on main")
    fake_refresh_queue([([1], {"1": issue(1)}, None)])
    fake_claude_queue([
        ({"session_id": "sess-FF", "result": "(ack)"}, None),
        ({"session_id": "sess-FF", "result": "read #1"}, None),
    ])
    answer, error = ghi_ask.ask("what covers X?", False, seat, "x/y")
    check("an ordinary ask refreshes the checkout on the way in",
          answer == "read #1" and (seat / "design.md").exists(), (answer, error))

    # A contended run publishes into a throwaway mirror precisely so it
    # cannot disturb the lock holder. Swapping the checkout's files beneath
    # the holder's running claude would undo that.
    origin, seat = _make_origin_and_seat(root, "ff-contended")
    _commit(origin, "design.md", "new design\n", "a design lands on main")
    fake_refresh_queue([([], {}, None)])
    fake_claude_queue([
        ({"session_id": "sess-THROWAWAY", "result": "(ack)"}, None),
        ({"session_id": "sess-THROWAWAY", "result": "read #9"}, None),
    ])
    lock_path = seat / ghi_ask.LOCK_FILE_NAME
    held_handle = open(lock_path, "a+")
    fcntl.flock(held_handle.fileno(), fcntl.LOCK_EX)
    try:
        answer, error = ghi_ask.ask("q", False, seat, "x/y")
    finally:
        fcntl.flock(held_handle.fileno(), fcntl.LOCK_UN)
        held_handle.close()
    check("a CONTENDED ask still answers", answer == "read #9", (answer, error))
    check("but never moves the checkout under the lock holder's running claude",
          not (seat / "design.md").exists(), list(seat.iterdir()))


    # --- the run's last message is not always the answer -----------------
    # Measured 2026-09-17: ghi-info answered the question at 20:16:59Z and
    # then answered the checkout-freshness Stop hook 13 seconds later, and
    # this script returns the run's last message. The hooks are gone from the
    # run now; this check is what catches whatever else says something last.
    check("a reply naming an issue is an answer",
          ghi_ask.reply_answers_the_question("read #39, #29 — start with #39"))
    check("the two passthrough replies are answers",
          ghi_ask.reply_answers_the_question("out-of-scope")
          and ghi_ask.reply_answers_the_question("escalate: an old ruling may bind"))
    check("a reply to a Stop hook is not an answer",
          not ghi_ask.reply_answers_the_question(
              "No action needed on my part — this session hasn't touched any "
              "scripts or tests; I only read the GHI mirror to answer requests."))

    seat_hook = root / "seat-hook-reply"
    seat_hook.mkdir()
    ghi_ask.save_state(seat_hook / ghi_ask.STATE_FILE_NAME,
                       {"session_id": "sess-H", "closes_since_birth": 0, "recent_matches": []})
    fake_refresh_queue([([], {}, None)])
    fake_claude_queue([({"session_id": "sess-H",
                         "result": "No action needed on my part — this session "
                                   "hasn't touched any scripts or tests."}, None)])
    answer, error = ghi_ask.ask("what covers memory policy?", False, seat_hook, "x/y")
    check("such a reply fails the ask instead of being returned",
          answer is None and error is not None and "names no issue" in error,
          (answer, error))

    # And the run itself no longer loads this project's hooks.
    seat_flag = root / "seat-setting-sources"
    seat_flag.mkdir()
    recorded_command = {}

    def recording_run(command, **keywords):
        recorded_command["argv"] = command
        raise AssertionError("stop here: the command is what this case pins")

    patch_module_function(ghi_ask.subprocess, "run", recording_run)
    try:
        # run_claude_real: the case before this one left a fake in its place.
        run_claude_real("a question", None, seat_flag, 5)
    except AssertionError:
        pass
    argv = recorded_command.get("argv", [])
    check("run_claude passes --setting-sources user, so no project hook runs",
          "--setting-sources" in argv
          and argv[argv.index("--setting-sources") + 1] == "user", argv)


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
