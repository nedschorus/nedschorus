#!/usr/bin/env python3
"""Tests for dangling-path-citation-check.py.

Each case builds a throwaway git repository, commits a base, changes one
file and runs the program as a subprocess against that base, because what
is under test is the pairing of a real git diff with the drift lint's
resolution — a unit test on the extractor alone would not have caught the
defect this program exists for.

The central case is that defect, reproduced: on 2026-09-19 a whole-system
move swept 33 files by extension and missed two comments in extensionless
shell scripts, each naming a path the move had emptied.

Run: python3 scripts/dangling-path-citation-check-test.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

CHECK_SCRIPT = Path(__file__).with_name("dangling-path-citation-check.py")
LINT_SCRIPT = Path(__file__).with_name("md-drift-lint.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
        return
    failures.append(case_name)
    print(f"FAIL  {case_name}")
    if detail:
        print(f"      {detail}")


def git(root, *arguments, check_exit=True):
    return subprocess.run(["git", *arguments], cwd=root, capture_output=True,
                          text=True, check=check_exit)


def build_repository(root: Path):
    """A repository whose scripts/ holds this program and the lint it calls,
    so the copy under test resolves its sibling import the way it will in
    the real tree."""
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@nedschorus.invalid")
    git(root, "config", "user.name", "test")
    (root / "scripts").mkdir()
    (root / "docs").mkdir()
    for source in (CHECK_SCRIPT, LINT_SCRIPT):
        (root / "scripts" / source.name).write_text(source.read_text(encoding="utf-8"),
                                                   encoding="utf-8")
    (root / "scripts" / "already-here.py").write_text("# a file that exists\n", encoding="utf-8")
    (root / ".gitignore").write_text("cold-read-records/\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    return git(root, "rev-parse", "HEAD").stdout.strip()


def run_check(root: Path, base: str, *arguments):
    completed = subprocess.run(
        [sys.executable, str(root / "scripts" / CHECK_SCRIPT.name), "--base", base, *arguments],
        cwd=root, capture_output=True, text=True, check=False)
    return completed.returncode, completed.stdout, completed.stderr


def commit_change(root: Path, relative: str, text: str, executable=False):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(0o755)
    git(root, "add", "-A")
    git(root, "commit", "-qm", f"change {relative}")


with tempfile.TemporaryDirectory() as workspace:
    root = Path(workspace) / "repo"
    root.mkdir()
    base = build_repository(root)

    # --- the defect this program exists for -----------------------------
    # An extensionless shell script whose comment names a path the tree does
    # not have. No backticks, no extension on the citing file: the two
    # reasons the 2026-09-19 sweep and a markdown linter both missed it.
    commit_change(root, "scripts/launcher-with-no-extension", """#!/bin/sh
# This follows the atomic write in scripts/main-gatekeeper.py (ruled 2026-08-12),
# and departs from it in two ways.
echo hello
""", executable=True)
    code, out, err = run_check(root, base)
    check("a plain path in an extensionless file's comment is reported",
          code == 1 and "scripts/main-gatekeeper.py" in out, f"{code} {out!r} {err!r}")
    check("the finding names the citing file and its line",
          "scripts/launcher-with-no-extension:2:" in out, out)

    # --- the scoping that keeps main's standing dangling paths out -------
    # The same dangling citation, already on the base, on a line the change
    # does not touch. Nobody in this change wrote it, so it is not reported.
    git(root, "checkout", "-q", "-b", "with-standing-drift", base)
    commit_change(root, "scripts/older-launcher", """#!/bin/sh
# An old comment citing scripts/gone-long-ago.py, nobody's defect today.
echo one
""", executable=True)
    standing_base = git(root, "rev-parse", "HEAD").stdout.strip()
    commit_change(root, "scripts/older-launcher", """#!/bin/sh
# An old comment citing scripts/gone-long-ago.py, nobody's defect today.
echo one
echo two
""", executable=True)
    code, out, err = run_check(root, standing_base)
    check("a dangling path on a line the change did not touch is not reported",
          code == 0 and "gone-long-ago" not in out, f"{code} {out!r} {err!r}")

    # --- a file the change adds and cites in the same commit -------------
    # Existence is tested in the change's own tree, so this is correct and
    # must not be reported; a check against the base would reject it.
    git(root, "checkout", "-q", "-b", "adds-and-cites", base)
    (root / "scripts" / "brand-new.py").write_text("# new\n", encoding="utf-8")
    (root / "docs" / "note.md").write_text("The new program is `scripts/brand-new.py`.\n",
                                           encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "add a program and cite it")
    code, out, err = run_check(root, base)
    check("a path added by the same change is not reported",
          code == 0 and "brand-new" not in out, f"{code} {out!r} {err!r}")

    # --- the Markdown shapes, delegated to the drift lint ----------------
    git(root, "checkout", "-q", "-b", "markdown-cases", base)
    commit_change(root, "docs/page.md", """# A page

A backticked path that is absent: `scripts/absent-program.py`.

A backticked path that is present: `scripts/already-here.py`.

A bare name with no directory: `dispositions.md`, which the user ruled on
2026-09-17 is not checked at all.

```
scripts/inside-a-fence.py
```
""")
    code, out, err = run_check(root, base)
    check("an absent backticked path in Markdown is reported",
          "scripts/absent-program.py" in out, out)
    check("a present backticked path is not reported",
          "already-here" not in out, out)
    check("a bare name with no directory is not reported (user-ruled 2026-09-17)",
          "dispositions.md" not in out, out)
    check("a path inside a code fence is not reported",
          "inside-a-fence" not in out, out)

    # --- shapes that are not citations ----------------------------------
    git(root, "checkout", "-q", "-b", "not-citations", base)
    commit_change(root, "scripts/various-shapes", """#!/bin/sh
# A URL is not a repository path: https://example.invalid/scripts/absent.py
# A git revision is not a path either: git show HEAD:scripts/absent.py
# A token with no leading directory is not a citation: absent-program.py
# A directory this repository does not track is skipped: cold-read-records/x/report.md
echo hello
""", executable=True)
    code, out, err = run_check(root, base)
    check("a URL is not read as a repository path",
          "example.invalid" not in out, out)
    check("a git revision spelling is not read as a path",
          "HEAD:scripts" not in out, out)
    check("a token with no leading directory is not a citation",
          "absent-program.py" not in out, out)
    check("a gitignored path that is absent is not reported",
          "cold-read-records" not in out, out)

    # --- the invocation's own shapes ------------------------------------
    git(root, "checkout", "-q", "-b", "invocation", base)
    commit_change(root, "scripts/one", "#!/bin/sh\n# cites scripts/absent-one.py\n", executable=True)
    commit_change(root, "scripts/two", "#!/bin/sh\n# cites scripts/absent-two.py\n", executable=True)
    code, out, err = run_check(root, base)
    check("every changed file is checked when none is named",
          "absent-one" in out and "absent-two" in out, out)
    code, out, err = run_check(root, base, "scripts/one")
    check("naming one file limits the check to it",
          "absent-one" in out and "absent-two" not in out, out)
    check("the summary line goes to stderr, the findings to stdout",
          "finding(s)" in err and "finding(s)" not in out, f"{out!r} {err!r}")

    code, out, err = run_check(root, "no-such-ref")
    check("an unresolvable base fails loudly rather than reporting clean",
          code != 0 and "no-such-ref" in (out + err), f"{code} {out!r} {err!r}")

    # --- BACKWARD: a path this change removed, still cited elsewhere ----
    # The real defect of 2026-09-19. The citing file is not part of the
    # change at all: it is a comment in an extensionless script that names a
    # program the change moved away. No changed-line check can see it.
    git(root, "checkout", "-q", "-b", "moves-a-cited-file", base)
    (root / "scripts" / "cited-by-a-comment.py").write_text("# the precedent\n", encoding="utf-8")
    (root / "scripts" / "innocent-launcher").write_text(
        "#!/bin/sh\n# follows the write in scripts/cited-by-a-comment.py, ruled 2026-08-12\necho hi\n",
        encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "add a program and a comment citing it")
    moved_base = git(root, "rev-parse", "HEAD").stdout.strip()
    (root / "nc-systems" / "thing").mkdir(parents=True)
    git(root, "mv", "scripts/cited-by-a-comment.py", "nc-systems/thing/cited-by-a-comment.py")
    git(root, "commit", "-qm", "move the program, sweeping nothing")
    code, out, err = run_check(root, moved_base)
    check("a path moved away, still cited by an untouched file, is reported",
          code == 1 and "scripts/innocent-launcher:2:" in out
          and "which this change removed" in out, f"{code} {out!r} {err!r}")
    check("the backward finding names the path that went",
          "cites scripts/cited-by-a-comment.py" in out, out)

    # A move that sweeps its citations leaves nothing to report.
    git(root, "checkout", "-q", "-b", "moves-and-sweeps", moved_base)
    (root / "nc-systems" / "thing").mkdir(parents=True, exist_ok=True)
    git(root, "mv", "scripts/cited-by-a-comment.py", "nc-systems/thing/cited-by-a-comment.py")
    (root / "scripts" / "innocent-launcher").write_text(
        "#!/bin/sh\n# follows the write in nc-systems/thing/cited-by-a-comment.py, ruled 2026-08-12\necho hi\n",
        encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "move the program and sweep its citation")
    code, out, err = run_check(root, moved_base)
    check("a move that sweeps its own citations reports nothing",
          code == 0, f"{code} {out!r} {err!r}")

    # --- FORWARD: a citation the change did not introduce ---------------
    # A line the change touches, carrying a dangling citation that was
    # already there. Measured on the 2026-09-19 move: its sweep rewrote one
    # path on a line that also held an unrelated forward reference to an
    # unbuilt test, and reporting that would have been a false alarm.
    git(root, "checkout", "-q", "-b", "pre-existing-on-a-touched-line", base)
    commit_change(root, "docs/mixed.md",
                  "A line naming `scripts/absent-forever.py` and `scripts/already-here.py`.\n")
    mixed_base = git(root, "rev-parse", "HEAD").stdout.strip()
    commit_change(root, "docs/mixed.md",
                  "A line naming `scripts/absent-forever.py` and `scripts/already-here.py` again.\n")
    code, out, err = run_check(root, mixed_base)
    check("a dangling citation the change did not introduce is not reported",
          code == 0 and "absent-forever" not in out, f"{code} {out!r} {err!r}")

    # --- a deleted file cites nothing -----------------------------------
    git(root, "checkout", "-q", "-b", "deletion", base)
    git(root, "rm", "-q", "scripts/already-here.py")
    git(root, "commit", "-qm", "delete a program")
    code, out, err = run_check(root, base)
    check("a deleted file is not read for citations",
          code == 0, f"{code} {out!r} {err!r}")

if failures:
    print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
