#!/usr/bin/env python3
"""Tests for md-drift-lint.py.

Run: python3 scripts/md-drift-lint-test.py
"""

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

LINT_SCRIPT = Path(__file__).with_name("md-drift-lint.py")

_spec = importlib.util.spec_from_file_location("md_drift_lint", LINT_SCRIPT)
lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def problems_for(md_text: str, repo_root: Path, name="doc.md"):
    path = repo_root / name
    path.write_text(md_text, encoding="utf-8")
    return [problem for _, problem in lint.lint_markdown(path, repo_root)]


with tempfile.TemporaryDirectory() as workspace:
    root = Path(workspace)
    (root / "scripts").mkdir()
    (root / "scripts" / "real-script.py").write_text(
        'parser.add_argument("--threshold")\nWORD_FLOOR = 2500\nWINDOW = 100_000\n',
        encoding="utf-8",
    )
    (root / "docs").mkdir()
    (root / "docs" / "real-doc.md").write_text(
        "# real\n"
        "The supervisor **must stop** working now and wait.\n"
        "The handoff scrub reports the store's depth alongside the other queues.\n",
        encoding="utf-8",
    )

    # --- Path existence ---------------------------------------------------
    check("an existing backtick path passes",
          problems_for("see `scripts/real-script.py` here", root) == [])
    problems = problems_for("see `scripts/ghost-script.py` here", root)
    check("a missing backtick path is reported",
          any("ghost-script" in p for p in problems), str(problems))
    check("a git-show ref is skipped",
          problems_for("at `git show abc123:docs/gone.md`", root) == [])
    check("a placeholder path is skipped",
          problems_for("as `scripts/<agent>-handoff.md` shows", root) == [])
    check("a glob path is skipped",
          problems_for("all `docs/*.md` files", root) == [])
    check("prose in backticks is not a path",
          problems_for("the `restart-counter` field", root) == [])

    # --- Markdown links ---------------------------------------------------
    check("an existing link target passes",
          problems_for("[doc](docs/real-doc.md)", root) == [])
    problems = problems_for("[doc](docs/ghost-doc.md)", root)
    check("a missing link target is reported",
          any("ghost-doc" in p for p in problems), str(problems))
    check("an external URL is skipped",
          problems_for("[gh](https://github.com/x/y)", root) == [])
    check("a file:// URL is skipped",
          problems_for("[f](file:///Volumes/nedhome/x.md)", root) == [])
    check("an anchor link is skipped",
          problems_for("[s](#section)", root) == [])

    # --- Dates ------------------------------------------------------------
    check("a real date passes", problems_for("ruled 2026-08-12 by", root) == [])
    problems = problems_for("ruled 2026-13-40 by", root)
    check("an impossible date is reported",
          any("2026-13-40" in p for p in problems), str(problems))
    check("february 30 is reported",
          any("2026-02-30" in p for p in problems_for("on 2026-02-30", root)))

    # --- Script flags -----------------------------------------------------
    check("a flag the script defines passes",
          problems_for("run `scripts/real-script.py --threshold 5`", root) == [])
    problems = problems_for("run `scripts/real-script.py --ghost-flag`", root)
    check("a flag the script lacks is reported",
          any("--ghost-flag" in p for p in problems), str(problems))
    check("flags without a script in the token are not checked",
          problems_for("pass `--anything-at-all` to it", root) == [])
    # Flags bind to the command's own script, not to any .py in the line
    # (fixed 2026-08-14). Scanning the whole token bound another program's
    # flags to whatever script the line happened to name — and these documents
    # are full of git commands naming script paths.
    problems = problems_for(
        "run `git log --follow --oneline scripts/real-script.py`", root)
    check("another program's flags are not charged to a named script",
          problems == [], str(problems))
    check("a flag check still fires when the script leads the command",
          any("--ghost" in p for p in
              problems_for("run `scripts/real-script.py --ghost`", root)))
    check("an interpreter prefix does not hide the script",
          any("--ghost" in p for p in
              problems_for("run `python3 scripts/real-script.py --ghost`", root)))
    # Whole-flag matching (fixed 2026-08-14): a substring test let a prefix of
    # a real flag pass, so a doc that drifted from --threshold to --thresh
    # reported nothing — the exact drift this check exists to catch.
    problems = problems_for("run `scripts/real-script.py --thresh 5`", root)
    check("a prefix of a real flag is reported, not silently accepted",
          any("--thresh" in p for p in problems), str(problems))

    # --- Bare basenames, history lines, placeholders ----------------------
    check("a bare basename existing elsewhere in the repo resolves",
          problems_for("run `real-script.py --threshold 1`", root) == [])
    # A name with no directory is not checked at all (user-ruled 2026-09-17,
    # nedschorus#336): it names a file inside some directory the prose is
    # discussing, or one a run creates. 126 of main's 200 missing-path
    # findings were of this shape that day.
    check("a name with no directory is not demanded to exist",
          problems_for("the run writes `state-exit.json` beside its trace", root) == [],
          str(problems_for("the run writes `state-exit.json` beside its trace", root)))
    check("and neither is one inside a command",
          problems_for("run `python3 real-script.py notes.md`", root) == [],
          str(problems_for("run `python3 real-script.py notes.md`", root)))
    # The half that must keep firing: a path carrying a directory is where
    # real drift shows, and the ruling does not touch it.
    check("a path with a directory that is absent is still reported",
          any("docs/ghost.md" in p
              for p in problems_for("see `docs/ghost.md`", root)),
          str(problems_for("see `docs/ghost.md`", root)))
    # The flag check reads the script a bare name points at, and still does:
    # skipping the existence check is not skipping the word.
    check("a bare script name still carries its flags to the real script",
          any("--ghost" in p
              for p in problems_for("run `real-script.py --ghost`", root)),
          str(problems_for("run `real-script.py --ghost`", root)))
    check("a git-history line's paths are not checked",
          problems_for("deleted, in git history at `docs/gone-forever.md`", root) == [])
    check("an ellipsis placeholder is skipped",
          problems_for("each has a `…-test.py` twin", root) == [])
    problems = problems_for("in git history at `x.md`, dated 2026-13-40", root)
    check("dates are still checked on a git-history line",
          any("2026-13-40" in p for p in problems), str(problems))

    # --- Paths the repo cannot vouch for (all fixed 2026-08-14) -----------
    # Each of these fired live on the project's central design document, and a
    # linter that always complains about that document is one every reader
    # learns to skim past.
    check("a bare file-type token is not demanded to exist",
          problems_for("a `.meta.json` carrying agentType", root) == [])
    check("an absolute install path outside the repo is not drift",
          problems_for("Working path: `/usr/local/lib/nc/gate.py`.", root) == [])
    check("a leading slash still resolves repo-root-relative",
          problems_for("see `/scripts/real-script.py`", root) == [])
    check("a repo-root-relative path that is absent is still reported",
          any("ghost" in p for p in problems_for("see `/scripts/ghost.py`", root)))
    check("a line citing the legacy tree is not checked",
          problems_for(
              "the legacy system's `gone.md` (`~/Projects/nedlern/docs/`)", root) == [])

    # --- Code fences ------------------------------------------------------
    check("fenced code blocks are skipped",
          problems_for("```\n`scripts/ghost.py` and 2026-13-40\n```\n", root) == [])

    # --- Quoted text vs its attributed source -----------------------------
    check("a quote present in the one named file passes",
          problems_for('it says "must stop working now and wait" ([d](docs/real-doc.md))',
                       root) == [])
    problems = problems_for('it says "never said anywhere in that file" ([d](docs/real-doc.md))',
                            root)
    check("a quote absent from the named file is reported",
          any("quoted text not found" in p for p in problems), str(problems))
    check("emphasis in the source does not break the quote match",
          problems_for('per "supervisor must stop working now" ([d](docs/real-doc.md))',
                       root) == [])
    check("an ellipsis quote checks its fragments and passes",
          problems_for('the ruling "reports the store\'s depth ... the other queues" '
                       "([d](docs/real-doc.md))", root) == [])
    problems = problems_for('the ruling "reports the store\'s depth ... never in the file" '
                            "([d](docs/real-doc.md))", root)
    check("an ellipsis quote with a missing fragment is reported",
          any("never in the file" in p for p in problems), str(problems))
    check("a quote under four words is not checked",
          problems_for('the "just a label" case ([d](docs/real-doc.md))', root) == [])
    check("a line naming two files attributes nothing checkable",
          problems_for('says "never said anywhere in that file" per [a](docs/real-doc.md) '
                       "and `scripts/real-script.py`", root) == [])
    check("a quote with no named file is not checked",
          problems_for('he said "never said anywhere in that file" today', root) == [])
    check("a quote touching a backtick span is skipped",
          problems_for('prints `"not in the doc at all"` ([d](docs/real-doc.md))', root) == [])
    check("punctuation closing the quoting sentence still matches",
          problems_for('asked "reports the store\'s depth alongside the other queues?" '
                       "([d](docs/real-doc.md))", root) == [])
    check("a quote the line says was deleted is not checked",
          problems_for('the "never said anywhere in that file" code was deleted 2026-08-10 '
                       "([d](docs/real-doc.md))", root) == [])

    # --- Numbers quoted from code -----------------------------------------
    check("a backtick number found in the named code file passes",
          problems_for("the floor is `2500` in `scripts/real-script.py`", root) == [])
    problems = problems_for("the floor is `9999` in `scripts/real-script.py`", root)
    check("a backtick number absent from the named code file is reported",
          any("number 9999 not found" in p for p in problems), str(problems))
    check("digit-group separators do not break the number match",
          problems_for("a window of `100000` in `scripts/real-script.py`", root) == [])
    check("a number inside a command span is a usage example, not checked",
          problems_for("run `scripts/real-script.py --threshold 9999`", root) == [])
    check("a prose number near a code file is not checked",
          problems_for("all 9999 cases in `scripts/real-script.py`", root) == [])
    check("a backtick number naming only an md file is not checked",
          problems_for("the value `9999` per [d](docs/real-doc.md)", root) == [])

    # --- JSON duplicate keys ----------------------------------------------
    good_json = root / "good.json"
    good_json.write_text('{"a": 1, "b": {"c": 2}}', encoding="utf-8")
    check("clean json passes", list(lint.lint_json(good_json)) == [])
    dup_json = root / "dup.json"
    dup_json.write_text('{"hooks": {"Stop": 1, "Pre": 2, "Stop": 3}}', encoding="utf-8")
    problems = [problem for _, problem in lint.lint_json(dup_json)]
    check("a duplicate nested key is reported",
          any("Stop" in p for p in problems), str(problems))
    # Every duplicate, at its own line (fixed 2026-08-14). Raising on the first
    # collision meant a file with three duplicated keys took three
    # edit-and-rerun cycles, each report pointing at line 1 regardless.
    many_json = root / "many-dups.json"
    many_json.write_text(
        '{\n "a": 1,\n "b": 2,\n "a": 3,\n "b": 4,\n "c": 5,\n "c": 6\n}',
        encoding="utf-8")
    findings = list(lint.lint_json(many_json))
    check("every duplicate key is reported, not just the first",
          len(findings) == 3, str(findings))
    check("a duplicate is reported at the line that silently wins",
          [line for line, _ in findings] == [4, 5, 7], str(findings))
    malformed_json = root / "malformed.json"
    malformed_json.write_text('{"a": ', encoding="utf-8")
    check("malformed json is still reported",
          len(list(lint.lint_json(malformed_json))) == 1)

# A path this repository deliberately does not track is not drift (user-ruled
# 2026-09-17). These cases need a REAL git repository: the fixtures above are
# plain temporary directories, where nothing is ignored and the rule would
# never be exercised, so a suite without this block would prove nothing.
with tempfile.TemporaryDirectory() as git_workspace:
    git_root = Path(git_workspace)
    subprocess.run(["git", "init", "-q"], cwd=git_root, check=True,
                   capture_output=True)
    (git_root / ".gitignore").write_text(
        "cold-read-records/\ndocs/walk/\n", encoding="utf-8")
    (git_root / "docs").mkdir()
    (git_root / "scripts").mkdir()

    check("an ignored path that is absent is not reported",
          problems_for("A record at `cold-read-records/2026-09-14-run/dispositions.md` says so.\n",
                       git_root) == [],
          str(problems_for("A record at `cold-read-records/2026-09-14-run/dispositions.md` says so.\n",
                           git_root)))

    # The same citation in a seat's own checkout, where the file IS present.
    # Both answers must match, because measuring in the wrong checkout is what
    # put a wrong pair of numbers into a merged comment on 2026-09-17.
    present = git_root / "cold-read-records" / "2026-09-14-run"
    present.mkdir(parents=True)
    (present / "dispositions.md").write_text("# real record\n", encoding="utf-8")
    check("an ignored path that is present reads the same as when absent",
          problems_for("A record at `cold-read-records/2026-09-14-run/dispositions.md` says so.\n",
                       git_root) == [])

    # The rule must not swallow real drift: an untracked-by-accident path is
    # still a missing path, and that is the whole point of the check.
    findings = problems_for("The script `scripts/not-built-yet.py` runs it.\n", git_root)
    check("a path git does not ignore is still reported",
          findings == ["path does not exist: scripts/not-built-yet.py"], str(findings))

    # A markdown link is folded against the citing document's directory before
    # git is asked, so a relative link out of docs/ resolves to docs/walk/.
    check("a relative link into an ignored directory is not reported",
          problems_for("See [the minutes](walk/seat-rulings-minutes.md).\n",
                       git_root, name="docs/doc.md") == [],
          str(problems_for("See [the minutes](walk/seat-rulings-minutes.md).\n",
                           git_root, name="docs/doc.md")))

    # A link that leaves the repository entirely cannot be ignored BY this
    # repository, and must not be silently swallowed by the relpath guard.
    findings = problems_for("See [outside](../elsewhere/gone.md).\n",
                            git_root, name="docs/doc.md")
    check("a link pointing outside the repository is still reported",
          findings == ["link target does not exist: ../elsewhere/gone.md"], str(findings))


# A directory of frozen measured data is skipped whole: its citations record
# what a document said when it was measured, and a triager who "fixes" one
# silently re-tunes every score published against those files
# (cold-read-reviewer-test-cases/README.md; user-ruled 2026-09-17).
with tempfile.TemporaryDirectory() as frozen_workspace:
    frozen_root = Path(frozen_workspace)
    frozen_text = "It cites `scripts/long-gone.py`, and quotes nothing.\n"

    (frozen_root / "cold-read-reviewer-test-cases").mkdir()
    findings = problems_for(frozen_text, frozen_root,
                            name="cold-read-reviewer-test-cases/trio.md")
    check("a file in a frozen-data directory reports nothing", findings == [],
          str(findings))

    # The same text outside it must still report, or the case above would pass
    # for the wrong reason -- a lint that found nothing anywhere.
    findings = problems_for(frozen_text, frozen_root, name="ordinary.md")
    check("the same text outside that directory is still reported",
          findings == ["path does not exist: scripts/long-gone.py"], str(findings))

    # Exact directory name, not a prefix: a neighbour that merely starts with
    # the same characters is ordinary content and must still be checked.
    (frozen_root / "cold-read-reviewer-test-cases-archive").mkdir()
    findings = problems_for(frozen_text, frozen_root,
                            name="cold-read-reviewer-test-cases-archive/old.md")
    check("a directory that merely shares the prefix is still checked",
          findings == ["path does not exist: scripts/long-gone.py"], str(findings))

    # Nested deeper than the top level, which is how the real trio files sit.
    nested = frozen_root / "cold-read-reviewer-test-cases" / "ghi-write-trio"
    nested.mkdir()
    findings = problems_for(frozen_text, frozen_root,
                            name="cold-read-reviewer-test-cases/ghi-write-trio/deep.md")
    check("a file nested inside a frozen-data directory reports nothing",
          findings == [], str(findings))


print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
