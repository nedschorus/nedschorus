#!/usr/bin/env python3
"""Tests for md-drift-lint.py.

Run: python3 scripts/md-drift-lint-test.py
"""

import importlib.util
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
        'parser.add_argument("--threshold")\n', encoding="utf-8"
    )
    (root / "docs").mkdir()
    (root / "docs" / "real-doc.md").write_text("# real\n", encoding="utf-8")

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

    # --- Bare basenames, history lines, placeholders ----------------------
    check("a bare basename existing elsewhere in the repo resolves",
          problems_for("run `real-script.py --threshold 1`", root) == [])
    check("a git-history line's paths are not checked",
          problems_for("deleted, in git history at `docs/gone-forever.md`", root) == [])
    check("an ellipsis placeholder is skipped",
          problems_for("each has a `…-test.py` twin", root) == [])
    problems = problems_for("in git history at `x.md`, dated 2026-13-40", root)
    check("dates are still checked on a git-history line",
          any("2026-13-40" in p for p in problems), str(problems))

    # --- Code fences ------------------------------------------------------
    check("fenced code blocks are skipped",
          problems_for("```\n`scripts/ghost.py` and 2026-13-40\n```\n", root) == [])

    # --- JSON duplicate keys ----------------------------------------------
    good_json = root / "good.json"
    good_json.write_text('{"a": 1, "b": {"c": 2}}', encoding="utf-8")
    check("clean json passes", list(lint.lint_json(good_json)) == [])
    dup_json = root / "dup.json"
    dup_json.write_text('{"hooks": {"Stop": 1, "Pre": 2, "Stop": 3}}', encoding="utf-8")
    problems = [problem for _, problem in lint.lint_json(dup_json)]
    check("a duplicate nested key is reported",
          any("Stop" in p for p in problems), str(problems))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
