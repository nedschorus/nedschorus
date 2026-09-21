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
    # The exit code the docstring promises, and the one that distinguishes a
    # failed run from a dirty one. SystemExit carrying a string exits 1, the
    # findings code, so this is a separate case from the one above: that one
    # passed throughout while a caller reading the code was told "findings".
    check("a bad invocation exits 2, not the findings code",
          code == 2, f"{code} {out!r} {err!r}")

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

    # --- the base a branch is BEHIND: the merge base, not the base tip ---
    # The two diffs were three-dot, from the merge base, while the base text
    # a forward finding was compared against came from `git show <base>:`,
    # the base TIP. When the base moves on and its new content happens to
    # name the same path, the branch's own new dangling citation was
    # suppressed against a file version the branch never saw, and the run
    # reported clean.
    git(root, "checkout", "-q", "-b", "fork-point-for-drift", base)
    commit_change(root, "docs/note.md", "# note\n\nNothing cited here yet.\n")
    drift_fork = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "checkout", "-q", "-b", "drifted-base", drift_fork)
    commit_change(root, "docs/note.md",
                  "# note\n\nNothing cited here yet.\n\nSee `docs/ghost.md` for the plan.\n")
    git(root, "checkout", "-q", "-b", "behind-its-base", drift_fork)
    commit_change(root, "docs/note.md",
                  "# note\n\nNothing cited here yet.\n\nThe author adds `docs/ghost.md` here.\n")
    code, out, err = run_check(root, "drifted-base")
    check("a branch behind its base still reports its own new dangling citation",
          code == 1 and "docs/ghost.md" in out, f"{code} {out!r} {err!r}")

    # --- the base already cites it, asked as a path and not a substring --
    # "is this citation one the change did not introduce" was asked as
    # `cited in base_text`, so a base naming a LONGER path that ends with
    # this one answered yes and the new citation went unreported.
    git(root, "checkout", "-q", "-b", "longer-path-in-the-base", base)
    commit_change(root, "docs/backup.md",
                  "# backup\n\nThe backup lives at `docs/page.md.bak`, which nobody reads.\n")
    longer_path_base = git(root, "rev-parse", "HEAD").stdout.strip()
    commit_change(root, "docs/backup.md",
                  "# backup\n\nThe backup lives at `docs/page.md.bak`, which nobody reads.\n"
                  "\nThe page itself is `docs/page.md`.\n")
    code, out, err = run_check(root, longer_path_base)
    check("a longer path in the base does not suppress a new citation of the shorter one",
          code == 1 and any(line.endswith(": path does not exist: docs/page.md")
                            for line in out.splitlines()), f"{code} {out!r} {err!r}")

    # --- an added line whose own text begins "++ " ----------------------
    # It renders as "+++ ..." and was read as a file header, so `current`
    # became a path that does not exist and every later hunk of the real
    # file went there instead, unread.
    git(root, "checkout", "-q", "-b", "added-line-that-looks-like-a-header", base)
    commit_change(root, "docs/plus.md", "# doc\n\nfiller\n\nfiller\n\ntail\n")
    plus_base = git(root, "rev-parse", "HEAD").stdout.strip()
    commit_change(root, "docs/plus.md",
                  "# doc\n\n++ a line whose own text begins with two plus signs\n\nfiller\n"
                  "\nfiller\n\ntail\n\nIt cites `scripts/absent-after-the-plus.py` here.\n")
    code, out, err = run_check(root, plus_base)
    check("an added line beginning '++ ' does not hide the file's later hunks",
          code == 1 and "scripts/absent-after-the-plus.py" in out, f"{code} {out!r} {err!r}")

    # --- a move that only deepens a path, swept correctly ---------------
    # git grep -F matched the old path INSIDE its own replacement, so the
    # backward check reported a correct sweep as a stale citation.
    git(root, "checkout", "-q", "-b", "deepening-move", base)
    (root / "docs").mkdir(exist_ok=True)
    (root / "scripts" / "swept-tool.py").write_text("# the tool\n", encoding="utf-8")
    (root / "docs" / "uses.md").write_text("Run `scripts/swept-tool.py` to do the thing.\n",
                                           encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "add a tool and a usage line")
    deepening_base = git(root, "rev-parse", "HEAD").stdout.strip()
    (root / "nc-systems" / "thing" / "scripts").mkdir(parents=True, exist_ok=True)
    git(root, "mv", "scripts/swept-tool.py", "nc-systems/thing/scripts/swept-tool.py")
    (root / "docs" / "uses.md").write_text(
        "Run `nc-systems/thing/scripts/swept-tool.py` to do the thing.\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "move the tool deeper and sweep its citation")
    code, out, err = run_check(root, deepening_base)
    check("a move that only deepens a path is not reported against its own correct sweep",
          code == 0, f"{code} {out!r} {err!r}")

    # --- BACKWARD: the drift lint's history exemption applies here too ---
    git(root, "checkout", "-q", "-b", "history-marker-backward", base)
    (root / "docs").mkdir(exist_ok=True)
    (root / "scripts" / "gone-to-history.py").write_text("# soon to go\n", encoding="utf-8")
    (root / "docs" / "history-note.md").write_text(
        "Its last version is reachable with `git show` at scripts/gone-to-history.py.\n",
        encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "add a program and a note about its history")
    history_base = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "rm", "-q", "scripts/gone-to-history.py")
    git(root, "commit", "-qm", "remove the program")
    code, out, err = run_check(root, history_base)
    check("a line naming git history is not reported by the backward check",
          code == 0 and "gone-to-history" not in out, f"{code} {out!r} {err!r}")

    # --- BACKWARD: a fenced usage example is NOT exempt ------------------
    # The pin for the line above. Fenced content is not blanket-exempt: a
    # usage example that runs a script by path genuinely needs sweeping when
    # the script moves. What names the noise is the history marker.
    git(root, "checkout", "-q", "-b", "fenced-usage-backward", base)
    (root / "docs").mkdir(exist_ok=True)
    (root / "scripts" / "fenced-tool.py").write_text("# the tool\n", encoding="utf-8")
    (root / "docs" / "usage.md").write_text(
        "# usage\n\n```\npython3 scripts/fenced-tool.py --check\n```\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "add a tool and a fenced usage example")
    fenced_base = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "rm", "-q", "scripts/fenced-tool.py")
    git(root, "commit", "-qm", "remove the tool, sweeping nothing")
    code, out, err = run_check(root, fenced_base)
    check("a fenced usage example of a removed script is still reported",
          code == 1 and "cites scripts/fenced-tool.py" in out, f"{code} {out!r} {err!r}")

    # --- a path carrying a line number in a non-Markdown file ------------
    # `":" in token` dropped it, though this program prints its own findings
    # in exactly that shape. The colon test still drops `git show REF:path`
    # and a URL, which the cases above hold.
    git(root, "checkout", "-q", "-b", "line-numbered-plain-citation", base)
    commit_change(root, "scripts/cites-with-a-line-number", """#!/bin/sh
# the shape is at scripts/absent-with-a-line-number.py:42, worth reading
echo hello
""", executable=True)
    code, out, err = run_check(root, base)
    check("a path carrying a line number in a non-Markdown file is checked",
          code == 1 and "scripts/absent-with-a-line-number.py" in out, f"{code} {out!r} {err!r}")

    # --- FORWARD: a file DECLARED_PATH_FIXTURE_FILES names ---------------
    # Its negative cases name paths that are deliberately absent, so against
    # a base where the file did not exist yet every one of them is a new
    # dangling citation and the program reported twenty on its own pull
    # request. Forward only, and the cost is stated in its docstring.
    git(root, "checkout", "-q", "-b", "declared-fixture-file", base)
    commit_change(root, "scripts/dangling-path-citation-check-test.py",
                  '#!/usr/bin/env python3\n'
                  '"""A stand-in for the real test file, at its declared path."""\n'
                  'FIXTURE = "scripts/deliberately-absent-fixture.py"\n')
    code, out, err = run_check(root, base)
    check("a dangling path written into a declared fixture file is not reported forward",
          code == 0 and "deliberately-absent-fixture" not in out, f"{code} {out!r} {err!r}")
    commit_change(root, "scripts/carries-the-same-line.py",
                  'FIXTURE = "scripts/deliberately-absent-fixture.py"\n')
    code, out, err = run_check(root, base)
    check("the same line in an undeclared file is still reported",
          code == 1 and "scripts/carries-the-same-line.py:1:" in out
          and "dangling-path-citation-check-test.py:" not in out, f"{code} {out!r} {err!r}")

    # --- BACKWARD: a citation carrying a leading or dotted slash --------
    # The six hook commands in .claude/settings.json are written
    # `"$CLAUDE_PROJECT_DIR"/scripts/<name>.py`, and a launcher runs a
    # program as ./scripts/<name>.py. The leading boundary is looked for
    # behind the slashes, so a move still reaches both; anchoring on the bare
    # character before the match saw neither.
    git(root, "checkout", "-q", "-b", "slash-prefixed-backward", base)
    (root / "scripts" / "hooked-tool.py").write_text("# the hook's program\n", encoding="utf-8")
    (root / "settings-like.json").write_text(
        '{"command": "python3 \\"$PROJECT_DIR\\"/scripts/hooked-tool.py"}\n', encoding="utf-8")
    (root / "runner.sh").write_text("#!/bin/sh\npython3 ./scripts/hooked-tool.py\n",
                                    encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "add a program and two slash-prefixed callers")
    slash_base = git(root, "rev-parse", "HEAD").stdout.strip()
    (root / "nc-systems").mkdir(parents=True, exist_ok=True)
    git(root, "mv", "scripts/hooked-tool.py", "nc-systems/hooked-tool.py")
    git(root, "commit", "-qm", "move the program, sweeping neither caller")
    code, out, err = run_check(root, slash_base)
    check("a citation prefixed with / or ./ is still reported when the path moves",
          code == 1 and "settings-like.json:1:" in out and "runner.sh:2:" in out,
          f"{code} {out!r} {err!r}")

    # --- BACKWARD: the declared fixture file is NOT exempt ---------------
    # The pin for the exemption above, and the property that stops it
    # widening: a fixture file names its own subject, and when that subject
    # moves the stale reference is a real one. Nothing but this case would
    # notice the predicate being consulted in citations_of_removed_paths.
    git(root, "checkout", "-q", "-b", "fixture-file-cites-a-moved-module", base)
    (root / "scripts" / "module-under-test.py").write_text("# the module\n", encoding="utf-8")
    (root / "scripts" / "dangling-path-citation-check-test.py").write_text(
        'CHECK_SCRIPT = "scripts/module-under-test.py"\n'
        'FIXTURE = "scripts/deliberately-absent-fixture.py"\n', encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "add a module and a fixture file naming it")
    fixture_base = git(root, "rev-parse", "HEAD").stdout.strip()
    (root / "nc-systems" / "moved").mkdir(parents=True, exist_ok=True)
    git(root, "mv", "scripts/module-under-test.py", "nc-systems/moved/module-under-test.py")
    git(root, "commit", "-qm", "move the module, forget the fixture file")
    code, out, err = run_check(root, fixture_base)
    check("a declared fixture file's stale citation of a moved module is still reported",
          code == 1 and "scripts/dangling-path-citation-check-test.py:1: "
          "cites scripts/module-under-test.py, which this change removed" in out,
          f"{code} {out!r} {err!r}")

    # --- FORWARD: a RENAMED file's base text, read at the name it had -----
    # The suppression asked git for the base text under the path as it stands
    # at HEAD. A rename destination was not at the merge base under that
    # name, so nothing came back, "the base already cited this" answered no,
    # and a rename plus an edit to any line reported that line's standing
    # dangling citations as newly written by the author -- which is the shape
    # of the 2026-09-19 move this program was built from.
    #
    # The fixture is padded with unrelated paragraphs deliberately: git
    # decides what a rename is by similarity, a small document can score
    # under the threshold, and a move it scores that way is a delete and an
    # add, which carries no old name and is a different shape than these
    # cases name. The last case here holds the padding to its job.
    rename_filler = "".join(
        f"An unrelated paragraph, number {number}, carrying no citation at all.\n\n"
        for number in range(1, 13))
    page_with_a_standing_citation = (
        "# a page\n\nThe old plan is recorded in `scripts/never-built-at-all.py` and "
        "stands.\n\n" + rename_filler)
    same_citation_edited = (
        "# a page\n\nThe old plan is recorded in `scripts/never-built-at-all.py` and "
        "STILL stands.\n\n" + rename_filler)

    git(root, "checkout", "-q", "-b", "fork-point-for-the-rename-cases", base)
    commit_change(root, "docs/page-that-moves.md", page_with_a_standing_citation)
    rename_base = git(root, "rev-parse", "HEAD").stdout.strip()

    git(root, "checkout", "-q", "-b", "renames-and-edits-a-citing-line", rename_base)
    git(root, "mv", "docs/page-that-moves.md", "docs/page-after-the-move.md")
    commit_change(root, "docs/page-after-the-move.md", same_citation_edited)
    renamed_row = git(root, "diff", "--name-status", f"{rename_base}..HEAD").stdout.strip()
    code, out, err = run_check(root, rename_base)
    check("a rename does not resurrect the file's standing dangling citation",
          code == 0 and "never-built-at-all" not in out, f"{code} {out!r} {err!r}")

    # The control, differing only by the rename: the same edit to the same
    # line of the same file. It was quiet before and must stay quiet, or the
    # case above could be passed by disabling the suppression altogether.
    git(root, "checkout", "-q", "-b", "edits-the-same-line-without-renaming", rename_base)
    commit_change(root, "docs/page-that-moves.md", same_citation_edited)
    code, out, err = run_check(root, rename_base)
    check("the same edit without a rename is still not reported",
          code == 0 and "never-built-at-all" not in out, f"{code} {out!r} {err!r}")

    # And the live one, which is what stops the case above being passed by
    # skipping a renamed file whole: a citation the author writes onto a
    # touched line of a renamed file is still reported. Only the new path is
    # asserted -- the standing one is the first case's subject, and asserting
    # its absence here would make this case red without the fix too.
    git(root, "checkout", "-q", "-b", "renames-and-writes-a-new-citation", rename_base)
    git(root, "mv", "docs/page-that-moves.md", "docs/page-after-the-move.md")
    commit_change(root, "docs/page-after-the-move.md",
                  "# a page\n\nThe old plan is recorded in `scripts/never-built-at-all.py` "
                  "and now also in `scripts/written-today-and-absent.py`.\n\n" + rename_filler)
    live_row = git(root, "diff", "--name-status", f"{rename_base}..HEAD").stdout.strip()
    code, out, err = run_check(root, rename_base)
    check("a citation newly written on a touched line of a renamed file is still reported",
          code == 1 and "scripts/written-today-and-absent.py" in out, f"{code} {out!r} {err!r}")

    # The fixture's own precondition. The three cases above are about the R
    # rows of --name-status, and under a delete-and-add pair the live one
    # would pass vacuously, everything in the file being reported. Where
    # git's threshold falls is git's business and not this suite's: measured
    # 2026-09-21, a five-line document whose changed word sits early in its
    # citing line is scored a delete and an add. So the shape is asserted
    # here rather than assumed of the text above.
    check("the rename fixtures read as a rename to git, not as a delete and an add",
          renamed_row.startswith("R") and live_row.startswith("R"),
          f"{renamed_row!r} {live_row!r}")

if failures:
    print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
