#!/usr/bin/env python3
"""Tests for scripts/worktree-owner-file-read-and-write.py.

Each case works in a scratch repository with a linked worktree, under a
scratch HOME, so the handoff-supervisor locks it reads are this suite's. A
running agent-session is a helper process this suite starts; a running
handoff-supervisor is a helper process running a file named
handoff-supervisor.py with --agent and the agent-seat's name, which is what
ps shows of a real one.

Run: python3 scripts/worktree-owner-file-read-and-write-test.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture)
_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).resolve().with_name("worktree-owner-file-read-and-write.py")

failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}: {detail}")
        failures.append(name)


def git(directory, *arguments):
    completed = subprocess.run(["git", "-C", str(directory), *arguments],
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def load_program():
    spec = importlib.util.spec_from_file_location("worktree_owner_file_read_and_write", PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def raised(call):
    try:
        call()
    except Exception as error:
        return error
    return None


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()
    home = scratch / "home"
    handoffs = home / ".claude" / "handoffs"
    handoffs.mkdir(parents=True)
    os.environ["HOME"] = str(home)
    checkout = scratch / "checkout"
    checkout.mkdir()
    git(checkout, "init", "-b", "main")
    git(checkout, "config", "user.email", "test@test.invalid")
    git(checkout, "config", "user.name", "worktree owner file test")
    (checkout / "README.md").write_text("# scratch\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-m", "seed")
    worktree = checkout / ".claude" / "worktrees" / "topic"
    git(checkout, "worktree", "add", "-b", "topic", str(worktree))
    module = load_program()

    # --- Writing and reading ---
    path = module.worktree_owner_file_write(worktree, module.OWNER_AGENT_SEAT, "seat-one")
    check("the owner file is written in the worktree's own git directory, under its name",
          path == Path(git(worktree, "rev-parse", "--absolute-git-dir")) / "worktree-owner.json",
          str(path))
    check("it holds the owner kind and the agent-seat, and reads back the same",
          json.loads(path.read_text()) == {"owner_kind": "agent-seat", "agent_seat": "seat-one"}
          and module.worktree_owner_file_read(worktree) == json.loads(path.read_text()),
          path.read_text())
    check("git status lists nothing, so the owner file never keeps a worktree as untracked work",
          git(worktree, "status", "--porcelain", "--untracked-files=all", "--ignored") == "")
    again = raised(lambda: module.worktree_owner_file_write(worktree, module.OWNER_AGENT_SEAT,
                                                             "seat-two"))
    check("a write never replaces an existing owner file",
          isinstance(again, module.WorktreeOwnerFileAlreadyExistsError)
          and "seat-one" in path.read_text(), repr(again))
    no_scratch_left = [name for name in os.listdir(path.parent) if name.startswith(".worktree-owner-")]
    check("a refused write leaves no scratch file beside the owner file", no_scratch_left == [],
          str(no_scratch_left))
    main_checkout = raised(lambda: module.worktree_owner_file_write(
        checkout, module.OWNER_AGENT_SEAT, "seat-one"))
    check("the reference-checkout gets no owner file",
          isinstance(main_checkout, module.WorktreeOwnerFileError)
          and "reference-checkout" in str(main_checkout), repr(main_checkout))
    for owner_kind, agent_seat, owner_key, why in (
            ("agent-seat", "", None, "an empty agent-seat name"),
            ("agent-seat", "two words", None, "an agent-seat name with a space"),
            ("agent-seat", "seat-one", "1-2-3", "an agent-seat with an owner key"),
            ("agent-session", "seat-one", None, "an agent-session without an owner key"),
            ("someone", "seat-one", None, "an owner kind that is neither")):
        error = raised(lambda: module.worktree_owner_file_record_validate_and_build(owner_kind, agent_seat, owner_key))
        check(f"an owner record with {why} is refused",
              isinstance(error, module.WorktreeOwnerFileError), repr(error))

    other = checkout / ".claude" / "worktrees" / "other"
    git(checkout, "worktree", "add", "-b", "other", str(other))
    check("a worktree with no owner file reads as None", module.worktree_owner_file_read(other) is None)
    other_owner_file = module.worktree_owner_file_path_find(other)
    for text, why in (("{not json", "is not JSON"),
                      ('["agent-seat"]', "does not hold an owner"),
                      ('{"owner_kind": "agent-seat", "agent_seat": "s", "extra": 1}',
                       "does not hold an owner"),
                      ('{"owner_kind": "agent-session", "agent_seat": "s"}', "neither")):
        other_owner_file.write_text(text)
        error = raised(lambda: module.worktree_owner_file_read(other))
        check(f"an owner file holding {text} cannot be read, and says it {why}",
              isinstance(error, module.WorktreeOwnerFileError) and why in str(error), repr(error))
    other_owner_file.unlink()
    other_owner_file.mkdir()
    error = raised(lambda: module.worktree_owner_file_read(other))
    check("an owner file that cannot be opened is reported, not read as missing",
          isinstance(error, module.WorktreeOwnerFileError) and "could not be read" in str(error),
          repr(error))
    other_owner_file.rmdir()
    gone = raised(lambda: module.worktree_owner_file_read(scratch / "not-a-worktree"))
    check("a directory git cannot name a git directory for is reported",
          isinstance(gone, module.WorktreeOwnerFileError)
          and "could not name its git directory" in str(gone), repr(gone))
    git_directory = module.worktree_owner_file_path_find(other).parent
    git_directory.chmod(0o500)
    try:
        unwritable = raised(lambda: module.worktree_owner_file_write(
            other, module.OWNER_AGENT_SEAT, "seat-one"))
    finally:
        git_directory.chmod(0o755)
    check("an owner file that cannot be written is reported",
          isinstance(unwritable, module.WorktreeOwnerFileError)
          and not isinstance(unwritable, module.WorktreeOwnerFileAlreadyExistsError)
          and "could not be written" in str(unwritable), repr(unwritable))

    # --- Claude Code's lock ---
    check("Claude Code's lock reason on a subagent's worktree names the dispatching process",
          module.claude_code_subagent_worktree_lock_reason_dispatching_process_id_parse(
              "claude agent agent-a59101f2afd522964 (pid 3052879 start 197651712)") == 3052879)
    for reason in ("", None, "test lock", "claude agent agent-x (pid 12)",
                   "claude agent agent-a1 (pid 12 start 3) and more"):
        check(f"no process is read from the lock reason {reason!r}",
              module.claude_code_subagent_worktree_lock_reason_dispatching_process_id_parse(reason) is None)
    check("an unlocked worktree has no lock reason", module.worktree_lock_reason_read(other) is None)
    git(checkout, "worktree", "lock", "--reason", "claude agent agent-a1 (pid 7 start 8)", str(other))
    check("a locked worktree's lock reason is read",
          module.worktree_lock_reason_read(other) == "claude agent agent-a1 (pid 7 start 8)")
    git(checkout, "worktree", "unlock", str(other))
    lock_file = module.worktree_owner_file_path_find(other).parent / "locked"
    lock_file.mkdir()
    unreadable_lock = raised(lambda: module.worktree_lock_reason_read(other))
    lock_file.rmdir()
    check("a lock file that cannot be read is reported, not read as no lock",
          isinstance(unreadable_lock, module.WorktreeOwnerFileError)
          and "could not be read" in str(unreadable_lock), repr(unreadable_lock))

    # --- Whether the owner runs ---
    session = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                               stdin=subprocess.PIPE)
    supervisor_script = scratch / "fake-supervisor" / "handoff-supervisor.py"
    supervisor_script.parent.mkdir()
    supervisor_script.write_text("import sys\nsys.stdin.read()\n")
    supervisor = subprocess.Popen([sys.executable, str(supervisor_script), "--agent", "seat-up"],
                                  stdin=subprocess.PIPE)
    try:
        snapshots = module.load_uncommitted_work_snapshots_module_once()
        running_key = snapshots.owner_key_of_process(session.pid)
        state, _ = module.worktree_owner_running_state(
            {"owner_kind": "agent-session", "agent_seat": "s", "owner_key": running_key})
        check("an agent-session whose claude process runs is running", state == module.RUNNING, state)
        state, explanation = module.worktree_owner_running_state(
            {"owner_kind": "agent-session", "agent_seat": "s", "owner_key": "malformed"})
        check("an agent-session whose owner key cannot be judged is unknown, never stopped",
              state == module.UNKNOWN and "could not be read" in explanation, explanation)
        (handoffs / "seat-up-supervisor.lock").write_text(f"{supervisor.pid}\n")
        state, _ = module.worktree_owner_running_state({"owner_kind": "agent-seat", "agent_seat": "seat-up"})
        check("an agent-seat whose handoff-supervisor runs is running", state == module.RUNNING, state)
        state, explanation = module.agent_seat_handoff_supervisor_running_state_check("seat-none", handoffs)
        check("an agent-seat with no handoff-supervisor lock has stopped",
              state == module.STOPPED and "no lock" in explanation, explanation)
        (handoffs / "seat-other-supervisor.lock").write_text(f"{session.pid}\n")
        state, _ = module.agent_seat_handoff_supervisor_running_state_check("seat-other", handoffs)
        check("an agent-seat whose lock names a process that is not its supervisor has stopped",
              state == module.STOPPED, state)
        (handoffs / "seat-garbled-supervisor.lock").write_text("not a number\n")
        state, explanation = module.agent_seat_handoff_supervisor_running_state_check("seat-garbled", handoffs)
        check("an agent-seat whose lock holds no process id is unknown",
              state == module.UNKNOWN and "not a process id" in explanation, explanation)
        (handoffs / "seat-unreadable-supervisor.lock").mkdir()
        state, explanation = module.agent_seat_handoff_supervisor_running_state_check("seat-unreadable", handoffs)
        check("an agent-seat whose lock cannot be read is unknown",
              state == module.UNKNOWN and "could not be read" in explanation, explanation)
    finally:
        for helper in (session, supervisor):
            helper.stdin.close()
            helper.wait(timeout=30)
    state, _ = module.worktree_owner_running_state(
        {"owner_kind": "agent-session", "agent_seat": "s", "owner_key": running_key})
    check("an agent-session whose claude process has ended has stopped", state == module.STOPPED, state)

    # --- The command line ---
    def run(*arguments, cwd=None, environment=None):
        return subprocess.run([sys.executable, str(PROGRAM), *arguments], capture_output=True,
                              text=True, check=False, cwd=cwd, env=environment)

    helped = run("--help")
    check("--help prints the usage and exits 0", helped.returncode == 0 and "Usage:" in helped.stdout)
    third = checkout / ".claude" / "worktrees" / "third"
    git(checkout, "worktree", "add", "-b", "third", str(third))
    written = run("write", "--agent-seat", "seat-three", cwd=third)
    check("write --agent-seat writes the owner file of the worktree holding the current directory",
          written.returncode == 0 and module.worktree_owner_file_read(third)
          == {"owner_kind": "agent-seat", "agent_seat": "seat-three"},
          written.stdout + written.stderr)
    shown = run("show", "--worktree", str(third))
    check("show prints the owner file and whether its owner runs",
          shown.returncode == 0 and '"agent_seat": "seat-three"' in shown.stdout
          and "stopped" in shown.stdout, shown.stdout + shown.stderr)
    refused = run("write", "--agent-seat", "seat-four", "--worktree", str(third))
    check("write exits 1 with FAILED when the worktree already has an owner file",
          refused.returncode == 1 and "FAILED" in refused.stderr and "already exists" in refused.stderr,
          refused.stderr)
    fourth = checkout / ".claude" / "worktrees" / "fourth"
    git(checkout, "worktree", "add", "-b", "fourth", str(fourth))
    # The suite itself may run under claude, so the walk up the parent processes is replaced.
    snapshots = module.load_uncommitted_work_snapshots_module_once()
    real_walk = snapshots.claude_owner_process_id
    environment_seat = os.environ.get("GIT_AUTHOR_NAME")
    os.environ["GIT_AUTHOR_NAME"] = "seat-four"
    try:
        snapshots.claude_owner_process_id = lambda start: None
        no_claude = module.main(["write", "--agent-session", "--worktree", str(fourth)])
        check("write --agent-session with no claude among its parent processes exits 1 and "
              "writes nothing", no_claude == 1 and module.worktree_owner_file_read(fourth) is None)
        snapshots.claude_owner_process_id = lambda start: os.getpid()
        with_claude = module.main(["write", "--agent-session", "--worktree", str(fourth)])
        check("write --agent-session names the claude process's agent-session and the agent-seat "
              "GIT_AUTHOR_NAME names",
              with_claude == 0 and module.worktree_owner_file_read(fourth)
              == {"owner_kind": "agent-session", "agent_seat": "seat-four",
                  "owner_key": snapshots.owner_key_of_process(os.getpid())})
    finally:
        snapshots.claude_owner_process_id = real_walk
        if environment_seat is None:
            os.environ.pop("GIT_AUTHOR_NAME", None)
        else:
            os.environ["GIT_AUTHOR_NAME"] = environment_seat
    outside = run("show", cwd=scratch)
    check("show outside any worktree exits 1 and says the directory is in no git worktree",
          outside.returncode == 1 and "is in no git worktree" in outside.stderr, outside.stderr)
    for arguments in ([], ["write"], ["write", "--agent-seat"], ["show", "extra"], ["--worktree"]):
        bad = run(*arguments)
        check(f"the invocation {arguments} exits 2", bad.returncode == 2, bad.stderr)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
