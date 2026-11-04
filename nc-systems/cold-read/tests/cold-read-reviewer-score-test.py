#!/usr/bin/env python3
"""Tests for nc-systems/cold-read/cold-read-reviewer-score.py.

Three kinds of case. SYNTHETIC: small placement tables and a small ruler built
in a scratch directory, where the right answer can be worked out by hand, so
parsing, weighting, unions and the exits are checked against arithmetic
rather than against the program's own output. PINNED: the weights the real
ghi-write ruler carries, checked against the figures the hunter arm published
in the log-store, so a change to the scoring math that would silently re-tune
every published number fails here instead. KEYS: the two committed defect
lists of the ghi-write trio, checked so that the newer one keeps the older
one's weights and neither older file nor the perfected draft changes.

The pinned cases drive the program's OWN summarize(), print_unions() and
print_unfound() with findings synthesized from each reviewer's published
rows-hit list, so the scoring math is what is under test; re-doing the sums
here would leave this half agreeing with itself. They deliberately do NOT use
the real placement tables: those are run output and live in the log-store,
not here.

Run: python3 nc-systems/cold-read/tests/cold-read-reviewer-score-test.py   (exit 0 = all passed)
"""

import contextlib
import hashlib
import importlib.util
import io
import pathlib
import subprocess
import sys
import tempfile

# This suite sits in nc-systems/cold-read/tests/; the programs it tests are
# one directory up.
SYSTEM_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent
SCORER = SYSTEM_DIRECTORY / "cold-read-reviewer-score.py"
TRIO = SYSTEM_DIRECTORY.parent.parent / "cold-read-reviewer-test-cases" / "ghi-write-trio"
REAL_RULER = TRIO / "ghi-write-defect-list-2026-09-07.md"
NEWER_RULER = TRIO / "ghi-write-defect-list-2026-11-03.md"
PERFECTED_DRAFT = TRIO / "ghi-write-perfected-2026-09-08.md"
FIRST_DRAFT = TRIO / "ghi-write-first-draft-6a098f4.md"
# Every published score was measured against these bytes.
FROZEN_FILE_SHA256 = {
    REAL_RULER: "d26b95e8a7d22b648fb4ea158bd30ee4c8367cc4cac93780e7c08cce8148a49c",
    PERFECTED_DRAFT: "bc6397219b3c853ca3061bd4e0195278c58ff498e92b334f63cb436400438639",
}

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
    """rows: (id, placement, confidence, reason[, quote]). Returns one table."""
    out = ["| Finding | Quote | Placement | Confidence | Reason |",
           "|---|---|---|---|---|"]
    for row in rows:
        finding_id, placement, confidence, reason = row[:4]
        quote = row[4] if len(row) > 4 else "some quote"
        out.append(f"| {finding_id} | {quote} | {placement} | {confidence} | {reason} |")
    return "\n".join(out) + "\n"


def write_placements(directory, files):
    directory.mkdir()
    for name, rows in files.items():
        (directory / name).write_text(placement_table(rows), encoding="utf-8")
    return directory


RULER = """\
# a small ruler

## A crosswalk that is not the declined table

| Old | New |
|---|---|
| U9 | 3 |

## Severity weights

| Row | Weight | Reason |
|---|---|---|
| 1 | 8 | heavy |
| 2 | 4 | middling |
| 3 | 1 | light |
| 4 | 0 | ruled not a defect |

## Something after it

| 1 | 99 | this table must NOT be read as a weight |

## Table 2 — declined

| U# | Raw | Why |
|---|---|---|
| U1 | a sentence | declined |

## Sentences with no defect

| Id | Sentence |
|---|---|
| N1 | Not for merely reading or citing an issue. |
| N2 | ## When Used |
"""

RULER_WITHOUT_EXTRAS = """\
# a small ruler with weights only

## Severity weights

| Row | Weight | Reason |
|---|---|---|
| 1 | 8 | heavy |
| 2 | 4 | middling |
| 3 | 1 | light |
| 4 | 0 | ruled not a defect |
"""

with tempfile.TemporaryDirectory(prefix="cold-read-reviewer-score-test-") as name:
    scratch = pathlib.Path(name)
    ruler = scratch / "ruler.md"
    ruler.write_text(RULER, encoding="utf-8")
    plain_ruler = scratch / "plain-ruler.md"
    plain_ruler.write_text(RULER_WITHOUT_EXTRAS, encoding="utf-8")

    placements = write_placements(scratch / "placements", {
        # alpha finds the heavy row and the light one, plus one false.
        "alpha--placement.md": [
            ("1", "ROW 1", "sure", "clean"),
            ("2", "ROW 3", "sure", "clean"),
            ("3", "FALSE", "unsure", "nearest miss, row 2"),
        ],
        # beta finds the middling row, one finding on the not-a-defect row and
        # one on a declined entry.
        "beta--placement.md": [
            ("1", "ROW 2", "sure", "clean"),
            ("2", "ROW 4", "sure", "the row the user ruled out"),
            ("3", "UNFIXED U1", "sure", "declined row"),
        ],
    })

    # --- The ruler ---------------------------------------------------------
    weights = scorer.read_severity_weights(ruler)
    check("the weights table is read, and only within its own section",
          weights == {1: 8, 2: 4, 3: 1, 4: 0}, str(weights))
    check("a numeric table AFTER the section is not read as weights, which is "
          "the bug that reported a row weighted twice",
          weights[1] == 8, str(weights))

    total = sum(weights.values())
    check("total weight is the sum including the zero row", total == 13, str(total))

    check("the declined entries are read from Table 2 only, not from a "
          "crosswalk that also holds U-numbers",
          scorer.read_defect_list_declined_entries(ruler) == {"U1"},
          str(scorer.read_defect_list_declined_entries(ruler)))
    check("a list with no Table 2 has no declined entries",
          scorer.read_defect_list_declined_entries(plain_ruler) == set())
    check("the sentences with no defect are read with their ids",
          scorer.read_defect_list_sentences_with_no_defect(ruler)
          == {"N1": "Not for merely reading or citing an issue.",
              "N2": "## When Used"},
          str(scorer.read_defect_list_sentences_with_no_defect(ruler)))
    check("a list with no sentences-with-no-defect section gives None, not an "
          "empty list that would print twelve true negatives for nothing",
          scorer.read_defect_list_sentences_with_no_defect(plain_ruler) is None)

    # --- Scoring arithmetic ------------------------------------------------
    result = run("--placements", str(placements), "--defect-list", str(ruler))
    check("it scores and exits 0", result.returncode == 0,
          result.stdout + result.stderr)
    check("the header states the scored rows and total weight, and names the "
          "row ruled not a defect",
          "3 scored rows, total weight 13" in result.stdout
          and "not defects: [4]" in result.stdout, result.stdout[:400])
    check("alpha's weight is 8 + 1 = 9 of 13, which is 69 %; precision 2 of 3",
          "| alpha | 3 | 2 | 2 | 67 % | 9 | 69 % | 1 | 0 | 0 | 0 | 67 % |"
          in result.stdout, result.stdout)
    check("beta's hit on the weight-0 row is neither a hit nor a false hit: "
          "one row, weight 4",
          "| beta | 3 | 1 | 1 | 33 % | 4 | 31 % | 0 | 1 | 1 | 0 |" in result.stdout,
          result.stdout)
    check("the union of both is every scored row, 13 of 13",
          "best 13 of 13 (100 %)" in result.stdout, result.stdout)
    check("no row is left unfound once both are counted",
          "## Rows no reviewer found\n\nnone" in result.stdout, result.stdout)
    check("with no run suffix on any file, no per-reader section is printed",
          "## Per reader over repeated runs" not in result.stdout, result.stdout)

    # --- Fault: precision counted neither-placements as false ---------------
    # beta has one hit, one weight-0 placement and one UNFIXED and no FALSE;
    # dividing by every finding gave 33 %.
    check("precision is hits over hits plus FALSE: beta's weight-0 and UNFIXED "
          "placements stay out of it, 1 of 1 = 100 %, not 33 %",
          "| beta | 3 | 1 | 1 | 33 % | 4 | 31 % | 0 | 1 | 1 | 0 | 100 % |"
          in result.stdout, result.stdout)
    nothing_judged = scorer.summarize(
        [{"reviewer": "x", "id": "1", "quote": "q", "placement": "UNFIXED U1",
          "rows": set(), "category": "UNFIXED", "confidence": "sure", "reason": ""}],
        weights, total, 4)
    check("precision with no hit and no FALSE is 0, not a division by zero",
          nothing_judged["precision"] == 0.0, str(nothing_judged))

    # --- Fault: findings true only of the reader checkout had no category----------------
    artifact_placements = write_placements(scratch / "artifact", {
        "delta--placement.md": [
            ("1", "ROW 1", "sure", "clean"),
            ("2", "TRUE-ONLY-OF-READER-CHECKOUT-NOT-OF-DRAFT", "sure", "path retired after the draft"),
            ("3", "FALSE", "sure", "nothing"),
        ],
    })
    result = run("--placements", str(artifact_placements), "--defect-list", str(ruler))
    check("a TRUE-ONLY-OF-READER-CHECKOUT-NOT-OF-DRAFT placement is neither hit nor false: counted in "
          "its own column and out of precision, 1 of 2 = 50 %",
          "| delta | 3 | 1 | 1 | 33 % | 8 | 62 % | 1 | 0 | 0 | 1 | 50 % |"
          in result.stdout, result.stdout + result.stderr)

    # --- Fault: any UNFIXED number was accepted ----------------------------
    wrong_u = write_placements(scratch / "wrong-u", {
        "eps--placement.md": [("1", "UNFIXED U9", "sure", "a crosswalk number")],
    })
    result = run("--placements", str(wrong_u), "--defect-list", str(ruler))
    check("an UNFIXED number the declined table does not hold is refused, exit "
          "64, naming the ones it holds",
          result.returncode == 64 and "UNFIXED U9" in result.stderr
          and "holds only U1" in result.stderr, result.stdout + result.stderr)
    result = run("--placements", str(placements), "--defect-list", str(plain_ruler))
    check("an UNFIXED placement against a list with no declined table is "
          "refused, saying the table is missing",
          result.returncode == 64
          and "has no declined table" in result.stderr
          and "`UNFIXED U<n>` for" not in result.stderr, result.stderr)
    result = run("--placements", str(wrong_u), "--defect-list", str(ruler))
    check("the UNFIXED refusal names the placement file by its path, offers "
          "UNFIXED while the declined table exists, and prints the command to "
          "rerun",
          str(wrong_u / "eps--placement.md") in result.stderr
          and "`UNFIXED U<n>` for" in result.stderr
          and "Scorer command: python3 " in result.stderr, result.stderr)

    # --- Fault: two readers' files were merged into one --------------------
    two_runs_old_style = write_placements(scratch / "old-style-runs", {
        "sonnet--run1--placement.md": [("1", "ROW 1", "sure", "x"),
                                       ("2", "ROW 2", "sure", "x")],
        "sonnet--run2--placement.md": [("1", "ROW 3", "sure", "x")],
    })
    result = run("--placements", str(two_runs_old_style), "--defect-list", str(ruler))
    check("two files whose names share the part before the first '--' stay two "
          "reviewers, so the first file's rows 1 and 2 are not lost",
          "- sonnet--run1 rows hit: 1, 2" in result.stdout
          and "- sonnet--run2 rows hit: 3" in result.stdout
          and "## Rows no reviewer found\n\nnone" in result.stdout,
          result.stdout + result.stderr)
    same_reviewer = write_placements(scratch / "same-reviewer", {
        "zeta.md": [("1", "ROW 1", "sure", "x")],
        "zeta--placement.md": [("1", "ROW 2", "sure", "x")],
    })
    result = run("--placements", str(same_reviewer), "--defect-list", str(ruler))
    check("two files that name one reviewer are refused, exit 64, naming both "
          "files, instead of one replacing the other",
          result.returncode == 64 and "zeta.md" in result.stderr
          and "zeta--placement.md" in result.stderr
          and "nothing was scored" in result.stderr
          and "The two files are different." in result.stderr
          and "Then run the scorer again: python3 " in result.stderr,
          result.stdout + result.stderr)
    identical_copies = write_placements(scratch / "identical-copies", {
        "theta.md": [("1", "ROW 1", "sure", "x")],
        "theta--placement.md": [("1", "ROW 1", "sure", "x")],
    })
    result = run("--placements", str(identical_copies), "--defect-list", str(ruler))
    check("two byte-identical files that name one reviewer are refused, saying "
          "they are byte-identical",
          result.returncode == 64
          and "The two files are byte-identical." in result.stderr,
          result.stdout + result.stderr)
    check("a reviewer's name is the file name before '--placement.md'",
          scorer.reviewer_name_from_placement_file_name(pathlib.Path("a--b--placement.md")) == "a--b"
          and scorer.reviewer_name_from_placement_file_name(pathlib.Path("a--b.md")) == "a--b")

    # --- Fault: repeated reads of one reader were not grouped --------------
    runs = write_placements(scratch / "runs", {
        "ann-run-1--placement.md": [("1", "ROW 1", "sure", "x")],
        "ann-run-2--placement.md": [("1", "ROW 2", "sure", "x")],
        "ann-run-3--placement.md": [("1", "ROW 3", "sure", "x")],
        "bob-run-1--placement.md": [("1", "ROW 2", "sure", "x")],
        "bob-run-2--placement.md": [("1", "ROW 1", "sure", "x")],
        "bob-run-3--placement.md": [("1", "ROW 1", "sure", "x"),
                                    ("2", "FALSE", "sure", "x")],
        "carl--placement.md": [("1", "ROW 3", "sure", "x")],
    })
    result = run("--placements", str(runs), "--defect-list", str(ruler))
    out = result.stdout
    check("a reader's runs are grouped: ann's weighted recall per run is 62, 31 "
          "and 8 %, median 31 %",
          "| ann | 3 | 62 %, 31 %, 8 % | 31 % | 100 %, 100 %, 100 % | 100 % | "
          "0, 0, 0 | 0 |" in out, out + result.stderr)
    check("bob's median precision is 100 % over runs of 100, 100 and 50 %",
          "| bob | 3 | 31 %, 62 %, 62 % | 62 % | 100 %, 100 %, 50 % | 100 % | "
          "0, 0, 1 | 0 |" in out, out)
    check("a file with no run suffix is run 1 of its own reader",
          "| carl | 1 | 8 % | 8 % |" in out, out)
    check("no set pairs two runs of one reader",
          "ann-run-1 + ann-run-2" not in out and "ann + bob" in out, out)
    check("ann + bob is scored per run index, 12, 12 and 9, and reported at "
          "its median, 12 of 13",
          "### Sets of 2 — best 12 of 13 (92 %)" in out
          and "| ann + bob | 12 | 92 % | 2 | none |" in out, out)
    check("a set takes only the run indices every member has: ann + carl is "
          "scored on run 1 alone, rows 1 and 3, weight 9",
          "| ann + carl | 9 | 69 % | 2 | none |" in out, out)
    check("the set of all three readers is scored on their common run 1",
          "### Sets of 3 — best 13 of 13 (100 %)" in out, out)
    check("a median between two values prints with one decimal, a whole one "
          "without", scorer.format_median_as_integer_or_one_decimal(12) == "12"
          and scorer.format_median_as_integer_or_one_decimal(10.5) == "10.5")
    check("a reviewer's reader and run come from its -run-<k> suffix",
          scorer.reader_and_run_index_from_reviewer_name("ann-run-12") == ("ann", 12)
          and scorer.reader_and_run_index_from_reviewer_name("gem38-high") == ("gem38-high", 1))

    heavy_missed = write_placements(scratch / "heavy-missed", {
        "ann-run-1--placement.md": [("1", "ROW 1", "sure", "x")],
        "ann-run-2--placement.md": [("1", "ROW 2", "sure", "x")],
        "bob-run-1--placement.md": [("1", "ROW 3", "sure", "x")],
        "bob-run-2--placement.md": [("1", "ROW 3", "sure", "x")],
    })
    result = run("--placements", str(heavy_missed), "--defect-list", str(ruler))
    check("a heavy row missed in half the runs of a set is listed as missed, "
          "and the median of 9 and 5 prints as 7",
          "| ann + bob | 7 | 54 % | 2 | 1 |" in result.stdout,
          result.stdout + result.stderr)

    # --- Flags on the sentences with no defect -----------------------------
    clean = write_placements(scratch / "clean", {
        "eta--placement.md": [
            ("1", "FALSE", "sure", "x", "\"Not for   merely reading\""),
            ("2", "FALSE", "sure", "x", "a sentence the list does not hold"),
            ("3", "ROW 1", "sure", "x", "Not for merely reading or citing an issue."),
            ("4", "FALSE", "sure", "x", "\"\""),
        ],
    })
    result = run("--placements", str(clean), "--defect-list", str(ruler))
    check("a FALSE finding whose quote, whitespace normalised and quotation "
          "marks stripped, lies inside a listed sentence counts once on that sentence; "
          "a hit there, an unlisted quote and an empty quote "
          "are not",
          "| eta | 1 | N1 | 1 |" in result.stdout, result.stdout + result.stderr)
    result = run("--placements", str(artifact_placements),
                 "--defect-list", str(plain_ruler))
    check("a list with no sentences-with-no-defect section prints no section on "
          "them", result.returncode == 0
          and "## Flags on the sentences with no defect" not in result.stdout,
          result.stdout + result.stderr)

    # --- The hand-check ranking -------------------------------------------
    result = run("--placements", str(placements), "--defect-list", str(ruler))
    check("a FALSE naming a row its reviewer does not hold is ranked, and by "
          "the weight of that row",
          "FALSE naming row 2, which this reviewer does not hold" in result.stdout,
          result.stdout)

    # --- The default ruler -------------------------------------------------
    alpha_only = write_placements(scratch / "alpha-only", {
        "alpha--placement.md": [("1", "ROW 1", "sure", "clean")],
    })
    result = run("--placements", str(alpha_only))
    check("with no --defect-list the ruler is the older list, so published "
          "scores reproduce",
          result.returncode == 0 and "Ruler: ghi-write-defect-list-2026-09-07.md — "
          "32 scored rows, total weight 102" in result.stdout,
          result.stdout + result.stderr)
    result = run("--placements", str(alpha_only), "--defect-list", str(NEWER_RULER))
    check("--defect-list names the newer list, which scores 33 rows of 104",
          result.returncode == 0 and "Ruler: ghi-write-defect-list-2026-11-03.md — "
          "33 scored rows, total weight 104" in result.stdout,
          result.stdout + result.stderr)

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

# --- The committed keys -----------------------------------------------------
for path, digest in FROZEN_FILE_SHA256.items():
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    check(f"{path.name} is byte-for-byte the file every published score was "
          f"measured against", actual == digest, f"sha256 {actual}")

if REAL_RULER.is_file() and NEWER_RULER.is_file():
    old_weights = scorer.read_severity_weights(REAL_RULER)
    new_weights = scorer.read_severity_weights(NEWER_RULER)
    changed = {r: (old_weights[r], new_weights.get(r)) for r in old_weights
               if new_weights.get(r) != old_weights[r]}
    check("rows 1 to 33 of the newer list carry the older list's weights",
          len(old_weights) == 33 and not changed, f"changed {changed}")
    check("the newer list adds only row 34, at weight 2: 34 rows, 33 scored, 104",
          set(new_weights) - set(old_weights) == {34} and new_weights[34] == 2
          and sum(new_weights.values()) == 104
          and sum(1 for w in new_weights.values() if w > 0) == 33,
          str(new_weights))
    check("the newer list declines the same entries as the older, U5, U7 and U8",
          scorer.read_defect_list_declined_entries(NEWER_RULER)
          == scorer.read_defect_list_declined_entries(REAL_RULER) == {"U5", "U7", "U8"},
          str(scorer.read_defect_list_declined_entries(NEWER_RULER)))
    check("the older list has no sentences-with-no-defect section, so its "
          "scores print as before",
          scorer.read_defect_list_sentences_with_no_defect(REAL_RULER) is None)
    clean_sentences = scorer.read_defect_list_sentences_with_no_defect(NEWER_RULER) or {}
    raw = scorer.normalise_whitespace(FIRST_DRAFT.read_text(encoding="utf-8"))
    not_in_raw = [i for i, s in clean_sentences.items() if s not in raw]
    check("the newer list names twelve sentences with no defect, each quoted "
          "exactly from the first draft",
          len(clean_sentences) == 12 and not not_in_raw,
          f"{len(clean_sentences)} sentences; not in the draft: {not_in_raw}")
else:
    check("both committed ghi-write defect lists are present", False,
          f"missing {REAL_RULER} or {NEWER_RULER}")

# --- Pinned to the published figures ---------------------------------------
# These cases drive the PROGRAM'S OWN summarize() and print_unions() with
# findings synthesized from each reviewer's published rows-hit list. The
# published figures are ghi-write's; the program is generic, and the only
# thing tying these cases to that document is the ruler they load.
if REAL_RULER.is_file():
    weights = scorer.read_severity_weights(REAL_RULER)
    total_weight = sum(weights.values())
    row_total = max(weights)
    scored = sum(1 for w in weights.values() if w > 0)
    check("the committed ghi-write ruler still carries 33 rows, 32 of them "
          "scored, totalling 102",
          len(weights) == 33 and scored == 32 and total_weight == 102,
          f"rows {len(weights)}, scored {scored}, total {total_weight}")
    check("row 22 is the one weighted 0, the user's ruling that it is not a defect",
          weights[22] == 0 and all(w > 0 for r, w in weights.items() if r != 22))
    check("the six heaviest rows and their weights are unchanged",
          [weights[r] for r in (30, 20, 6, 17, 11, 15)] == [8, 7, 6, 6, 5, 5],
          str([weights[r] for r in (30, 20, 6, 17, 11, 15)]))

    # Each reviewer's rows-hit list as published in RESULT.md, and the weight
    # the severity-weighted addendum reported for it.
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

    def findings_for(reviewer, rows):
        """One HIT finding per published row, in the shape the parser emits."""
        return [{"reviewer": reviewer, "id": str(i), "quote": "q",
                 "placement": f"ROW {row}", "rows": {row}, "category": "HIT",
                 "confidence": "sure", "reason": ""}
                for i, row in enumerate(rows, start=1)]

    summaries = {}
    for reviewer, (rows, published_weight) in PUBLISHED.items():
        summary = scorer.summarize(findings_for(reviewer, rows), weights,
                                   total_weight, row_total)
        summaries[reviewer] = summary
        check(f"summarize() gives {reviewer} the published weight "
              f"{published_weight}",
              summary["weight_hit"] == published_weight,
              f"got {summary['weight_hit']}")
        check(f"summarize() gives {reviewer} the published rows",
              summary["rows_hit"] == set(rows),
              str(sorted(summary["rows_hit"])))

    check("summarize() puts sol-max top on weighted recall, at 74 %",
          round(summaries["sol-max"]["weighted_recall"] * 100) == 74,
          str(summaries["sol-max"]["weighted_recall"]))
    check("summarize() has fable51-max outweigh gem38-high on FEWER rows, "
          "which is what weighting changed",
          summaries["fable51-max"]["weight_hit"] > summaries["gem38-high"]["weight_hit"]
          and len(summaries["fable51-max"]["rows_hit"])
          < len(summaries["gem38-high"]["rows_hit"]))

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        scorer.print_unions(summaries, weights, total_weight, [2, 3, 4], 6)
    unions_output = captured.getvalue()
    check("print_unions() reports the published best set of four, 100 of 102",
          "### Sets of 4 — best 100 of 102 (98 %)" in unions_output,
          unions_output[-600:])
    check("print_unions() reports the published best set of three, 98 of 102",
          "### Sets of 3 — best 98 of 102 (96 %)" in unions_output,
          unions_output[:600])
    check("print_unions() reports the published best pair, 92 of 102",
          "### Sets of 2 — best 92 of 102 (90 %)" in unions_output,
          unions_output[:300])
    check("print_unions() prints no repeated-runs note when no reviewer has runs",
          "run index" not in unions_output, unions_output[:300])

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        scorer.print_unfound(summaries, weights, total_weight)
    check("print_unfound() reports row 19 as the only scored row nobody found",
          "1 rows, weight 2 of 102: row 19 (weight 2)" in captured.getvalue(),
          captured.getvalue())
else:
    check("the committed ghi-write ruler is present", False, f"missing {REAL_RULER}")

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
