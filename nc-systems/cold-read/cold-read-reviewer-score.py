#!/usr/bin/env python3
"""Score reviewers against a defect list, individually and in sets.

Severity weights belong to the defect list. Precision is hits over hits plus
FALSE findings and is unweighted, because false findings have no defect row
and therefore no severity weight. A placement on a weight-0 row, an UNFIXED
placement and a TRUE-ONLY-OF-READER-CHECKOUT-NOT-OF-DRAFT placement are neither hits nor false, and
stay out of recall and precision alike.

A placement file is named `<reviewer>--placement.md`. Repeated reads of one
reader are named `<reader>-run-<k>--placement.md`: each file is scored on its
own, and sets of readers are scored once per run index k from the k-th run of
each member, reporting the median over the run indices every member has. A
file with no `-run-<k>` is run 1 of its reader, and two files that give one
reader the same run index, such as `ann--placement.md` and
`ann-run-1--placement.md`, are refused with exit 64.

When the defect list has a `## Sentences with no defect` section, a FALSE
finding whose quote, whitespace normalised, lies inside one of its sentences
is counted as a FALSE finding on a sentence with no defect. The match is plain substring
containment: a short quote such as one word can lie inside a listed sentence
while the reader meant another sentence that shares the word."""

import argparse
import itertools
import pathlib
import re
import shlex
import statistics
import sys

PROGRAM = "cold-read-reviewer-score"
WEIGHTS_SECTION_HEADING = "## Severity weights"
DECLINED_SECTION_HEADING = "## Table 2"
CLEAN_SENTENCES_SECTION_HEADING = "## Sentences with no defect"
# Published scores were measured against this list, so it stays the default
# when a newer list exists beside it.
DEFAULT_DEFECT_LIST = (pathlib.Path(__file__).resolve().parent.parent.parent
                       / "cold-read-reviewer-test-cases" / "ghi-write-trio"
                       / "ghi-write-defect-list-2026-09-07.md")
PLACEMENT_FILE_SUFFIX = "--placement.md"

PLACEMENT_ROW_PATTERN = re.compile(r"^ROW\s+(\d+)(?:\s*\+\s*(\d+))?$")
PLACEMENT_UNFIXED_PATTERN = re.compile(r"^UNFIXED\s+(U\d+)$")
PLACEMENT_TRUE_ONLY_OF_READER_CHECKOUT_NOT_OF_DRAFT = "TRUE-ONLY-OF-READER-CHECKOUT-NOT-OF-DRAFT"
REVIEWER_RUN_PATTERN = re.compile(r"^(.+)-run-(\d+)$")
SELF_REPORTED_TOTAL_PATTERN = re.compile(r"^\s*Findings:\s*(\d+)\s*$", re.MULTILINE)

EXIT_SCORED = 0
EXIT_BAD_INVOCATION = 64


class PlacementParseError(Exception):
    pass


def read_section(text: str, heading: str):
    """Return the text under the first heading starting with `heading`, up to the next `## `, or None."""
    # Other sections contain tables of the same shape; an unbounded scan would read them.
    start = re.search(r"^" + re.escape(heading), text, re.MULTILINE)
    if not start:
        return None
    section = text[start.end():]
    section = section[section.find("\n") + 1:] if "\n" in section else ""
    next_heading = re.search(r"^## ", section, re.MULTILINE)
    if next_heading:
        section = section[:next_heading.start()]
    return section


def table_rows(section: str):
    for line in section.splitlines():
        yield [cell.strip() for cell in line.strip().strip("|").split("|")]


def read_severity_weights(path: pathlib.Path) -> dict:
    """Return {row: weight} from the Severity weights table."""
    section = read_section(path.read_text(encoding="utf-8"), WEIGHTS_SECTION_HEADING)
    if section is None:
        raise SystemExit(
            f"{PROGRAM}: {path} has no '{WEIGHTS_SECTION_HEADING}' section, so "
            f"it cannot be used as a ruler")
    weights = {}
    for cells in table_rows(section):
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


def read_defect_list_declined_entries(path: pathlib.Path) -> set:
    """Return the U-numbers of the declined table; empty when the list has none."""
    section = read_section(path.read_text(encoding="utf-8"), DECLINED_SECTION_HEADING)
    if section is None:
        return set()
    return {cells[0] for cells in table_rows(section)
            if cells and re.fullmatch(r"U\d+", cells[0])}


def normalise_whitespace(text: str) -> str:
    return " ".join(text.split())


def read_defect_list_sentences_with_no_defect(path: pathlib.Path):
    """Return {id: sentence} from the sentences-with-no-defect table, or None when the list has none."""
    section = read_section(path.read_text(encoding="utf-8"),
                           CLEAN_SENTENCES_SECTION_HEADING)
    if section is None:
        return None
    sentences = {}
    for cells in table_rows(section):
        if len(cells) >= 2 and re.fullmatch(r"N\d+", cells[0]):
            sentences[cells[0]] = normalise_whitespace(cells[1])
    return sentences


def clean_sentences_holding_quote(quote: str, clean_sentences: dict) -> set:
    # Placers often wrap a quote in quotation marks; the marks are not the reader's words.
    normalised = normalise_whitespace(quote).strip("\"“”").strip()
    if not normalised:
        return set()
    return {sentence_id for sentence_id, sentence in clean_sentences.items()
            if normalised in sentence}


def reviewer_name_from_placement_file_name(path: pathlib.Path) -> str:
    if path.name.endswith(PLACEMENT_FILE_SUFFIX):
        return path.name[:-len(PLACEMENT_FILE_SUFFIX)]
    return path.stem


def reader_and_run_index_from_reviewer_name(reviewer: str):
    """Return (reader, run index); a reviewer with no `-run-<k>` suffix is run 1 of itself."""
    match = REVIEWER_RUN_PATTERN.match(reviewer)
    if match:
        return match.group(1), int(match.group(2))
    return reviewer, 1


def classify_placement(placement: str, source: str, finding_id: str,
                       row_total: int, declined: set):
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
    match = PLACEMENT_UNFIXED_PATTERN.match(placement)
    if match:
        if match.group(1) not in declined:
            held = ", ".join(sorted(declined, key=lambda u: int(u[1:])))
            raise PlacementParseError(
                f"{source}: finding {finding_id} is placed `UNFIXED {match.group(1)}`, "
                f"but "
                + (f"the defect list's declined table, its '## Table 2' section, "
                   f"holds only {held}"
                   if held else "the defect list has no declined table, no "
                   "'## Table 2' section")
                + f". Nothing was scored, because a U-number the list does not "
                f"hold would make that finding count as neither hit nor false "
                f"without anyone seeing it.\n"
                f"Place that finding again in {source} with one of the forms the "
                f"scorer reads: "
                + ("`UNFIXED U<n>` for a U-number the declined table holds, "
                   if held else "")
                + f"`ROW <n>` for the Table 1 row whose fault the finding "
                f"names, `{PLACEMENT_TRUE_ONLY_OF_READER_CHECKOUT_NOT_OF_DRAFT}` "
                f"when the finding is true only of the reader's checkout and "
                f"tools, or `FALSE` when it names no fault the defect list holds; "
                f"then run the scorer command printed below again. The scorer "
                f"stops at the first such placement, so the rerun may show "
                f"another.\n"
                f"When the finding names a declined entry this list does not "
                f"hold, the form is `FALSE`: tell the agent or person who asked "
                f"for the score which finding that was and which entry it names, "
                f"and do not edit the defect list, whose rows every published "
                f"score was measured against.")
        return set(), "UNFIXED"
    if placement == PLACEMENT_TRUE_ONLY_OF_READER_CHECKOUT_NOT_OF_DRAFT:
        return set(), "TRUE_ONLY_OF_READER_CHECKOUT_NOT_OF_DRAFT"
    if placement == "FALSE":
        return set(), "FALSE"
    raise PlacementParseError(
        f"{source}: finding {finding_id} has unparseable placement {placement!r}")


def parse_one_placement_file(path: pathlib.Path, row_total: int, declined: set):
    """Return (reviewer, findings, anomalies) for one placement table."""
    # A stray pipe can split a finding into extra cells; dropping that row would change the totals.
    reviewer = reviewer_name_from_placement_file_name(path)
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
        # Markdown emphasis is formatting, not a judgment.
        placement = placement_as_written.strip("`* ")
        rows, category = classify_placement(
            placement, str(path), finding_id, row_total, declined)
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


def summarize(findings, weights, total_weight, row_total, clean_sentences=None):
    """Return reviewer figures; weight-zero rows, UNFIXED and findings true only of the reader checkout count as neither hits nor false hits."""
    hits, false_count, unfixed_count, not_a_defect, true_only_of_reader_checkout = [], 0, 0, 0, 0
    false_on_sentences_with_no_defect, sentences_flagged = 0, set()
    for finding in findings:
        if finding["category"] == "HIT":
            if finding["rows"] and all(weights[r] == 0 for r in finding["rows"]):
                not_a_defect += 1
            else:
                hits.append(finding)
        elif finding["category"] == "FALSE":
            false_count += 1
            if clean_sentences:
                holding = clean_sentences_holding_quote(finding["quote"], clean_sentences)
                if holding:
                    false_on_sentences_with_no_defect += 1
                    sentences_flagged |= holding
        elif finding["category"] == "TRUE_ONLY_OF_READER_CHECKOUT_NOT_OF_DRAFT":
            true_only_of_reader_checkout += 1
        else:
            unfixed_count += 1
    rows_hit = set()
    for finding in hits:
        rows_hit |= {r for r in finding["rows"] if weights[r] > 0}
    weight_hit = sum(weights[r] for r in rows_hit)
    scored_rows = sum(1 for w in weights.values() if w > 0)
    judged = len(hits) + false_count
    return {
        "findings": len(findings), "hit_findings": len(hits),
        "rows_hit": rows_hit, "weight_hit": weight_hit,
        "flat_recall": len(rows_hit) / scored_rows if scored_rows else 0.0,
        "weighted_recall": weight_hit / total_weight if total_weight else 0.0,
        "false": false_count, "unfixed": unfixed_count,
        "not_a_defect": not_a_defect,
        "true_only_of_reader_checkout": true_only_of_reader_checkout,
        "false_on_sentences_with_no_defect": false_on_sentences_with_no_defect,
        "clean_sentences_flagged": sentences_flagged,
        "precision": len(hits) / judged if judged else 0.0,
    }


def format_median_as_integer_or_one_decimal(value) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def print_per_reviewer(summaries, weights, total_weight):
    scored_rows = sum(1 for w in weights.values() if w > 0)
    print("## Per reviewer\n")
    print(f"Flat recall is rows over {scored_rows}; weighted recall is the weight "
          f"of those rows over {total_weight}. Precision is hits over hits plus "
          f"False; weight-0 rows, Unfixed and True only of reader checkout are neither.\n")
    print("| Reviewer | Findings | Hits | Rows | Flat recall | Weight | "
          "Weighted recall | False | Weight-0 rows | Unfixed | "
          "True only of reader checkout | Precision |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for reviewer, s in sorted(summaries.items(),
                              key=lambda kv: (-kv[1]["weighted_recall"], kv[0])):
        print(f"| {reviewer} | {s['findings']} | {s['hit_findings']} | "
              f"{len(s['rows_hit'])} | {s['flat_recall'] * 100:.0f} % | "
              f"{s['weight_hit']} | {s['weighted_recall'] * 100:.0f} % | "
              f"{s['false']} | {s['not_a_defect']} | {s['unfixed']} | "
              f"{s['true_only_of_reader_checkout']} | {s['precision'] * 100:.0f} % |")
    print()
    for reviewer, s in sorted(summaries.items()):
        print(f"- {reviewer} rows hit: "
              f"{', '.join(str(r) for r in sorted(s['rows_hit']))}")
    print()


def print_clean_sentences(summaries, clean_sentences):
    print("## Flags on the sentences with no defect\n")
    print(f"{len(clean_sentences)} sentences are listed in the defect list. A "
          f"FALSE finding on a sentence with no defect is one whose quote lies inside "
          f"one of them; a true negative is a listed sentence no such finding "
          f"lies inside.\n")
    print("| Reviewer | FALSE on sentences with no defect | Sentences flagged | "
          "True negatives |")
    print("|---|---|---|---|")
    for reviewer, s in sorted(summaries.items()):
        flagged = sorted(s["clean_sentences_flagged"], key=lambda n: int(n[1:]))
        print(f"| {reviewer} | {s['false_on_sentences_with_no_defect']} | "
              f"{', '.join(flagged) or 'none'} | "
              f"{len(clean_sentences) - len(flagged)} |")
    print()


def runs_by_reader(summaries):
    grouped = {}
    for reviewer, summary in summaries.items():
        reader, run = reader_and_run_index_from_reviewer_name(reviewer)
        grouped.setdefault(reader, {})[run] = summary
    return grouped


def has_repeated_runs(summaries) -> bool:
    return any(REVIEWER_RUN_PATTERN.match(reviewer) for reviewer in summaries)


def print_per_reader(summaries):
    print("## Per reader over repeated runs\n")
    print("| Reader | Runs | Weighted recall per run | Median weighted recall | "
          "Precision per run | Median precision | False per run | Median false |")
    print("|---|---|---|---|---|---|---|---|")
    for reader, runs in sorted(runs_by_reader(summaries).items()):
        ordered = [runs[k] for k in sorted(runs)]
        recalls = [s["weighted_recall"] * 100 for s in ordered]
        precisions = [s["precision"] * 100 for s in ordered]
        falses = [s["false"] for s in ordered]
        print(f"| {reader} | {len(ordered)} | "
              f"{', '.join(f'{r:.0f} %' for r in recalls)} | "
              f"{statistics.median(recalls):.0f} % | "
              f"{', '.join(f'{p:.0f} %' for p in precisions)} | "
              f"{statistics.median(precisions):.0f} % | "
              f"{', '.join(str(f) for f in falses)} | "
              f"{format_median_as_integer_or_one_decimal(statistics.median(falses))} |")
    print()


def print_unions(summaries, weights, total_weight, sizes, show_top):
    readers = runs_by_reader(summaries)
    print("## Unions — the number that picks a roster\n")
    if has_repeated_runs(summaries):
        print("Each set is scored once per run index, from that run of each "
              "member, over the run indices every member has; the weight and "
              "rows shown are medians over those runs, and a heavy row is "
              "listed as missed when at least half of those runs miss it.\n")
    for size in sizes:
        if size > len(readers):
            continue
        scored = []
        for combination in itertools.combinations(sorted(readers), size):
            common_runs = set.intersection(
                *(set(readers[reader]) for reader in combination))
            if not common_runs:
                continue
            unions = []
            for run in sorted(common_runs):
                union = set()
                for reader in combination:
                    union |= readers[reader][run]["rows_hit"]
                unions.append(union)
            weight = statistics.median(sum(weights[r] for r in u) for u in unions)
            rows = statistics.median(len(u) for u in unions)
            scored.append((weight, rows, combination, unions))
        if not scored:
            continue
        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        best = scored[0]
        print(f"### Sets of {size} — best {format_median_as_integer_or_one_decimal(best[0])} of {total_weight} "
              f"({best[0] / total_weight * 100:.0f} %)\n")
        print("| Set | Weight | Weighted recall | Rows | Heavy rows missed |")
        print("|---|---|---|---|---|")
        for weight, rows, combination, unions in scored[:show_top]:
            missed = sorted((r for r in weights if weights[r] >= 5
                             and 2 * sum(r not in u for u in unions) >= len(unions)),
                            key=lambda r: -weights[r])
            print(f"| {' + '.join(combination)} | {format_median_as_integer_or_one_decimal(weight)} | "
                  f"{weight / total_weight * 100:.0f} % | {format_median_as_integer_or_one_decimal(rows)} | "
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
    """Print placements ranked by how much changing each would affect the totals."""
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
                        help="directory of placement tables, one per reviewer, "
                             "named <reviewer>--placement.md, or "
                             "<reader>-run-<k>--placement.md for repeated runs")
    parser.add_argument("--defect-list", type=pathlib.Path,
                        default=DEFAULT_DEFECT_LIST,
                        help="the defect list, which carries the severity weights "
                             f"(default {DEFAULT_DEFECT_LIST.name})")
    parser.add_argument("--union-sizes", default="2,3,4",
                        help="set sizes to score, comma-separated (default 2,3,4)")
    parser.add_argument("--top", type=int, default=6,
                        help="how many sets to show per size (default 6)")
    parser.add_argument("--hand-check-depth", type=int, default=10,
                        help="how many placements to rank for hand-checking")
    arguments = parser.parse_args()
    rerun_command = shlex.join(["python3", *sys.argv])

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
    declined = read_defect_list_declined_entries(arguments.defect_list)
    clean_sentences = read_defect_list_sentences_with_no_defect(arguments.defect_list)
    total_weight = sum(weights.values())
    row_total = max(weights)

    placement_files = sorted(arguments.placements.glob("*.md"))
    if not placement_files:
        print(f"{PROGRAM}: no *.md placement tables under {arguments.placements}",
              file=sys.stderr)
        return EXIT_BAD_INVOCATION

    summaries, all_findings, anomalies_by_reviewer, files_by_reviewer = {}, [], {}, {}
    files_by_reader_run = {}
    for path in placement_files:
        # Report malformed input without a traceback that would obscure the actionable error.
        try:
            reviewer, findings, anomalies = parse_one_placement_file(
                path, row_total, declined)
        except PlacementParseError as problem:
            print(f"{PROGRAM}: {problem}\nDefect list: {arguments.defect_list}\n"
                  f"Scorer command: {rerun_command}", file=sys.stderr)
            return EXIT_BAD_INVOCATION
        if reviewer in files_by_reviewer:
            earlier = files_by_reviewer[reviewer]
            identical = earlier.read_bytes() == path.read_bytes()
            print(f"{PROGRAM}: nothing was scored, because the placement files "
                  f"{earlier.name} and {path.name}, in the directory "
                  f"{arguments.placements}, map to the same reviewer name "
                  f"{reviewer!r}, and scoring both would let one file's findings "
                  f"replace the other's. The scorer takes a reviewer's name from "
                  f"the file name, before '{PLACEMENT_FILE_SUFFIX}' or else before "
                  f"'.md'. The two files are "
                  f"{'byte-identical' if identical else 'different'}.\n"
                  f"When they are byte-identical, delete one.\n"
                  f"When they are two runs of one model or reviewer, rename them "
                  f"<name>-run-<k>{PLACEMENT_FILE_SUFFIX}, numbering k on from the "
                  f"highest -run-<k> that name already has in that directory, or "
                  f"from 1.\n"
                  f"When they are two different reviewers, rename the one whose "
                  f"name is not its reviewer's to <its reviewer's name>"
                  f"{PLACEMENT_FILE_SUFFIX}.\n"
                  f"Then run the scorer again: {rerun_command}", file=sys.stderr)
            return EXIT_BAD_INVOCATION
        reader, run = reader_and_run_index_from_reviewer_name(reviewer)
        if (reader, run) in files_by_reader_run:
            earlier = files_by_reader_run[(reader, run)]
            identical = earlier.read_bytes() == path.read_bytes()
            next_run = 1 + max(
                reader_and_run_index_from_reviewer_name(
                    reviewer_name_from_placement_file_name(other))[1]
                for other in placement_files
                if reader_and_run_index_from_reviewer_name(
                    reviewer_name_from_placement_file_name(other))[0] == reader)
            new_path = path.with_name(f"{reader}-run-{next_run}{PLACEMENT_FILE_SUFFIX}")
            remedy = (f"The two files are byte-identical, so they are one run "
                      f"saved twice: delete {path}." if identical else
                      f"The two files are different.\n"
                      f"When both are runs of reader {reader!r}, give either "
                      f"one run {next_run}, the next run number free for that "
                      f"reader in that directory; it does not matter which: "
                      f"rename {path} to {new_path}.\n"
                      f"When one of the two was written by a reader other "
                      f"than {reader!r}, rename that one to "
                      f"<that reader's name>-run-<k>{PLACEMENT_FILE_SUFFIX}, "
                      f"with k the next run number free for that reader in "
                      f"that directory, or 1 when it has none.")
            print(f"{PROGRAM}: nothing was scored, because the placement files "
                  f"{earlier.name} and {path.name}, in the directory "
                  f"{arguments.placements}, are both run {run} of reader "
                  f"{reader!r}. Had it gone on, it would have scored "
                  f"{path.name}'s findings as that run and left "
                  f"{earlier.name}'s findings out of the score; neither file "
                  f"is changed on disk. A file "
                  f"with no -run-<k> in its name is run 1 of its reader, and "
                  f"-run-01 is the same run as -run-1.\n"
                  f"{remedy}\n"
                  f"Then run the scorer again: {rerun_command}", file=sys.stderr)
            return EXIT_BAD_INVOCATION
        files_by_reader_run[(reader, run)] = path
        files_by_reviewer[reviewer] = path
        summaries[reviewer] = summarize(findings, weights, total_weight, row_total,
                                        clean_sentences)
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
    if clean_sentences is not None:
        print_clean_sentences(summaries, clean_sentences)
    if has_repeated_runs(summaries):
        print_per_reader(summaries)
    print_unions(summaries, weights, total_weight, sizes, arguments.top)
    print_unfound(summaries, weights, total_weight)
    print_hand_check(all_findings, summaries, weights, arguments.hand_check_depth)
    return EXIT_SCORED


if __name__ == "__main__":
    sys.exit(main())
