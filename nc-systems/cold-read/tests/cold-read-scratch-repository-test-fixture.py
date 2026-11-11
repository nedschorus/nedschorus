#!/usr/bin/env python3
"""The scratch git repository the cold-read suites run their cells inside.

Not a test file, and not a program a seat runs: the cold-read suites beside
it load it, and so do the suites of the programs that run
cold-read-fast-read.py, through
cold_read_fast_read_scratch_repository_whose_stub_agy_answers_in_chat. Its name ends `-test-fixture.py` rather than `-test.py` so
scripts/run-all-test-suites.py, which finds suites with
`git ls-files -- '*-test.py'`, does not run it as a suite of its own — it
has no cases. The same ending keeps scripts/design-to-main/tests/
design-to-main-test-fixture.py out of that list.

WHY A COPY OF nc-systems/cold-read/ RATHER THAN AN IMPORT. The cold-read cells derive
the repository root -- the tree their stray-write detector runs
`git status` over -- from their own path. Copying the system into a
scratch tree is the only way to point that at a throwaway repository, so
every one of these suites runs its cell out of a copy.

WHY THIS MODULE EXISTS (user-ruled 2026-09-21, walk
md-skills-seat-open-decisions-2026-09-20 item 14). Six suites --
cold-read-agy-cell, cold-read-cell-common, cold-read-fast-read,
cold-read-grid, cold-read-restater-judge-cell and
cold-read-restater-judge-runner -- each carried their own
build_scratch_repository, 25 to 34 lines apiece, and nine statements were
the same in all six: the scripts copy, the .gitignore write, `init -b
main`, the four config and commit calls, and the return. The two comments
that record why -- the whole-directory copy and the maintenance.auto
switch -- were repeated six times with them, which is six places to fix a
reason that turns out to be wrong. The seeding is NOT shared and stays in
each suite: which file the suite writes, what goes in it, and which
prompts it copies differ suite by suite, and the ruling says each suite
keeps its own.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

# This fixture sits in nc-systems/cold-read/tests/; the system it copies is
# one directory up.
SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
GIT_OUTPUT_MODULE = (SYSTEM_DIRECTORY.parent / "general-tools"
                     / "git-machine-readable-output-runner-and-parser-common.py")

# The seed commit's author. One fixed name rather than a parameter: nothing
# reads it, and it points a scratch checkout left behind by a crashed run
# back at the fixture that made it. Each suite used to name itself here.
SEED_COMMIT_AUTHOR_NAME = "cold-read scratch repository test fixture"
SEED_COMMIT_AUTHOR_EMAIL = "test@test.invalid"

# The variables that redirect git, stripped from the environment git runs
# with, so a suite run directly with one of them set still builds its scratch
# repository here rather than in the repository the variable names. The
# cold-read cells load the same module from their copy of the system, so it is
# copied into every scratch repository too.
GIT_REDIRECTING_REMOVAL_MODULE = (
    SYSTEM_DIRECTORY.parent / "general-tools"
    / "git-redirecting-environment-variables-removal-common.py")
_git_redirecting_removal_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_variables_removal_common", GIT_REDIRECTING_REMOVAL_MODULE)
git_redirecting_removal = importlib.util.module_from_spec(_git_redirecting_removal_spec)
_git_redirecting_removal_spec.loader.exec_module(git_redirecting_removal)
GIT_REDIRECTING_ENVIRONMENT_VARIABLES = git_redirecting_removal.GIT_REDIRECTING_ENVIRONMENT_VARIABLES
# cold-read-grid.py reads ned-box's home and the Mac's mount of it from this module.
NED_BOX_HOME_MODULE = (
    SYSTEM_DIRECTORY.parent / "general-tools" / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
# cold-read-claude-cell.py starts its claude command line from this module.
CLAUDE_CODE_COMMAND_LINE_PREFIX_MODULE = (
    SYSTEM_DIRECTORY.parent / "general-tools"
    / "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")


def git(repository, *arguments):
    environment = git_redirecting_removal.environment_without_git_redirecting_variables()
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True, text=True, check=False, env=environment,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {completed.stderr.strip()}")
    return completed.stdout


def commit_seeded_cold_read_scratch_repository(repository):
    """Turn a seeded scratch tree into the git repository a cell runs in.

    Call it AFTER writing this suite's own seed files into `repository`:
    it copies nc-systems/cold-read/ in, writes the ignore file, and commits the whole
    tree, seed files included, as `seed`. Returns `repository`.
    """
    # The whole nc-systems/cold-read/ directory, __pycache__ aside, so a shared module
    # added tomorrow needs no edit here (user-ruled 2026-09-20, walk
    # md-skills-seat-open-decisions-2026-09-20 item 3).
    shutil.copytree(SYSTEM_DIRECTORY, repository / "nc-systems" / "cold-read",
                    ignore=shutil.ignore_patterns("__pycache__"))
    # The cell reads git status through the shared git-output module, and
    # cold-read-fast-read.py strips the variables that redirect git through
    # the shared removal module.
    (repository / "nc-systems" / "general-tools").mkdir(parents=True)
    shutil.copy2(GIT_OUTPUT_MODULE, repository / "nc-systems" / "general-tools")
    shutil.copy2(GIT_REDIRECTING_REMOVAL_MODULE, repository / "nc-systems" / "general-tools")
    shutil.copy2(NED_BOX_HOME_MODULE, repository / "nc-systems" / "general-tools")
    shutil.copy2(CLAUDE_CODE_COMMAND_LINE_PREFIX_MODULE, repository / "nc-systems" / "general-tools")
    # The records tree is gitignored in the real repository, which is what
    # keeps a reviewer's own report out of the detector's sight.
    (repository / ".gitignore").write_text("cold-read-records/\n", encoding="utf-8")
    git(repository, "init", "-b", "main")
    # Auto maintenance off: with the whole scripts/ directory committed (as it
    # was until the cold read moved into nc-systems/cold-read/ on 2026-09-23), git
    # 2.55 repacks this repository in the background, and its temporary files
    # race the deletion of these throwaway checkouts — measured 2026-09-20,
    # a FileNotFoundError on a `bitmap-ref-tips` file inside shutil.rmtree.
    git(repository, "config", "maintenance.auto", "false")
    git(repository, "config", "user.email", SEED_COMMIT_AUTHOR_EMAIL)
    git(repository, "config", "user.name", SEED_COMMIT_AUTHOR_NAME)
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "seed")
    return repository


# A stub `agy` that answers in chat, long enough for the cell to keep the
# answer as the report, and a stub `claude` that fails, so no model starts.
# agy prints stream-json, and the cell takes the chat answer only from its result line.
STUB_AGY_ANSWERING_IN_CHAT = """#!/usr/bin/env python3
import json, sys
answer = " ".join(f"word{index}" for index in range(150)) + "\\n"
sys.stdout.write(json.dumps({"event": "result", "result": {
    "conversation_id": "", "status": "SUCCESS", "response": answer, "error": ""}}) + "\\n")
"""
STUB_CLAUDE_FAILING = """#!/usr/bin/env python3
import sys
sys.stderr.write("stub claude: no model in a test\\n")
sys.exit(1)
"""


def cold_read_fast_read_scratch_repository_whose_stub_agy_answers_in_chat(scratch, ship_destination):
    """A scratch repository holding a copy of nc-systems/cold-read/, and the
    environment under which that copy's cold-read-fast-read.py reads a
    document with stub models and ships its record to `ship_destination`.
    Returns (the copy's cold-read-fast-read.py, that environment), the path
    resolved, because the copy derives its record directory from its own
    resolved path, and a temporary directory can sit under a symlink, as
    /var/folders does under /private on the Mac."""
    scratch = Path(scratch).resolve()
    repository = scratch / "fast-read-scratch-checkout"
    repository.mkdir(parents=True)
    commit_seeded_cold_read_scratch_repository(repository)
    stubs = scratch / "fast-read-stub-models"
    stubs.mkdir()
    for name, text in (("agy", STUB_AGY_ANSWERING_IN_CHAT), ("claude", STUB_CLAUDE_FAILING)):
        (stubs / name).write_text(text, encoding="utf-8")
        (stubs / name).chmod(0o755)
    install_fake_sandbox_programs(stubs)
    # The agy cell scans HOME for credential files at launch, and the real home takes seconds to walk.
    home = scratch / "fast-read-scratch-home"
    home.mkdir()
    environment = dict(os.environ, HOME=str(home),
                       PATH=f"{stubs}{os.pathsep}{os.environ.get('PATH', '')}",
                       COLD_READ_RECORD_SHIP_DESTINATION=str(ship_destination))
    # A suite run inside an agent-session must not write that session's ID beside the report.
    environment.pop("CLAUDE_CODE_SESSION_ID", None)
    return repository / "nc-systems" / "cold-read" / "cold-read-fast-read.py", environment


# A stand-in for bwrap and sandbox-exec, so a suite whose program starts one
# of them can run inside the nc-test-sandbox, where the real bwrap cannot
# start. It confines nothing: it checks the options it is given, applies
# --chdir, --clearenv, --setenv and --unsetenv in order, runs the command at the source of a bind whose
# destination is the command's path, and replaces itself with the command, so
# exit codes, signals and child processes pass through as they would. An
# option it does not know fails the run, so a sandbox prefix that gains one
# shows up here. Whether the real sandbox keeps a file out is tested only by
# the suites in SUITES_RUN_WITHOUT_ANY_SANDBOX that run the real program.
# FAKE_SANDBOX_PROGRAM_ARGV_LOG, when set, is a file each launch appends its
# argv to, one JSON list per line.
FAKE_SANDBOX_PROGRAM_PASSING_THE_COMMAND_THROUGH = r'''import json, os, sys
name = os.path.basename(sys.argv[0])
arguments = sys.argv[1:]
log = os.environ.get("FAKE_SANDBOX_PROGRAM_ARGV_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps([name, *arguments]) + "\n")
environment = dict(os.environ)
binds = {}
directory = None
if name == "sandbox-exec":
    taking_value = {"-p", "-f", "-n", "-D"}
    while arguments and arguments[0] in taking_value:
        arguments = arguments[2:]
elif name == "bwrap":
    no_value = {"--unshare-user", "--unshare-user-try", "--unshare-ipc", "--unshare-pid",
                "--unshare-net", "--unshare-uts", "--unshare-cgroup", "--unshare-cgroup-try",
                "--unshare-all", "--share-net", "--clearenv", "--new-session",
                "--die-with-parent", "--as-pid-1"}
    one_value = {"--tmpfs", "--dev", "--proc", "--dir", "--chdir", "--remount-ro",
                 "--mqueue", "--unsetenv", "--hostname", "--uid", "--gid", "--perms", "--size",
                 "--cap-add", "--cap-drop", "--argv0", "--lock-file"}
    two_values = {"--bind", "--bind-try", "--dev-bind", "--dev-bind-try", "--ro-bind",
                  "--ro-bind-try", "--symlink", "--setenv", "--chmod"}
    while arguments and arguments[0].startswith("--"):
        option = arguments[0]
        if option in no_value:
            # bwrap clears the environment where --clearenv stands, so a later --setenv still holds.
            if option == "--clearenv":
                environment.clear()
            arguments = arguments[1:]
        elif option in one_value and len(arguments) >= 2:
            if option == "--chdir":
                directory = arguments[1]
            elif option == "--unsetenv":
                environment.pop(arguments[1], None)
            arguments = arguments[2:]
        elif option in two_values and len(arguments) >= 3:
            if option == "--setenv":
                environment[arguments[1]] = arguments[2]
            elif option != "--symlink" and option != "--chmod":
                binds[arguments[2]] = arguments[1]
            arguments = arguments[3:]
        else:
            sys.exit(f"fake {name}: option {option} is unknown to this test stand-in, "
                     "or lacks its values; add it to the fake's option lists")
else:
    sys.exit(f"fake sandbox program: started as {name!r}, expected bwrap or sandbox-exec")
if not arguments:
    sys.exit(f"fake {name}: no command after the options")
command = [binds.get(arguments[0], arguments[0]), *arguments[1:]]
if directory is not None:
    os.makedirs(directory, exist_ok=True)
    os.chdir(directory)
os.execvpe(command[0], command, environment)
'''


def install_fake_sandbox_programs(directory):
    """Write the pass-through stand-ins for bwrap and sandbox-exec into
    `directory`, which the caller puts on PATH ahead of the real ones.
    Returns `directory`. The first line names this Python by its full path,
    so a stand-in started with a PATH that holds no python3 still runs."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("bwrap", "sandbox-exec"):
        (directory / name).write_text(
            f"#!{sys.executable}\n" + FAKE_SANDBOX_PROGRAM_PASSING_THE_COMMAND_THROUGH,
            encoding="utf-8")
        (directory / name).chmod(0o755)
    return directory
