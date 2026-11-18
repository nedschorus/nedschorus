#!/usr/bin/env python3
"""Tests for scripts/project-rename-repository-contents-rewrite-hack.py, each on a scratch git checkout."""

import importlib.util
import os
import stat
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

PROGRAM = Path(__file__).resolve().parent / "project-rename-repository-contents-rewrite-hack.py"
failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name + ("" if condition else f": {detail}"))
    if not condition:
        failures.append(name)


def git(checkout, *arguments):
    return subprocess.run(["git", "-C", str(checkout), *arguments], capture_output=True, text=True, check=True).stdout


def scratch_checkout(files):
    checkout = Path(tempfile.mkdtemp(prefix="project-rename-rewrite-test-"))
    git(checkout, "init", "-q")
    for path, text in files.items():
        file = checkout / path
        file.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            file.write_bytes(text)
        else:
            file.write_text(text, encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "fixture")
    return checkout


def run(checkout, *arguments):
    return subprocess.run([sys.executable, str(PROGRAM), "--checkout", str(checkout), *arguments],
                          capture_output=True, text=True)


def read(checkout, path):
    return (checkout / path).read_text(encoding="utf-8")


MIXED = ("gh api repos/nedschorus/nedschorus/pulls; cd /home/nedlern/Projects/nedschorus/nc-systems/x; "
         "echo $NEDSCHORUS_AGENTS_ROOT\n")

# --- Each stage changes only its own names, on one mixed line ------------------------------------
for stage, expected in (
        ("1", "gh api repos/nedsnodes/nedsnodes/pulls; cd /home/nedlern/Projects/nedschorus/nc-systems/x; "
              "echo $NEDSCHORUS_AGENTS_ROOT\n"),
        ("2", "gh api repos/nedschorus/nedschorus/pulls; cd /home/nedlern/Projects/nedsnodes/nc-systems/x; "
              "echo $NEDSNODES_AGENTS_ROOT\n"),
        ("3", "gh api repos/nedschorus/nedschorus/pulls; cd /home/nedlern/Projects/nedschorus/nn-systems/x; "
              "echo $NEDSCHORUS_AGENTS_ROOT\n")):
    checkout = scratch_checkout({"scripts/mixed.sh": MIXED})
    result = run(checkout, "--stage", stage)
    check(f"stage {stage} alone changes only its own names on a mixed line",
          result.returncode == 0 and read(checkout, "scripts/mixed.sh") == expected,
          (result.stdout, result.stderr, read(checkout, "scripts/mixed.sh")))

# --- Anchoring: names that end in nc- or NC_ are left as they are --------------------------------
ANCHORS = ("def func-x(): pass  # sync-state async-io func-name fnc-x SYNC_LOCK ASYNC_MODE "
           "rsync_systems xnedschorus-logs funcNcSharedDatabase\n")
checkout = scratch_checkout({"scripts/anchors.py": ANCHORS})
for stage in ("1", "2", "3"):
    run(checkout, "--stage", stage)
check("sync-, async-, func-, fnc-, SYNC_ and names with an old name inside them are left unchanged",
      read(checkout, "scripts/anchors.py") == ANCHORS, read(checkout, "scripts/anchors.py"))

# --- Stage 3 moves the directories and nc-/nedschorus- files, and their citations follow -----------
checkout = scratch_checkout({
    "nc-systems/nc-shared-database/nc-shared-database-service.py":
        "NC_SHARED_DATABASE_FILE_PATH = Path.home() / '.local/state/nedschorus/nc-shared-database.sqlite3'\n"
        "TOKEN = '~/.config/nedschorus/nc-shared-database-service.token'\n"
        "BACKUP = f'nc-shared-database-{stamp}.sqlite3'\n"
        "class NcSharedDatabaseServiceCallFailed(Exception): pass\n"
        "nc_shared_database_event_send_single_attempt = 1\n",
    "docs/nedschorus-wiki/nedschorus-glossary.md": "- **nc-head-commit** — a term.\n",
    "nc-queue/README.md": "See docs/nedschorus-wiki/nedschorus-glossary.md and `nedschorus-glossary.md`.\n",
    "CLAUDE.md": "Read `docs/nedschorus-wiki/nedschorus-style-guide.md`; overview: "
                 "`docs/nedschorus-wiki/nedschorus-<system>-architecture-overview.md`; "
                 "proposals start `nedschorus-style-`.\n",
    "docs/nedschorus-wiki/nedschorus-style-guide.md": "style\n",
    "scripts/tool.py": 'PAGE = f"docs/nedschorus-wiki/nedschorus-{system}-architecture-overview.md"\n'
                       'TASKS = f"nedschorus-{seat}-tasks"\n',
})
result = run(checkout, "--stage", "3")
tracked = set(git(checkout, "ls-files").split())
check("stage 3 moves nc-systems, nc-queue, the wiki and the nc- and nedschorus- file names",
      result.returncode == 0 and {"nn-systems/nn-shared-database/nn-shared-database-service.py",
                                  "docs/nedsnodes-wiki/nedsnodes-glossary.md", "nn-queue/README.md",
                                  "docs/nedsnodes-wiki/nedsnodes-style-guide.md"} <= tracked,
      (result.stdout, result.stderr, sorted(tracked)))
service = read(checkout, "nn-systems/nn-shared-database/nn-shared-database-service.py")
check("stage 3 renames the nc- system names in code and the shared database's file, token and backup names, "
      "and leaves their directories to stage 2",
      "NN_SHARED_DATABASE_FILE_PATH" in service and "NnSharedDatabaseServiceCallFailed" in service
      and "nn_shared_database_event_send_single_attempt" in service
      and ".local/state/nedschorus/nn-shared-database.sqlite3" in service
      and "nedschorus/nn-shared-database-service.token" in service
      and "f'nn-shared-database-{stamp}.sqlite3'" in service, service)
check("stage 3 rewrites path citations, including a page cited by name alone and a page-name pattern",
      read(checkout, "nn-queue/README.md")
      == "See docs/nedsnodes-wiki/nedsnodes-glossary.md and `nedsnodes-glossary.md`.\n"
      and "`docs/nedsnodes-wiki/nedsnodes-<system>-architecture-overview.md`" in read(checkout, "CLAUDE.md")
      and "proposals start `nedsnodes-style-`." in read(checkout, "CLAUDE.md"),
      (read(checkout, "nn-queue/README.md"), read(checkout, "CLAUDE.md")))
check("stage 3 renames a wiki page template and leaves the task-list template to stage 2",
      read(checkout, "scripts/tool.py")
      == 'PAGE = f"docs/nedsnodes-wiki/nedsnodes-{system}-architecture-overview.md"\n'
         'TASKS = f"nedschorus-{seat}-tasks"\n', read(checkout, "scripts/tool.py"))
check("stage 3 leaves an nc- glossary term in prose", "nc-head-commit" in read(
    checkout, "docs/nedsnodes-wiki/nedsnodes-glossary.md"))

# --- A second run changes nothing; a file an open branch added under the old directory still moves --
git(checkout, "add", "-A")
git(checkout, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "stage 3")
second = run(checkout, "--stage", "3")
check("a second run of stage 3 changes nothing",
      second.returncode == 0 and git(checkout, "status", "--porcelain") == "", (second.stdout, git(checkout, "status")))
(checkout / "nc-systems" / "handoff").mkdir(parents=True)
(checkout / "nc-systems" / "handoff" / "new.py").write_text("import nc_systems\n", encoding="utf-8")
git(checkout, "add", "-A")
third = run(checkout, "--stage", "3")
check("a file added under nc-systems beside nn-systems moves into nn-systems",
      third.returncode == 0 and (checkout / "nn-systems/handoff/new.py").read_text() == "import nn_systems\n"
      and not (checkout / "nc-systems/handoff/new.py").exists(), (third.stdout, third.stderr))

# --- A path whose new name holds other content is refused, and the rest still moves ----------------
checkout = scratch_checkout({"nc-queue/a.md": "old a\n", "nn-queue/a.md": "new a\n", "nc-queue/b.md": "b\n"})
refused = run(checkout, "--stage", "3")
check("stage 3 refuses a move onto a path that holds other content, names it, and exits 1",
      refused.returncode == 1 and "nc-queue/a.md -> nn-queue/a.md" in refused.stdout
      and (checkout / "nn-queue/b.md").exists() and read(checkout, "nn-queue/a.md") == "new a\n",
      (refused.returncode, refused.stdout))

# --- Stage 1 leaves Markdown, kept paths and the skip list alone; modes survive --------------------
checkout = scratch_checkout({
    "README.md": "gh pr list --repo nedschorus/nedschorus\n",
    "scripts/merge-gate-test-captured-github-responses/x.json": '{"url": "repos/nedschorus/nedschorus"}\n',
    "scripts/project-rename-machine-state-move-hack.py": 'OLD_REPOSITORY = "nedschorus/nedschorus"\n',
    "docs/issues/1-a.md": "nc-systems/x and /home/nedlern/nedschorus-logs\n",
    "scripts/run.sh": "gh pr list --repo nedschorus/nedschorus\n",
    "scripts/binary.bin": b"\xff\xfe nedschorus/nedschorus\n",
})
os.chmod(checkout / "scripts/run.sh", 0o755)
for stage in ("1", "2", "3"):
    run(checkout, "--stage", stage)
check("stage 1 leaves Markdown, captured responses, the move program and non-UTF-8 files alone",
      read(checkout, "README.md") == "gh pr list --repo nedschorus/nedschorus\n"
      and "nedschorus/nedschorus" in read(checkout, "scripts/merge-gate-test-captured-github-responses/x.json")
      and "nedschorus/nedschorus" in read(checkout, "scripts/project-rename-machine-state-move-hack.py")
      and (checkout / "scripts/binary.bin").read_bytes() == b"\xff\xfe nedschorus/nedschorus\n")
check("stages 2 and 3 rewrite a GHI-MD file's paths like any other file's",
      read(checkout, "docs/issues/1-a.md") == "nn-systems/x and /home/nedlern/nedsnodes-logs\n",
      read(checkout, "docs/issues/1-a.md"))
check("a rewritten executable stays executable",
      read(checkout, "scripts/run.sh") == "gh pr list --repo nedsnodes/nedsnodes\n"
      and os.stat(checkout / "scripts/run.sh").st_mode & stat.S_IXUSR)

# --- Stage 2's machine names ----------------------------------------------------------------------
checkout = scratch_checkout({"scripts/jobs.py": (
    'LABEL = "com.nedschorus.clean-worktrees"\n'
    'LIST = task_lists / f"nedschorus-{agent_seat}-tasks"\n'
    'OTHER = task_lists / f"nedschorus-{given[\'agent_seat\']}-tasks"\n'
    'KEY = "-Users-el-Projects-nedschorus"\n'
    'CLONE = home / "Projects" / "nedschorus"\n'
    'WORKTREES = "~/Projects/nedschorus-worktrees"\n'
    'UNIT = "nc-shared-database-service.service"\n'
    'STATE = "~/.local/state/nedschorus/user-alerts"\n'
    'STATE_PARTS = Path.home() / ".local" / "state" / "nedschorus" / "user-alerts"\n'
    'VENV = Path.home() / ".local" / "share" / "nedschorus" / "cosmic-ray-venv"\n'
    'SHARED = "~/.local/share/nedschorus/x"\n'
    'CACHE = Path.home() / ".cache" / "nedschorus-markdown-commonmark-parser-install"\n'
    'INPUTS = "~/.cache/nedschorus-test-suite-recorded-inputs"\n'
    'DOC = "~/.claude/tasks/nedschorus-<seat>-tasks/"\n')})
run(checkout, "--stage", "2")
check("stage 2 renames labels, task lists, project keys, checkout paths, the unit, ~/.local/state, ~/.local/share "
      "and ~/.cache/nedschorus-*",
      read(checkout, "scripts/jobs.py") == (
          'LABEL = "com.nedsnodes.clean-worktrees"\n'
          'LIST = task_lists / f"nedsnodes-{agent_seat}-tasks"\n'
          'OTHER = task_lists / f"nedsnodes-{given[\'agent_seat\']}-tasks"\n'
          'KEY = "-Users-el-Projects-nedsnodes"\n'
          'CLONE = home / "Projects" / "nedsnodes"\n'
          'WORKTREES = "~/Projects/nedsnodes-worktrees"\n'
          'UNIT = "nn-shared-database-service.service"\n'
          'STATE = "~/.local/state/nedsnodes/user-alerts"\n'
          'STATE_PARTS = Path.home() / ".local" / "state" / "nedsnodes" / "user-alerts"\n'
          'VENV = Path.home() / ".local" / "share" / "nedsnodes" / "cosmic-ray-venv"\n'
          'SHARED = "~/.local/share/nedsnodes/x"\n'
          'CACHE = Path.home() / ".cache" / "nedsnodes-markdown-commonmark-parser-install"\n'
          'INPUTS = "~/.cache/nedsnodes-test-suite-recorded-inputs"\n'
          'DOC = "~/.claude/tasks/nedsnodes-<seat>-tasks/"\n'), read(checkout, "scripts/jobs.py"))

# --- The residue report ---------------------------------------------------------------------------
checkout = scratch_checkout({"a.py": "x = 1  # see nedschorus#418 and nc-head-commit\n"})
covered = run(checkout, "--residue-report")
check("the residue report exits 0 when the allowlist covers every old name, and counts each by reason",
      covered.returncode == 0 and "2 old-name matches covered" in covered.stdout, covered.stdout)
checkout = scratch_checkout({"a.py": "PATH = 'nc-systems/x'\n"})
uncovered = run(checkout, "--residue-report")
check("the residue report exits 1 and prints each old name no reason covers",
      uncovered.returncode == 1 and "a.py:1: PATH = 'nc-systems/x'" in uncovered.stdout, uncovered.stdout)

# --- A git failure is reported and exits 1 --------------------------------------------------------
not_a_checkout = Path(tempfile.mkdtemp(prefix="project-rename-rewrite-test-not-git-"))
failed = run(not_a_checkout, "--stage", "1")
check("a failing git command prints FAILED and exits 1",
      failed.returncode == 1 and "FAILED: git ls-files" in failed.stderr, (failed.returncode, failed.stderr))

fake_git_directory = Path(tempfile.mkdtemp(prefix="project-rename-rewrite-test-fake-git-"))
(fake_git_directory / "git").write_text("#!/bin/sh\nkill -9 $$\n", encoding="utf-8")
os.chmod(fake_git_directory / "git", 0o755)
killed = subprocess.run([sys.executable, str(PROGRAM), "--checkout", str(not_a_checkout), "--stage", "1"],
                        capture_output=True, text=True,
                        env={**os.environ, "PATH": f"{fake_git_directory}{os.pathsep}{os.environ['PATH']}"})
check("a git command killed by a signal is reported as a failure and exits 1",
      killed.returncode == 1 and "FAILED: git ls-files -z exited -9" in killed.stderr, (killed.returncode, killed.stderr))

checkout = scratch_checkout({"scripts/hook.py": 'GITHUB_REPOSITORY_OWNER = "nedschorus"\nGITHUB_REPOSITORY_NAME = "nedschorus"\n'})
run(checkout, "--stage", "1")
check("stage 1 renames the citation hook's owner and name constants together",
      read(checkout, "scripts/hook.py") == 'GITHUB_REPOSITORY_OWNER = "nedsnodes"\nGITHUB_REPOSITORY_NAME = "nedsnodes"\n',
      read(checkout, "scripts/hook.py"))

checkout = scratch_checkout({"scripts/reader.py": 'OLD_REPOSITORY = "nedschorus/nedschorus"\nNEW = "nedschorus/nedschorus"\n',
                             "scripts/gate.sh": "OLD_REPOSITORY=nedschorus/nedschorus\n"})
run(checkout, "--stage", "1")
check("stage 1 leaves the value of an OLD_REPOSITORY constant, so a rerun keeps the old name a reader accepts",
      read(checkout, "scripts/reader.py") == 'OLD_REPOSITORY = "nedschorus/nedschorus"\nNEW = "nedsnodes/nedsnodes"\n'
      and read(checkout, "scripts/gate.sh") == "OLD_REPOSITORY=nedschorus/nedschorus\n",
      (read(checkout, "scripts/reader.py"), read(checkout, "scripts/gate.sh")))
covered = run(checkout, "--residue-report")
check("the residue report covers an OLD_REPOSITORY constant's value",
      covered.returncode == 0, covered.stdout)

checkout = scratch_checkout({
    "nc-systems/x/tests/x-fixtures/nedschorus-capture.md": "cites nc-systems/x/x.py\n",
    "nc-systems/x/x.py": ('ROOT = tree + b"\\tnc-systems\\0"\n'
                          'BACKUPS = Path.home() / "backups" / "nc-shared-database"\n'
                          'REMOTE = "~/backups/nc-shared-database"\n'
                          'NAMES = [n for n in names if n.startswith("nc-shared-database-")]\n'
                          'LABEL = "LaunchAgents/com.nedsnodes.nc-shared-database-"\n'
                          'PAGE = "nedschorus-aardvark-architecture-overview.md"\n'
                          'SERVICE = "the nc-shared-database service"\n'
                          'EMAIL = "unconfigured-agent@nedschorus.invalid"\n')})
run(checkout, "--stage", "3")
check("stage 3 moves a kept fixture with its directory and keeps its name and content",
      read(checkout, "nn-systems/x/tests/x-fixtures/nedschorus-capture.md") == "cites nc-systems/x/x.py\n")
check("stage 3 renames a name after an escape in a string, and the backups' directory and name prefix",
      read(checkout, "nn-systems/x/x.py") == ('ROOT = tree + b"\\tnn-systems\\0"\n'
                                             'BACKUPS = Path.home() / "backups" / "nn-shared-database"\n'
                                             'REMOTE = "~/backups/nn-shared-database"\n'
                                             'NAMES = [n for n in names if n.startswith("nn-shared-database-")]\n'
                                             'LABEL = "LaunchAgents/com.nedsnodes.nn-shared-database-"\n'
                                             'PAGE = "nedsnodes-aardvark-architecture-overview.md"\n'
                                             'SERVICE = "the nn-shared-database service"\n'
                                             'EMAIL = "unconfigured-agent@nedschorus.invalid"\n'),
      read(checkout, "nn-systems/x/x.py"))

checkout = scratch_checkout({"scripts/x.py": ("NED_BOX_NC_SHARED_DATABASE_BACKUP_DIRECTORY = 1\n"
                                             "create_nc_shared_database_if_absent = old_nc_systems = 2\n"
                                             'SLICE = r"nc\\x2dtest\\x2dsuites.slice"\n')})
before = run(checkout, "--residue-report")
check("the residue report sees an old name inside a longer identifier and in systemd's escaped spelling",
      before.returncode == 1 and "scripts/x.py:1:" in before.stdout and "scripts/x.py:2:" in before.stdout
      and "scripts/x.py:3:" in before.stdout, before.stdout)
for stage in ("1", "2", "3"):
    run(checkout, "--stage", stage)
check("stage 3 renames a system name inside a longer identifier, and stage 2 the escaped slice name",
      read(checkout, "scripts/x.py") == ("NED_BOX_NN_SHARED_DATABASE_BACKUP_DIRECTORY = 1\n"
                                        "create_nn_shared_database_if_absent = old_nn_systems = 2\n"
                                        'SLICE = r"nn\\x2dtest\\x2dsuites.slice"\n'), read(checkout, "scripts/x.py"))

# --- Stage 3 beside a twin the branch already renamed -------------------------------------------
checkout = scratch_checkout({"nc-systems/x/a.py": "see nc-systems/x/b.py\n", "nn-systems/x/a.py": "see nn-systems/x/b.py\n"})
twin = run(checkout, "--stage", "3")
check("stage 3 removes an old path whose rewritten content equals its already-renamed twin",
      twin.returncode == 0 and not (checkout / "nc-systems/x/a.py").exists()
      and read(checkout, "nn-systems/x/a.py") == "see nn-systems/x/b.py\n", (twin.returncode, twin.stdout, twin.stderr))
checkout = scratch_checkout({"nc-systems/x/c.py": "c = 1\n"})
(checkout / "nn-systems/x/c.py").parent.mkdir(parents=True, exist_ok=True)
(checkout / "nn-systems/x/c.py").write_text("c = 1\n", encoding="utf-8")
run(checkout, "--stage", "3")
check("stage 3 adds to git an untracked new path that holds the old path's content, so a commit keeps the file",
      git(checkout, "ls-files", "--", "nn-systems/x/c.py").strip() == "nn-systems/x/c.py"
      and git(checkout, "ls-files", "--", "nc-systems/x/c.py").strip() == "", git(checkout, "status", "--short"))

# --- Stage 2 keeps the old task-list ID prefix a reader accepts -----------------------------------
checkout = scratch_checkout({"scripts/reader.py": 'TASK_LIST_ID_PREFIX_BEFORE_PROJECT_RENAME = "nedschorus-"\nPREFIX = "nedschorus-"\n'})
run(checkout, "--stage", "2")
check("stage 2 leaves the value of a TASK_LIST_ID_PREFIX_BEFORE_PROJECT_RENAME constant, so a reader keeps accepting the old prefix",
      read(checkout, "scripts/reader.py") == 'TASK_LIST_ID_PREFIX_BEFORE_PROJECT_RENAME = "nedschorus-"\nPREFIX = "nedsnodes-"\n',
      read(checkout, "scripts/reader.py"))
covered = run(checkout, "--residue-report")
check("the residue report covers a TASK_LIST_ID_PREFIX_BEFORE_PROJECT_RENAME constant's value", covered.returncode == 0, covered.stdout)

# --- A GHI-MD keeps its own file name and the old names its prose holds --------------------------
checkout = scratch_checkout({
    "docs/issues/7-a-fix-in-nc-systems-handoff.md": "See notes.nedschorus.com and the retired nedschorus-founding-plan.md.\n",
    "docs/issues/8-b.md": "Run nc-systems/handoff/x.py.\n",
})
for stage in ("1", "2", "3"):
    run(checkout, "--stage", stage)
covered = run(checkout, "--residue-report")
check("a GHI-MD keeps its file name and its prose's old names, and the residue report covers both",
      covered.returncode == 0
      and git(checkout, "ls-files", "--", "docs/issues/7-a-fix-in-nc-systems-handoff.md").strip()
      == "docs/issues/7-a-fix-in-nc-systems-handoff.md"
      and read(checkout, "docs/issues/8-b.md") == "Run nn-systems/handoff/x.py.\n",
      covered.stdout)

print(f"{len(failures)} failed" if failures else "all passed")
sys.exit(1 if failures else 0)
