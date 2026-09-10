#!/usr/bin/env python3
"""Tests for scripts/cold-read-reviewer-score.py.

Two kinds of case. SYNTHETIC: small placement tables and a small ruler built
in a scratch directory, where the right answer can be worked out by hand, so
parsing, weighting, unions and the exits are checked against arithmetic
rather than against the program's own output. PINNED: the weights the real
ghi-write ruler carries, checked against the figures already published in
`cold-read-records/2026-09-08-hunter-arm-trio-one/RESULT-addendum-2-severity-weighted-2026-09-08.md`,
so a change to the scoring math that would silently re-tune every published
number fails here instead.

The pinned cases use the committed ruler and a fixture of each reviewer's
rows-hit list. They deliberately do NOT use the real placement tables: those
are run output and live in the log-store, not in this repository.

Run: python3 scripts/cold-read-reviewer-score-test.py   (exit 0 = all passed)
"""

import importlib.util
import pathlib
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
SCORER = SCRIPTS_DIR / "cold-read-reviewer-score.py"
REAL_RULER = (SCRIPTS_DIR.parent / "cold-read-reviewer-test-cases"
              / "ghi-write-trio" / "ghi-write-defect-list-2026-09-07.md")

failures = []


def check(case_name, condition, detail=""):
    print(f"{'ok' if condition else 'FAIL'}: {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


def load_scorer():
    spec = importlib.util.spec_from_file_location("cold_read_reviewer_score", SCORER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scorer = load_scorer()


def run(*args):
    return subprocess.run([sys.executable, str(SCORER), *args],
                          capture_output=True, text=True, check=False)


def placement_table(rows):
    """rows: (id, placement, confidence, reason). Returns one table."""
    out = ["| Finding | Quote | Placement | Confidence | Reason |",
           "|---|---|---|---|---|"]
    for finding_id, placement, confidence, reason in rows:
        out.append(f"| {finding_id} | some quote | {placement} | {confidence} | {reason} |")
    return "\n".join(out) + "\n"


RULER = """\
# a small ruler

## Severity weights

| Row | Weight | Reason |
|---|---|---|
| 1 | 8 | heavy |
| 2 | 4 | middling |
| 3 | 1 | light |
| 4 | 0 | ruled not a defect |

## Something after it

| 1 | 99 | this table must NOT be read as a weight |
"""

with tempfile.TemporaryDirectory(prefix="cold-read-reviewer-score-test-") as name:
    scratch = pathlib.Path(name)
    ruler = scratch / "ruler.md"
    ruler.write_text(RULER, encoding="utf-8")
    placements = scratch / "placements"
    placements.mkdir()

    # alpha finds the heavy row and the light one, plus one false.
    (placements / "alpha--placement.md").write_text(placement_table([
        ("1", "ROW 1", "sure", "clean"),
        ("2", "ROW 3", "sure", "clean"),
        ("3", "FALSE", "unsure", "nearest miss, row 2"),
    ]), encoding="utf-8")
    # beta finds the middling row, and one finding on the not-a-defect row.
    (placements / "beta--placement.md").write_text(placement_table([
        ("1", "ROW 2", "sure", "clean"),
        ("2", "ROW 4", "sure", "the row the user ruled out"),
        ("3", "UNFIXED U1", "sure", "declined row"),
    ]), encoding="utf-8")

    # --- The ruler ---------------------------------------------------------
    weights = scorer.read_severity_weights(ruler)
    check("the weights table is read, and only within its own section",
          weights == {1: 8, 2: 4, 3: 1, 4: 0}, str(weights))
    check("a numeric table AFTER the section is not read as weights, which is "
          "the bug that reported a row weighted twice",
          weights[1] == 8, str(weights))

    total = sum(weights.values())
    check("total weight is the sum including the zero row", total == 13, str(total))

    # --- Scoring arithmetic ------------------------------------------------
    result = run("--placements", str(placements), "--defect-list", str(ruler))
    check("it scores and exits 0", result.returncode == 0,
          result.stdout + result.stderr)
    check("the header states the scored rows and total weight, and names the "
          "row ruled not a defect",
          "3 scored rows, total weight 13" in result.stdout
          and "not defects: [4]" in result.stdout, result.stdout[:400])
    check("alpha's weight is 8 + 1 = 9 of 13, which is 69 %",
          "| alpha | 3 | 2 | 2 | 67 % | 9 | 69 % | 1 | 67 % |" in result.stdout,
          result.stdout)
    check("beta's hit on the weight-0 row is neither a hit nor a false hit: "
          "one row, weight 4",
          "| beta | 3 | 1 | 1 | 33 % | 4 | 31 % | 0 | 33 % |" in result.stdout,
          result.stdout)
    check("the union of both is every scored row, 13 of 13",
          "best 13 of 13 (100 %)" in result.stdout, result.stdout)
    check("no row is left unfound once both are counted",
          "## Rows no reviewer found\n\nnone" in result.stdout, result.stdout)

    # --- The hand-check ranking -------------------------------------------
    check("a FALSE naming a row its reviewer does not hold is ranked, and by "
          "the weight of that row",
          "FALSE naming row 2, which this reviewer does not hold" in result.stdout,
          result.stdout)

    # --- Bad invocations ---------------------------------------------------
    check("a missing defect list is a bad invocation, exit 64",
          run("--placements", str(placements),
              "--defect-list", str(scratch / "nope.md")).returncode == 64)
    check("a missing placements directory is a bad invocation, exit 64",
          run("--placements", str(scratch / "nope"),
              "--defect-list", str(ruler)).returncode == 64)
    check("a non-numeric --union-sizes is a bad invocation, exit 64",
          run("--placements", str(placements), "--defect-list", str(ruler),
              "--union-sizes", "two").returncode == 64)

    empty = scratch / "empty"
    empty.mkdir()
    check("an empty placements directory is a bad invocation, not a zero score",
          run("--placements", str(empty),
              "--defect-list", str(ruler)).returncode == 64)

    ruler_without = scratch / "no-weights.md"
    ruler_without.write_text("# a list with no weights section\n", encoding="utf-8")
    result = run("--placements", str(placements), "--defect-list", str(ruler_without))
    check("a defect list with no weights section is refused, saying so",
          result.returncode != 0 and "cannot be used as a ruler" in
          (result.stdout + result.stderr), result.stdout + result.stderr)

    # --- Parse anomalies are reported, not swallowed -----------------------
    stray = scratch / "stray"
    stray.mkdir()
    (stray / "gamma--placement.md").write_text(
        "| Finding | Quote | Placement | Confidence | Reason |\n"
        "|---|---|---|---|---|\n"
        "| 1 | ROW 1 | sure |\n"
        "| 2 | a quote | ROW 1 | sure | clean |\n", encoding="utf-8")
    result = run("--placements", str(stray), "--defect-list", str(ruler))
    check("a line that does not split into five cells is REPORTED, not skipped "
          "silently, because a lost finding moves every total",
          "cells, not 5" in result.stdout, result.stdout)

# --- Pinned to the published figures ---------------------------------------
if REAL_RULER.is_file():
    weights = scorer.read_severity_weights(REAL_RULER)
    scored = sum(1 for w in weights.values() if w > 0)
    check("the committed ghi-write ruler still carries 33 rows, 32 of them "
          "scored, totalling 102",
          len(weights) == 33 and scored == 32 and sum(weights.values()) == 102,
          f"rows {len(weights)}, scored {scored}, total {sum(weights.values())}")
    check("row 22 is the one weighted 0, the user's ruling that it is not a defect",
          weights[22] == 0 and all(w > 0 for r, w in weights.items() if r != 22))
    check("the six heavy rows and their weights are unchanged",
          [weights[r] for r in (30, 20, 6, 17, 11, 15)] == [8, 7, 6, 6, 5, 5],
          str([weights[r] for r in (30, 20, 6, 17, 11, 15)]))

    # Each reviewer's rows-hit list as published in RESULT.md, and the weight
    # the addendum reported for it. If the weighting math changes, these move.
    PUBLISHED = {
        "sol-max": ([1, 2, 3, 4, 6, 8, 11, 12, 13, 14, 16, 17, 20, 21, 23, 24,
                     25, 26, 27, 28, 29, 30], 75),
        "opus5-max": ([1, 2, 3, 4, 5, 7, 9, 10, 11, 12, 14, 16, 18, 20, 24, 25,
                       27, 28, 29, 30, 33], 65),
        "gem38-high": ([1, 2, 3, 4, 5, 7, 8, 10, 11, 12, 14, 16, 18, 20, 25, 27,
                        28, 29, 31, 33], 58),
        "fable51-max": ([1, 2, 3, 6, 7, 8, 11, 13, 14, 16, 17, 18, 20, 21, 23,
                         24, 26, 27], 60),
        "luna-xhigh": ([1, 2, 3, 4, 12, 13, 14, 15, 16, 23, 24, 25, 27, 28, 29,
                        32], 39),
        "terra-low": ([1, 2, 3, 4, 7, 8, 11, 12, 20, 27, 28, 29, 32], 38),
        "gem38-low": ([2, 3, 4, 7, 9, 11, 14, 20, 28, 29, 33], 35),
    }
    for reviewer, (rows, published_weight) in PUBLISHED.items():
        computed = sum(weights[r] for r in rows)
        check(f"{reviewer}'s published rows still weigh {published_weight}",
              computed == published_weight, f"computed {computed}")

    best_four = max(
        sum(weights[r] for r in set().union(*(set(PUBLISHED[m][0]) for m in combo)))
        for combo in __import__("itertools").combinations(PUBLISHED, 4))
    check("the best set of four still covers 100 of 102, as published",
          best_four == 100, str(best_four))

    found = set().union(*(set(rows) for rows, _ in PUBLISHED.values()))
    unfound = sorted(r for r in weights if weights[r] > 0 and r not in found)
    check("row 19 is still the only scored row no reviewer found",
          unfound == [19], str(unfound))
else:
    check("the committed ghi-write ruler is present", False, f"missing {REAL_RULER}")

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
