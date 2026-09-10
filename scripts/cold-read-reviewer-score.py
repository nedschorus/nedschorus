#!/usr/bin/env python3
"""Score reviewers against a defect list: per reviewer, and by union of a set.

WHAT THIS MEASURES. Point several reviewers at a document's first draft and
each writes findings. A separate placement agent maps each finding onto a row
of that document's defect list, or marks it FALSE. This program turns those
placement tables into the numbers: what fraction of the defects each reviewer
found, how much that is worth once severity is counted, and which SET of
reviewers covers the most between them, which is what picks a roster.

TWO RECALLS, PRINTED SIDE BY SIDE.

  FLAT     distinct rows hit, over the number of rows.
  WEIGHTED the weight of the rows hit, over the total weight.

Weighted is the one to read. Flat scoring treats a row whose defect erases an
issue body the same as one whose defect costs a reader one grep, and the two
are not the same miss. The weights live in the defect list itself, in its
"Severity weights" section, and this program reads them from there rather
than holding a copy: the list is the ruler, so the ruler has one home. A row
weighted 0 is one the user has ruled is not a defect at all; a finding placed
on it is neither a hit nor a false hit, the treatment the list's declined
rows already get.

PRECISION IS COUNT-BASED and unweighted, because a false finding lands on no
row and so has no weight.

WHERE THIS CAME FROM. It was two programs living inside a shipped cold-read
record, which is add-only: the first could not be edited once shipped, so the
second was written beside it rather than changing it. Code cannot be
maintained in a log-store. Consolidated here 2026-09-10, on the user's
ruling, with a test that pins its numbers to the ones already published.

INPUTS. `--placements` is a directory of placement tables, one markdown file
per reviewer, named `<reviewer>--*.md`, each holding one five-column table
whose Placement cell is `ROW n`, `ROW a+b`, `UNFIXED Un` or `FALSE` and whose
Confidence cell is `sure` or `unsure`. Those files are run output and live in
the log-store, not in this repository. `--defect-list` is the ruler, which
does live here, under cold-read-reviewer-test-cases/.

OUTPUT is markdown on stdout, for pasting into a record. Nothing is written
to disk. Exit 0 when it scored, 64 for a bad invocation.
"""

import argparse
import itertools
import pathlib
import re
import sys

PROGRAM = "cold-read-reviewer-score"
WEIGHTS_SECTION_HEADING = "## Severity weights"

PLACEMENT_ROW_PATTERN = re.compile(r"^ROW\s+(\d+)(?:\s*\+\s*(\d+))?$")
PLACEMENT_UNFIXED_PATTERN = re.compile(r"^UNFIXED\s+(U\d+)$")
SELF_REPORTED_TOTAL_PATTERN = re.compile(r"^\s*Findings:\s*(\d+)\s*$", re.MULTILINE)

EXIT_SCORED = 0
EXIT_BAD_INVOCATION = 64


class PlacementParseError(Exception):
    pass


def read_severity_weights(path: pathlib.Path) -> dict:
    """{row: weight} from the defect list's Severity weights table.

    Bounded to that one section: the list holds other numeric tables, and an
    unbounded scan reads a row number out of the old-to-new crosswalk and
    reports a row weighted twice. That happened, which is why the bound is
    here and this sentence is with it.
    """
    text = path.read_text(encoding="utf-8")
    start = text.find(WEIGHTS_SECTION_HEADING)
    if start < 0:
        raise SystemExit(
            f"{PROGRAM}: {path} has no '{WEIGHTS_SECTION_HEADING}' section, so "
            f"it cannot be used as a ruler")
    section = text[start + len(WEIGHTS_SECTION_HEADING):]
    next_heading = re.search(r"^## ", section, re.MULTILINE)
    if next_heading:
        section = section[:next_heading.start()]
    weights = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not re.fullmatch(r"\d+", cells[0]):
            continue
        if not re.fullmatch(r"\d+", cells[1]):
            continue
        row, weight = int(cells[0]), int(cells[1])
        if row in weights:
            raise SystemExit(f"{PROGRAM}: {path} weights row {row} twice")
        weights[row] = weight
    if not weights:
        raise SystemExit(f"{PROGRAM}: {path} has no weight rows")
    expected = set(range(1, max(weights) + 1))
    missing = sorted(expected - set(weights))
    if missing:
        raise SystemExit(f"{PROGRAM}: {path} weights are not contiguous from 1 — "
                         f"missing {missing}")
    return weights


def classify_placement(placement: str, source: str, finding_id: str, row_total: int):
    match = PLACEMENT_ROW_PATTERN.match(placement)
    if match:
        rows = {int(match.group(1))}
        if match.group(2):
            rows.add(int(match.group(2)))
        for row in rows:
            if not 1 <= row <= row_total:
                raise PlacementParseError(
                    f"{source}: finding {finding_id} placed on row {row}, "
                    f"outside 1-{row_total}")
        return rows, "HIT"
    if PLACEMENT_UNFIXED_PATTERN.match(placement):
        return set(), "UNFIXED"
    if placement == "FALSE":
        return set(), "FALSE"
    raise PlacementParseError(
        f"{source}: finding {finding_id} has unparseable placement {placement!r}")


def parse_one_placement_file(path: pathlib.Path, row_total: int):
    """(reviewer, findings, anomalies) for one placement table.

    NOTHING IS DROPPED SILENTLY. A pipe-line after the header that does not
    split into five cells is reported as an anomaly rather than skipped: the
    one way this parse loses a finding is a stray pipe inside a quoted phrase,
    and a lost finding moves every total.
    """
    reviewer = path.name.split("--")[0]
    findings, anomalies = [], []
    seen_header = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and cells[0].lower() == "finding":
            seen_header = True
            continue
        if cells and cells[0] and set(cells[0]) <= {"-", ":", " "}:
            continue
        if not seen_header:
            continue
        if len(cells) != 5:
            anomalies.append(f"{len(cells)} cells, not 5 — not parsed: {line[:120]}")
            continue
        finding_id, quote, placement_as_written, confidence, reason = cells
        # Markdown emphasis around the value is formatting, not a judgement:
        # one placer wrapped every cell in backticks.
        placement = placement_as_written.strip("`* ")
        rows, category = classify_placement(
            placement, path.name, finding_id, row_total)
        if len(rows) > 1 and rows != {2, 3}:
            anomalies.append(
                f"finding {finding_id}: two-row placement {placement!r} outside "
                f"the one ruled case — reported as written, not corrected")
        findings.append({
            "reviewer": reviewer, "id": finding_id, "quote": quote,
            "placement": placement, "rows": rows, "category": category,
            "confidence": confidence.strip("`* ").lower(), "reason": reason,
        })
    if not findings:
        raise PlacementParseError(f"{path}: no placement rows parsed")
    self_reported = SELF_REPORTED_TOTAL_PATTERN.search(
        path.read_text(encoding="utf-8"))
    if self_reported and int(self_reported.group(1)) != len(findings):
        anomalies.append(
            f"the placer's own total says {self_reported.group(1)} findings, "
            f"this parse found {len(findings)}")
    return reviewer, findings, anomalies


def summarize(findings, weights, total_weight, row_total):
    """One reviewer's figures. A hit on a weight-0 row counts as neither."""
    hits, false_count, unfixed_count, not_a_defect = [], 0, 0, 0
    for finding in findings:
        if finding["category"] == "HIT":
            if finding["rows"] and all(weights[r] == 0 for r in finding["rows"]):
                not_a_defect += 1
            else:
                hits.append(finding)
        elif finding["category"] == "FALSE":
            false_count += 1
        else:
            unfixed_count += 1
    rows_hit = set()
    for finding in hits:
        rows_hit |= {r for r in finding["rows"] if weights[r] > 0}
    weight_hit = sum(weights[r] for r in rows_hit)
    scored_rows = sum(1 for w in weights.values() if w > 0)
    return {
        "findings": len(findings), "hit_findings": len(hits),
        "rows_hit": rows_hit, "weight_hit": weight_hit,
        "flat_recall": len(rows_hit) / scored_rows if scored_rows else 0.0,
        "weighted_recall": weight_hit / total_weight if total_weight else 0.0,
        "false": false_count, "unfixed": unfixed_count,
        "not_a_defect": not_a_defect,
        "precision": len(hits) / len(findings) if findings else 0.0,
    }


def print_per_reviewer(summaries, weights, total_weight):
    scored_rows = sum(1 for w in weights.values() if w > 0)
    print("## Per reviewer\n")
    print(f"Flat recall is rows over {scored_rows}; weighted recall is the weight "
          f"of those rows over {total_weight}.\n")
    print("| Reviewer | Findings | Hits | Rows | Flat recall | Weight | "
          "Weighted recall | False | Precision |")
    print("|---|---|---|---|---|---|---|---|---|")
    for reviewer, s in sorted(summaries.items(),
                              key=lambda kv: (-kv[1]["weighted_recall"], kv[0])):
        print(f"| {reviewer} | {s['findings']} | {s['hit_findings']} | "
              f"{len(s['rows_hit'])} | {s['flat_recall'] * 100:.0f} % | "
              f"{s['weight_hit']} | {s['weighted_recall'] * 100:.0f} % | "
              f"{s['false']} | {s['precision'] * 100:.0f} % |")
    print()
    for reviewer, s in sorted(summaries.items()):
        print(f"- {reviewer} rows hit: "
              f"{', '.join(str(r) for r in sorted(s['rows_hit']))}")
    print()


def print_unions(summaries, weights, total_weight, sizes, show_top):
    print("## Unions — the number that picks a roster\n")
    for size in sizes:
        if size > len(summaries):
            continue
        scored = []
        for combination in itertools.combinations(sorted(summaries), size):
            union = set()
            for reviewer in combination:
                union |= summaries[reviewer]["rows_hit"]
            scored.append((sum(weights[r] for r in union), len(union), combination))
        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        best = scored[0]
        print(f"### Sets of {size} — best {best[0]} of {total_weight} "
              f"({best[0] / total_weight * 100:.0f} %)\n")
        print("| Set | Weight | Weighted recall | Rows | Heavy rows missed |")
        print("|---|---|---|---|---|")
        for weight, rows, combination in scored[:show_top]:
            union = set()
            for reviewer in combination:
                union |= summaries[reviewer]["rows_hit"]
            missed = sorted((r for r in weights
                             if weights[r] >= 5 and r not in union),
                            key=lambda r: -weights[r])
            print(f"| {' + '.join(combination)} | {weight} | "
                  f"{weight / total_weight * 100:.0f} % | {rows} | "
                  f"{', '.join(str(r) for r in missed) or 'none'} |")
        print()


def print_unfound(summaries, weights, total_weight):
    found = set()
    for s in summaries.values():
        found |= s["rows_hit"]
    unfound = sorted(r for r in weights if weights[r] > 0 and r not in found)
    print("## Rows no reviewer found\n")
    if unfound:
        total = sum(weights[r] for r in unfound)
        print(f"{len(unfound)} rows, weight {total} of {total_weight}: "
              + ", ".join(f"row {r} (weight {weights[r]})" for r in unfound))
    else:
        print("none")
    print()


def print_hand_check(all_findings, summaries, weights, depth):
    """The placements worth a person's time, ranked by the weight they move.

    Ranking every placement equally sends the check at rows worth one point.
    A placement matters in proportion to the weight of the row it bears on,
    and only where flipping it would actually move a total: a FALSE whose
    reason names a row the reviewer already holds moves nothing.
    """
    row_hits, reviewer_row_hits = {}, {}
    for finding in all_findings:
        if finding["category"] == "HIT":
            for row in finding["rows"]:
                row_hits.setdefault(row, []).append(finding)
                reviewer_row_hits.setdefault(
                    (finding["reviewer"], row), []).append(finding)

    ranked = []
    for finding in all_findings:
        reasons, bearing = [], set()
        held = summaries[finding["reviewer"]]["rows_hit"]
        if finding["category"] == "HIT":
            bearing = {r for r in finding["rows"] if weights[r] > 0
                       and len(reviewer_row_hits[(finding["reviewer"], r)]) == 1}
            sole = [r for r in bearing if len(row_hits[r]) == 1]
            if sole:
                reasons.append("only hit anywhere on row "
                               + ", ".join(str(r) for r in sorted(sole)))
        if finding["confidence"] != "sure":
            reasons.append("placer marked unsure")
        if finding["category"] == "FALSE":
            named = {int(m) for m in re.findall(
                r"\brow\s+(\d+)", finding["reason"], re.IGNORECASE)}
            named = {r for r in named
                     if r in weights and weights[r] > 0 and r not in held}
            if named:
                reasons.append("FALSE naming row "
                               + ", ".join(str(r) for r in sorted(named))
                               + ", which this reviewer does not hold")
                bearing = named
        if not reasons:
            continue
        marginality = (3 * any(r.startswith("only hit") for r in reasons)
                       + 2 * any("unsure" in r for r in reasons)
                       + 1 * any("FALSE naming" in r for r in reasons))
        bearing_weight = max((weights[r] for r in bearing), default=1)
        ranked.append((marginality * bearing_weight, finding, reasons, bearing_weight))
    ranked.sort(key=lambda item: (-item[0], item[1]["reviewer"], item[1]["id"]))

    print("## Placements worth checking by hand, ranked by weight moved\n")
    print("| Rank | Reviewer | Finding | Placement | Confidence | Bears on | "
          "Score | Why |")
    print("|---|---|---|---|---|---|---|---|")
    for index, (score, finding, reasons, bearing_weight) in enumerate(
            ranked[:depth], start=1):
        print(f"| {index} | {finding['reviewer']} | {finding['id']} | "
              f"{finding['placement']} | {finding['confidence']} | "
              f"weight {bearing_weight} | {score} | {'; '.join(reasons)} |")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Score reviewers against a defect list, flat and weighted.")
    parser.add_argument("--placements", required=True, type=pathlib.Path,
                        help="directory of placement tables, one per reviewer")
    parser.add_argument("--defect-list", required=True, type=pathlib.Path,
                        help="the defect list, which carries the severity weights")
    parser.add_argument("--union-sizes", default="2,3,4",
                        help="set sizes to score, comma-separated (default 2,3,4)")
    parser.add_argument("--top", type=int, default=6,
                        help="how many sets to show per size (default 6)")
    parser.add_argument("--hand-check-depth", type=int, default=10,
                        help="how many placements to rank for hand-checking")
    arguments = parser.parse_args()

    if not arguments.defect_list.is_file():
        print(f"{PROGRAM}: no defect list at {arguments.defect_list}", file=sys.stderr)
        return EXIT_BAD_INVOCATION
    if not arguments.placements.is_dir():
        print(f"{PROGRAM}: no placements directory at {arguments.placements}",
              file=sys.stderr)
        return EXIT_BAD_INVOCATION
    try:
        sizes = [int(s) for s in arguments.union_sizes.split(",") if s.strip()]
    except ValueError:
        print(f"{PROGRAM}: --union-sizes takes comma-separated integers, not "
              f"{arguments.union_sizes!r}", file=sys.stderr)
        return EXIT_BAD_INVOCATION

    weights = read_severity_weights(arguments.defect_list)
    total_weight = sum(weights.values())
    row_total = max(weights)

    placement_files = sorted(arguments.placements.glob("*.md"))
    if not placement_files:
        print(f"{PROGRAM}: no *.md placement tables under {arguments.placements}",
              file=sys.stderr)
        return EXIT_BAD_INVOCATION

    summaries, all_findings, anomalies_by_reviewer = {}, [], {}
    for path in placement_files:
        reviewer, findings, anomalies = parse_one_placement_file(path, row_total)
        summaries[reviewer] = summarize(findings, weights, total_weight, row_total)
        all_findings.extend(findings)
        if anomalies:
            anomalies_by_reviewer[reviewer] = anomalies

    scored_rows = sum(1 for w in weights.values() if w > 0)
    zero_rows = sorted(r for r in weights if weights[r] == 0)
    print(f"Ruler: {arguments.defect_list.name} — {scored_rows} scored rows, "
          f"total weight {total_weight}"
          + (f"; not defects: {zero_rows}" if zero_rows else "") + ".")
    print(f"Placements: {len(placement_files)} reviewers, "
          f"{len(all_findings)} findings.\n")
    print("## Parse anomalies\n")
    if anomalies_by_reviewer:
        for reviewer, anomalies in sorted(anomalies_by_reviewer.items()):
            for anomaly in anomalies:
                print(f"- {reviewer}: {anomaly}")
    else:
        print("None: every table row parsed to five cells.")
    print()
    print_per_reviewer(summaries, weights, total_weight)
    print_unions(summaries, weights, total_weight, sizes, arguments.top)
    print_unfound(summaries, weights, total_weight)
    print_hand_check(all_findings, summaries, weights, arguments.hand_check_depth)
    return EXIT_SCORED


if __name__ == "__main__":
    sys.exit(main())
