#!/usr/bin/env python3
"""The scratch git repository the cold-read suites run their cells inside.

Not a test file, and not a program a seat runs: the cold-read suites beside
it load it. Its name ends `-test-fixture.py` rather than `-test.py` so
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

import os
import shutil
import subprocess
from pathlib import Path

# This fixture sits in nc-systems/cold-read/tests/; the system it copies is
# one directory up.
SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent

# The seed commit's author. One fixed name rather than a parameter: nothing
# reads it, and it points a scratch checkout left behind by a crashed run
# back at the fixture that made it. Each suite used to name itself here.
SEED_COMMIT_AUTHOR_NAME = "cold-read scratch repository test fixture"
SEED_COMMIT_AUTHOR_EMAIL = "test@test.invalid"

# Stripped from the environment git runs with, so a suite run directly with
# one of them set still builds its scratch repository here rather than in the
# repository the variable names, as a GIT_DIR run did to ned-box's shared
# clone on 2026-09-24. The list is scripts/run-all-test-suites.py's, which is
# the source; its docstring says what each one was measured to do.
GIT_REDIRECTING_ENVIRONMENT_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
)


def git(repository, *arguments):
    environment = dict(os.environ)
    for variable in GIT_REDIRECTING_ENVIRONMENT_VARIABLES:
        environment.pop(variable, None)
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
