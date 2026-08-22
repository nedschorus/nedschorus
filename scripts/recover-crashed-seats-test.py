#!/usr/bin/env python3
"""Tests for recover-crashed-seats.py (nedschorus#120).

Every case runs against a sandboxed workspace — throwaway agents root,
handoff directory, and projects root — with tmux and lsof answered by
monkeypatched functions, so no test touches a real seat, server, or
process listing. The launch step is captured, never executed.

The refusal cases are the script's whole safety story: it must never act
on a live seat, a watched seat, an occupied directory, or an unprovable
answer. The recovery cases prove the 2026-08-21 hand procedure is what
actually runs: newest real transcript wins, empty successors are skipped,
and the resume rides --resume-session-id to the supervisor.

Run: python3 scripts/recover-crashed-seats-test.py
"""

import importlib.util
import json
import os
import shlex
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("recover-crashed-seats.py")

_spec = importlib.util.spec_from_file_location("recover_crashed_seats", SCRIPT_PATH)
recovery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recovery)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def write_transcript(directory: Path, session_id: str, first_user_text: str,
                     age_seconds: float = 0.0, records: int = 3,
                     tool_turns: int = 0):
    """One harness transcript whose first user turn says first_user_text.
    records-1 text-bearing assistant turns, then tool_turns assistant turns
    carrying only tool_use blocks (the terse tool-heavy shape, round 3
    finding 2)."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{session_id}.jsonl"
    lines = [json.dumps({"type": "user", "isMeta": False,
                         "message": {"content": first_user_text}})]
    for index in range(records - 1):
        lines.append(json.dumps({"type": "assistant",
                                 "message": {"content": f"turn {index}"}}))
    for index in range(tool_turns):
        lines.append(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": f"tool-{index}", "name": "Bash",
             "input": {"command": "true"}}]}}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if age_seconds:
        stamp = time.time() - age_seconds
        import os
        os.utime(path, (stamp, stamp))
    return path


class Workspace:
    """A sandboxed seat world, plus captured launches."""

    def __init__(self, root: Path, name="seat-a"):
        self.name = name
        self.agents_root = root / "agents"
        self.handoffs = root / "handoffs"
        self.projects = root / "projects"
        self.seat_directory = self.agents_root / name
        self.seat_directory.mkdir(parents=True)
        self.handoffs.mkdir(parents=True)
        self.projects.mkdir(parents=True)
        self.launches = []

    def project_directory(self) -> Path:
        return recovery.harness_project_directory(self.seat_directory, self.projects)

    def assess(self):
        return recovery.assess_seat(self.name, self.agents_root, self.handoffs,
                                    self.projects)

    def recover(self, dry_run=False, ignite_fallback=False):
        return recovery.recover_seat(self.name, self.agents_root, self.handoffs,
                                     self.projects, dry_run, ignite_fallback)




def real_subprocess_run_help():
    import subprocess
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH.with_name("handoff-supervisor.py")), "--help"],
        capture_output=True, text=True).stdout

def patch(monkey_target, value):
    setattr(recovery, monkey_target, value)


def all_dead():
    """Monkeypatch the world to 'seat is fully dead, directory vacant'."""
    patch("tmux_session_alive_anywhere", lambda name: (False, ""))
    patch("seat_directory_occupied", lambda directory: (False, ""))


real_launch_seat = recovery.launch_seat  # for cases that probe the real one


def capture_launches(workspace: Workspace):
    def fake_launch(name, seat_directory, handoff_directory, extra_arguments,
                    first_prompt_file=None):
        workspace.launches.append((name, extra_arguments, first_prompt_file))
        return 0
    patch("launch_seat", fake_launch)


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)

    # --- refusals -----------------------------------------------------------
    workspace = Workspace(root / "w1")
    patch("tmux_session_alive_anywhere",
          lambda name: (True, f"tmux session '{name}' is alive on socket '{name}'"))
    verdict, detail = workspace.assess()
    check("a live tmux session refuses (per-seat socket)",
          verdict == "refuse" and "never touches live seats" in detail, (verdict, detail))

    patch("tmux_session_alive_anywhere", lambda name: (False, ""))
    state_path = workspace.handoffs / f"{workspace.name}-supervisor-state.json"
    state_path.write_text(json.dumps({
        "session_id": "x", "generation": 1,
        "last_poll_at": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    verdict, detail = workspace.assess()
    check("a live supervisor heartbeat refuses",
          verdict == "refuse" and "supervisor is watching" in detail, (verdict, detail))
    state_path.unlink()

    patch("seat_directory_occupied",
          lambda directory: (True, f"a live process is rooted in {directory}"))
    verdict, detail = workspace.assess()
    check("an occupied seat directory refuses",
          verdict == "refuse" and "live process" in detail, (verdict, detail))

    patch("seat_directory_occupied",
          lambda directory: (True, "lsof is not installed, so the seat cannot be proven vacant"))
    verdict, detail = workspace.assess()
    check("an unprovable vacancy answer refuses (fail closed)",
          verdict == "refuse" and "cannot be proven" in detail, (verdict, detail))

    workspace_missing = Workspace(root / "w2", name="seat-b")
    all_dead()
    verdict, detail = recovery.assess_seat("no-such-seat", workspace_missing.agents_root,
                                           workspace_missing.handoffs,
                                           workspace_missing.projects)
    check("a seat with no home directory refuses",
          verdict == "refuse" and "no seat directory" in detail, (verdict, detail))

    # --- defer to boot-ignition when a handoff genuinely waits --------------
    workspace = Workspace(root / "w3")
    all_dead()
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        "# Handoff\nrestart-counter: 5\nnext-step: continue\n", encoding="utf-8")
    verdict, detail = workspace.assess()
    check("an unconsumed handoff defers to the supervisor's boot-ignition",
          verdict == "defer-to-boot-ignition" and "counter 5" in detail,
          (verdict, detail))

    state_path = workspace.handoffs / f"{workspace.name}-supervisor-state.json"
    state_path.write_text(json.dumps({"consumed_counter": 5}), encoding="utf-8")
    write_transcript(workspace.project_directory(), "real-session", "do the work", records=4)
    verdict, detail = workspace.assess()
    check("a consumed handoff does not defer; the transcript resume proceeds",
          verdict == "resume" and detail[0] == "real-session", (verdict, detail))

    # --- transcript selection ----------------------------------------------
    workspace = Workspace(root / "w4")
    all_dead()
    write_transcript(workspace.project_directory(), "old-real",
                     "start the build", age_seconds=3600)
    write_transcript(workspace.project_directory(), "empty-successor",
                     "You are seat-a. No handoff exists yet; ask what to work on.",
                     records=2)  # died at its first reply: under the turn minimum
    verdict, detail = workspace.assess()
    check("an empty-successor transcript never shadows the real one",
          verdict == "resume" and detail[0] == "old-real", (verdict, detail))

    workspace = Workspace(root / "w5")
    all_dead()
    write_transcript(workspace.project_directory(), "older-real", "first stint",
                     age_seconds=7200)
    write_transcript(workspace.project_directory(), "newer-real", "second stint",
                     age_seconds=60)
    verdict, detail = workspace.assess()
    check("the newest real transcript wins",
          verdict == "resume" and detail[0] == "newer-real", (verdict, detail))

    workspace = Workspace(root / "w6")
    all_dead()
    write_transcript(workspace.project_directory(), "empty-only",
                     "You are seat-a. No handoff exists yet; ask what to work on.",
                     records=1)  # never replied at all
    verdict, detail = workspace.assess()
    check("only empty successors on disk routes to ignite, not resume",
          verdict == "ignite" and "nothing worth resuming" in detail, (verdict, detail))

    workspace = Workspace(root / "w7")
    all_dead()
    verdict, detail = workspace.assess()
    check("no transcripts at all routes to ignite",
          verdict == "ignite" and "no harness project directory" in detail,
          (verdict, detail))

    # Caught live 2026-08-22: a seat's FIRST session legitimately starts with
    # the no-handoff prompt and then does real work — the marker alone must
    # not write it off. Size decides: big-with-marker resumes.
    workspace = Workspace(root / "w7b")
    all_dead()
    big = write_transcript(workspace.project_directory(), "first-ever-session",
                           "You are seat-a. No handoff exists yet; ask what to work on.")
    big.write_text(big.read_text() +
                   ("\n" + json.dumps({"type": "assistant",
                                        "message": {"content": "x" * 400}})) * 300,
                   encoding="utf-8")
    verdict, detail = workspace.assess()
    check("a LARGE transcript that began with the no-handoff prompt still resumes",
          verdict == "resume" and detail[0] == "first-ever-session",
          (verdict, detail))

    # --- recovery actions ---------------------------------------------------
    workspace = Workspace(root / "w8")
    all_dead()
    write_transcript(workspace.project_directory(), "crashed-session", "real work",
                     records=6)
    capture_launches(workspace)
    report = workspace.recover(dry_run=True)
    check("dry-run resumes nothing and names the session",
          "would resume session crashed-session" in report and not workspace.launches,
          (report, workspace.launches))
    report = workspace.recover()
    check("the resume launch rides --resume-session-id to the supervisor",
          workspace.launches
          and shlex.split(workspace.launches[0][1])
              == ["--resume-session-id", "crashed-session"],
          workspace.launches)
    check("the resume report names the session and its size",
          "resuming crashed-session" in report and "KB transcript" in report, report)

    workspace = Workspace(root / "w9")
    all_dead()
    write_transcript(workspace.project_directory(), "crashed-session", "real work")
    (workspace.handoffs / f"{workspace.name}-dialog-0007.md").write_text(
        "the dialog extract", encoding="utf-8")
    capture_launches(workspace)
    report = workspace.recover(ignite_fallback=True)
    check("--ignite-fallback launches fresh reading the newest extract",
          workspace.launches and workspace.launches[0][1] == ""
          and workspace.launches[0][2] is not None
          and "igniting from seat-a-dialog-0007.md" in report,
          (report, workspace.launches))
    prompt_text = workspace.launches[0][2].read_text(encoding="utf-8")
    check("the recovery ignition prompt names the extract, the crash, and #120",
          "seat-a-dialog-0007.md" in prompt_text and "died without a handoff" in prompt_text
          and "nedschorus#120" in prompt_text, prompt_text)

    workspace = Workspace(root / "w10")
    all_dead()
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        "# Handoff\nrestart-counter: 9\nnext-step: go\n", encoding="utf-8")
    capture_launches(workspace)
    report = workspace.recover()
    check("the defer path relaunches plain (no extra supervisor arguments)",
          workspace.launches and workspace.launches[0][1] == ""
          and workspace.launches[0][2] is None and "relaunched plain" in report,
          (report, workspace.launches))

    # --- the supervisor's --resume-session-id flag --------------------------
    supervisor_spec = importlib.util.spec_from_file_location(
        "handoff_supervisor_under_test", SCRIPT_PATH.with_name("handoff-supervisor.py"))
    supervisor_module = importlib.util.module_from_spec(supervisor_spec)
    supervisor_spec.loader.exec_module(supervisor_module)

    launched = []
    class FakeProcess:
        pass
    def fake_popen(argv, cwd=None):
        launched.append((argv, cwd))
        return FakeProcess()
    # supervisor_module.subprocess IS the shared subprocess module: patch the
    # attribute and restore it, or every later real_subprocess.run breaks.
    real_popen = supervisor_module.subprocess.Popen
    try:
        supervisor_module.subprocess.Popen = fake_popen
        supervisor_module.launch_agent_session("claude", "abc-123", Path("/tmp"),
                                               "the prompt", resume=True)
        check("supervisor resume launch uses --resume, not --session-id",
              launched and launched[0][0] == ["claude", "--resume", "abc-123", "the prompt"],
              launched)
        launched.clear()
        supervisor_module.launch_agent_session("claude", "abc-123", Path("/tmp"),
                                               "the prompt")
        check("supervisor plain launch still uses --session-id",
              launched and launched[0][0] == ["claude", "--session-id", "abc-123", "the prompt"],
              launched)
    finally:
        supervisor_module.subprocess.Popen = real_popen

    # --- PR #131 review round: the fix-round regressions --------------------

    # F1: an unanswerable tmux axis refuses (fail closed, like lsof).
    workspace = Workspace(root / "r1")
    patch("tmux_session_alive_anywhere",
          lambda name: (None, "tmux cannot be run here, so seat liveness cannot be "
                              "checked — refusing rather than guessing"))
    patch("seat_directory_occupied", lambda directory: (False, ""))
    verdict, detail = workspace.assess()
    check("F1: tmux unanswerable refuses instead of reading as dead",
          verdict == "refuse" and "cannot be checked" in detail, (verdict, detail))

    # F1: a failing launch is reported and counted, not claimed as success.
    workspace = Workspace(root / "r2")
    all_dead()
    write_transcript(workspace.project_directory(), "real-work", "do things", records=5)
    def failing_launch(name, seat_directory, handoff_directory, extra,
                       first_prompt_file=None):
        workspace.launches.append((name, extra, first_prompt_file))
        return 2
    patch("launch_seat", failing_launch)
    report = workspace.recover()
    check("F1: a failed launch reports LAUNCH FAILED, never 'relaunched'",
          "LAUNCH FAILED (exit 2)" in report and "relaunched" not in report, report)

    # F2: the resume launch carries the crash-recovery prompt file.
    workspace = Workspace(root / "r3")
    all_dead()
    write_transcript(workspace.project_directory(), "real-work", "do things", records=5)
    capture_launches(workspace)
    workspace.recover()
    check("F2: the resume launch passes a first-prompt file",
          workspace.launches and workspace.launches[0][2] is not None,
          workspace.launches)
    resume_prompt = workspace.launches[0][2].read_text(encoding="utf-8")
    check("F2: the resume prompt says crash-not-recycle and re-verify, not ask-for-work",
          "died without writing a handoff" in resume_prompt
          and "Re-verify" in resume_prompt
          and "No handoff exists yet" not in resume_prompt, resume_prompt)

    # F3: recovery's own fresh-session shapes are skipped when small and workless...
    workspace = Workspace(root / "r4")
    all_dead()
    write_transcript(workspace.project_directory(), "pre-crash-real", "real work",
                     age_seconds=3600, records=6)
    write_transcript(workspace.project_directory(), "failed-ignition",
                     "Read x-dialog-0004.md (crash recovery, nedschorus#120). Continue.",
                     records=1)  # died before working
    verdict, detail = workspace.assess()
    check("F3/R4: a failed-ignition successor that died before working is skipped",
          verdict == "resume" and detail[0] == "pre-crash-real", (verdict, detail))

    workspace = Workspace(root / "r5")
    all_dead()
    write_transcript(workspace.project_directory(), "pre-crash-real", "real work",
                     age_seconds=3600, records=6)
    empty = workspace.project_directory() / "zero-byte.jsonl"
    empty.write_text("", encoding="utf-8")
    verdict, detail = workspace.assess()
    check("F3: a 0-byte transcript never shadows the pre-crash transcript",
          verdict == "resume" and detail[0] == "pre-crash-real", (verdict, detail))

    workspace = Workspace(root / "r6")
    all_dead()
    write_transcript(workspace.project_directory(), "pre-crash-real", "real work",
                     age_seconds=3600, records=6)
    ignition_shape = write_transcript(
        workspace.project_directory(), "supervisor-ignition",
        "Read /x/y-dialog-0002.md — it is the dialog from the session you are "
        "continuing, written 0 minutes ago.", records=1)  # died before working
    verdict, detail = workspace.assess()
    check("F3/P2: a supervisor-ignition successor that died before working is skipped",
          verdict == "resume" and detail[0] == "pre-crash-real", (verdict, detail))

    # F8: every cross-file literal the filter relies on is asserted against
    # the supervisor's actual source, so a wording change there fails HERE
    # (round-3 P3-3: the round-2 assertion covered only the first marker).
    source = SCRIPT_PATH.with_name("handoff-supervisor.py").read_text(encoding="utf-8")
    check("F8: the no-handoff marker is verbatim in handoff-supervisor.py",
          "No handoff exists yet" in source
          and "No handoff exists yet" in recovery.EMPTY_SUCCESSOR_MARKERS,
          recovery.EMPTY_SUCCESSOR_MARKERS)
    check("F8: the ignition-opener literal is verbatim in handoff-supervisor.py",
          "it is the dialog from the session you are continuing" in source
          and "it is the dialog from the session you are continuing"
              in recovery.EMPTY_SUCCESSOR_MARKERS,
          "opener literal missing from supervisor source or the marker set")

    # Q2: an unparseable handoff counter refuses with both paths named.
    workspace = Workspace(root / "r7")
    all_dead()
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        "# Handoff\nrestart-counter: not-a-number\nnext-step: x\n", encoding="utf-8")
    verdict, detail = workspace.assess()
    check("Q2: an unreadable restart-counter refuses, naming fix and delete paths",
          verdict == "refuse" and "restart-counter" in detail
          and "delete it" in detail, (verdict, detail))

    # Q3: a live-held supervisor lock refuses.
    workspace = Workspace(root / "r8")
    all_dead()
    (workspace.handoffs / f"{workspace.name}-supervisor.lock").write_text(
        f"{os.getpid()}\n", encoding="utf-8")
    verdict, detail = workspace.assess()
    check("Q3: a supervisor lock held by a live process refuses",
          verdict == "refuse" and "supervisor lock" in detail, (verdict, detail))
    (workspace.handoffs / f"{workspace.name}-supervisor.lock").write_text(
        "999999999\n", encoding="utf-8")
    write_transcript(workspace.project_directory(), "real", "work", records=4)
    verdict, detail = workspace.assess()
    check("Q3: a stale lock (dead pid) does not block recovery",
          verdict == "resume", (verdict, detail))

    # F4: the supervisor's resume path consumes a stale handoff instead of
    # letting the wait loop kill the resumed session. Proven through the
    # boot-sequence branch in supervise_sessions via source inspection plus
    # the flag's help text; the live-loop probe belongs to the reviewer's
    # harness and stays there.
    help_text = " ".join(real_subprocess_run_help().split())
    check("F4: --resume-session-id help states the handoff-consumption rule",
          "marked consumed" in help_text
          and "chooses the transcript over any waiting handoff" in help_text,
          help_text[:300])

    # F4 behavioral: drive supervise_sessions far enough to prove a stale
    # handoff is consume-marked BEFORE the resume launch, so the wait loop
    # cannot kill the resumed session for it. The fake launch records the
    # state file's counter at launch time, then raises to stop the loop.
    workspace = Workspace(root / "r9")
    state_seen_at_launch = {}
    class StopLoop(Exception):
        pass
    def probe_launch(agent_command, session_id, working_directory, prompt, resume=False):
        state_seen_at_launch.update(json.loads(
            (workspace.handoffs / "seat-a-supervisor-state.json").read_text()))
        state_seen_at_launch["resume_flag"] = resume
        raise StopLoop()
    (workspace.handoffs / "seat-a-handoff.md").write_text(
        "# Handoff\nrestart-counter: 7\nnext-step: stale\n", encoding="utf-8")
    sup = supervisor_module
    original_launch = sup.launch_agent_session
    original_sync = sup.sync_working_branch_with_main
    try:
        sup.launch_agent_session = probe_launch
        sup.sync_working_branch_with_main = lambda d: "sync skipped (probe)"
        settings = sup.SupervisorSettings(
            agent="seat-a", working_directory=workspace.seat_directory,
            handoff_directory=workspace.handoffs, agent_command="claude",
            first_prompt="", resume_session_id="resume-me")
        try:
            sup.supervise_sessions(settings)
        except StopLoop:
            pass
    finally:
        sup.launch_agent_session = original_launch
        sup.sync_working_branch_with_main = original_sync
    check("F4: a stale handoff is consume-marked before the resume launch",
          state_seen_at_launch.get("consumed_counter") == 7
          and state_seen_at_launch.get("resume_flag") is True,
          state_seen_at_launch)

    # Round 3 P1: an underscore-named seat's transcripts are FOUND — the
    # mangling is the harness's (every non-alphanumeric becomes a dash),
    # delegated to watch-agent-dialogs' probe-verified rule.
    workspace = Workspace(root / "r10", name="under_score_seat")
    all_dead()
    mangled = recovery.harness_project_directory(workspace.seat_directory,
                                                 workspace.projects)
    check("P1: underscore in the seat path mangles to a dash (harness rule)",
          "under-score-seat" in mangled.name and "_" not in mangled.name,
          mangled.name)
    write_transcript(mangled, "underscore-real", "real work here", records=6)
    verdict, detail = workspace.assess()
    check("P1: an underscore-named seat's intact transcript is found and resumed",
          verdict == "resume" and detail[0] == "underscore-real", (verdict, detail))

    # Round 3 P2: a recycled successor that crashed AFTER doing real work is
    # resumed, not skipped for its handed-off parent; one that died before
    # doing anything is skipped. Both under 100KB — turns decide, not bytes.
    ignition_opener = ("Read /x/seat-a-dialog-0003.md — it is the dialog from "
                      "the session you are continuing, written 0 minutes ago.")
    workspace = Workspace(root / "r11")
    all_dead()
    write_transcript(workspace.project_directory(), "generation-3-handed-off",
                     "older real work", age_seconds=7200, records=8)
    write_transcript(workspace.project_directory(), "generation-4-crashed",
                     ignition_opener, records=9)  # 8 assistant turns: real work
    verdict, detail = workspace.assess()
    check("P2: a crashed recycled successor WITH real work is resumed, not its parent",
          verdict == "resume" and detail[0] == "generation-4-crashed",
          (verdict, detail))

    workspace = Workspace(root / "r12")
    all_dead()
    write_transcript(workspace.project_directory(), "generation-3-handed-off",
                     "older real work", age_seconds=7200, records=8)
    write_transcript(workspace.project_directory(), "generation-4-stillborn",
                     ignition_opener, records=1)  # no assistant turns at all
    verdict, detail = workspace.assess()
    check("P2: a recycled successor that died before working is skipped for its parent",
          verdict == "resume" and detail[0] == "generation-3-handed-off",
          (verdict, detail))

    # P3-4: the supervisor's own default prompt on a resume launch is the
    # truthful crash-recovery text, not ask-for-work.
    launched_prompts = []
    def prompt_probe(agent_command, session_id, working_directory, prompt, resume=False):
        launched_prompts.append((prompt, resume))
        raise StopIteration()
    sup = supervisor_module
    original_launch2 = sup.launch_agent_session
    original_sync2 = sup.sync_working_branch_with_main
    try:
        sup.launch_agent_session = prompt_probe
        sup.sync_working_branch_with_main = lambda d: "sync skipped (probe)"
        ws = Workspace(root / "r13")
        settings = sup.SupervisorSettings(
            agent="seat-a", working_directory=ws.seat_directory,
            handoff_directory=ws.handoffs, agent_command="claude",
            first_prompt="", resume_session_id="resume-me")
        try:
            sup.supervise_sessions(settings)
        except StopIteration:
            pass
    finally:
        sup.launch_agent_session = original_launch2
        sup.sync_working_branch_with_main = original_sync2
    check("P3-4: a by-hand resume launch defaults to the crash-recovery prompt",
          launched_prompts and launched_prompts[0][1] is True
          and "resumed by crash recovery" in launched_prompts[0][0]
          and "No handoff exists yet" not in launched_prompts[0][0],
          launched_prompts)

    # --- PR #131 review round 4 --------------------------------------------

    # Round 4 finding 1: the turn gate covers EVERY marker, not only the
    # recycle opener — the reviewer measured markers 1 and 2 skipping real
    # work on size alone. Same shape as the accepted round-3 P2 cases: small
    # transcript, 8 text-bearing assistant turns, beside an older parent.
    workspace = Workspace(root / "r14")
    all_dead()
    write_transcript(workspace.project_directory(), "handed-off-parent",
                     "older real work", age_seconds=7200, records=8)
    write_transcript(workspace.project_directory(), "first-ever-crashed",
                     "You are seat-a. No handoff exists yet; ask what to work on.",
                     records=9)  # 8 assistant turns: real work
    verdict, detail = workspace.assess()
    check("R4-1: a small first-ever session WITH real work is resumed, not its parent",
          verdict == "resume" and detail[0] == "first-ever-crashed",
          (verdict, detail))

    workspace = Workspace(root / "r15")
    all_dead()
    write_transcript(workspace.project_directory(), "handed-off-parent",
                     "older real work", age_seconds=7200, records=8)
    write_transcript(workspace.project_directory(), "ignition-then-crashed",
                     "Read x-dialog-0004.md (crash recovery, nedschorus#120). Continue.",
                     records=9)  # the --ignite-fallback loop the reviewer named
    verdict, detail = workspace.assess()
    check("R4-1: an ignite-fallback successor WITH real work is resumed, not its parent",
          verdict == "resume" and detail[0] == "ignition-then-crashed",
          (verdict, detail))

    # Round 4 finding 2: tool_use-only assistant turns are work. The
    # reviewer's shapes: 12 tool-only turns and no text reply, and the same
    # with one text reply — both were skipped for the parent before.
    workspace = Workspace(root / "r16")
    all_dead()
    write_transcript(workspace.project_directory(), "handed-off-parent",
                     "older real work", age_seconds=7200, records=8)
    tool_heavy = write_transcript(
        workspace.project_directory(), "tool-heavy-crashed", ignition_opener,
        records=1, tool_turns=12)  # no text replies at all, 12 tool calls
    check("R4-2: substantive_turn_count counts tool_use-only turns",
          recovery.substantive_turn_count(tool_heavy) == 12,
          recovery.substantive_turn_count(tool_heavy))
    verdict, detail = workspace.assess()
    check("R4-2: a terse tool-heavy successor is resumed, not its parent",
          verdict == "resume" and detail[0] == "tool-heavy-crashed",
          (verdict, detail))

    # Round 4 codex finding A (handoff dir) and finding B (agents root):
    # probed through the REAL launch_seat on the launcher branch, in codex's
    # own scenario — the defer path with an override handoff directory.
    workspace = Workspace(root / "r17")
    all_dead()
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        "# Handoff\nrestart-counter: 3\nnext-step: go\n", encoding="utf-8")
    captured_run = {}
    def capture_subprocess_run(command, env=None, check=False):
        captured_run["command"] = command
        captured_run["env"] = env
        class Done:
            returncode = 0
        return Done()
    real_run = recovery.subprocess.run
    real_launcher_path = recovery.launcher_path
    try:
        patch("launch_seat", real_launch_seat)
        recovery.subprocess.run = capture_subprocess_run
        recovery.launcher_path = lambda: Path("/fake/launch-claude-mac")
        report = workspace.recover()
    finally:
        recovery.subprocess.run = real_run
        recovery.launcher_path = real_launcher_path
    supervisor_arguments = captured_run["env"].get(
        "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS", "")
    # Assertions parse the composed string the way the launch shell will
    # (shlex.split), instead of matching hand-written quotes — the quoting
    # itself is under test since PR #134's review finding 1.
    check("A: the defer launch hands the supervisor the assessed handoff directory",
          shlex.split(supervisor_arguments) == ["--handoff-dir", str(workspace.handoffs)]
          and "relaunched plain" in report,
          (supervisor_arguments, report))
    check("B: the launcher branch pins NEDSCHORUS_AGENTS_ROOT to the assessed root",
          captured_run["env"].get("NEDSCHORUS_AGENTS_ROOT")
          == str(workspace.agents_root),
          captured_run["env"].get("NEDSCHORUS_AGENTS_ROOT"))

    # Finding A on the resume path: --handoff-dir and --resume-session-id
    # travel together, and the box branch composes the same into its
    # supervisor command.
    workspace = Workspace(root / "r18")
    tmux_commands = []
    def capture_tmux(*arguments_after_tmux, socket_name=None):
        tmux_commands.append((arguments_after_tmux, socket_name))
        class Done:
            returncode = 0
        return Done()
    try:
        recovery.subprocess.run = capture_subprocess_run
        recovery.launcher_path = lambda: Path("/fake/launch-claude-mac")
        real_launch_seat(workspace.name, workspace.seat_directory,
                         workspace.handoffs,
                         f"--resume-session-id {shlex.quote('abc-123')}")
    finally:
        recovery.subprocess.run = real_run
        recovery.launcher_path = real_launcher_path
    resume_arguments = captured_run["env"].get(
        "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS", "")
    check("A: the resume launch carries --handoff-dir alongside --resume-session-id",
          shlex.split(resume_arguments) == ["--handoff-dir", str(workspace.handoffs),
                                            "--resume-session-id", "abc-123"],
          resume_arguments)
    real_run_tmux = recovery.run_tmux
    try:
        recovery.launcher_path = lambda: None
        recovery.run_tmux = capture_tmux
        real_launch_seat(workspace.name, workspace.seat_directory,
                         workspace.handoffs,
                         f"--resume-session-id {shlex.quote('abc-123')}")
    finally:
        recovery.launcher_path = real_launcher_path
        recovery.run_tmux = real_run_tmux
    box_command = tmux_commands[0][0][-1] if tmux_commands else ""
    box_tokens = shlex.split(box_command)
    check("A: the box branch composes --handoff-dir into the supervisor command",
          str(workspace.handoffs) in box_tokens
          and str(workspace.seat_directory) in box_tokens
          and "abc-123" in box_tokens
          and "--handoff-dir" in box_tokens,
          box_command)

    # PR #134 review finding 1: an apostrophe in an operator's directory path
    # must survive the one shell parse each composed value gets — the
    # reviewer measured the hand-quoted version killing the seat and then
    # failing the launch. Both branches, parsed as the launch shell would.
    apostrophe_handoffs = root / "r19" / "agent's handoffs"
    apostrophe_handoffs.mkdir(parents=True)
    try:
        recovery.subprocess.run = capture_subprocess_run
        recovery.launcher_path = lambda: Path("/fake/launch-claude-mac")
        real_launch_seat(workspace.name, workspace.seat_directory,
                         apostrophe_handoffs, "")
    finally:
        recovery.subprocess.run = real_run
        recovery.launcher_path = real_launcher_path
    check("F1: an apostrophe handoff dir survives the mac hook's shell parse",
          shlex.split(captured_run["env"]["LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"])
          == ["--handoff-dir", str(apostrophe_handoffs)],
          captured_run["env"]["LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"])
    tmux_commands.clear()
    try:
        recovery.launcher_path = lambda: None
        recovery.run_tmux = capture_tmux
        real_launch_seat(workspace.name, workspace.seat_directory,
                         apostrophe_handoffs, "")
    finally:
        recovery.launcher_path = real_launcher_path
        recovery.run_tmux = real_run_tmux
    check("F1: an apostrophe handoff dir survives the box command's shell parse",
          str(apostrophe_handoffs) in shlex.split(tmux_commands[0][0][-1]),
          tmux_commands[0][0][-1])

    # PR #134 review finding 2: a --handoff-dir that does not exist yet must
    # not traceback after assessment already chose to resume — the resume
    # prompt's directory is created, as the supervisor creates its own.
    workspace = Workspace(root / "r20")
    all_dead()
    write_transcript(workspace.project_directory(), "resume-me", "real work",
                     records=5)
    capture_launches(workspace)
    missing_handoffs = workspace.handoffs / "not-created-yet"
    report = recovery.recover_seat(workspace.name, workspace.agents_root,
                                   missing_handoffs, workspace.projects,
                                   False, False)
    check("F2: a nonexistent --handoff-dir does not traceback; the resume proceeds",
          "relaunched resuming resume-me" in report, report)
    check("F2: the resume prompt lands in the created directory",
          (missing_handoffs / f"{workspace.name}-resume-recovery-prompt.md").is_file(),
          missing_handoffs)

    # Round-4 review note (user-ruled 2026-08-22: allowed overrides must
    # work): default_agents_root resolves the same way the launchers do —
    # ${NEDSCHORUS_AGENTS_ROOT:-~/agents}. Resolving differently assesses a
    # root no seat lives in, and recovery refuses on "no seat directory".
    saved_root = os.environ.get("NEDSCHORUS_AGENTS_ROOT")
    try:
        os.environ["NEDSCHORUS_AGENTS_ROOT"] = str(root / "custom-agents")
        check("default_agents_root honors NEDSCHORUS_AGENTS_ROOT",
              recovery.default_agents_root() == root / "custom-agents",
              recovery.default_agents_root())
        os.environ["NEDSCHORUS_AGENTS_ROOT"] = ""
        check("an empty NEDSCHORUS_AGENTS_ROOT falls back to ~/agents (the :- rule)",
              recovery.default_agents_root() == Path("~/agents").expanduser(),
              recovery.default_agents_root())
    finally:
        if saved_root is None:
            os.environ.pop("NEDSCHORUS_AGENTS_ROOT", None)
        else:
            os.environ["NEDSCHORUS_AGENTS_ROOT"] = saved_root

    import subprocess as real_subprocess
    completed = real_subprocess.run(
        [sys.executable, str(SCRIPT_PATH.with_name("handoff-supervisor.py")),
         "--agent", "x", "--resume-session-id", "a", "--adopt-session-id", "b",
         "--adopt-process-id", "1"],
        capture_output=True, text=True)
    check("supervisor refuses --resume-session-id together with adoption",
          completed.returncode != 0 and "different recoveries" in completed.stderr,
          completed.stderr)


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
