#!/usr/bin/env python3
"""Write section 3.3's diagram of the design-to-main state machine from
TRANSITION_TABLE, or check that the design's diagram is what it would write.

User-ruled 2026-09-16, the eleventh design walk
(design-state-tables-source-of-truth-and-checker), item 4: section 3.3's
Mermaid `stateDiagram-v2` block is generated from TRANSITION_TABLE, a test
fails when the block in the design is not what this script would write, and
an agent that changes a row runs this script before committing.

Usage:
  python3 scripts/design-to-main/design-to-main-state-diagram-generator.py
      rewrites the block between the ```mermaid fence and its closing fence
      under "### 3.3 The diagram", and nothing else in the design.
  python3 scripts/design-to-main/design-to-main-state-diagram-generator.py --check
      writes nothing; exits 1, printing the difference, when the design's
      block is not what it would write, and 0 when it is.
  --design-file PATH   another copy of the design (default: this checkout's).

What it draws, keeping the conventions section 3.3 states:
- a state's name with its hyphens as underscores, since Mermaid identifiers
  cannot carry hyphens (`design-writing` is `design_writing`);
- each reviewing state as a composite block holding its sub-states and the
  edges between them: row 16's advance to the next acceptance-check, in the
  order STATE_TABLE lists the sub-states, and every row whose to-state is a
  sub-state of its own from-state, drawn from the sub-state its "from ..."
  guard names (rows 6, 8, 37);
- every other edge from the state the row is keyed by, the composite state
  for a reviewing state's rows;
- one edge per pair of states, labelled with the verdicts of the rows it
  carries, in table order, joined by " / "; an `input-quick-check-failed`
  carries the input its guard names, in parentheses; a row with no verdict
  (row 65) is labelled with its guard words; no other guard is drawn;
- a row from several states whose verdicts differ by state (row 67) labels
  each state's edge with the verdicts STATE_TABLE lists for that state.

What it does not draw, as section 3.3 says: the retry loops (rows whose
to-state is the same state), the user's `discuss` returns, and the
arbitrator's `advance` from a reviewer's ceiling (row 60), which continues
that work-stream wherever its reviewing state's own advance goes.

The destinations that are not a state are drawn as the states the machine
goes to (DRAWN_STATES_OF_DESTINATION_MARKER below). A destination it does
not know is an error, never a silent omission.
"""

import argparse
import difflib
import importlib.util
import pathlib
import sys

MACHINE_DIRECTORY = pathlib.Path(__file__).resolve().parent
REPOSITORY_ROOT = MACHINE_DIRECTORY.parent.parent
DESIGN_PATH = REPOSITORY_ROOT / "docs" / "design-to-main" / "design-to-main-state-machine-design.md"


def load_state_tables_module():
    spec = importlib.util.spec_from_file_location(
        "design_to_main_state_tables", MACHINE_DIRECTORY / "design-to-main-state-tables.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T = load_state_tables_module()

SECTION_3_3_HEADING_LINE = "### 3.3 The diagram"
MERMAID_OPENING_FENCE_LINE = "```mermaid"
CLOSING_FENCE_LINE = "```"
INDENT = "    "


class StateDiagramCannotBeDrawn(Exception):
    """A row of TRANSITION_TABLE this generator does not know how to draw."""


class DesignDiagramBlockNotFound(Exception):
    """The design has no ```mermaid block under section 3.3's heading."""


# The destinations of section 3.2 that are not a state, drawn as the states
# the machine goes to (design-to-main-state-machine.py, apply_transition_row).
# The retry and row 60's destination are not drawn (see the module docstring).
DRAWN_STATES_OF_DESTINATION_MARKER = {
    # A work-stream's advance that holds at ready-for-test-suite waits for
    # the other work-stream at the join, test-suite-executing (section 3.1,
    # Work-streams): drawn as the edge to the join, with the rows that reach it.
    T.TO_HOLD_READY_FOR_TEST_SUITE: (T.TEST_SUITE_EXECUTING,),
    # Row 9: the implementation-work-stream re-enters implementation-writing
    # and, when tests have begun, the test-work-stream test-design-writing.
    T.TO_BOTH_WORK_STREAMS_RE_ENTER: (T.IMPLEMENTATION_WRITING, T.TEST_DESIGN_WRITING),
    # Row 64: both writers.
    T.TO_BOTH_WRITERS_FRESH: (T.IMPLEMENTATION_WRITING, T.TEST_WRITING),
}
DESTINATION_MARKERS_NOT_DRAWN = (
    T.TO_RETRY_SAME_STATE,
    T.TO_WHEREVER_THAT_REVIEWING_STATES_ADVANCE_GOES,
)
# Drawn by rules of their own below: row 16 inside each composite, row 63 by
# WRITER_STATE_FOR_VERDICT, row 72 by RESUME_DESTINATION_BY_EDITED_DOCUMENT.
DESTINATION_MARKERS_DRAWN_BY_RULE = (
    T.TO_THE_NEXT_ACCEPTANCE_CHECK,
    T.TO_THE_WRITER_THE_VERDICT_NAMES,
    T.TO_RESUME_DESTINATION,
)

# The input an input-quick-check-failed names, read from its guard.
INPUT_LABEL_OF_GUARD = {
    T.G_AGAINST_THE_DESIGN: "design",
    T.G_AGAINST_THE_COMPONENT_CONTRACT: "contract",
    T.G_A_REJECT_OF_OR_A_FAILED_CHECK_AGAINST_THE_COMPONENT_CONTRACT: "contract",
    T.G_AGAINST_THE_TEST_DESIGN: "test-design",
}

SUB_STATE_NAMES = tuple(T.COMPOSITE_STATE_OF_SUB_STATE)
# The sub-state a "from ..." guard names: the guard's words are "from "
# and the sub-state's name, except the program check's.
SUB_STATE_OF_FROM_GUARD = dict(
    [("from " + sub_state, sub_state) for sub_state in SUB_STATE_NAMES]
    + [(T.G_FROM_PROGRAM_CHECK, T.CONTRACT_ACCEPTANCE_BY_PROGRAM)])


def mermaid_identifier(name):
    return name.replace("-", "_")


def verdict_label(verdict, row):
    if verdict != T.V_INPUT_QUICK_CHECK_FAILED:
        return verdict
    inputs = [INPUT_LABEL_OF_GUARD[guard] for guard in row.guards if guard in INPUT_LABEL_OF_GUARD]
    return "%s (%s)" % (verdict, inputs[0]) if inputs else verdict


def drawn_verdicts(row, from_state):
    """The row's verdicts drawn on from_state's edge: the user's discuss is
    not drawn; a row from several states keeps, for each, the verdicts
    STATE_TABLE lists for it, where it lists any of them."""
    verdicts = [verdict for verdict in row.verdicts if verdict != T.V_DISCUSS]
    if len(row.from_states) > 1:
        listed = T.STATE_TABLE_BY_NAME[from_state].verdicts
        verdicts = [verdict for verdict in verdicts if verdict in listed] or verdicts
    return verdicts


class StateDiagramEdges:
    """Edges in the order first drawn, one per (inside, from, to), each
    with its labels in the order first drawn."""

    def __init__(self):
        self.labels_by_edge = {}

    def add(self, inside, from_name, to_name, label):
        labels = self.labels_by_edge.setdefault((inside, from_name, to_name), [])
        if label not in labels:
            labels.append(label)

    def edges(self, inside, from_name=None):
        return [(edge_from, edge_to, labels)
                for (edge_inside, edge_from, edge_to), labels in self.labels_by_edge.items()
                if edge_inside == inside and (from_name is None or edge_from == from_name)]


def state_diagram_edges(transition_table):
    state_names = {row.name for row in T.STATE_TABLE}
    edges = StateDiagramEdges()
    for row in transition_table:
        if row.to_state in DESTINATION_MARKERS_NOT_DRAWN:
            continue
        for from_state in row.from_states:
            verdicts = drawn_verdicts(row, from_state)
            if row.verdicts and not verdicts:
                continue
            labels = ([verdict_label(verdict, row) for verdict in verdicts]
                      or [", ".join(row.guards)])

            if row.to_state == T.TO_THE_NEXT_ACCEPTANCE_CHECK:
                sub_states = T.STATE_TABLE_BY_NAME[from_state].sub_states
                for earlier, later in zip(sub_states, sub_states[1:]):
                    for label in labels:
                        edges.add(from_state, earlier, later, label)
                continue
            if row.to_state == T.TO_THE_WRITER_THE_VERDICT_NAMES:
                for verdict in verdicts:
                    edges.add(None, from_state, T.WRITER_STATE_FOR_VERDICT[verdict],
                              verdict_label(verdict, row))
                continue
            if row.to_state == T.TO_RESUME_DESTINATION:
                for document, state in T.RESUME_DESTINATION_BY_EDITED_DOCUMENT:
                    for label in labels:
                        edges.add(None, from_state, state, "%s, %s edited" % (label, document))
                continue

            if row.to_state in DRAWN_STATES_OF_DESTINATION_MARKER:
                to_states = DRAWN_STATES_OF_DESTINATION_MARKER[row.to_state]
            elif row.to_state in state_names or row.to_state in SUB_STATE_NAMES:
                to_states = (row.to_state,)
            else:
                raise StateDiagramCannotBeDrawn(
                    "row %s: destination %r is neither a state nor a destination this "
                    "generator draws" % (row.row, row.to_state))

            for to_state in to_states:
                if T.COMPOSITE_STATE_OF_SUB_STATE.get(to_state) == from_state:
                    sources = [SUB_STATE_OF_FROM_GUARD[guard] for guard in row.guards
                               if guard in SUB_STATE_OF_FROM_GUARD]
                    if len(sources) != 1:
                        raise StateDiagramCannotBeDrawn(
                            "row %s: goes to %s inside %s, from no one sub-state a guard names"
                            % (row.row, to_state, from_state))
                    for label in labels:
                        edges.add(from_state, sources[0], to_state, label)
                else:
                    for label in labels:
                        edges.add(None, from_state, to_state, label)
    return edges


def edge_line(from_name, to_name, labels, indent):
    label = " / ".join(label for label in labels if label)
    return "%s%s --> %s%s" % (indent, mermaid_identifier(from_name), mermaid_identifier(to_name),
                              ": " + label if label else "")


def state_diagram_mermaid_lines(transition_table=None):
    """The lines between the fences, without their line ends."""
    edges = state_diagram_edges(T.TRANSITION_TABLE if transition_table is None
                                else transition_table)
    lines = ["stateDiagram-v2",
             "%s[*] --> %s" % (INDENT, mermaid_identifier(T.STATE_TABLE[0].name))]
    for state in T.STATE_TABLE:
        if state.sub_states:
            lines.append("%sstate %s {" % (INDENT, mermaid_identifier(state.name)))
            inner = edges.edges(state.name)
            for from_name, to_name, labels in inner:
                lines.append(edge_line(from_name, to_name, labels, INDENT * 2))
            drawn = {name for from_name, to_name, _ in inner for name in (from_name, to_name)}
            for sub_state in state.sub_states:
                if sub_state not in drawn:
                    lines.append("%s%s" % (INDENT * 2, mermaid_identifier(sub_state)))
            lines.append("%s}" % INDENT)
        for from_name, to_name, labels in edges.edges(None, state.name):
            lines.append(edge_line(from_name, to_name, labels, INDENT))
    lines.append("%s%s --> [*]" % (INDENT, mermaid_identifier(T.ENDED)))
    return lines


def section_3_3_block_span(design_text):
    """(start, end) of the block's text: from the line after the opening
    fence to the start of the closing fence's line."""
    lines = design_text.splitlines(keepends=True)
    offsets, offset = [], 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    stripped = [line.rstrip("\n") for line in lines]
    if stripped.count(SECTION_3_3_HEADING_LINE) != 1:
        raise DesignDiagramBlockNotFound("no single %r heading" % SECTION_3_3_HEADING_LINE)
    heading = stripped.index(SECTION_3_3_HEADING_LINE)
    for index in range(heading + 1, len(stripped)):
        if stripped[index].startswith("#"):
            break
        if stripped[index] == MERMAID_OPENING_FENCE_LINE:
            for closing in range(index + 1, len(stripped)):
                if stripped[closing] == CLOSING_FENCE_LINE:
                    return offsets[index + 1], offsets[closing]
            break
    raise DesignDiagramBlockNotFound("no %s block closed by %s under %r" % (
        MERMAID_OPENING_FENCE_LINE, CLOSING_FENCE_LINE, SECTION_3_3_HEADING_LINE))


def design_text_with_generated_diagram(design_text, transition_table=None):
    start, end = section_3_3_block_span(design_text)
    block = "".join(line + "\n" for line in state_diagram_mermaid_lines(transition_table))
    return design_text[:start] + block + design_text[end:]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 when the design's block differs")
    parser.add_argument("--design-file", type=pathlib.Path, default=DESIGN_PATH)
    arguments = parser.parse_args(argv)

    current = arguments.design_file.read_text()
    generated = design_text_with_generated_diagram(current)
    if arguments.check:
        if generated == current:
            return 0
        sys.stdout.writelines(difflib.unified_diff(
            current.splitlines(keepends=True), generated.splitlines(keepends=True),
            "%s (as it is)" % arguments.design_file, "%s (as generated)" % arguments.design_file))
        print("section 3.3's diagram is not what %s writes; run it without --check"
              % pathlib.Path(__file__).name, file=sys.stderr)
        return 1
    if generated != current:
        arguments.design_file.write_text(generated)
        print("rewrote section 3.3's diagram in %s" % arguments.design_file)
    else:
        print("section 3.3's diagram in %s is already what this script writes"
              % arguments.design_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
