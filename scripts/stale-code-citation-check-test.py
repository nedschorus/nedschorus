#!/usr/bin/env python3
"""Tests for stale-code-citation-check.py.

Run: python3 scripts/stale-code-citation-check-test.py

Each case builds a throwaway git repository with commits at controlled dates
and runs the program as a subprocess inside it, because what is under test is
the pairing of a real git history with scripts/md-drift-lint.py's resolution
of a citation. Both scripts are copied into the throwaway repository, since
the program reads its repository root from its own location.

Every check is demonstrated both ways: once where it must fire and once where
it must not. A detector that reports nothing anywhere would pass half a suite.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PROGRAM = SCRIPTS / "stale-code-citation-check.py"
LINT = SCRIPTS / "md-drift-lint.py"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(root: Path, *arguments, date=None):
    environment = dict(os.environ)
    environment.update({
        "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
    })
    if date is not None:
        stamp = f"{date}T12:00:00+00:00"
        environment["GIT_AUTHOR_DATE"] = stamp
        environment["GIT_COMMITTER_DATE"] = stamp
    completed = subprocess.run(["git", *arguments], cwd=str(root), env=environment,
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0 and arguments[0] not in ("rev-parse", "check-ignore"):
        raise AssertionError(f"git {' '.join(arguments)}: {completed.stderr}")
    return completed.stdout.strip()


def new_repository(workspace: str) -> Path:
    """A repository holding the two scripts, committed before every test date."""
    root = Path(workspace)
    (root / "scripts").mkdir()
    shutil.copy(PROGRAM, root / "scripts" / PROGRAM.name)
    shutil.copy(LINT, root / "scripts" / LINT.name)
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "scripts", date="2026-01-01")
    return root


def write_code(root: Path, name: str, body: str, date: str):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    git(root, "add", "--", name)
    git(root, "commit", "-q", "-m", f"code {name}", date=date)


def write_document(root: Path, name: str, text: str, date="2026-01-02", commit=True):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if commit:
        git(root, "add", "--", name)
        git(root, "commit", "-q", "-m", f"document {name}", date=date)
    return path


def run(root: Path, *arguments):
    completed = subprocess.run(
        [sys.executable, str(root / "scripts" / PROGRAM.name), *arguments],
        cwd=str(root), capture_output=True, text=True, check=False)
    return completed.returncode, completed.stdout, completed.stderr


def document(stamp="2026-05-01", status="design", body=""):
    return f"---\nstatus: {status}\ndesign-as-of: {stamp}\n---\n\n# A design\n\n{body}\n"


CODE = "".join(f"line {n}\n" for n in range(1, 61))


# --- The cited file's history since the stamp is the key ------------------
with tempfile.TemporaryDirectory() as workspace:
    root = new_repository(workspace)
    write_code(root, "scripts/moved.py", CODE, date="2026-06-01")
    write_code(root, "scripts/settled.py", CODE, date="2026-04-01")
    write_code(root, "scripts/same-day.py", CODE, date="2026-05-01")

    moved = write_document(root, "docs/moved.md",
                           document(body="The test is `scripts/moved.py` lines 20-24."))
    citation_line = next(
        number for number, line in enumerate(moved.read_text().splitlines(), 1)
        if "lines 20-24" in line)
    code, out, err = run(root, "docs/moved.md")
    check("a cited file that changed after the stamp is reported",
          code == 1 and f"docs/moved.md:{citation_line}: " in out
          and "lines 20-24" in out, f"{code} {out} {err}")
    check("the finding is anchored to the citation's own line in the document",
          f"docs/moved.md:{citation_line}: scripts/moved.py changed 2026-06-01" in out,
          out)

    write_document(root, "docs/settled.md",
                   document(body="The test is `scripts/settled.py` lines 20-24."))
    code, out, err = run(root, "docs/settled.md")
    check("a cited file that last changed before the stamp is not reported",
          code == 0 and out == "", f"{code} {out}")

    write_document(root, "docs/same-day.md",
                   document(body="The test is `scripts/same-day.py` lines 20-24."))
    code, out, err = run(root, "docs/same-day.md")
    check("a cited file that changed on the stamp's own day is not reported",
          code == 0 and out == "", f"{code} {out}")

    # The document's own history is NOT the key: this is the 413 case, where
    # nobody edited the document and the code moved underneath it.
    untouched = write_document(root, "docs/untouched.md",
                               document(body="See `scripts/moved.py` lines 3-5."),
                               date="2026-04-02")
    code, out, err = run(root, "docs/untouched.md")
    check("a document nobody edited is reported when its cited code moved",
          code == 1 and "lines 3-5" in out, f"{code} {out}")


# --- Which citation shapes are read ---------------------------------------
with tempfile.TemporaryDirectory() as workspace:
    root = new_repository(workspace)
    write_code(root, "scripts/moved.py", CODE, date="2026-06-01")
    write_code(root, "scripts/other.py", CODE, date="2026-06-01")
    write_code(root, "docs/data.md", "a\nb\nc\n", date="2026-06-01")

    write_document(root, "docs/suffix.md",
                   document(body="Today's test is `scripts/moved.py:428`."))
    code, out, err = run(root, "docs/suffix.md")
    check("a backticked path with a line suffix is reported",
          code == 1 and "line 428" in out, f"{code} {out}")

    write_document(root, "docs/singular.md",
                   document(body="It is named in `scripts/moved.py` line 375."))
    code, out, err = run(root, "docs/singular.md")
    check("a singular `line N` phrase is reported",
          code == 1 and "line 375" in out, f"{code} {out}")

    # The project's prose writes a range with an en dash as often as a hyphen.
    write_document(root, "docs/en-dash.md",
                   document(body="The test is `scripts/moved.py` lines 20\u2013244."))
    code, out, err = run(root, "docs/en-dash.md")
    check("a range written with an en dash is reported",
          code == 1 and "lines 20-244" in out, f"{code} {out}")

    # A word ending in "lines" is not a citation.
    write_document(root, "docs/word.md",
                   document(body="It outlines 4 cases for `scripts/moved.py`."))
    code, out, err = run(root, "docs/word.md")
    check("a word merely ending in lines is not a line-number phrase",
          code == 0 and out == "", f"{code} {out}")

    write_document(root, "docs/nearest.md", document(
        body="Chains hold one model (`scripts/other.py` lines 1-2, "
             "`scripts/moved.py` lines 8-9)."))
    code, out, err = run(root, "docs/nearest.md")
    check("each phrase attaches to the nearest code file before it",
          code == 1
          and "scripts/other.py changed" in out and "lines 1-2" in out
          and "scripts/moved.py changed" in out and "lines 8-9" in out,
          f"{code} {out}")

    write_document(root, "docs/unattached.md",
                   document(body="The closing text has three branches (lines 591-643)."))
    code, out, err = run(root, "docs/unattached.md")
    check("a line phrase with no code file before it is not reported",
          code == 0 and out == "", f"{code} {out}")

    write_document(root, "docs/after.md",
                   document(body="Its stub, lines 166-213, is in `scripts/moved.py`."))
    check("a code file named after the phrase does not attach to it",
          run(root, "docs/after.md")[0] == 0, run(root, "docs/after.md")[1])

    write_document(root, "docs/not-code.md",
                   document(body="Quoted in `docs/data.md` lines 1-2."))
    code, out, err = run(root, "docs/not-code.md")
    check("a line number into a file that is not code is not reported",
          code == 0 and out == "", f"{code} {out}")

    write_document(root, "docs/bare-name.md",
                   document(body="The stub in `moved.py` lines 8-9 keeps no state."))
    code, out, err = run(root, "docs/bare-name.md")
    check("a backticked name with no directory is not checked (2026-09-17 ruling)",
          code == 0 and out == "", f"{code} {out}")

    write_document(root, "docs/fenced.md", document(
        body="Nothing here.\n\n```\nsee `scripts/moved.py` lines 8-9\n```\n"))
    code, out, err = run(root, "docs/fenced.md")
    check("a citation inside a code fence is not reported",
          code == 0 and out == "", f"{code} {out}")

    write_document(root, "docs/history.md", document(
        body="In git history, `scripts/moved.py` lines 8-9 held the old test."))
    code, out, err = run(root, "docs/history.md")
    check("a line naming git history is skipped, as the lint skips it",
          code == 0 and out == "", f"{code} {out}")

    write_document(root, "docs/absent.md",
                   document(body="See `scripts/never-built.py` lines 8-9."))
    code, out, err = run(root, "docs/absent.md")
    check("a citation of a file that does not exist is not this check's finding",
          code == 0 and out == "", f"{code} {out}")


# --- A citation pinned to a commit is not checked -------------------------
with tempfile.TemporaryDirectory() as workspace:
    root = new_repository(workspace)
    write_code(root, "scripts/moved.py", CODE, date="2026-06-01")
    pinned_commit = git(root, "rev-parse", "--short=7", "HEAD")

    def section(intro):
        return (f"## 1. What happened before\n\n{intro}\n\n"
                f"- The test is `scripts/moved.py` lines 20-24.\n")

    write_document(root, "docs/pinned.md", document(
        body=section(f"Facts from origin/main at {pinned_commit}. "
                     f"Line numbers are that commit's.")))
    code, out, err = run(root, "docs/pinned.md")
    check("a citation in a section pinned to a commit is not reported",
          code == 0 and out == "", f"{code} {out}")
    check("the pinned citations are counted on stderr, never silently dropped",
          "1 citation(s) not checked" in err, err)

    write_document(root, "docs/commit-only.md", document(
        body=section(f"Facts from origin/main at {pinned_commit}.")))
    code, out, err = run(root, "docs/commit-only.md")
    check("naming a commit without saying line numbers does not pin a section",
          code == 1 and "lines 20-24" in out, f"{code} {out}")

    write_document(root, "docs/phrase-only.md", document(
        body=section("Line numbers are that commit's.")))
    code, out, err = run(root, "docs/phrase-only.md")
    check("saying line numbers without a commit this repository holds does not pin",
          code == 1 and "lines 20-24" in out, f"{code} {out}")

    write_document(root, "docs/unknown-commit.md", document(
        body=section("Facts from origin/main at deadbee. "
                     "Line numbers are that commit's.")))
    code, out, err = run(root, "docs/unknown-commit.md")
    check("a hex token that is no commit of this repository does not pin",
          code == 1 and "lines 20-24" in out, f"{code} {out}")

    # A "#" inside a code fence is a shell comment. Reading it as a heading
    # would end the pinned section early and carry its bullets out of the pin.
    write_document(root, "docs/pin-fence.md", document(
        body=f"## 1. What happened before\n\n"
             f"Facts from origin/main at {pinned_commit}. "
             f"Line numbers are that commit's.\n\n"
             f"```\n# a shell comment, not a heading\n```\n\n"
             f"- The test is `scripts/moved.py` lines 20-24.\n"))
    code, out, err = run(root, "docs/pin-fence.md")
    check("a hash inside a code fence does not end the pinned section",
          code == 0 and out == "", f"{code} {out}")

    # The pin is scoped to its own heading-section, so a later section that
    # describes the code as it stands now is still checked.
    write_document(root, "docs/pin-scope.md", document(
        body=section(f"Facts from origin/main at {pinned_commit}. "
                     f"Line numbers are that commit's.")
        + "\n## 2. What it does now\n\nThe marker is `scripts/moved.py` lines 40-44.\n"))
    code, out, err = run(root, "docs/pin-scope.md")
    check("a section after the pinned one is still checked",
          code == 1 and "lines 40-44" in out and "lines 20-24" not in out,
          f"{code} {out}")


# --- The frontmatter the check reads --------------------------------------
with tempfile.TemporaryDirectory() as workspace:
    root = new_repository(workspace)
    write_code(root, "scripts/moved.py", CODE, date="2026-06-01")

    write_document(root, "docs/unstamped.md",
                   "# Not a design\n\nSee `scripts/moved.py` lines 20-24.\n")
    code, out, err = run(root, "docs/unstamped.md")
    check("a document with no design-as-of stamp is not checked",
          code == 0 and out == "" and "carries no design-as-of stamp" in err,
          f"{code} {out} {err}")

    write_document(root, "docs/bad-stamp.md",
                   document(stamp="last Tuesday",
                            body="See `scripts/moved.py` lines 20-24."))
    code, out, err = run(root, "docs/bad-stamp.md")
    check("a stamp that is not a date is reported as one",
          code == 1 and "is not a date" in out, f"{code} {out}")

    # ... but not to the author of a code change who never touched it.
    base = git(root, "rev-parse", "HEAD")
    write_code(root, "scripts/elsewhere.py", CODE, date="2026-06-02")
    code, out, err = run(root, "--base", base)
    check("changed-paths mode leaves a broken stamp in an untouched document alone",
          code == 0 and "is not a date" not in out, f"{code} {out}")

    # A "---" in the body is a horizontal rule; taking a stamp from one would
    # date a document by its prose.
    write_document(root, "docs/rule.md",
                   "# Not a design\n\n---\ndesign-as-of: 2026-05-01\n---\n\n"
                   "See `scripts/moved.py` lines 20-24.\n")
    code, out, err = run(root, "docs/rule.md")
    check("a --- fence in the body is not frontmatter",
          code == 0 and "carries no design-as-of stamp" in err, f"{code} {err}")


# --- The status finding rides on a stale-citation finding -----------------
with tempfile.TemporaryDirectory() as workspace:
    root = new_repository(workspace)
    write_code(root, "scripts/moved.py", CODE, date="2026-06-01")
    write_code(root, "scripts/settled.py", CODE, date="2026-04-01")

    write_document(root, "docs/still-design.md", document(
        status="design; its cold-read-full-run is triaged",
        body="The test is `scripts/moved.py` lines 20-24."))
    code, out, err = run(root, "docs/still-design.md")
    check("a status naming neither landed nor built is reported beside a stale citation",
          code == 1 and "docs/still-design.md:2:" in out
          and "says neither landed nor built" in out, f"{code} {out}")
    reported = [line.split(":")[1] for line in out.splitlines() if line.startswith("docs/")]
    check("findings print in the document's own line order",
          reported == sorted(reported, key=int), out)

    write_document(root, "docs/landed.md", document(
        status="landed design; built in pull request 508",
        body="The test is `scripts/moved.py` lines 20-24."))
    code, out, err = run(root, "docs/landed.md")
    check("a status naming landed gets no status finding",
          code == 1 and "says neither landed nor built" not in out, f"{code} {out}")

    write_document(root, "docs/design-but-current.md", document(
        status="design, not built",
        body="The test is `scripts/settled.py` lines 20-24."))
    code, out, err = run(root, "docs/design-but-current.md")
    check("a status saying design raises nothing when no citation is stale",
          code == 0 and out == "", f"{code} {out}")


# --- Changed-paths mode ---------------------------------------------------
with tempfile.TemporaryDirectory() as workspace:
    root = new_repository(workspace)
    write_code(root, "scripts/moved.py", CODE, date="2026-04-01")
    write_code(root, "scripts/untouched.py", CODE, date="2026-04-01")
    write_document(root, "docs/design.md", document(
        body="The test is `scripts/moved.py` lines 20-24, and the marker is "
             "`scripts/untouched.py` lines 30-34."), date="2026-05-02")
    base = git(root, "rev-parse", "HEAD")
    write_code(root, "scripts/moved.py", CODE + "a new line\n", date="2026-06-01")

    code, out, err = run(root, "--base", base)
    check("changed-paths mode reports a document citing a path this change touches",
          code == 1 and "scripts/moved.py changed" in out and "lines 20-24" in out,
          f"{code} {out} {err}")
    check("changed-paths mode leaves a citation of an untouched path alone",
          "scripts/untouched.py" not in out, out)
    check("changed-paths mode sweeps the tree without being given the document",
          "docs/design.md:" in out, out)

    # A stamp newer than the change is not stale, whatever the history says.
    write_document(root, "docs/fresh.md", document(
        stamp="2026-06-02", body="The test is `scripts/moved.py` lines 20-24."),
        date="2026-06-02")
    code, out, err = run(root, "--base", base)
    check("changed-paths mode leaves a document stamped after the change alone",
          "docs/fresh.md" not in out, out)

    # An uncommitted edit is part of the change too.
    (root / "scripts" / "untouched.py").write_text(CODE + "edited\n", encoding="utf-8")
    code, out, err = run(root, "--base", base)
    check("changed-paths mode counts an uncommitted edit as a changed path",
          "scripts/untouched.py changed" in out and "lines 30-34" in out, out)


# --- Invocation and frozen data -------------------------------------------
with tempfile.TemporaryDirectory() as workspace:
    root = new_repository(workspace)
    write_code(root, "scripts/moved.py", CODE, date="2026-06-01")

    code, out, err = run(root, "--no-such-flag")
    check("a bad invocation exits 2", code == 2, f"{code} {err}")

    # An unresolvable base would otherwise read as a change touching no code
    # and pass every document in the tree without a word.
    code, out, err = run(root, "--base", "origin/does-not-exist")
    check("a --base git cannot resolve is refused, not answered with silence",
          code == 2 and "pass --base a ref this repository holds" in err,
          f"{code} {out} {err}")

    code, out, err = run(root, "docs/absent-document.md")
    check("a named file that is not there is reported and exits 1",
          code == 1 and "file not found" in out, f"{code} {out}")

    # A file under a frozen-measured-data directory records what a document
    # said when it was measured; no drift check may report it.
    (root / "cold-read-reviewer-test-cases").mkdir()
    frozen_body = "The test is `scripts/moved.py` lines 20-24."
    write_document(root, "cold-read-reviewer-test-cases/trio.md",
                   document(body=frozen_body))
    code, out, err = run(root, "cold-read-reviewer-test-cases/trio.md")
    check("a file in a frozen-measured-data directory reports nothing",
          code == 0 and out == "", f"{code} {out}")

    write_document(root, "docs/ordinary.md", document(body=frozen_body))
    code, out, err = run(root, "docs/ordinary.md")
    check("the same text outside that directory is still reported",
          code == 1 and "lines 20-24" in out, f"{code} {out}")


print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
