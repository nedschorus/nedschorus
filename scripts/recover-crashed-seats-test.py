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
                     age_seconds: float = 0.0, records: int = 3):
    """One harness transcript whose first user turn says first_user_text."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{session_id}.jsonl"
    lines = [json.dumps({"type": "user", "isMeta": False,
                         "message": {"content": first_user_text}})]
    for index in range(records - 1):
        lines.append(json.dumps({"type": "assistant",
                                 "message": {"content": f"turn {index}"}}))
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


def patch(monkey_target, value):
    setattr(recovery, monkey_target, value)


def all_dead():
    """Monkeypatch the world to 'seat is fully dead, directory vacant'."""
    patch("tmux_session_alive_anywhere", lambda name: (False, ""))
    patch("seat_directory_occupied", lambda directory: (False, ""))


def capture_launches(workspace: Workspace):
    def fake_launch(name, seat_directory, extra_arguments, first_prompt_file=None):
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
                     "You are seat-a. No handoff exists yet; ask what to work on.")
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
                     "You are seat-a. No handoff exists yet; ask what to work on.")
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
          and workspace.launches[0][1] == "--resume-session-id 'crashed-session'",
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
