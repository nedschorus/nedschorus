#!/usr/bin/env python3
"""Tests for git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py.

The shipping cases run the hook end to end as a subprocess, the way Claude
Code does, on a real git worktree in a scratch directory, with the real
shippers pointed at a scratch log-store by COLD_READ_RECORD_SHIP_DESTINATION,
as the shippers' own tests do. A failed shipment is a stub ssh and rsync that
exit 255 first on PATH, with the destination given a host, so the shippers
take ned-box to be unreachable. The cases for a shipper that prints nothing,
a shipment past the hook's time limit, and a failing worktree listing inject
those failures in-process through main's runner and clock. The command
reading cases call main in-process.

Run: python3 .claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import atexit
import contextlib
import importlib.util
import io
import json
import os
import shutil
import site
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name(
    "git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py")

_spec = importlib.util.spec_from_file_location("git_worktree_remove_records_ship_first_guard_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

SHIP_DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
# Any test run that reaches a shipper ships here, never into the real log-store.
# Resolved, because the hook names a worktree by its resolved path and the test sandbox's TMPDIR is a symlink.
_scratch = Path(tempfile.mkdtemp(prefix="git-worktree-remove-records-ship-first-test-")).resolve()
atexit.register(shutil.rmtree, _scratch, ignore_errors=True)
STORE = _scratch / "store"
os.environ[SHIP_DESTINATION_VARIABLE] = str(STORE / "cold-read-records")
# Before anything runs git, so a run started with GIT_DIR or another redirecting variable set builds its
# scratch repositories here and not in the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    HOOK_SCRIPT.resolve().parents[2] / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(directory, *arguments):
    subprocess.run(["git", "-C", str(directory), *arguments], check=True, capture_output=True, text=True)


def checkout_with_worktree(name):
    """Return (main checkout, worktree) under the scratch directory; the worktree holds one
    cold-read-record, one sanity-check record and an empty record directory."""
    parent = _scratch / name
    checkout = parent / "checkout"
    checkout.mkdir(parents=True)
    git(checkout, "init", "-q")
    git(checkout, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init")
    worktree = parent / f"{name}-worktree"
    git(checkout, "worktree", "add", "-q", str(worktree))
    cold_read_record = worktree / "cold-read-records" / f"{name}-doc-2026-11-03"
    cold_read_record.mkdir(parents=True)
    (cold_read_record / "fast-read.md").write_text(f"{name} report\n")
    sanity_check_record = worktree / "sanity-check-records" / f"2026-11-03-{name}-doc"
    sanity_check_record.mkdir(parents=True)
    (sanity_check_record / "finding-dispositions.md").write_text(f"{name} dispositions\n")
    (worktree / "cold-read-records" / "empty-record").mkdir()
    return checkout, worktree


def run_hook_process(command, cwd, environment=None):
    """Run the hook as Claude Code does; return (exit code, parsed stdout or None, stderr)."""
    completed = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)], capture_output=True, text=True, timeout=300,
        env=environment, input=json.dumps({"tool_name": "Bash", "cwd": str(cwd),
                                           "tool_input": {"command": command}}))
    text = completed.stdout.strip()
    return completed.returncode, (json.loads(text) if text else None), completed.stderr


def run_hook(payload, runner=subprocess.run, clock=None):
    """Run main in-process; return (exit code, parsed stdout or None)."""
    stdout = io.StringIO()
    keywords = {"runner": runner}
    if clock is not None:
        keywords["clock"] = clock
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(payload if isinstance(payload, str) else json.dumps(payload)),
                         **keywords)
    text = stdout.getvalue().strip()
    return code, (json.loads(text) if text else None)


def refusal(output):
    if output is None:
        return None
    return output["hookSpecificOutput"].get("permissionDecisionReason")


def removals(command, cwd="/work"):
    return [(directory, word, unreadable)
            for directory, word, unreadable, _ in hook.worktree_removals_in_command(command, cwd)]


# An unshipped record reaches the log-store before the removal, and the removal is let through.
checkout, worktree = checkout_with_worktree("shipped")
code, output, stderr = run_hook_process(f"git worktree remove {worktree}", checkout)
cold_read_copy = STORE / "cold-read-records" / "shipped-doc-2026-11-03" / "fast-read.md"
sanity_check_copy = STORE / "sanity-check-records" / "2026-11-03-shipped-doc" / "finding-dispositions.md"
check("unshipped records reach the log-store and the removal is let through silently",
      code == 0 and output is None and cold_read_copy.is_file() and sanity_check_copy.is_file()
      and cold_read_copy.read_text() == "shipped report\n",
      (code, output, stderr, sorted(str(path) for path in STORE.rglob("*"))))
check("an empty record directory is not shipped",
      not (STORE / "cold-read-records" / "empty-record").exists())
code, output, stderr = run_hook_process(f"git worktree remove {worktree}", checkout)
check("records already in the log-store ship as nothing new and the removal is let through",
      code == 0 and output is None, (code, output, stderr))

# The removal is named by the worktree path's last component, as git allows.
(worktree / "cold-read-records" / "later-record").mkdir()
(worktree / "cold-read-records" / "later-record" / "triage.md").write_text("later\n")
code, output, stderr = run_hook_process(f"git worktree remove --force {worktree.name}", checkout)
check("a worktree named by its last path component is found through git worktree list and shipped",
      code == 0 and output is None
      and (STORE / "cold-read-records" / "later-record" / "triage.md").is_file(), (code, output, stderr))

# A failed shipment refuses the removal, naming each record and the command that ships it again.
checkout, worktree = checkout_with_worktree("unreachable")
stubs = _scratch / "unreachable-stubs"
stubs.mkdir()
for tool in ("ssh", "rsync"):
    (stubs / tool).write_text("#!/bin/sh\nexit 255\n")
    (stubs / tool).chmod(0o755)
unreachable_environment = dict(os.environ)
unreachable_environment[SHIP_DESTINATION_VARIABLE] = "nedlern@ned-box:/nonexistent-test-log-store/cold-read-records"
unreachable_environment["PATH"] = f"{stubs}{os.pathsep}{os.environ['PATH']}"
code, output, stderr = run_hook_process(f"cd {checkout} && git worktree remove ../{worktree.name}",
                                        _scratch, unreachable_environment)
reason = refusal(output) or ""
cold_read_record = worktree / "cold-read-records" / "unreachable-doc-2026-11-03"
sanity_check_record = worktree / "sanity-check-records" / "2026-11-03-unreachable-doc"
cold_read_rerun = f"python3 {hook.REPOSITORY_ROOT}/nc-systems/cold-read/cold-read-record-ship.py {cold_read_record}"
sanity_check_rerun = f"python3 {hook.REPOSITORY_ROOT}/scripts/sanity-check-record-ship.py {sanity_check_record}"
check("a failed shipment refuses the removal",
      code == 0 and output["hookSpecificOutput"]["permissionDecision"] == "deny", (code, output, stderr))
check("the refusal opens by saying it refused on purpose and names the worktree and how many records",
      reason.startswith(f"Refused on purpose: this `git worktree remove` would delete 2 record(s) in {worktree} "),
      reason)
check("the refusal names each record with the shipper's own FAILED line",
      f"Record {cold_read_record}: FAILED:" in reason and f"Record {sanity_check_record}: FAILED:" in reason
      and "could not reach the log-store" in reason, reason)
check("the refusal gives each record's ship command",
      f"  Shipped with: {cold_read_rerun}\n" in reason and f"  Shipped with: {sanity_check_rerun}\n" in reason,
      reason)
for line in (f"If a Record line says the log-store or ned-box could not be reached, leave the worktree in place, "
             f"stop, and {hook.TELL_THE_USER_OR_DISPATCHING_AGENT} that the worktree "
             f"{worktree} is kept because records in it could not be shipped to the log-store, quoting each Record "
             f"line above word for word.",
             "Otherwise, first run any command a Record line gives, such as an `mv` to a free name; you need not run "
             "the \"Shipped with\" commands, because this hook runs them itself. Then run your `git worktree remove` "
             "command again, once.",
             f"If this hook refuses it again, leave the worktree in place, stop, and "
             f"{hook.TELL_THE_USER_OR_DISPATCHING_AGENT} that the worktree {worktree} is kept because records in it "
             f"could not be shipped to the log-store, quoting each Record line of the second refusal word for "
             f"word."):
    check(f"the refusal carries the instruction {line[:50]!r}...", line in reason, reason)
check("the refused removal leaves the records in place", cold_read_record.is_dir() and sanity_check_record.is_dir())

# Run again once ned-box can be reached, as the refusal says, the removal ships the records and is let through.
code, output, stderr = run_hook_process(f"cd {checkout} && git worktree remove ../{worktree.name}", _scratch)
check("the removal run again ships the records and is let through",
      code == 0 and output is None
      and (STORE / "cold-read-records" / cold_read_record.name / "fast-read.md").is_file()
      and (STORE / "sanity-check-records" / sanity_check_record.name / "finding-dispositions.md").is_file(),
      (code, output, stderr))
reruns = [subprocess.run(rerun.split(), capture_output=True, text=True, check=False)
          for rerun in (cold_read_rerun, sanity_check_rerun)]
check("each ship command the refusal gives runs and ships its record",
      all(rerun.returncode == 0 and rerun.stdout.startswith("shipped:") for rerun in reruns),
      [(rerun.returncode, rerun.stdout, rerun.stderr) for rerun in reruns])

# A worktree with no records is let through silently, without loading a shipper.
checkout, worktree = checkout_with_worktree("no-records")
shutil.rmtree(worktree / "cold-read-records")
shutil.rmtree(worktree / "sanity-check-records")
shipper_calls = []


def shippers_only(runner):
    """Return a runner that injects runner into shipper calls only; the worktree listing runs real git."""
    def runner_for_shippers(argv, **keywords):
        if argv[0] == "git":
            return subprocess.run(argv, **keywords)
        return runner(argv, **keywords)
    return runner_for_shippers


def runner_recording_shipper_calls(argv, **keywords):
    shipper_calls.append(argv)
    return subprocess.run(argv, **keywords)


code, output = run_hook({"tool_name": "Bash", "cwd": str(checkout),
                         "tool_input": {"command": f"git worktree remove {worktree}"}},
                        shippers_only(runner_recording_shipper_calls))
check("a worktree holding no records is let through silently, with no shipper run",
      code == 0 and output is None and shipper_calls == [], (code, output, shipper_calls))


# A shipper that exits 0 but prints nothing, or exits nonzero, refuses the removal.
checkout, worktree = checkout_with_worktree("injected")
payload = {"tool_name": "Bash", "cwd": str(checkout), "tool_input": {"command": f"git worktree remove {worktree}"}}


def runner_answering(returncode, stdout, stderr=""):
    def runner(argv, **keywords):
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)
    return runner


code, output = run_hook(payload, shippers_only(runner_answering(0, "")))
check("a shipper that exits 0 and prints nothing refuses the removal, with its exit code",
      "Record " in (refusal(output) or "") and ": the shipper printed nothing (exit 0)\n" in refusal(output),
      output)
code, output = run_hook(payload, shippers_only(runner_answering(1, "", "Traceback ...\nOSError: disk full\n")))
check("a shipper that dies printing nothing refuses the removal, with its last stderr line",
      ": the shipper printed nothing (exit 1): OSError: disk full\n" in (refusal(output) or ""), output)
code, output = run_hook(payload, shippers_only(
    runner_answering(2, "REFUSED: x — already in the store with different content")))
check("a shipper's REFUSED line refuses the removal and is quoted",
      ": REFUSED: x — already in the store with different content\n" in (refusal(output) or ""), output)
code, output = run_hook(payload, shippers_only(runner_answering(-9, "shipped: x — 1 file added")))
check("a shipper killed by a signal refuses the removal, though it printed shipped:",
      "Refused on purpose:" in (refusal(output) or ""), output)
code, output = run_hook(payload, shippers_only(runner_answering(0, "shipped: x — 1 file added")))
check("shippers that print shipped: let the removal through", code == 0 and output is None, output)


# The time limit: a shipper still running when it runs out, and records it never reached, refuse.
def runner_timing_out(argv, **keywords):
    raise subprocess.TimeoutExpired(argv, keywords.get("timeout"))


budget_line = f"not shipped: this hook's limit of {hook.SHIPPING_BUDGET_SECONDS} seconds for shipping ran out first"
code, output = run_hook(payload, shippers_only(runner_timing_out))
check("a shipper past the time limit refuses the removal",
      (refusal(output) or "").count(f": {budget_line}\n") == 2, output)
times = iter([0, 0, hook.SHIPPING_BUDGET_SECONDS])
timeouts_given = []


def runner_recording_timeout(argv, **keywords):
    timeouts_given.append(keywords.get("timeout"))
    return subprocess.CompletedProcess(argv, 0, "shipped: x", "")


code, output = run_hook(payload, shippers_only(runner_recording_timeout), clock=lambda: next(times))
check("a record reached after the time limit ran out is not shipped and refuses the removal",
      timeouts_given == [hook.SHIPPING_BUDGET_SECONDS]
      and (refusal(output) or "").count(f": {budget_line}\n") == 1
      and "would delete 1 record(s)" in refusal(output), (timeouts_given, output))


# A worktree word that names no directory and no worktree is let through, since git refuses it too.
def runner_failing_listing(argv, **keywords):
    return subprocess.CompletedProcess(argv, 128, b"", b"fatal: not a git repository")


def runner_raising(error):
    def runner(argv, **keywords):
        raise error
    return runner


check("a worktree word that matches no worktree is let through",
      hook.git_worktree_remove_target_word_candidate_worktree_directories_find(str(checkout), "no-such-worktree", subprocess.run) == [])
check("a failing worktree listing finds no worktree",
      hook.git_worktree_remove_target_word_candidate_worktree_directories_find("/nonexistent", "x", runner_failing_listing) == [])
listing_naming_a_worktree = f"worktree {worktree}\0HEAD {'0' * 40}\0detached\0\0".encode()
for code_given in (128, -9):
    check(f"a worktree listing that exits {code_given} is not read, though it names a matching worktree",
          hook.git_worktree_remove_target_word_candidate_worktree_directories_find("/nonexistent", worktree.name,
                                    runner_answering(code_given, listing_naming_a_worktree)) == [])
check("a worktree listing that exits 0 is read",
      hook.git_worktree_remove_target_word_candidate_worktree_directories_find("/nonexistent", worktree.name, runner_answering(0, listing_naming_a_worktree))
      == [worktree])
check("a worktree listing that cannot run finds no worktree",
      hook.git_worktree_remove_target_word_candidate_worktree_directories_find("/nonexistent", "x", runner_raising(OSError("no git"))) == [])
check("a worktree listing that times out finds no worktree",
      hook.git_worktree_remove_target_word_candidate_worktree_directories_find("/nonexistent", "x", runner_raising(subprocess.TimeoutExpired("git", 10))) == [])
second_checkout, second_worktree = checkout_with_worktree("ambiguous")
other_worktree = second_checkout.parent / "other" / second_worktree.name
git(second_checkout, "worktree", "add", "-q", "--detach", str(other_worktree))
check("a last path component two worktrees share finds both, since git may remove either",
      sorted(hook.git_worktree_remove_target_word_candidate_worktree_directories_find(str(second_checkout), second_worktree.name, subprocess.run))
      == sorted([second_worktree, other_worktree]))
check("a last path component one worktree has finds that worktree",
      hook.git_worktree_remove_target_word_candidate_worktree_directories_find(str(second_checkout), f"other/{second_worktree.name}", subprocess.run)
      == [other_worktree])
# git matches a word against the worktrees' last path components before it reads the word as a path.
suffix_checkout, suffix_worktree = checkout_with_worktree("suffix-first")
(suffix_checkout / suffix_worktree.name).mkdir()
check("a word that is both an ordinary directory and one worktree's last path component finds both",
      sorted(hook.git_worktree_remove_target_word_candidate_worktree_directories_find(str(suffix_checkout), suffix_worktree.name, subprocess.run))
      == sorted([suffix_worktree, suffix_checkout / suffix_worktree.name]))
check("a failing worktree listing takes a word naming a directory as that directory",
      hook.git_worktree_remove_target_word_candidate_worktree_directories_find(str(suffix_checkout), suffix_worktree.name, runner_failing_listing)
      == [suffix_checkout / suffix_worktree.name])

# Review 5768090675, finding 1: a removal pointed at another repository by --git-dir ships that worktree's records.
other_repository_checkout, other_repository_worktree = checkout_with_worktree("git-dir-elsewhere")
unrelated_checkout, _ = checkout_with_worktree("git-dir-from-here")
code, output, stderr = run_hook_process(
    f"git --git-dir={other_repository_checkout}/.git worktree remove --force {other_repository_worktree}",
    unrelated_checkout)
check("a removal given --git-dir of another repository ships that worktree's records",
      code == 0 and output is None
      and (STORE / "cold-read-records" / "git-dir-elsewhere-doc-2026-11-03" / "fast-read.md").is_file(),
      (code, output, stderr))
(other_repository_worktree / "cold-read-records" / "git-dir-by-name").mkdir()
(other_repository_worktree / "cold-read-records" / "git-dir-by-name" / "triage.md").write_text("by name\n")
code, output, stderr = run_hook_process(
    f"git --git-dir {other_repository_checkout}/.git worktree remove --force {other_repository_worktree.name}",
    unrelated_checkout)
check("a worktree named by its last path component in a repository --git-dir names is found and shipped",
      code == 0 and output is None
      and (STORE / "cold-read-records" / "git-dir-by-name" / "triage.md").is_file(), (code, output, stderr))
check("--git-dir and --work-tree, joined or apart, are carried to the worktree listing",
      [options for _, _, _, options in hook.worktree_removals_in_command(
          "git --git-dir=/b/.git --work-tree /b worktree remove wt", "/work")]
      == [("--git-dir=/b/.git", "--work-tree", "/b")])

# Review 5768090675, finding 3: a symlink with a trailing slash names the worktree it points to, which git removes.
alias_checkout, alias_target = checkout_with_worktree("alias-target")
alias_other = alias_checkout.parent / "elsewhere" / "alias"
git(alias_checkout, "worktree", "add", "-q", "--detach", str(alias_other))
(alias_checkout / "alias").symlink_to(alias_target)
check("a word through a symlink finds the worktree it points to, beside any worktree whose path ends in it",
      alias_target in hook.git_worktree_remove_target_word_candidate_worktree_directories_find(str(alias_checkout), "alias/", subprocess.run),
      hook.git_worktree_remove_target_word_candidate_worktree_directories_find(str(alias_checkout), "alias/", subprocess.run))
code, output, stderr = run_hook_process("git worktree remove alias/", alias_checkout)
check("removing a worktree through a symlink ships the records of the worktree it points to",
      code == 0 and output is None
      and (STORE / "cold-read-records" / "alias-target-doc-2026-11-03" / "fast-read.md").is_file(),
      (code, output, stderr))

# Reading the command.
check("a plain removal", removals("git worktree remove wt") == [("/work", "wt", None)], removals("git worktree remove wt"))
check("--force and -f are options, and a word after -- is a worktree",
      removals("git worktree remove --force -f -- -odd") == [("/work", "-odd", None)])
check("a cd before the removal changes its directory",
      removals("cd /repo && git worktree remove ../wt") == [("/repo", "../wt", None)])
check("a cd inside ( ) does not change the directory after it",
      removals("(cd /elsewhere) && git worktree remove wt") == [("/work", "wt", None)])
check("git -C, joined or apart, changes the directory",
      removals("git -C /repo worktree remove wt; git -C/repo2 worktree remove wt2")
      == [("/repo", "wt", None), ("/repo2", "wt2", None)])
check("git's other global options are skipped",
      removals("git -c core.x=y --no-pager worktree remove wt") == [("/work", "wt", None)])
check("env -C changes the directory", removals("env -C /repo git worktree remove wt") == [("/repo", "wt", None)])
check("a removal inside bash -c is read",
      removals("cd /repo && bash -c 'git worktree remove wt'") == [("/repo", "wt", None)])
check("other worktree subcommands are not removals",
      removals("git worktree list; git worktree add x; git worktree prune") == [])
check("echo of a removal is data", removals("echo git worktree remove wt") == [])
check("a removal on another machine through ssh is not read",
      removals("ssh nedlern@ned-box 'git worktree remove wt'") == [])
check("a variable no NAME=value sets cannot be read",
      removals('git worktree remove "$WT"') == [("/work", "$WT", "$WT")])
check("a variable in a cd before the removal cannot be read",
      removals('cd "$REPO" && git worktree remove wt') == [("/work", "wt", "$REPO")])
check("a variable in git's -C cannot be read",
      removals('git -C "$REPO" worktree remove wt') == [("/work", "wt", "$REPO")])
check("a cd to a written-out path after a variable one is read again",
      removals('cd "$REPO"; cd /repo && git worktree remove wt') == [("/repo", "wt", None)])
check("a loop variable cannot be read, though the variable before it can",
      removals("S=/s; for w in a b; do git worktree remove $S/$w; done") == [("/work", "/s/$w", "/s/$w")])
check("NAME=value sets the worktree path, in both $NAME and ${NAME} forms",
      removals('W=/a/b; git worktree remove "$W"; git worktree remove ${W}2') == [("/work", "/a/b", None),
                                                                                    ("/work", "/a/b2", None)])
check("NAME=value sets a cd directory and git's -C, quoted, exported or built from another variable",
      removals('S="/s"; export T=$S/t; cd "$S/x" && git -C $T worktree remove wt') == [("/s/t", "wt", None)])
check("a value starting with ~ is expanded",
      removals("W=~/wt; git worktree remove $W") == [("/work", os.path.expanduser("~/wt"), None)])
check("a later assignment holding an expansion adds an unreadable reading beside the earlier value",
      removals("W=/a; W=$(pwd); git worktree remove $W") == [("/work", "/a", None), ("/work", "$W", "$W")],
      removals("W=/a; W=$(pwd); git worktree remove $W"))
# Review 5768090675, finding 2: text inside another value's quotes may look like an assignment.
check("an assignment-like text inside another value's quotes adds a reading and keeps the real one",
      removals("W=/a; NOTE='example W=/b here'; git worktree remove \"$W\"")
      == [("/work", "/a", None), ("/work", "/b", None)],
      removals("W=/a; NOTE='example W=/b here'; git worktree remove \"$W\""))
check("each value of each name gives its own reading, as in a cd and a worktree word",
      removals("D=/x; D=/y; W=a; cd $D && git worktree remove $W")
      == [("/x", "a", None), ("/y", "a", None)],
      removals("D=/x; D=/y; W=a; cd $D && git worktree remove $W"))
check("a value in single quotes is taken as written",
      removals("W='/a b'; git worktree remove \"$W\"") == [("/work", "/a b", None)])
check("a value of quoted and bare pieces run together is read whole",
      removals('W="/repo"/wt; git worktree remove "$W"') == [("/work", "/repo/wt", None)],
      removals('W="/repo"/wt; git worktree remove "$W"'))
check("a value with a backslash cannot be read, and is an unreadable reading beside an earlier value",
      removals('W=/a; W=/b\\ c; git worktree remove "$W"') == [("/work", "/a", None), ("/work", "$W", "$W")],
      removals('W=/a; W=/b\\ c; git worktree remove "$W"'))
quoted_checkout, quoted_worktree = checkout_with_worktree("quoted-lookalike")
code, output = run_hook({"tool_name": "Bash", "cwd": str(quoted_checkout), "tool_input": {
    "command": f"W={quoted_worktree}; NOTE='example W=/nonexistent here'; git worktree remove --force \"$W\""}})
check("a worktree set by NAME=value has its records shipped though quoted text assigns the name too",
      code == 0 and output is None
      and (STORE / "cold-read-records" / "quoted-lookalike-doc-2026-11-03" / "fast-read.md").is_file(), output)
check("a wrapper's directory applies to the command string of bash -c",
      removals("env -C /b/checkout bash -c 'git worktree remove ../wt'", "/a/checkout")
      == [("/b/checkout", "../wt", None)],
      removals("env -C /b/checkout bash -c 'git worktree remove ../wt'", "/a/checkout"))
check("a variable in a wrapper's directory before bash -c cannot be read",
      removals("env -C \"$D\" bash -c 'git worktree remove wt'") == [("/work", "wt", "$D")])

# The shell expands the leading ~ of an unquoted word before git sees it.
check("a worktree word starting with ~/ is expanded",
      removals("git worktree remove ~/wt") == [("/work", os.path.expanduser("~/wt"), None)],
      removals("git worktree remove ~/wt"))
check("a worktree word starting with ~user/ is expanded",
      removals("git worktree remove ~root/wt") == [("/work", os.path.expanduser("~root/wt"), None)],
      removals("git worktree remove ~root/wt"))
check("a cd to a directory starting with ~/ is expanded",
      removals("cd ~/repo; git worktree remove wt") == [(os.path.expanduser("~/repo"), "wt", None)],
      removals("cd ~/repo; git worktree remove wt"))
check("a cd with no directory goes to the home directory",
      removals("cd; git worktree remove wt") == [(os.path.expanduser("~"), "wt", None)],
      removals("cd; git worktree remove wt"))
check("a ~ before a variable is expanded and the variable read",
      removals("X=wt; git worktree remove ~/$X") == [("/work", os.path.expanduser("~/wt"), None)],
      removals("X=wt; git worktree remove ~/$X"))
check("a quoted ~ is kept as written",
      removals('git worktree remove "~/wt"') == [("/work", "~/wt", None)], removals('git worktree remove "~/wt"'))
check("a ~ that a variable's value brings in is kept as written, as the shell keeps it",
      removals("W='~/wt'; git worktree remove $W") == [("/work", "~/wt", None)],
      removals("W='~/wt'; git worktree remove $W"))
tilde_checkout, tilde_worktree = checkout_with_worktree("tilde")
# The user base is kept, because the shell reader's tree-sitter is installed under the real home.
code, output, stderr = run_hook_process(f"git worktree remove ~/{tilde_worktree.name}", tilde_checkout,
                                        dict(os.environ, HOME=str(tilde_worktree.parent),
                                             PYTHONUSERBASE=site.getuserbase()))
check("a worktree named through ~/ has its records shipped and the removal let through",
      code == 0 and output is None
      and (STORE / "cold-read-records" / "tilde-doc-2026-11-03" / "fast-read.md").is_file(), (code, output, stderr))

# Readings are bounded only where variables multiply them, and a cut is reported, never silent.
many_removals = "; ".join(f"git worktree remove wt{number}" for number in range(40))
check("every one of 40 written-out removals is read",
      removals(many_removals) == [("/work", f"wt{number}", None) for number in range(40)],
      len(removals(many_removals)))
cap = hook.MAXIMUM_ALTERNATIVE_SHELL_VARIABLE_VALUE_READINGS_PER_WORD
two_names_six_values_each = "; ".join([f"A=a{number}" for number in range(6)] + [f"B=b{number}" for number in range(6)])
cut = removals(f"{two_names_six_values_each}; git worktree remove $A$B")
check("readings of one worktree word past the limit are cut, and the cut is an unreadable reading",
      len([removal for removal in cut if removal[2] is None]) == cap and cut[-1] == ("/work", "$A$B", "$A$B"), cut)
one_name_too_many_values = "; ".join(f"W=/w{number}" for number in range(cap + 1))
cut = removals(f"{one_name_too_many_values}; git worktree remove $W")
check("values of one name past the limit are cut, and the cut is an unreadable reading",
      len([removal for removal in cut if removal[2] is None]) == cap and cut[-1] == ("/work", "$W", "$W"), cut)
cut = removals(f"{two_names_six_values_each}; W=/$A$B; git worktree remove $W")
check("values an assignment builds past the limit are cut, and the cut is an unreadable reading",
      len([removal for removal in cut if removal[2] is None]) == cap and cut[-1] == ("/work", "$W", "$W"), cut)
cut = removals(f"{one_name_too_many_values}; cd $W; git worktree remove wt")
check("cd directories past the limit are cut, and the cut is an unreadable reading",
      len([removal for removal in cut if removal[2] is None]) == cap and cut[-1] == ("/work", "wt", "$W"), cut)
cut = removals(f"{one_name_too_many_values}; git -C $W worktree remove wt")
check("git -C directories past the limit are cut, and the cut is an unreadable reading",
      len([removal for removal in cut if removal[2] is None]) == cap and cut[-1] == ("/work", "wt", "$W"), cut)
cut = removals(f"{one_name_too_many_values}; git --git-dir=$W worktree remove wt")
check("repository option readings past the limit are cut, and the cut is an unreadable reading",
      len([removal for removal in cut if removal[2] is None]) == cap and cut[-1] == ("/work", "wt", "--git-dir=$W"),
      cut)
cut = removals("D=/x; D=/y; " + "; ".join(f"A=a{number}" for number in range(20))
               + "; cd $D && git worktree remove $A")
check("removals one worktree word gives in several directories past the limit are cut, and the cut is unreadable",
      len([removal for removal in cut if removal[2] is None]) == cap and cut[-1][2] is not None, cut)
code, output = run_hook({"tool_name": "Bash", "cwd": "/nonexistent",
                         "tool_input": {"command": f"{two_names_six_values_each}; git worktree remove $A$B"}},
                        runner=runner_failing_listing)
check("a removal whose readings were cut is let through with the not-checked notice naming the word",
      code == 0 and output is not None and "permissionDecision" not in output["hookSpecificOutput"]
      and output["hookSpecificOutput"].get("additionalContext", "").startswith(
          "Not checked: the hook that ships a worktree's cold-read-records and sanity-check records to the "
          "log-store before `git worktree remove` could not read $A$B in this command"), output)

# A slow shipment must be refused by the hook, not cut off by Claude Code, which lets the command through.
settings = json.loads((hook.REPOSITORY_ROOT / ".claude" / "settings.json").read_text())
hook_timeouts = [entry.get("timeout") for group in settings["hooks"]["PreToolUse"] for entry in group["hooks"]
                 if HOOK_SCRIPT.name in entry.get("command", "")]
check("the hook's timeout in .claude/settings.json exceeds its shipping limit plus its worktree listing",
      len(hook_timeouts) == 1 and isinstance(hook_timeouts[0], (int, float))
      and hook_timeouts[0] > hook.SHIPPING_BUDGET_SECONDS + hook.GIT_TIMEOUT_SECONDS, hook_timeouts)

# A worktree path set by NAME=value has its records shipped before the removal.
checkout, worktree = checkout_with_worktree("assigned")
code, output = run_hook({"tool_name": "Bash", "cwd": str(checkout),
                         "tool_input": {"command": f'W={worktree}; git worktree remove --force "$W"'}})
check("a worktree named through NAME=value has its records shipped and the removal let through",
      code == 0 and output is None
      and (STORE / "cold-read-records" / "assigned-doc-2026-11-03" / "fast-read.md").is_file(), output)

# A path the hook cannot read is let through, unshipped, with a notice for the agent.
checkout, worktree = checkout_with_worktree("unread")
code, output = run_hook({"tool_name": "Bash", "cwd": str(checkout),
                         "tool_input": {"command": f"for w in {worktree.name}; do git worktree remove $w; done"}})
specific = (output or {}).get("hookSpecificOutput", {})
notice = specific.get("additionalContext", "")
check("a removal whose worktree path cannot be read is let through, with no permission decision",
      code == 0 and "permissionDecision" not in specific, output)
check("the notice says the path could not be read and the records were not shipped",
      notice.startswith("Not checked: the hook that ships a worktree's cold-read-records and sanity-check records "
                        "to the log-store before `git worktree remove` could not read $w in this command, so it did "
                        "not ship them, and let the command run.")
      and not (STORE / "cold-read-records" / "unread-doc-2026-11-03").exists(), notice)
check("the notice says what to do from now on",
      "From now on, write out the path of the worktree each `git worktree remove` removes, one command per "
      "worktree rather than a loop, or set the path earlier in the same command, as in "
      "`W=<path>; git worktree remove \"$W\"`, with no variable in <path>, so this hook can ship the "
      "worktree's records first." in notice, notice)
# The form the notice recommends is one this hook reads.
check("the notice's W=<path> form is read",
      removals('W=/a/wt; git worktree remove "$W"') == [("/work", "/a/wt", None)])
code, output = run_hook({"tool_name": "Bash", "cwd": str(checkout), "tool_input": {
    "command": f"for w in x; do git worktree remove $w; done; git worktree remove {worktree}"}},
    shippers_only(runner_answering(1, "FAILED: unread-doc-2026-11-03 — ned-box unreachable")))
check("a failed shipment is refused even when another removal in the command cannot be read",
      (refusal(output) or "").startswith("Refused on purpose:"), output)
for shipper in ("nc-systems/cold-read/cold-read-record-ship.py", "scripts/sanity-check-record-ship.py"):
    usage = subprocess.run([sys.executable, str(hook.REPOSITORY_ROOT / shipper), "--help"],
                           capture_output=True, text=True, check=False)
    check(f"{shipper}, which the parser-unavailable lines name, takes --all",
          f"python3 {shipper} --all" in hook.PARSER_UNAVAILABLE_NEXT_STEP_LINES and "--all" in usage.stdout,
          (usage.returncode, usage.stdout[-300:], usage.stderr))

check("a command with no removal is let through", run_hook({"tool_name": "Bash", "cwd": "/work",
                                                            "tool_input": {"command": "ls"}}) == (0, None))
check("another tool is let through", run_hook({"tool_name": "Write", "tool_input": {"file_path": "x"}}) == (0, None))
check("unreadable hook input is let through", run_hook("not json") == (0, None))

# The shell reader cannot run: the command is let through, and the agent is told what to do.
readings_as_written = hook.shell_reader.simple_commands


def unavailable(command, *arguments):
    raise hook.shell_reader.ShellParserUnavailable("tree-sitter-bash missing")


hook.shell_reader.simple_commands = unavailable
try:
    code, output = run_hook({"tool_name": "Bash", "cwd": "/work", "tool_input": {"command": "git worktree remove wt"}})
finally:
    hook.shell_reader.simple_commands = readings_as_written
specific = (output or {}).get("hookSpecificOutput", {})
check("when the shell reader cannot run, the command is let through with the next steps",
      code == 0 and "permissionDecision" not in specific
      and hook.PARSER_UNAVAILABLE_NEXT_STEP_LINES in specific.get("additionalContext", ""), output)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
