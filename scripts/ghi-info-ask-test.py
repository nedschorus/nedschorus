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
import shlex
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("ghi-info-ask.py")

_spec = importlib.util.spec_from_file_location("ghi_info_ask", SCRIPT_PATH)
ghi_ask = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ghi_ask)

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
          state["session_id"] == "sess-A", state)
    check("state resets counters on a cold start",
          state["closes_since_birth"] == 0 and state["recent_matches"] == [False], state)

    # --- resume: existing session, no recycle trigger -> one claude call ---
    seat2 = root / "seat2"
    seat2.mkdir()
    ghi_ask.save_state(seat2 / ghi_ask.STATE_FILE_NAME,
                       {"session_id": "sess-B", "closes_since_birth": 0, "recent_matches": []})
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

    # --- recycle: closes-since-birth over threshold forces a cold start ----
    seat3 = root / "seat3"
    seat3.mkdir()
    ghi_ask.save_state(seat3 / ghi_ask.STATE_FILE_NAME, {
        "session_id": "sess-OLD",
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
    check("recycle replaces the old session id with the new one",
          state3["session_id"] == "sess-NEW", state3)

    # --- lock contention: throwaway session, nothing persisted -------------
    seat4 = root / "seat4"
    seat4.mkdir()
    ghi_ask.save_state(seat4 / ghi_ask.STATE_FILE_NAME,
                       {"session_id": "sess-HELD", "closes_since_birth": 0, "recent_matches": []})
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

    # --- transcript-size recycle trigger (real project-dir mangling) -------
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


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
