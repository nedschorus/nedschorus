#!/usr/bin/env python3
"""Tests for work-snapshots: the hook, the shared module, the cleaner's step,
and the handoff-supervisor's first-prompt list.

Design: nc-systems/handoff/uncommitted-work-snapshots-across-crashes-design.md;
each section below is one bullet of its "How it will be tested".

Every case works in a scratch clone with the programs copied into it, so the
hook's own clone, and every ref written, is the scratch clone's. Git reads a
scratch global config and no system config.

The hook finds its owner by walking up to a process named claude. The suite
stands one in with a copy of a shell binary named `claude`, which both Linux
and macOS name after the copied file; the cases that run the hook under it
print SKIP, with the names observed, only where no such copy is named claude.
No case sends a signal: the stand-in ends when its stdin closes.

Run: python3 nc-systems/handoff/tests/uncommitted-work-snapshots-test.py
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import threading
import time
from pathlib import Path

SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = SYSTEM_DIRECTORY.parent.parent

_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture)
_fixture.remove_git_redirecting_environment_variables_from_this_process()

MODULE_RELATIVE = Path("nc-systems/handoff/uncommitted-work-snapshots.py")
HOOK_RELATIVE = Path("scripts/uncommitted-work-snapshot-hook.py")
CLEANER_RELATIVE = Path("scripts/clean-worktrees.py")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


snapshots = load(REPOSITORY_ROOT / MODULE_RELATIVE, "uncommitted_work_snapshots")

failures = []
SKIPPED = []


def check(condition, name, detail=""):
    if condition:
        print(f"ok   {name}")
    else:
        print(f"FAIL {name}" + (f": {detail}" if detail else ""))
        failures.append(name)


def skip(name, reason):
    print(f"SKIP {name}: {reason}")
    SKIPPED.append(name)


def git(directory, *arguments, check_exit=True, input_text=None, environment=None):
    result = subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True,
                            text=True, input=input_text, env=environment)
    if check_exit and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} in {directory}: {result.stderr}")
    return result.stdout.strip()


SCRATCH = Path(tempfile.mkdtemp(prefix="uncommitted-work-snapshots-test-"))
HOME = SCRATCH / "home"
HOME.mkdir()
GLOBAL_EXCLUDES = SCRATCH / "global-excludes"
GLOBAL_EXCLUDES.write_text("*.globally-ignored\n")
GLOBAL_CONFIG = SCRATCH / "gitconfig"
GLOBAL_CONFIG.write_text(
    "[user]\n\tname = work-snapshot test\n\temail = test@nedschorus.invalid\n"
    f"[core]\n\texcludesFile = {GLOBAL_EXCLUDES}\n"
    "[init]\n\tdefaultBranch = main\n[advice]\n\tdetachedHead = false\n")
os.environ.update(HOME=str(HOME), GIT_CONFIG_GLOBAL=str(GLOBAL_CONFIG), GIT_CONFIG_NOSYSTEM="1")
os.environ.pop("GIT_AUTHOR_NAME", None)

# The stand-in for claude is a copy of a shell binary named claude: both Linux
# (/proc/<pid>/comm) and macOS ps name a process after the file it executes, so
# a shell script named claude would be named after its interpreter on macOS.
CLAUDE_STAND_IN = SCRATCH / "bin" / "claude"
CLAUDE_STAND_IN.parent.mkdir()
CLAUDE_STAND_IN_SCRIPT = (
    'echo stand-in-ready\n'
    'while read hook_input; do\n'
    '  "$@" < "$hook_input"\n'
    '  echo "hook-done $?"\n'
    'done\n')


def find_claude_stand_in():
    """Copy a shell to CLAUDE_STAND_IN; return None if it is named claude, else why not."""
    observed = []
    candidates = []
    for found in (shutil.which("bash"), "/bin/bash", shutil.which("sh"), "/bin/sh"):
        if found and os.path.exists(found) and os.path.realpath(found) not in candidates:
            candidates.append(os.path.realpath(found))
    for candidate in candidates:
        try:
            shutil.copy2(candidate, CLAUDE_STAND_IN)
            CLAUDE_STAND_IN.chmod(0o755)
            probe = subprocess.Popen([str(CLAUDE_STAND_IN), "-c", "echo ready; read x"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        except OSError as error:
            observed.append(f"{candidate}: {error}")
            continue
        try:
            probe.stdout.readline()
            name = snapshots.process_command_name_and_parent(probe.pid)[0]
        except (OSError, snapshots.WorkSnapshotError) as error:
            name = f"unreadable ({error})"
        probe.stdin.close()
        probe.wait(timeout=30)
        probe.stdout.close()
        if name == snapshots.OWNER_PROCESS_COMMAND_NAME:
            return None
        observed.append(f"a copy of {candidate} is named {name!r}")
    return "; ".join(observed) or "no shell binary found"


CLAUDE_STAND_IN_PROBLEM = find_claude_stand_in()
CLAUDE_STAND_IN_WORKS = CLAUDE_STAND_IN_PROBLEM is None


def stand_in_skip_reason():
    return f"no claude stand-in that this platform names claude: {CLAUDE_STAND_IN_PROBLEM}"


def dead_process_id():
    """The id of a process that has exited and been reaped, so no process has it."""
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    try:
        os.kill(gone.pid, 0)
    except ProcessLookupError:
        return gone.pid
    raise RuntimeError(f"process id {gone.pid} was reused at once; run the suite again")


def dead_owner_key(linux_process_id):
    """An owner key of the running platform's form naming no live process."""
    if sys.platform.startswith("linux"):
        # A boot id that is not this boot's.
        return "0" * 32 + f"-{linux_process_id}-1"
    return f"{dead_process_id()}-1"


clone_count = [0]


def new_clone():
    """A scratch clone holding the programs, with origin/main, and its main checkout."""
    clone_count[0] += 1
    base = SCRATCH / f"clone-{clone_count[0]}"
    origin = base / "origin.git"
    git(SCRATCH, "init", "-q", "--bare", str(origin))
    main = base / "main"
    git(SCRATCH, "clone", "-q", str(origin), str(main))
    for relative in (MODULE_RELATIVE, HOOK_RELATIVE, CLEANER_RELATIVE):
        (main / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPOSITORY_ROOT / relative, main / relative)
    (main / "tracked.txt").write_text("one\n")
    (main / "doomed.txt").write_text("to be deleted\n")
    (main / ".gitignore").write_text("*.ignored\n.claude/worktrees/\n")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "base")
    git(main, "push", "-q", "origin", "main")
    return main


def add_worktree(main, path, branch):
    git(main, "worktree", "add", "-q", "-b", branch, str(path), "origin/main")
    return Path(path).resolve()


class ClaudeStandIn:
    """A process named claude that runs the clone's hook once per run_hook call."""

    started = 0

    def __init__(self, main, environment=None):
        self.main = main
        ClaudeStandIn.started += 1
        self.inputs = SCRATCH / f"hook-inputs-{ClaudeStandIn.started}"
        self.inputs.mkdir()
        self.count = 0
        self.last_exit = None
        self.process = subprocess.Popen(
            [str(CLAUDE_STAND_IN), "-c", CLAUDE_STAND_IN_SCRIPT, "claude", sys.executable,
             str(main / HOOK_RELATIVE)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            env=dict(os.environ, **(environment or {})))
        # Read only after the exec, so the owner key names the stand-in, not this process.
        self.process.stdout.readline()
        self.owner_key = snapshots.owner_key_of_process(self.process.pid)

    def run_hook(self, payload):
        self.count += 1
        path = self.inputs / f"{self.count}.json"
        path.write_text(json.dumps(payload))
        self.process.stdin.write(f"{path}\n")
        self.process.stdin.flush()
        output = []
        while True:
            line = self.process.stdout.readline()
            if line.startswith("hook-done"):
                self.last_exit = int(line.split()[1])
                break
            if not line:
                break
            output.append(line)
        text = "".join(output).strip()
        return json.loads(text)["hookSpecificOutput"]["additionalContext"] if text else None

    def end(self):
        self.process.stdin.close()
        self.process.wait(timeout=30)
        self.process.stdout.close()


def refs_of(main, owner_key=None):
    prefix = snapshots.WORK_SNAPSHOT_REF_PREFIX + (f"{owner_key}/" if owner_key else "")
    return git(main, "for-each-ref", "--format=%(refname)", prefix).split()


def files_in_snapshot(main, ref):
    return sorted(git(main, "ls-tree", "-r", "--name-only", ref).split())


def bash(cwd):
    return {"tool_name": "Bash", "cwd": str(cwd), "tool_input": {"command": "true"},
            "transcript_path": str(SCRATCH / "transcript.jsonl")}


def edit(path):
    return {"tool_name": "Edit", "cwd": str(path.parent),
            "tool_input": {"file_path": str(path)},
            "transcript_path": str(SCRATCH / "transcript.jsonl")}


# ---------------------------------------------------------------- the hook


def test_what_a_work_snapshot_holds():
    name = "a work-snapshot holds modified, deleted and new files, not ignored ones"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, stand_in_skip_reason())
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    (worktree / "tracked.txt").write_text("two\n")
    (worktree / "doomed.txt").unlink()
    (worktree / "new.txt").write_text("new\n")
    (worktree / "a.ignored").write_text("x\n")
    (worktree / "b.globally-ignored").write_text("x\n")
    exclude = Path(git(worktree, "rev-parse", "--path-format=absolute", "--git-path",
                       "info/exclude"))
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("c.locally-excluded\n")
    (worktree / "c.locally-excluded").write_text("x\n")
    index = Path(git(worktree, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    index_before = index.read_bytes()
    head_before = git(worktree, "rev-parse", "HEAD")
    claude = ClaudeStandIn(main, {"GIT_AUTHOR_NAME": "seat-one"})
    message = claude.run_hook(edit(worktree / "tracked.txt"))
    check(message is None, "the hook says nothing when the work-snapshot is written", message)
    refs = refs_of(main, claude.owner_key)
    check(len(refs) == 1, "one work-snapshot ref for the worktree", refs)
    if refs:
        held = files_in_snapshot(main, refs[0])
        check("new.txt" in held and "doomed.txt" not in held
              and git(main, "show", f"{refs[0]}:tracked.txt") == "two",
              name, held)
        check(not any(path.endswith(("ignored", "excluded")) for path in held),
              "ignored, locally excluded and globally excluded files are not held", held)
        trailers = snapshots.all_work_snapshots(main)[0]
        check(trailers["agent_seat"] == "seat-one" and trailers["branch"] == "fork-branch"
              and trailers["worktree"] == str(worktree)
              and trailers["transcript"] == str(SCRATCH / "transcript.jsonl"),
              "the trailers name the agent-seat, branch, worktree and transcript", trailers)
        check(git(main, "rev-parse", f"{refs[0]}^") == head_before,
              "the work-snapshot's parent is the worktree's HEAD")
    check(index.read_bytes() == index_before, "the worktree's index is unchanged")
    check(git(worktree, "rev-parse", "HEAD") == head_before
          and git(worktree, "symbolic-ref", "--short", "HEAD") == "fork-branch",
          "the worktree's HEAD and branch are unchanged")
    claude.end()


def test_same_size_edit_in_the_index_second():
    name = ("a same-size edit made in the second the index was written is held when the "
            "work-snapshot is built a second later")
    main = new_clone()
    for attempt in range(20):
        worktree = add_worktree(main, main / ".claude" / "worktrees" / f"racy-{attempt}",
                                f"racy-{attempt}")
        (worktree / "tracked.txt").write_text("two\n")
        index = Path(git(worktree, "rev-parse", "--path-format=absolute", "--git-path", "index"))
        if int(os.stat(worktree / "tracked.txt").st_mtime) == int(os.stat(index).st_mtime):
            break
    else:
        return skip(name, "no edit landed in the index's second in 20 tries")
    # A copy of the index made in a later second, with a fresh mtime, would make git trust the
    # entry's stat data, which this same-size, same-second edit leaves unchanged.
    time.sleep(1.05)
    snapshots.refresh_work_snapshot(worktree, "3-3", "seat", "")
    ref = snapshots.work_snapshot_ref("3-3", worktree)
    check(git(main, "show", f"{ref}:tracked.txt") == "two", name)


def test_ref_names():
    name = "two worktrees with the same directory name get different refs; a space is legal"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, stand_in_skip_reason())
    main = new_clone()
    first = add_worktree(main, main / ".claude" / "worktrees" / "a" / "same", "a-branch")
    second = add_worktree(main, main / ".claude" / "worktrees" / "b" / "same", "b-branch")
    spaced = add_worktree(main, main / ".claude" / "worktrees" / "with space", "spaced")
    for worktree in (first, second, spaced):
        (worktree / "tracked.txt").write_text("changed\n")
    claude = ClaudeStandIn(main)
    for worktree in (first, second, spaced):
        message = claude.run_hook(edit(worktree / "tracked.txt"))
        check(message is None, f"the hook wrote a work-snapshot for {worktree.name!r}", message)
    refs = refs_of(main, claude.owner_key)
    check(len(set(refs)) == 3, name, refs)
    claude.end()


def test_bash_commit_deletes_and_other_worktrees_follow():
    name = "a Bash call that commits everything deletes the ref"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, stand_in_skip_reason())
    main = new_clone()
    fork = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    other = add_worktree(main, main / ".claude" / "worktrees" / "other", "other-branch")
    claude = ClaudeStandIn(main)
    (fork / "new.txt").write_text("work\n")
    claude.run_hook(bash(fork))
    fork_ref = snapshots.work_snapshot_ref(claude.owner_key, fork)
    check(fork_ref in refs_of(main), "a Bash call whose cwd is a fork's worktree handles it")
    (other / "tracked.txt").write_text("first\n")
    claude.run_hook(edit(other / "tracked.txt"))
    other_ref = snapshots.work_snapshot_ref(claude.owner_key, other)
    (other / "tracked.txt").write_text("second\n")
    claude.run_hook(bash(fork))
    check(git(main, "show", f"{other_ref}:tracked.txt") == "second",
          "a Bash call elsewhere refreshes a worktree that already has this owner's "
          "work-snapshot")
    git(fork, "add", "-A")
    git(fork, "commit", "-q", "-m", "work")
    claude.run_hook(bash(fork))
    check(fork_ref not in refs_of(main), name, refs_of(main))
    claude.end()


def test_overlapping_runs_end_on_the_final_state():
    name = "overlapping runs leave the ref on a work-snapshot of the final state"
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    (worktree / "tracked.txt").write_text("first\n")
    owner = "1-1"
    ref = snapshots.work_snapshot_ref(owner, worktree)
    real_build = snapshots.build_work_snapshot_commit
    interleaved = []

    def build_while_another_run_lands(*arguments):
        commit = real_build(*arguments)
        if not interleaved:
            interleaved.append(True)
            (worktree / "tracked.txt").write_text("final\n")
            other = real_build(*arguments)
            git(main, "update-ref", ref, other)
        return commit

    snapshots.build_work_snapshot_commit = build_while_another_run_lands
    try:
        snapshots.refresh_work_snapshot(worktree, owner, "seat", "")
    finally:
        snapshots.build_work_snapshot_commit = real_build
    check(git(main, "show", f"{ref}:tracked.txt") == "final", name)
    threads = [threading.Thread(target=snapshots.refresh_work_snapshot,
                                args=(worktree, owner, "seat", "")) for _ in range(2)]
    (worktree / "tracked.txt").write_text("last\n")
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    check(git(main, "show", f"{ref}:tracked.txt") == "last",
          "two concurrent runs end on the worktree's state")


def test_operation_trailer():
    name = "during a merge with conflicts the operation trailer is merge"
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    (worktree / "tracked.txt").write_text("fork side\n")
    git(worktree, "commit", "-q", "-am", "fork side")
    git(main, "checkout", "-q", "-b", "other")
    (main / "tracked.txt").write_text("other side\n")
    git(main, "commit", "-q", "-am", "other side")
    git(worktree, "merge", "-q", "other", check_exit=False)
    snapshots.refresh_work_snapshot(worktree, "2-2", "seat", "")
    found = [s for s in snapshots.all_work_snapshots(main) if s["owner_key"] == "2-2"]
    check(found and found[0]["operation"] == "merge", name, found)


def test_hook_failure_is_reported():
    name = "a hook that cannot write reports it through additionalContext and exits 0"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, stand_in_skip_reason())
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    (worktree / "tracked.txt").write_text("changed\n")
    claude = ClaudeStandIn(main)
    ref = snapshots.work_snapshot_ref(claude.owner_key, worktree)
    lock = Path(git(main, "rev-parse", "--path-format=absolute", "--git-common-dir")) / (
        ref + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("")
    message = claude.run_hook(edit(worktree / "tracked.txt"))
    check(message is not None and str(worktree) in message and "no work-snapshot" in message,
          name, message)
    check(claude.last_exit == 0, "the hook exits 0 when it reports a failure",
          claude.last_exit)
    check(claude.process.poll() is None, "the stand-in claude carried on after the failure")
    claude.end()
    hook = load(main / HOOK_RELATIVE, "hook_without_claude")
    hook.snapshots = hook.load_snapshots_module()
    hook.snapshots.claude_owner_process_id = lambda start: None
    messages = hook.run(edit(worktree / "tracked.txt"), os.getpid())
    check(len(messages) == 1 and "no process named claude" in messages[0]
          and str(worktree) in messages[0],
          "with no claude among its parents the hook tells the agent, naming the worktree",
          messages)
    (worktree / "tracked.txt").write_text("one\n")
    check(hook.run(edit(worktree / "tracked.txt"), os.getpid()) == [],
          "with no claude parent and nothing uncommitted the hook says nothing")


def test_other_repository_is_untouched():
    name = "an edit or a Bash call in another repository writes no work-snapshot there"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, stand_in_skip_reason())
    main = new_clone()
    other = SCRATCH / f"unrelated-repository-{clone_count[0]}"
    git(SCRATCH, "init", "-q", str(other))
    (other / "file.txt").write_text("one\n")
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "base")
    (other / "file.txt").write_text("two\n")
    claude = ClaudeStandIn(main)
    message = claude.run_hook(edit(other / "file.txt"))
    claude.run_hook(bash(other))
    claude.end()
    other_refs = git(other, "for-each-ref", "--format=%(refname)",
                     snapshots.WORK_SNAPSHOT_REF_PREFIX).split()
    check(other_refs == [] and refs_of(main) == [] and message is None, name,
          (other_refs, refs_of(main), message))


def test_worktree_discovery_failure_is_reported():
    name = "a worktree that git fails to find, for a reason other than no repository, is reported"
    main = new_clone()
    bare = SCRATCH / f"bare-{clone_count[0]}.git"
    git(SCRATCH, "init", "-q", "--bare", str(bare))
    try:
        snapshots.worktree_containing(bare)
        raised = False
    except snapshots.WorkSnapshotError:
        raised = True
    check(raised, "worktree_containing raises when git fails inside a repository")
    outside = SCRATCH / "outside-every-repository"
    outside.mkdir(exist_ok=True)
    check(snapshots.worktree_containing(outside) is None,
          "worktree_containing gives None outside any repository")
    hook = load(main / HOOK_RELATIVE, "hook_discovery_failure")
    hook.snapshots = hook.load_snapshots_module()
    worktrees, messages = hook.candidate_worktrees(edit(bare / "config"), None)
    check(worktrees == [] and len(messages) == 1 and str(bare) in messages[0]
          and "could not be found" in messages[0], name, (worktrees, messages))


def test_module_load_failure_is_reported():
    name = "a module that cannot be loaded is reported through additionalContext, exit 0"
    main = new_clone()
    (main / MODULE_RELATIVE).write_text("this is not python (\n")
    result = subprocess.run([sys.executable, str(main / HOOK_RELATIVE)],
                            input=json.dumps(edit(main / "tracked.txt")),
                            capture_output=True, text=True)
    try:
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError):
        context = ""
    check(result.returncode == 0 and "could not be loaded" in context
          and "no work-snapshot" in context, name,
          (result.returncode, result.stdout, result.stderr))


class FakePs:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def test_macos_ps_failure_is_not_a_dead_owner():
    real_run_ps, real_process_exists = snapshots.run_ps, snapshots.process_exists
    try:
        # A gone process is decided before ps runs: macOS ps exits 1 for an id no
        # process has, sometimes with a message, which must not raise.
        snapshots.process_exists = lambda process_id: False
        for fake, why in ((FakePs(1, stderr="ps: process id too large: 999999\n"),
                           "with \"process id too large\""),
                          (FakePs(1), "with no output")):
            snapshots.run_ps = lambda arguments, fake=fake: fake
            try:
                started = snapshots.macos_start_seconds(100)
                outcome = f"returned {started}"
                alive = snapshots.owner_process_is_alive("100-5", platform="darwin")
            except snapshots.WorkSnapshotError as error:
                outcome, alive = f"raised {error}", None
            check(outcome == "returned None" and alive is False,
                  f"a process id no process has counts as gone, whatever ps says ({why})",
                  outcome)
        # The process exits between the check and ps: exit 1 with no output, and
        # the check now says gone.
        answers = iter((True, False))
        snapshots.process_exists = lambda process_id: next(answers)
        snapshots.run_ps = lambda arguments: FakePs(1)
        check(snapshots.macos_start_seconds(100) is None,
              "a process that exits just before ps reads it counts as gone")
        # A process that exists: every ps failure raises.
        snapshots.process_exists = lambda process_id: True
        for fake, why in ((FakePs(1), "exit 1 with no output"),
                          (FakePs(-9), "killed by a signal"),
                          (FakePs(1, stderr="ps: illegal option"), "an error message"),
                          (FakePs(2), "another exit code")):
            snapshots.run_ps = lambda arguments, fake=fake: fake
            try:
                alive = snapshots.owner_process_is_alive("100-5", platform="darwin")
                outcome = f"returned {alive}"
            except snapshots.WorkSnapshotError:
                outcome = "raised"
            check(outcome == "raised",
                  f"a ps failure for a live process ({why}) raises instead of counting "
                  "the owner dead", outcome)
    finally:
        snapshots.run_ps, snapshots.process_exists = real_run_ps, real_process_exists
    dead = dead_process_id()
    check(not snapshots.process_exists(dead) and snapshots.process_exists(os.getpid()),
          "process_exists tells a reaped process from this one")
    # A process of another user refuses the signal: it exists all the same. Only
    # the module's name for os is replaced, so the real os.kill is never touched.
    def refuse(process_id, signal_number):
        raise PermissionError(1, "Operation not permitted")
    real_os = snapshots.os
    snapshots.os = types.SimpleNamespace(kill=refuse)
    try:
        exists = snapshots.process_exists(dead)
    finally:
        snapshots.os = real_os
    check(exists, "a process that refuses the signal exists")
    if shutil.which("ps") is None:
        return skip("ps on this machine reads a live and a gone process", "no ps here")
    check(snapshots.macos_start_seconds(os.getpid()) is not None,
          "ps on this machine gives a live process's start")
    check(snapshots.macos_start_seconds(dead) is None,
          "ps on this machine gives None for a process that is gone")


# ---------------------------------------------------------------- owners


def fake_proc(root, boot_id, processes, btime="1000"):
    """processes: pid -> (name, parent, start ticks)."""
    (root / "sys" / "kernel" / "random").mkdir(parents=True, exist_ok=True)
    (root / "sys" / "kernel" / "random" / "boot_id").write_text(boot_id + "\n")
    (root / "stat").write_text(f"cpu 1 2 3\nbtime {btime}\n")
    for pid, (name, parent, ticks) in processes.items():
        directory = root / str(pid)
        directory.mkdir(exist_ok=True)
        (directory / "comm").write_text(name + "\n")
        fields = ["S", str(parent)] + ["0"] * 17 + [str(ticks)] + ["0"] * 10
        (directory / "stat").write_text(f"{pid} ({name} with (spaces)) " + " ".join(fields))


def test_owner_liveness():
    root = SCRATCH / "fake-proc"
    boot = "1234abcd-0000-0000-0000-000000000000"
    fake_proc(root, boot, {300: ("python3", 200, 50), 200: ("sh", 100, 40),
                           100: ("claude", 1, 30)})
    linux = "linux"
    check(snapshots.claude_owner_process_id(300, str(root), linux) == 100,
          "the owner is the nearest ancestor named claude")
    key = snapshots.owner_key_of_process(100, str(root), linux)
    check(key == "1234abcd000000000000000000000000-100-30",
          "a Linux owner key is boot id, process id and start ticks", key)
    check(snapshots.owner_process_is_alive(key, str(root), linux),
          "an owner process still running is alive")
    fake_proc(root, boot, {}, btime="999999")
    check(snapshots.owner_process_is_alive(key, str(root), linux),
          "a live owner still counts as alive after the system clock is stepped")
    fake_proc(root, boot, {100: ("claude", 1, 31)})
    check(not snapshots.owner_process_is_alive(key, str(root), linux),
          "a reused process id with a different start counts as dead")
    fake_proc(root, "ffff" + boot[4:], {100: ("claude", 1, 30)})
    check(not snapshots.owner_process_is_alive(key, str(root), linux),
          "an owner from an earlier boot counts as dead")
    shutil.rmtree(root / "100")
    check(not snapshots.owner_process_is_alive(key, str(root), linux),
          "an owner process that is gone counts as dead")
    root2 = SCRATCH / "fake-proc-no-claude"
    fake_proc(root2, boot, {300: ("python3", 200, 50), 200: ("bash", 1, 40)})
    check(snapshots.claude_owner_process_id(300, str(root2), linux) is None,
          "no claude among the ancestors gives no owner")


def test_live_and_dead_owners_listed():
    name = ("a dead owner's work-snapshot is listed when its worktree is gone or changed, "
            "not while the worktree still holds its changes")
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, stand_in_skip_reason())
    main = new_clone()
    kept = add_worktree(main, main / ".claude" / "worktrees" / "kept", "kept-branch")
    removed = add_worktree(main, main / ".claude" / "worktrees" / "removed", "removed-branch")
    changed = add_worktree(main, main / ".claude" / "worktrees" / "changed", "changed-branch")
    for worktree in (kept, removed, changed):
        (worktree / "new.txt").write_text("work\n")
    claude = ClaudeStandIn(main, {"GIT_AUTHOR_NAME": "seat-two"})
    for worktree in (kept, removed, changed):
        claude.run_hook(bash(worktree))
    handoffs = SCRATCH / "handoffs-listing"
    handoffs.mkdir()
    check(snapshots.first_prompt_text(main, "seat-two", handoffs) == "",
          "a live owner's work-snapshots are not listed")
    claude.end()
    check(snapshots.first_prompt_text(main, "seat-two", handoffs) == "",
          "a dead owner's work-snapshots are not listed while their worktrees still hold "
          "their changes, as after a session-handoff")
    git(main, "worktree", "remove", "--force", str(removed))
    (changed / "new.txt").write_text("changed with no hook to see it\n")
    text = snapshots.first_prompt_text(main, "seat-two", handoffs)
    check(str(removed) in text and "(is gone)" in text and str(changed) in text
          and str(kept) not in text, name, text)
    check(snapshots.first_prompt_text(main, "another-seat", handoffs) == "",
          "another agent-seat's leftovers are not listed")


# ---------------------------------------------------------------- listing


def test_list_caps_and_failure():
    main = new_clone()
    for number in range(21):
        worktree = add_worktree(main, main / ".claude" / "worktrees" / f"many-{number}",
                                f"many-{number}")
        for file_number in range(12):
            (worktree / f"file-{file_number:02d}.txt").write_text("x\n")
        snapshots.refresh_work_snapshot(worktree, f"{number + 10}-1", "seat-three", "")
        git(main, "worktree", "remove", "--force", str(worktree))
    handoffs = SCRATCH / "handoffs-caps"
    handoffs.mkdir()
    text = snapshots.first_prompt_text(main, "seat-three", handoffs, now=1000,
                                       is_alive=lambda key: False)
    entries = [line for line in text.splitlines() if line.startswith("- refs/")]
    check(len(entries) == 20, "the list caps at 20 entries", len(entries))
    check("and 1 more; list them all with:" in text and "list --agent-seat seat-three" in text,
          "the rest are counted, with the command that lists them all")
    check(entries and entries[0].endswith("and 2 more"), "each entry names ten files and "
          "counts the rest", entries[:1])
    recorded = json.loads((handoffs / "seat-three-work-snapshots-first-listed.json").read_text())
    check(len(recorded) == 21 and set(recorded.values()) == {1000},
          "every listed work-snapshot's first listing is recorded", recorded)
    snapshots.first_prompt_text(main, "seat-three", handoffs, now=5000,
                                is_alive=lambda key: False)
    recorded = json.loads((handoffs / "seat-three-work-snapshots-first-listed.json").read_text())
    check(set(recorded.values()) == {1000}, "a later listing keeps the first listing's time")
    not_a_repository = SCRATCH / "not-a-repository"
    not_a_repository.mkdir()
    check(snapshots.first_prompt_text(not_a_repository, "seat-three", handoffs) == "",
          "a working directory outside any clone has no work-snapshots to list")

    def liveness_that_fails(key):
        raise snapshots.WorkSnapshotError("ps could not read process 10")

    failed = snapshots.first_prompt_text(main, "seat-three", handoffs,
                                         is_alive=liveness_that_fails)
    check("could not be listed" in failed and "list --agent-seat seat-three" in failed,
          "a failure to build the list is stated, with the list command", failed)
    blocked = SCRATCH / "handoffs-blocked"
    blocked.write_text("a file where the handoff directory should be")
    text = snapshots.first_prompt_text(main, "seat-three", blocked, is_alive=lambda key: False)
    check("could not be recorded" in text and "never listed" in text,
          "a failure to record the first listing is said in the prompt", text[-300:])


def test_supervisor_appends_the_list():
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    (worktree / "new.txt").write_text("work\n")
    snapshots.refresh_work_snapshot(worktree, "1-1", "seat-four", "")
    git(main, "worktree", "remove", "--force", str(worktree))
    fixture = load(SYSTEM_DIRECTORY / "tests" / "handoff-supervisor-test-fixture.py",
                   "handoff_supervisor_test_fixture")
    supervisor = fixture.supervisor
    supervisor.uncommitted_work_snapshots.owner_process_is_alive = (
        lambda key, *rest, **keywords: False)
    handoffs = SCRATCH / "handoffs-supervisor"
    handoffs.mkdir()
    text = supervisor.uncommitted_work_snapshot_text("seat-four", main, handoffs)
    check(text.startswith("Leftover work-snapshots: 1") and "Handle each of them" in text,
          "the handoff-supervisor builds the leftover list with the restore steps", text[:200])
    launched = []
    supervisor.launch_agent_session = (
        lambda command, session_id, working_directory, prompt, **keywords:
        launched.append(prompt) or (_ for _ in ()).throw(StopIteration()))
    supervisor.sync_working_branch_with_main = lambda working_directory: "branch sync: test"
    settings = supervisor.SupervisorSettings(
        agent="seat-four", working_directory=main, handoff_directory=handoffs,
        agent_command="claude", first_prompt="Founding prompt.",
        first_prompt_wins_over_crashed_transcript=True, agent_update_timeout_seconds=0)
    try:
        supervisor.supervise_sessions(settings)
    except StopIteration:
        pass
    check(launched and launched[0].startswith("Founding prompt.\n\nLeftover work-snapshots: 1"),
          "every launch's prompt carries the leftover list after the prompt",
          launched[:1] and launched[0][:120])


# ---------------------------------------------------------------- restore


def restore_steps_commit(main, ref, keep):
    """Follow the restore steps' commands; return the new worktree holding the commit."""
    name = "restored-" + "-".join(ref.split("/")[-2:])
    clone = Path(git(main, "rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    target = clone / ".claude" / "worktrees" / name
    git(main, "worktree", "add", "-q", "-b", name, str(target), f"{ref}^")
    diff = subprocess.run(["git", "-C", str(target), "diff", "--binary", f"{ref}^", ref, "--",
                           *keep], capture_output=True, check=True).stdout
    subprocess.run(["git", "-C", str(target), "apply", "--index"], input=diff, check=True)
    git(target, "commit", "-q", "-m", f"Restore work from {ref}")
    return target


def test_restore_a_subset():
    for worktree_survives in (False, True):
        where = ("into a new worktree, the changed original left alone" if worktree_survives
                 else "into a new worktree from <ref>^")
        into_new = worktree_survives
        main = new_clone()
        worktree = add_worktree(main, main / ".claude" / "worktrees" / f"fork-{into_new}",
                                f"fork-{into_new}")
        (worktree / "tracked.txt").write_text("kept change\n")
        (worktree / "doomed.txt").unlink()
        (worktree / "new.txt").write_text("kept new\n")
        (worktree / "mutant.txt").write_text("a mutant to drop\n")
        snapshots.refresh_work_snapshot(worktree, "7-7", "seat-five", "")
        ref = snapshots.work_snapshot_ref("7-7", worktree)
        if worktree_survives:
            (worktree / "new.txt").write_text("changed since\n")
        else:
            git(main, "worktree", "remove", "--force", str(worktree))
        target = restore_steps_commit(main, ref, ["tracked.txt", "doomed.txt", "new.txt"])
        changed = git(target, "diff-tree", "-r", "--no-commit-id", "--name-status",
                      "HEAD").splitlines()
        check(sorted(changed) == ["A\tnew.txt", "D\tdoomed.txt", "M\ttracked.txt"],
              f"restoring a chosen subset {where} commits exactly those changes", changed)
        check(git(target, "status", "--porcelain") == "",
              f"nothing dropped is left behind {where}")
        if worktree_survives:
            check((worktree / "new.txt").read_text() == "changed since\n",
                  "the changed original worktree is left alone")
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "drift", "drift")
    (worktree / "new.txt").write_text("work\n")
    snapshots.refresh_work_snapshot(worktree, "8-8", "seat", "")
    ref = snapshots.work_snapshot_ref("8-8", worktree)
    snapshot = next(s for s in snapshots.all_work_snapshots(main) if s["ref"] == ref)
    check(snapshots.snapshot_matches_worktree(main, snapshot),
          "an unchanged worktree matches its work-snapshot")
    (worktree / "new.txt").write_text("changed since\n")
    check(not snapshots.snapshot_matches_worktree(main, snapshot),
          "a worktree changed since no longer matches")
    (worktree / "new.txt").write_text("work\n")
    git(worktree, "add", "-A")
    git(worktree, "commit", "-q", "-m", "the same changes, committed")
    check(not snapshots.snapshot_matches_worktree(main, snapshot),
          "a worktree whose HEAD moved no longer matches, though the tree is the same")


# ---------------------------------------------------------------- cleaner


def test_cleaner():
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    owners = {"old": "11-1", "recent": "12-1", "never": "13-1", "alive": "14-1"}
    refs = {}
    for label, owner in owners.items():
        # Different content each time, so none duplicates another.
        (worktree / "new.txt").write_text(f"work, version {label}\n")
        refs[label] = snapshot_at(worktree, owner, 1000, "seat-six")
    git(main, "worktree", "remove", "--force", str(worktree))
    now = 100 * 86400
    handoffs = SCRATCH / "handoffs-cleaner"
    handoffs.mkdir()
    (handoffs / "seat-six-work-snapshots-first-listed.json").write_text(json.dumps({
        refs["old"]: now - 11 * 86400, refs["recent"]: now - 5 * 86400,
        refs["alive"]: now - 30 * 86400}))
    alive = lambda key: key == owners["alive"]
    report = []
    failures_seen = snapshots.clean_leftover_work_snapshots(
        main, remove=False, only_due=False, handoff_directory=handoffs, now=now,
        is_alive=alive, out=report.append)
    check(failures_seen == 0 and set(refs_of(main)) == set(refs.values()),
          "run without --remove it deletes nothing", report)
    check(any(refs["old"] in line and "due for deletion" in line for line in report)
          and any(refs["never"] in line and "never listed" in line for line in report),
          "it reports leftovers with whether and when they were listed", report)
    check(not any(refs["alive"] in line for line in report),
          "a live owner's work-snapshot is not reported", report)
    report = []
    snapshots.clean_leftover_work_snapshots(
        main, remove=True, only_due=False, handoff_directory=handoffs, now=now,
        is_alive=alive, out=report.append)
    left = set(refs_of(main))
    check(refs["old"] not in left and any(refs["old"] in line and "deleted" in line
                                         and "new.txt" in line for line in report),
          "the cleaner deletes a dead owner's work-snapshot first listed more than 10 days "
          "ago, naming it and its files", report)
    check({refs["recent"], refs["never"], refs["alive"]} <= left,
          "it keeps one listed more recently, one never listed, and a live owner's one", left)
    report = []
    count = snapshots.clean_leftover_work_snapshots(
        SCRATCH / "not-a-repository", remove=True, only_due=False,
        handoff_directory=handoffs, now=now, is_alive=alive, out=report.append)
    check(count == 1 and "could not be listed" in report[0],
          "a failure to list work-snapshots is said and counted", report)


def snapshot_at(worktree, owner_key, seconds, agent_seat):
    """refresh_work_snapshot with its author date set, so later ones sort later."""
    os.environ["GIT_AUTHOR_DATE"] = f"@{seconds} +0000"
    try:
        snapshots.refresh_work_snapshot(worktree, owner_key, agent_seat, "")
    finally:
        del os.environ["GIT_AUTHOR_DATE"]
    return snapshots.work_snapshot_ref(owner_key, worktree)


def test_in_place_and_duplicate_leftovers():
    main = new_clone()
    handoffs = SCRATCH / "handoffs-in-place"
    handoffs.mkdir()
    dead = lambda key: False
    home = add_worktree(main, main / ".claude" / "worktrees" / "home", "home-branch")
    (home / "draft.md").write_text("a draft kept uncommitted on purpose\n")
    first = snapshot_at(home, "21-1", 1000, "seat-eight")
    report = []
    snapshots.clean_leftover_work_snapshots(main, remove=True, only_due=False,
                                            handoff_directory=handoffs, now=2000,
                                            is_alive=dead, out=report.append)
    check(snapshots.first_prompt_text(main, "seat-eight", handoffs, is_alive=dead) == ""
          and first in refs_of(main)
          and any(first in line and "still in its worktree" in line for line in report),
          "after a session-handoff the dead owner's work-snapshot is kept, unlisted, while its "
          "worktree still holds its changes", report)
    second = snapshot_at(home, "22-1", 1500, "seat-eight")
    report = []
    snapshots.clean_leftover_work_snapshots(main, remove=False, only_due=True,
                                            handoff_directory=handoffs, now=2000,
                                            is_alive=dead, out=report.append)
    check(any(first in line and "a duplicate of the newer leftover " + second in line
              for line in report) and not any(second in line.split(":")[0] for line in report),
          "--only-done shows the older of two leftovers with the same parent and tree as due",
          report)
    report = []
    snapshots.clean_leftover_work_snapshots(main, remove=True, only_due=False,
                                            handoff_directory=handoffs, now=2000,
                                            is_alive=dead, out=report.append)
    check(first not in refs_of(main) and second in refs_of(main)
          and any(first in line and "deleted, a duplicate" in line for line in report),
          "the cleaner deletes the older duplicate and keeps the newer one", report)
    (home / "notes.md").write_text("notes the next agent-session added\n")
    third = snapshot_at(home, "26-1", 1700, "seat-eight")
    snapshots.clean_leftover_work_snapshots(main, remove=True, only_due=False,
                                            handoff_directory=handoffs, now=2000,
                                            is_alive=dead, out=lambda line: None)
    check({second, third} <= set(refs_of(main)),
          "leftovers whose trees differ are both kept")
    git(home, "add", "-A")
    git(home, "commit", "-q", "-m", "the draft, committed")
    text = snapshots.first_prompt_text(main, "seat-eight", handoffs, is_alive=dead)
    report = []
    snapshots.clean_leftover_work_snapshots(main, remove=True, only_due=False,
                                            handoff_directory=handoffs, now=2000,
                                            is_alive=dead, out=report.append)
    check(third in text and third in refs_of(main),
          "a leftover whose changes were committed is listed and kept, an accepted cost: "
          "the restore diff shows the agent the work is committed", (text[:300], report))
    gone = add_worktree(main, main / ".claude" / "worktrees" / "gone", "gone-branch")
    (gone / "work.txt").write_text("work\n")
    older = snapshot_at(gone, "23-1", 1000, "seat-eight")
    newer = snapshot_at(gone, "24-1", 1500, "seat-eight")
    git(main, "worktree", "remove", "--force", str(gone))
    text = snapshots.first_prompt_text(main, "seat-eight", handoffs, is_alive=dead)
    check(newer in text and older not in text,
          "of two duplicate leftovers of a gone worktree, only the newer is listed", text[:400])
    unreadable = add_worktree(main, main / ".claude" / "worktrees" / "unreadable",
                              "unreadable-branch")
    (unreadable / "work.txt").write_text("work\n")
    broken = snapshot_at(unreadable, "25-1", 1000, "seat-nine")
    (unreadable / ".git").write_text("gitdir: /nonexistent/work-snapshot-test\n")
    text = snapshots.first_prompt_text(main, "seat-nine", handoffs, is_alive=dead)
    check(broken in text and "could not be compared" in text,
          "a leftover whose worktree cannot be read is listed, saying why", text[:400])
    report = []
    failures_seen = snapshots.clean_leftover_work_snapshots(
        main, remove=True, only_due=False, handoff_directory=handoffs, now=2000,
        is_alive=lambda key: key != "25-1", out=report.append)
    check(failures_seen == 1 and broken in refs_of(main)
          and any(broken in line and "could not be checked, kept" in line for line in report),
          "the cleaner keeps a leftover whose worktree cannot be read and counts a failure",
          report)


def test_same_tree_on_another_head_is_not_a_duplicate():
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "moved", "moved-branch")
    (worktree / "draft.md").write_text("draft\n")
    older = snapshot_at(worktree, "41-1", 1000, "seat-eleven")
    git(worktree, "commit", "-q", "--allow-empty", "-m", "HEAD moves, the tree does not")
    newer = snapshot_at(worktree, "42-1", 1500, "seat-eleven")
    tree = lambda ref: git(main, "rev-parse", f"{ref}^{{tree}}")
    handoffs = SCRATCH / "handoffs-moved"
    handoffs.mkdir()
    report = []
    snapshots.clean_leftover_work_snapshots(main, remove=True, only_due=False,
                                            handoff_directory=handoffs, now=2000,
                                            is_alive=lambda key: False, out=report.append)
    check(tree(older) == tree(newer) and {older, newer} <= set(refs_of(main)),
          "two leftovers with the same tree but different parents are both kept", report)


def test_unreadable_head_is_reported():
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "bad-head", "bad-head")
    (worktree / "work.txt").write_text("work\n")
    dead_key = dead_owner_key(43)
    ref = snapshot_at(worktree, dead_key, 1000, "seat-eleven")
    head_file = Path(git(worktree, "rev-parse", "--path-format=absolute", "--git-path", "HEAD"))
    head_file.write_text("1234567890123456789012345678901234567890\n")
    handoffs = SCRATCH / "handoffs-bad-head"
    handoffs.mkdir()
    text = snapshots.first_prompt_text(main, "seat-eleven", handoffs, is_alive=lambda key: False)
    check(ref in text and "could not be compared" in text,
          "a HEAD that cannot be resolved is reported with the listing, not taken for a "
          "mismatch", text[:400])
    report = []
    failures_seen = snapshots.clean_leftover_work_snapshots(
        main, remove=True, only_due=False, handoff_directory=handoffs, now=2000,
        is_alive=lambda key: False, out=report.append)
    check(failures_seen == 1 and ref in refs_of(main),
          "the cleaner counts an unresolvable HEAD as a failure and keeps the work-snapshot",
          report)
    result = subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / MODULE_RELATIVE), "list", "--repo", str(main)],
        capture_output=True, text=True, check=False)
    check(result.returncode == 1 and ref in result.stdout,
          "list exits 1 after an unresolvable HEAD", (result.returncode, result.stdout[-300:]))
    unborn = new_clone()
    orphan = add_worktree(unborn, unborn / ".claude" / "worktrees" / "orphan", "orphan-base")
    git(orphan, "checkout", "-q", "--orphan", "orphan-branch")
    git(orphan, "rm", "-rq", "--cached", ".")
    check(snapshots.head_commit_or_raise(orphan) is None,
          "an unborn HEAD is no commit, not a failure")


def test_branch_ref_naming_a_missing_object_is_reported():
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "bad-branch", "bad-branch")
    (worktree / "work.txt").write_text("work\n")
    dead_key = dead_owner_key(44)
    ref = snapshot_at(worktree, dead_key, 1000, "seat-twelve")
    branch_file = Path(git(worktree, "rev-parse", "--path-format=absolute", "--git-path",
                           "refs/heads/bad-branch"))
    branch_file.parent.mkdir(parents=True, exist_ok=True)
    branch_file.write_text("1234567890123456789012345678901234567890\n")
    raised = None
    try:
        snapshots.head_commit_or_raise(worktree)
    except snapshots.WorkSnapshotError as error:
        raised = str(error)
    check(raised is not None and "show-ref" in raised,
          "a branch whose ref names a missing object is a failure, not an unborn HEAD", raised)
    handoffs = SCRATCH / "handoffs-bad-branch"
    handoffs.mkdir()
    text = snapshots.first_prompt_text(main, "seat-twelve", handoffs, is_alive=lambda key: False)
    check(ref in text and "could not be compared" in text,
          "the listing names the failure for a branch ref naming a missing object", text[:400])
    result = subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / MODULE_RELATIVE), "list", "--repo", str(main)],
        capture_output=True, text=True, check=False)
    check(result.returncode == 1 and ref in result.stdout,
          "list exits 1 when a branch ref names a missing object",
          (result.returncode, result.stdout[-300:]))


def test_unborn_head_snapshot_stays_in_place():
    main = new_clone()
    orphan = add_worktree(main, main / ".claude" / "worktrees" / "unborn", "unborn-base")
    git(orphan, "checkout", "-q", "--orphan", "unborn-branch")
    git(orphan, "rm", "-rq", "--cached", ".")
    (orphan / "draft.md").write_text("a draft on a branch with no commit yet\n")
    ref = snapshot_at(orphan, "45-1", 1000, "seat-twelve")
    snapshot = next(item for item in snapshots.all_work_snapshots(main) if item["ref"] == ref)
    check(snapshots.leftover_state(main, snapshot) == snapshots.IN_PLACE,
          "a work-snapshot taken on an unborn HEAD is in place while that HEAD is still unborn",
          snapshots.leftover_state(main, snapshot))


def test_duplicates_count_only_within_one_agent_seat():
    for label, newer_seat in (("other-seat", "seat-fourteen"), ("unknown", "unknown")):
        main = new_clone()
        worktree = add_worktree(main, main / ".claude" / "worktrees" / label, f"{label}-branch")
        (worktree / "draft.md").write_text("a draft\n")
        older = snapshot_at(worktree, "46-1", 1000, "seat-thirteen")
        newer = snapshot_at(worktree, "47-1", 1500, newer_seat)
        git(main, "worktree", "remove", "--force", str(worktree))
        handoffs = SCRATCH / f"handoffs-seat-{label}"
        handoffs.mkdir()
        dead = lambda key: False
        text = snapshots.first_prompt_text(main, "seat-thirteen", handoffs, is_alive=dead)
        report = []
        snapshots.clean_leftover_work_snapshots(main, remove=True, only_due=False,
                                                handoff_directory=handoffs, now=2000,
                                                is_alive=dead, out=report.append)
        check(older in text and {older, newer} <= set(refs_of(main))
              and not any("duplicate" in line for line in report),
              f"an identical newer leftover under {newer_seat} does not make the older one a "
              "duplicate: it is listed to its own agent-seat and kept", (text[:300], report))


def leftover_with_worktree_then(label, change_after):
    """A dead owner's work-snapshot of new.txt added and tracked.txt edited, then change_after(worktree)."""
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / label, f"{label}-branch")
    (worktree / "tracked.txt").write_text("edited by the dead agent\n")
    (worktree / "new.txt").write_text("a new file from the dead agent\n")
    ref = snapshot_at(worktree, "31-1", 1000, "seat-ten")
    change_after(worktree)
    return main, worktree, ref


def test_discarded_work_is_listed_and_kept():
    dead = lambda key: False
    def discard_by_checkout(worktree):
        git(worktree, "checkout", "--", "tracked.txt")
        (worktree / "new.txt").unlink()
    def discard_by_reset(worktree):
        git(worktree, "add", "-A")
        git(worktree, "reset", "-q", "--hard")
    def discard_part_then_edit(worktree):
        git(worktree, "checkout", "--", "tracked.txt")
        (worktree / "other.txt").write_text("the next agent's own edit\n")
        snapshot_at(worktree, "32-1", 1500, "seat-ten")
    for label, change in (("checkout", discard_by_checkout), ("reset", discard_by_reset),
                          ("part", discard_part_then_edit)):
        main, worktree, ref = leftover_with_worktree_then(f"discard-{label}", change)
        handoffs = SCRATCH / f"handoffs-discard-{label}"
        handoffs.mkdir()
        text = snapshots.first_prompt_text(main, "seat-ten", handoffs, is_alive=dead)
        report = []
        snapshots.clean_leftover_work_snapshots(main, remove=True, only_due=False,
                                                handoff_directory=handoffs, now=2000,
                                                is_alive=dead, out=report.append)
        check(ref in text and ref in refs_of(main)
              and not any(ref in line and "deleted" in line for line in report),
              f"work a later agent discarded ({label}) is listed and kept",
              (text[:300], report))


def test_live_owner_duplicate_does_not_count():
    main, worktree, ref = leftover_with_worktree_then(
        "live-copy", lambda worktree: snapshot_at(worktree, "33-1", 1500, "seat-ten"))
    handoffs = SCRATCH / "handoffs-live-copy"
    handoffs.mkdir()
    report = []
    snapshots.clean_leftover_work_snapshots(main, remove=True, only_due=False,
                                            handoff_directory=handoffs, now=2000,
                                            is_alive=lambda key: key == "33-1",
                                            out=report.append)
    check(ref in refs_of(main),
          "a live owner's identical later work-snapshot does not make a dead owner's one a "
          "duplicate, since the live owner's hook may delete it", report)


def test_edited_draft_older_version_is_listed():
    main, worktree, ref = leftover_with_worktree_then(
        "edited", lambda worktree: ((worktree / "new.txt").write_text("rewritten\n"),
                                    snapshot_at(worktree, "34-1", 1500, "seat-ten")))
    handoffs = SCRATCH / "handoffs-edited"
    handoffs.mkdir()
    text = snapshots.first_prompt_text(main, "seat-ten", handoffs, is_alive=lambda key: False)
    check(ref in text,
          "an older version whose tree differs from the later leftover's is listed",
          text[:300])


def test_empty_leftover_directory_is_not_the_worktree():
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "emptied", "emptied-branch")
    (worktree / "work.txt").write_text("work\n")
    ref = snapshot_at(worktree, "35-1", 1000, "seat-ten")
    git(main, "worktree", "remove", "--force", str(worktree))
    worktree.mkdir(parents=True)
    handoffs = SCRATCH / "handoffs-emptied"
    handoffs.mkdir()
    dead = lambda key: False
    text = snapshots.first_prompt_text(main, "seat-ten", handoffs, is_alive=dead)
    report = []
    snapshots.clean_leftover_work_snapshots(main, remove=True, only_due=False,
                                            handoff_directory=handoffs, now=2000,
                                            is_alive=dead, out=report.append)
    check(ref in text and ref in refs_of(main),
          "an empty directory left where the worktree was is not taken for the clean checkout "
          "around it: the work-snapshot is listed and kept", (text[:300], report))
    (main / "work.txt").write_text("work\n")
    text = snapshots.first_prompt_text(main, "seat-ten", handoffs, is_alive=dead)
    check(ref in text,
          "nor for the checkout around it when that checkout holds the same uncommitted "
          "change: the work-snapshot is still listed", text[:300])
    git(main, "add", "work.txt")
    git(main, "commit", "-q", "-m", "the same file, committed in the checkout around it")
    text = snapshots.first_prompt_text(main, "seat-ten", handoffs, is_alive=dead)
    check(ref in text,
          "nor when the checkout around it has committed the same file: only the worktree's "
          "own HEAD counts", text[:300])
    (worktree / ".git").mkdir()
    text = snapshots.first_prompt_text(main, "seat-ten", handoffs, is_alive=dead)
    report = []
    failures_seen = snapshots.clean_leftover_work_snapshots(
        main, remove=True, only_due=False, handoff_directory=handoffs, now=2000,
        is_alive=dead, out=report.append)
    check(ref in text and "could not be compared" in text and failures_seen == 1
          and ref in refs_of(main),
          "an empty .git directory, which git skips to answer for the checkout around it, is "
          "reported as a .git entry git cannot use, and the work-snapshot kept",
          (text[:400], report))


def test_in_place_leftover_is_not_expired():
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "kept", "kept-branch")
    (worktree / "draft.md").write_text("a draft kept uncommitted\n")
    ref = snapshot_at(worktree, "36-1", 1000, "seat-ten")
    handoffs = SCRATCH / "handoffs-in-place-expiry"
    handoffs.mkdir()
    now = 100 * 86400
    (handoffs / "seat-ten-work-snapshots-first-listed.json").write_text(
        json.dumps({ref: now - 30 * 86400}))
    report = []
    snapshots.clean_leftover_work_snapshots(main, remove=True, only_due=False,
                                            handoff_directory=handoffs, now=now,
                                            is_alive=lambda key: False, out=report.append)
    check(ref in refs_of(main),
          "a work-snapshot first listed long ago but now in place in its worktree is kept",
          report)


def test_list_exits_nonzero_after_a_comparison_failure():
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "broken", "broken-branch")
    (worktree / "work.txt").write_text("work\n")
    dead_key = dead_owner_key(37)
    ref = snapshot_at(worktree, dead_key, 1000, "seat-ten")
    (worktree / ".git").write_text("gitdir: /nonexistent/work-snapshot-test\n")
    result = subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / MODULE_RELATIVE), "list", "--repo", str(main)],
        capture_output=True, text=True, check=False)
    check(result.returncode == 1 and ref in result.stdout,
          "list prints a work-snapshot it could not compare and exits 1",
          (result.returncode, result.stdout[-300:], result.stderr[-300:]))


# ---------------------------------------------------------------- replay


def test_the_2026_10_05_loss_replayed():
    name = "the 2026-10-05 loss replayed: the restore brings both files back as a commit"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, stand_in_skip_reason())
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "concurrency-step-1",
                            "concurrency-step-1")
    (worktree / "tracked.txt").write_text("edited by the fork\n")
    (worktree / "new-test.py").write_text("print('a new test')\n")
    claude = ClaudeStandIn(main, {"GIT_AUTHOR_NAME": "seat-seven"})
    claude.run_hook(edit(worktree / "tracked.txt"))
    claude.run_hook(edit(worktree / "new-test.py"))
    claude.end()
    cleaner = subprocess.run([sys.executable, str(main / CLEANER_RELATIVE), "--remove"],
                             capture_output=True, text=True, cwd=main)
    check(not worktree.exists(), "the cleaner removes the dead fork's worktree, as on "
          "2026-10-05", cleaner.stdout + cleaner.stderr)
    check("work-snapshot refs/work-snapshots/" in cleaner.stdout
          and "never listed in a first prompt" in cleaner.stdout,
          "the cleaner reports the work-snapshot it keeps", cleaner.stdout)
    handoffs = HOME / ".claude" / "handoffs"
    handoffs.mkdir(parents=True, exist_ok=True)
    text = snapshots.first_prompt_text(main, "seat-seven", handoffs)
    refs = [line.split(":")[0][2:] for line in text.splitlines() if line.startswith("- refs/")]
    check(len(refs) == 1 and "(is gone)" in text,
          "the next agent-session's first prompt lists the work-snapshot", text[:300])
    if refs:
        target = restore_steps_commit(main, refs[0], ["tracked.txt", "new-test.py"])
        check(git(target, "show", "HEAD:tracked.txt") == "edited by the fork"
              and git(target, "show", "HEAD:new-test.py") == "print('a new test')",
              name)
        git(main, "update-ref", "-d", refs[0])
        check(refs_of(main) == [], "step 4 deletes the ref")


def main():
    try:
        for case in (test_what_a_work_snapshot_holds, test_same_size_edit_in_the_index_second,
                     test_ref_names,
                     test_bash_commit_deletes_and_other_worktrees_follow,
                     test_overlapping_runs_end_on_the_final_state, test_operation_trailer,
                     test_hook_failure_is_reported, test_other_repository_is_untouched,
                     test_worktree_discovery_failure_is_reported,
                     test_module_load_failure_is_reported, test_owner_liveness,
                     test_macos_ps_failure_is_not_a_dead_owner,
                     test_live_and_dead_owners_listed, test_list_caps_and_failure,
                     test_supervisor_appends_the_list, test_restore_a_subset, test_cleaner,
                     test_in_place_and_duplicate_leftovers,
                     test_same_tree_on_another_head_is_not_a_duplicate,
                     test_unreadable_head_is_reported,
                     test_branch_ref_naming_a_missing_object_is_reported,
                     test_unborn_head_snapshot_stays_in_place,
                     test_duplicates_count_only_within_one_agent_seat,
                     test_discarded_work_is_listed_and_kept,
                     test_live_owner_duplicate_does_not_count,
                     test_edited_draft_older_version_is_listed,
                     test_empty_leftover_directory_is_not_the_worktree,
                     test_in_place_leftover_is_not_expired,
                     test_list_exits_nonzero_after_a_comparison_failure,
                     test_the_2026_10_05_loss_replayed):
            try:
                case()
            except Exception as error:
                check(False, f"{case.__name__} raised", f"{type(error).__name__}: {error}")
    finally:
        shutil.rmtree(SCRATCH, ignore_errors=True)
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
