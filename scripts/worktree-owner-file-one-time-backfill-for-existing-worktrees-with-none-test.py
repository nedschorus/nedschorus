#!/usr/bin/env python3
"""Tests for scripts/worktree-owner-file-one-time-backfill-for-existing-worktrees-with-none.py.

Run: python3 scripts/worktree-owner-file-one-time-backfill-for-existing-worktrees-with-none-test.py
Prints one line per case and exits non-zero if any case fails. Each case runs the program on a
throwaway clone with HOME pointed at a scratch directory holding the agent-seats' directories and
handoff records, so it reads no real agent-seat.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).resolve().with_name(
    "worktree-owner-file-one-time-backfill-for-existing-worktrees-with-none.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def main():
    root = Path(tempfile.mkdtemp(prefix="worktree-owner-file-backfill-test-")).resolve()
    try:
        run_cases(root)
    finally:
        for directory in root.rglob("*"):
            if directory.is_dir() and not directory.is_symlink():
                directory.chmod(0o755)
        shutil.rmtree(root, ignore_errors=True)
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


def run_cases(root):
    home = root / "home"
    clone = home / "Projects" / "nedschorus"
    agents = home / "agents"
    handoffs = home / ".claude" / "handoffs"
    handoffs.mkdir(parents=True)
    for seat in ("seat", "seat-long"):
        (handoffs / f"{seat}-handoff.md").write_text("handoff\n")
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("GIT_", "NEDSCHORUS_"))}
    environment.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1",
                       GIT_CONFIG_GLOBAL=str(root / "empty-gitconfig"))
    (root / "empty-gitconfig").write_text("")

    def git(*arguments, cwd=clone):
        return subprocess.run(["git", *arguments], cwd=cwd, env=environment,
                              capture_output=True, text=True, check=True).stdout

    clone.mkdir(parents=True)
    git("init", "--quiet", "--initial-branch=main")
    git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "--quiet", "--allow-empty", "-m", "base")
    git("remote", "add", "origin", str(root / "never-fetched-origin"))
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    worktrees = {}

    def add(name, path):
        git("worktree", "add", "--quiet", "-b", f"branch-{name}", str(path))
        worktrees[name] = path
        return path

    add("agent-home", agents / "seat")
    add("long-agent-home", agents / "seat-long")
    add("topic", agents / "seat-d2m-wording")
    add("seat-worktrees", agents / "seat-worktrees" / "topic")
    add("longest", agents / "seat-long-worktrees" / "topic")
    add("unmatched", agents / "ghi-32-edit")
    (agents / "ghi-32-edit" / "notes.txt").write_text("uncommitted\n")
    add("outside", root / "elsewhere" / "wt")
    (clone / ".git" / "info").mkdir(exist_ok=True)
    (clone / ".git" / "info" / "exclude").write_text("ignored-state.json\n")
    (root / "elsewhere" / "wt" / "ignored-state.json").write_text("{}\n")
    git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "--quiet", "--allow-empty", "-m", "unlanded", cwd=worktrees["outside"])
    add("upstream", root / "elsewhere" / "with-upstream")
    git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "--quiet", "--allow-empty", "-m", "pushed", cwd=worktrees["upstream"])
    git("update-ref", "refs/remotes/origin/branch-upstream", "HEAD", cwd=worktrees["upstream"])
    git("config", "branch.branch-upstream.remote", "origin")
    git("config", "branch.branch-upstream.merge", "refs/heads/branch-upstream")
    git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "--quiet", "--allow-empty", "-m", "unpushed", cwd=worktrees["upstream"])
    git("worktree", "add", "--quiet", "--detach", str(root / "elsewhere" / "detached"))
    worktrees["detached"] = root / "elsewhere" / "detached"
    add("review", home / ".cache" / "merge-lane-review-worktrees" / "pr12-head")
    subagent_ids = {"locked-subagent": "a45a189e6c5e2e31e", "one-seat-subagent": "a0000000000000001",
                    "no-seat-subagent": "a0000000000000002", "two-seat-subagent": "a0000000000000003",
                    "hand-locked-subagent": "a0000000000000004"}
    for name, agent_id in subagent_ids.items():
        add(name, clone / ".claude" / "worktrees" / f"agent-{agent_id}")
    git("worktree", "lock", "--reason", f"claude agent agent-{subagent_ids['locked-subagent']} "
        f"(pid 1 start 1)", str(worktrees["locked-subagent"]))
    git("worktree", "lock", "--reason", "kept by hand", str(worktrees["hand-locked-subagent"]))

    def transcript(seat, agent_id):
        project = home / ".claude" / "projects" / re.sub(r"[^a-zA-Z0-9]", "-",
                                                         str((agents / seat).resolve()))
        (project / "session" / "subagents").mkdir(parents=True, exist_ok=True)
        (project / "session" / "subagents" / f"agent-{agent_id}.jsonl").write_text("{}\n")

    transcript("seat", subagent_ids["one-seat-subagent"])
    transcript("seat", subagent_ids["two-seat-subagent"])
    transcript("seat-long", subagent_ids["two-seat-subagent"])
    transcript("seat", subagent_ids["locked-subagent"])
    add("restored", clone / ".claude" / "worktrees" / "restored-agent-a45a189e6c5e2e31e")
    add("short-agent-id", clone / ".claude" / "worktrees" / "agent-a45a189e6c5e2e31")
    add("owned", agents / "seat-owned")
    add("unreadable", agents / "seat-unreadable")
    add("unwritable", agents / "seat-unwritable")

    def owner_file(name):
        located = git("rev-parse", "--absolute-git-dir", cwd=worktrees[name]).strip()
        return Path(located) / "worktree-owner.json"

    def owner(name):
        path = owner_file(name)
        return json.loads(path.read_text()) if path.is_file() else None

    owner_file("owned").write_text(json.dumps({"owner_kind": "agent-seat", "agent_seat": "seat-long"}))
    owner_file("unreadable").write_text("{not json")

    def run(*arguments):
        return subprocess.run([sys.executable, str(PROGRAM), "--repo", str(clone), *arguments],
                              env=environment, capture_output=True, text=True, check=False)

    def line_of(output, name):
        return next((line for line in output.splitlines()
                     if line.startswith(f"{worktrees[name]}:")), "")

    report = run()
    check("without --write it says what --write would write, and writes nothing",
          "--write gives it an owner file naming the agent-seat seat, since seat's name begins "
          "seat-d2m-wording" in line_of(report.stdout, "topic")
          and owner("topic") is None and owner("seat-worktrees") is None,
          report.stdout + report.stderr)

    git_directory = owner_file("unwritable").parent
    git_directory.chmod(0o500)
    try:
        written = run("--write")
    finally:
        git_directory.chmod(0o755)
    output = written.stdout
    check("a topic worktree beside the agent-homes names the agent-seat whose name begins its name",
          owner("topic") == {"owner_kind": "agent-seat", "agent_seat": "seat"}, output)
    check("a worktree in <agent-seat>-worktrees names that agent-seat",
          owner("seat-worktrees") == {"owner_kind": "agent-seat", "agent_seat": "seat"}, output)
    check("the longest agent-seat name that begins the directory's name is named",
          owner("longest") == {"owner_kind": "agent-seat", "agent_seat": "seat-long"}, output)
    check("an agent-home, a merge-lane review checkout and a worktree with an owner file are left "
          "alone, silently",
          owner("agent-home") is None and owner("long-agent-home") is None
          and owner("review") is None
          and owner("owned") == {"owner_kind": "agent-seat", "agent_seat": "seat-long"}
          and not any(line_of(output, name)
                      for name in ("agent-home", "long-agent-home", "review", "owned")), output)
    check("a locked subagent's worktree is given none, even when one agent-seat's transcripts "
          "name its subagent, and named with why, not listed for the user",
          owner("locked-subagent") is None
          and "given no owner file, since it is a locked Claude Code subagent's worktree; "
          in line_of(output, "locked-subagent")
          and "for the user" not in line_of(output, "locked-subagent"), output)
    if sys.platform.startswith("linux"):
        check("a locked subagent's worktree whose lock names an ended claude process is named with "
              "what the cleaner's next --remove does: unlock it, first writing the owner file",
              "the next scripts/clean-worktrees.py --remove unlocks it, first giving it an owner "
              "file naming the agent-seat seat, whose Claude Code transcripts name its subagent, "
              "since Claude Code's lock names claude process 1"
              in line_of(output, "locked-subagent"), output)
    check("a subagent's worktree locked in another form is named with the cleaner keeping it",
          owner("hand-locked-subagent") is None
          and "scripts/clean-worktrees.py --remove keeps it, so nothing needs doing now: locked "
              "with git worktree lock (kept by hand)" in line_of(output, "hand-locked-subagent"),
          output)
    check("an unlocked subagent's worktree whose subagent one agent-seat's transcripts name is "
          "given an owner file naming that agent-seat",
          owner("one-seat-subagent") == {"owner_kind": "agent-seat", "agent_seat": "seat"}
          and "owner file written, naming the agent-seat seat, since seat's Claude Code transcripts "
              f"name its subagent agent-{subagent_ids['one-seat-subagent']}"
          in line_of(output, "one-seat-subagent"), output)
    check("an unlocked subagent's worktree whose subagent no agent-seat's transcripts name is "
          "listed for the user",
          owner("no-seat-subagent") is None
          and "no agent-seat's Claude Code transcripts name its subagent "
              f"agent-{subagent_ids['no-seat-subagent']}; for the user to keep or delete"
          in line_of(output, "no-seat-subagent"), output)
    check("an unlocked subagent's worktree whose subagent two agent-seats' transcripts name is "
          "listed for the user, naming both",
          owner("two-seat-subagent") is None
          and "the Claude Code transcripts of 2 agent-seats, seat, seat-long, name its subagent "
              f"agent-{subagent_ids['two-seat-subagent']}; for the user to keep or delete"
          in line_of(output, "two-seat-subagent"), output)
    check("a worktree for the user is named with its uncommitted, untracked and ignored files, "
          "the commits origin/main lacks, and whether its branch is merged",
          line_of(output, "unmatched").endswith(
              "for the user to keep or delete: 1 uncommitted, untracked or ignored file(s); "
              "0 commit(s) origin/main lacks; its branch branch-unmatched is merged into "
              "origin/main")
          and line_of(output, "outside").endswith(
              "1 uncommitted, untracked or ignored file(s); 1 commit(s) origin/main lacks; its "
              "branch branch-outside is not merged into origin/main"), output)
    check("a worktree whose branch has an upstream is named with the commits its upstream lacks",
          line_of(output, "upstream").endswith(
              "1 commit(s) origin/branch-upstream lacks; its branch branch-upstream is not merged "
              "into origin/main"), output)
    check("a worktree on a detached HEAD is named with the commits origin/main lacks and no branch",
          line_of(output, "detached").endswith(
              "0 commit(s) origin/main lacks; on a detached HEAD, so no branch to merge"), output)
    check("the list is followed by how to keep a worktree for the user",
          "To keep one, do nothing: scripts/clean-worktrees.py never removes a listed worktree "
          "while it has no owner file.\n" in output, output)
    check("the list ends with the two commands that delete one worktree for the user",
          "  scripts/worktree-owner-file-read-and-write.py write --agent-seat <agent-seat> "
          "--worktree <worktree>\n"
          f"  scripts/clean-worktrees.py --repo {clone} "
          "--remove-worktree-and-force-delete-its-branch <worktree>\n" in output, output)
    check("a restored-* worktree, or an agent-a one without 16 hex digits, in .claude/worktrees is "
          "not taken for a subagent's: it is listed for the user",
          all(owner(name) is None
              and "for the user to keep or delete" in line_of(output, name)
              and "subagent" not in line_of(output, name)
              for name in ("restored", "short-agent-id")), output)
    for_the_user_line = next((line for line in output.splitlines()
                              if "worktree(s) for the user to keep or delete" in line), "")
    listed_for_the_user = ("outside", "upstream", "detached", "unmatched", "restored",
                           "short-agent-id", "no-seat-subagent", "two-seat-subagent")
    check("worktrees owned by no agent-seat the program can tell are given none and listed for "
          "the user",
          owner("unmatched") is None and owner("outside") is None
          and for_the_user_line.startswith(f"{len(listed_for_the_user)} worktree(s) for the user "
                                           "to keep or delete, owned by no agent-seat this "
                                           "program can tell: ")
          and all(str(worktrees[name]) in for_the_user_line for name in listed_for_the_user),
          output)
    check("an owner file that cannot be read is named on a FAILED line",
          "FAILED, its owner file could not be read" in line_of(output, "unreadable"), output)
    check("an owner file that cannot be written is named on a FAILED line, and the others are "
          "still written, with exit 1",
          written.returncode == 1 and owner("unwritable") is None
          and "FAILED, its owner file could not be written" in line_of(output, "unwritable")
          and owner("topic") is not None, output)
    check("the last line names every worktree whose owner file could not be read or written",
          f"FAILED: the owner files of 2 worktree(s) could not be read or written, as their lines "
          f"above say: {worktrees['unreadable']}, {worktrees['unwritable']}" in output, output)

    again = run("--write")
    check("a second --write writes only the owner file the first could not write",
          [line for line in again.stdout.splitlines() if "owner file written" in line]
          == [line_of(again.stdout, "unwritable")] and owner("unwritable") is not None,
          again.stdout)
    check("an owner file that cannot be read alone still exits 1",
          again.returncode == 1 and "FAILED: the owner files of 1 worktree(s)" in again.stdout,
          again.stdout)
    failing_git = root / "failing-git"
    failing_git.mkdir()
    (failing_git / "git").write_text(
        "#!/bin/sh\n"
        'case " $* " in *" worktree list "*) echo "listing refused" >&2; exit 1 ;; esac\n'
        f'exec {shutil.which("git")} "$@"\n')
    (failing_git / "git").chmod(0o755)
    unlisted = subprocess.run(
        [sys.executable, str(PROGRAM), "--repo", str(clone)],
        env={**environment, "PATH": f"{failing_git}{os.pathsep}{environment['PATH']}"},
        capture_output=True, text=True, check=False)
    check("git failing to list the worktrees is reported, with exit 2",
          unlisted.returncode == 2 and "git could not list the worktrees" in unlisted.stderr
          and "listing refused" in unlisted.stderr, unlisted.stderr)
    facts_failing_git = root / "facts-failing-git"
    facts_failing_git.mkdir()
    (facts_failing_git / "git").write_text(
        "#!/bin/sh\n"
        'case " $* " in\n'
        '  *" status "*) echo "facts refused" >&2; exit 1 ;;\n'
        f'  *"@{{upstream}}"*) case " $* " in *" {worktrees["upstream"]} "*) kill -9 $$ ;; esac ;;\n'
        '  *" rev-list "*) printf "rev-list\\nrefused" >&2\n'
        f'    case " $* " in *" {worktrees["outside"]} "*) kill -9 $$ ;; esac; exit 1 ;;\n'
        '  *" merge-base "*) case " $* " in *" refs/heads/branch-outside "*) kill -9 $$ ;; esac\n'
        '    exit 128 ;;\n'
        'esac\n'
        f'exec {shutil.which("git")} "$@"\n')
    (facts_failing_git / "git").chmod(0o755)
    unread_facts = subprocess.run(
        [sys.executable, str(PROGRAM), "--repo", str(clone)],
        env={**environment, "PATH": f"{facts_failing_git}{os.pathsep}{environment['PATH']}"},
        capture_output=True, text=True, check=False)
    check("a fact git cannot read, or whose git a signal kills, is printed as unknown, with git's "
          "exit code and error on one line",
          "for the user to keep or delete: uncommitted, untracked or ignored files unknown "
          "(facts refused); "
          "how many commits its HEAD has that origin/main lacks is unknown (git rev-list exited 1: rev-list "
          "refused); whether its branch branch-unmatched"
          in line_of(unread_facts.stdout, "unmatched")
          and "how many commits its HEAD has that origin/main lacks is unknown (git rev-list exited -9: rev-list "
              "refused); whether its branch branch-outside"
          in line_of(unread_facts.stdout, "outside"), unread_facts.stdout + unread_facts.stderr)
    check("a merge check git cannot make is printed as unknown, never as not merged, and a git "
          "error with no text says so",
          line_of(unread_facts.stdout, "unmatched").endswith(
              "whether its branch branch-unmatched is merged into origin/main is unknown (git "
              "merge-base --is-ancestor exited 128: no error text)")
          and "not merged" not in line_of(unread_facts.stdout, "unmatched"), unread_facts.stdout)
    check("a merge check whose git a signal kills is printed as unknown, never as merged",
          line_of(unread_facts.stdout, "outside").endswith(
              "whether its branch branch-outside is merged into origin/main is unknown (git "
              "merge-base --is-ancestor exited -9: no error text)"), unread_facts.stdout)
    check("a branch whose upstream git cannot read is compared with origin/main",
          "how many commits its HEAD has that origin/main lacks is unknown (git rev-list exited 1: rev-list "
          "refused); whether its branch branch-upstream"
          in line_of(unread_facts.stdout, "upstream"), unread_facts.stdout)
    refused = run("--remove")
    check("an unknown argument is refused with exit 2", refused.returncode == 2, refused.stderr)
    not_a_repository = subprocess.run(
        [sys.executable, str(PROGRAM), "--repo", str(root / "elsewhere-not-a-repository")],
        env=environment, capture_output=True, text=True, check=False)
    check("a --repo that is not a git repository is refused with exit 2",
          not_a_repository.returncode == 2 and "is not a git repository" in not_a_repository.stderr,
          not_a_repository.stderr)


if __name__ == "__main__":
    sys.exit(main())
