#!/usr/bin/env python3
"""Write section 3.3's four diagram views of the design-to-main state machine
from TRANSITION_TABLE, or check that the design's views are what it would write.

User-ruled 2026-09-16, the eleventh design walk
(design-state-tables-source-of-truth-and-checker), item 4: section 3.3's
Mermaid `stateDiagram-v2` diagram is generated from TRANSITION_TABLE, a test
fails when the design is not what this script would write, and an agent
that changes a row runs this script before committing. User-ruled
2026-09-16, the walk design-tables-checker-findings-from-pr-409, items 3
to 5: an edge is labelled `verdict [guard]`, UML's transition notation, and
section 3.3 is four views of the one table, each row the diagram draws in
exactly one, a row entered from many states drawn once, from a box around
them.

Usage:
  python3 scripts/design-to-main/design-to-main-state-diagram-generator.py
      rewrites, under each view's subheading in "### 3.3 The diagram", the
      block between the ```mermaid fence and its closing fence, and nothing
      else in the design.
  python3 scripts/design-to-main/design-to-main-state-diagram-generator.py --check
      writes nothing; exits 1, printing the difference, when any view's
      block is not what it would write, and 0 when none differs.
  --design-file PATH   another copy of the design (default: this checkout's).

The views. Each row of TRANSITION_TABLE names the view that draws it in its
`view` field (DIAGRAM_VIEWS_DRAWN in design-to-main-state-tables.py), or
DIAGRAM_VIEW_NOT_DRAWN; a row with no view or an unknown one is an error.
Section 3.3 shows the views in DIAGRAM_VIEWS_DRAWN's order, each under its
subheading (SECTION_3_3_VIEW_SUBHEADING_LINES below).

What a view draws, keeping the conventions section 3.3 states:
- a state's name with its hyphens as underscores, since Mermaid identifiers
  cannot carry hyphens (`design-writing` is `design_writing`);
- a reviewing state as a plain state, unless the view draws an edge that
  starts or ends at one of its sub-states: then as a composite block
  holding every sub-state and the edges between them — row 16's advance to
  the next acceptance-check, in the order STATE_TABLE lists the sub-states,
  and every row whose to-state is a sub-state of its own from-state, drawn
  from the sub-state its "from ..." guard names (rows 6, 8, 37);
- every other edge from the state the row is keyed by, the composite state
  for a reviewing state's rows;
- a row keyed by several states with one destination (rows 67 and 69) once,
  from a box around those states, UML's group transition: a composite
  state `row_<n>_from_states` holding them. A state is in one box at most
  in a view, since Mermaid holds a state in one composite only;
- one edge per pair of states, labelled with each row it carries, in table
  order, joined by " / ": the row's verdicts, comma-separated, and in
  brackets its guards, comma-separated (UML: `trigger, trigger [guard,
  guard]`); a row with no guard drawn has no brackets, and a row with no
  verdict (row 65) is its bracket alone. The counter guards and the
  "from ..." guards are left off (guard_is_left_off_the_label);
- a semicolon in a label as `#59;`, since Mermaid ends a statement at one.

What it does not draw, as section 3.3 says: the retry loops (rows whose
to-state is the same state), the user's `discuss` returns, and the
arbitrator's `advance` from a reviewer's ceiling (row 60), which continues
that work-stream wherever its reviewing state's own advance goes. These are
the rows marked DIAGRAM_VIEW_NOT_DRAWN, and no others: a row of these kinds
in a drawn view, or a drawable row marked not drawn, is an error.

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
SECTION_3_3_VIEW_SUBHEADING_LINES = {
    T.DIAGRAM_VIEW_MAIN_PATH: "#### 3.3.1 The main path",
    T.DIAGRAM_VIEW_REWORK_AND_ARBITRATION: "#### 3.3.2 Rework and arbitration",
    T.DIAGRAM_VIEW_INVESTIGATION: "#### 3.3.3 The investigation",
    T.DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES: "#### 3.3.4 Inside the reviewing states",
}
assert tuple(SECTION_3_3_VIEW_SUBHEADING_LINES) == T.DIAGRAM_VIEWS_DRAWN
MERMAID_OPENING_FENCE_LINE = "```mermaid"
CLOSING_FENCE_LINE = "```"
INDENT = "    "


class StateDiagramCannotBeDrawn(Exception):
    """A row of TRANSITION_TABLE this generator does not know how to draw."""


class DesignDiagramBlockNotFound(Exception):
    """Section 3.3 lacks a view's subheading or its ```mermaid block, or holds
    a block that is no view's."""


# The destinations of section 3.2 that are not a state, drawn as the states
# the machine goes to (design-to-main-state-machine.py, apply_transition_row).
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
# The retry and row 60's destination: section 3.3 does not draw them.
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

SUB_STATE_NAMES = tuple(T.COMPOSITE_STATE_OF_SUB_STATE)
# The sub-state a "from ..." guard names: the guard's words are "from "
# and the sub-state's name, except the program check's.
SUB_STATE_OF_FROM_GUARD = dict(
    [("from " + sub_state, sub_state) for sub_state in SUB_STATE_NAMES]
    + [(T.G_FROM_PROGRAM_CHECK, T.CONTRACT_ACCEPTANCE_BY_PROGRAM)])


def mermaid_identifier(name):
    return name.replace("-", "_")


def group_transition_box_identifier(row):
    return "row_%s_from_states" % row.row


def mermaid_label_text(text):
    return text.replace(";", "#59;")


def guard_is_left_off_the_label(guard):
    """Section 3.3's counter guards, which read a counter of section 7
    against its ceiling ("the contract-revisions counter below its ceiling",
    "resume to design-writing, the redesigns counter at its ceiling"), and
    the "from ..." guards, which name the sub-state a row starts at and
    no more (user-ruled 2026-09-16, the walk
    design-tables-checker-findings-from-pr-409, item 3)."""
    reads_a_counter_against_its_ceiling = "counter" in guard and "ceiling" in guard
    return reads_a_counter_against_its_ceiling or guard.startswith("from ")


def transition_label(verdicts, guards):
    """`verdict, verdict [guard, guard]`, the guards left off the label
    removed; a row with no verdict is its bracket alone."""
    drawn_guards = [guard for guard in guards if not guard_is_left_off_the_label(guard)]
    parts = []
    if verdicts:
        parts.append(", ".join(verdicts))
    if drawn_guards:
        parts.append("[%s]" % ", ".join(drawn_guards))
    return " ".join(parts)


def row_is_a_kind_section_3_3_does_not_draw(row):
    return row.to_state in DESTINATION_MARKERS_NOT_DRAWN or row.verdicts == (T.V_DISCUSS,)


def check_every_row_has_a_known_view(transition_table):
    known = T.DIAGRAM_VIEWS_DRAWN + (T.DIAGRAM_VIEW_NOT_DRAWN,)
    for row in transition_table:
        if row.view not in known:
            raise StateDiagramCannotBeDrawn(
                "row %s: view %r is none of %s" % (row.row, row.view, ", ".join(known)))
        not_drawn_kind = row_is_a_kind_section_3_3_does_not_draw(row)
        if row.view == T.DIAGRAM_VIEW_NOT_DRAWN and not not_drawn_kind:
            raise StateDiagramCannotBeDrawn(
                "row %s: marked %s, but it is not a retry loop, a discuss return or "
                "row 60's advance, which are all section 3.3 leaves undrawn"
                % (row.row, T.DIAGRAM_VIEW_NOT_DRAWN))
        if row.view != T.DIAGRAM_VIEW_NOT_DRAWN and not_drawn_kind:
            raise StateDiagramCannotBeDrawn(
                "row %s: in view %s, but section 3.3 does not draw it; mark it %s"
                % (row.row, row.view, T.DIAGRAM_VIEW_NOT_DRAWN))


class StateDiagramViewDrawing:
    """One view's edges, in the order first drawn, one per (from, to), each
    with its labels in the order first drawn and the rows it carries; and
    its group-transition boxes, each with the states it holds."""

    def __init__(self, view):
        self.view = view
        self.labels_by_edge = {}
        self.rows_by_edge = {}
        self.box_states_by_box = {}
        self.box_of_state = {}
        self.row_number_of_box = {}

    def add_edge(self, from_name, to_name, label, row):
        labels = self.labels_by_edge.setdefault((from_name, to_name), [])
        if label not in labels:
            labels.append(label)
        rows = self.rows_by_edge.setdefault((from_name, to_name), [])
        if row.row not in rows:
            rows.append(row.row)

    def add_group_transition_box(self, row):
        box = group_transition_box_identifier(row)
        for state in row.from_states:
            if self.box_of_state.get(state, box) != box:
                raise StateDiagramCannotBeDrawn(
                    "row %s: %s is already in the box of %s in view %s; Mermaid holds a "
                    "state in one composite only" % (row.row, state, self.box_of_state[state],
                                                      self.view))
            self.box_of_state[state] = box
        self.box_states_by_box[box] = tuple(
            state.name for state in T.STATE_TABLE if state.name in row.from_states)
        self.row_number_of_box[box] = row.row
        return box

    def rows_drawn(self):
        return {number for rows in self.rows_by_edge.values() for number in rows}

    def names_drawn(self):
        return ({name for edge in self.labels_by_edge for name in edge}
                | {name for states in self.box_states_by_box.values() for name in states})


def state_diagram_view_drawing(view, transition_table=None):
    transition_table = T.TRANSITION_TABLE if transition_table is None else transition_table
    check_every_row_has_a_known_view(transition_table)
    state_names = {row.name for row in T.STATE_TABLE}
    drawing = StateDiagramViewDrawing(view)
    for row in transition_table:
        if row.view != view:
            continue
        draw_transition_row(drawing, row, state_names)
        if row.row not in drawing.rows_drawn():
            raise StateDiagramCannotBeDrawn("row %s: in view %s, and drew nothing" % (row.row, view))
    return drawing


def draw_transition_row(drawing, row, state_names):
    if row.to_state == T.TO_THE_NEXT_ACCEPTANCE_CHECK:
        label = transition_label(row.verdicts, row.guards)
        for from_state in row.from_states:
            sub_states = T.STATE_TABLE_BY_NAME[from_state].sub_states
            for earlier, later in zip(sub_states, sub_states[1:]):
                drawing.add_edge(earlier, later, label, row)
        return

    if len(row.from_states) > 1:
        from_name = drawing.add_group_transition_box(row)
    else:
        from_name = row.from_states[0]

    if row.to_state == T.TO_THE_WRITER_THE_VERDICT_NAMES:
        for writer in dict.fromkeys(T.WRITER_STATE_FOR_VERDICT[verdict] for verdict in row.verdicts):
            verdicts = [verdict for verdict in row.verdicts
                        if T.WRITER_STATE_FOR_VERDICT[verdict] == writer]
            drawing.add_edge(from_name, writer, transition_label(verdicts, row.guards), row)
        return
    if row.to_state == T.TO_RESUME_DESTINATION:
        # The earliest state downstream of what the user edited (section
        # 6.6), the edited document read as the edge's guard.
        for document, state in T.RESUME_DESTINATION_BY_EDITED_DOCUMENT:
            drawing.add_edge(from_name, state, transition_label(
                row.verdicts, row.guards + ("%s edited" % document,)), row)
        return

    if row.to_state in DRAWN_STATES_OF_DESTINATION_MARKER:
        to_states = DRAWN_STATES_OF_DESTINATION_MARKER[row.to_state]
    elif row.to_state in state_names or row.to_state in SUB_STATE_NAMES:
        to_states = (row.to_state,)
    else:
        raise StateDiagramCannotBeDrawn(
            "row %s: destination %r is neither a state nor a destination this "
            "generator draws" % (row.row, row.to_state))

    label = transition_label(row.verdicts, row.guards)
    for to_state in to_states:
        if T.COMPOSITE_STATE_OF_SUB_STATE.get(to_state) == from_name:
            sources = [SUB_STATE_OF_FROM_GUARD[guard] for guard in row.guards
                       if guard in SUB_STATE_OF_FROM_GUARD]
            if len(sources) != 1:
                raise StateDiagramCannotBeDrawn(
                    "row %s: goes to %s inside %s, from no one sub-state a guard names"
                    % (row.row, to_state, from_name))
            drawing.add_edge(sources[0], to_state, label, row)
        else:
            drawing.add_edge(from_name, to_state, label, row)


def edge_line(from_name, to_name, labels, indent):
    label = " / ".join(label for label in labels if label)
    return "%s%s --> %s%s" % (indent, mermaid_identifier(from_name), mermaid_identifier(to_name),
                              ": " + mermaid_label_text(label) if label else "")


def state_diagram_view_mermaid_lines(view, transition_table=None):
    """One view's lines between the fences, without their line ends."""
    drawing = state_diagram_view_drawing(view, transition_table)
    names_drawn = drawing.names_drawn()
    opened_composites = {state.name: state for state in T.STATE_TABLE if state.sub_states
                         and any(sub_state in names_drawn for sub_state in state.sub_states)}
    inner_edges = {}
    root_edges = []
    for (from_name, to_name), labels in drawing.labels_by_edge.items():
        composite = T.COMPOSITE_STATE_OF_SUB_STATE.get(from_name)
        if composite is not None and composite == T.COMPOSITE_STATE_OF_SUB_STATE.get(to_name):
            inner_edges.setdefault(composite, []).append((from_name, to_name, labels))
        else:
            root_edges.append((from_name, to_name, labels))

    def composite_block(state, indent):
        block = ["%sstate %s {" % (indent, mermaid_identifier(state.name))]
        edges = inner_edges.get(state.name, [])
        for from_name, to_name, labels in edges:
            block.append(edge_line(from_name, to_name, labels, indent + INDENT))
        drawn = {name for from_name, to_name, _ in edges for name in (from_name, to_name)}
        for sub_state in state.sub_states:
            if sub_state not in drawn:
                block.append("%s%s" % (indent + INDENT, mermaid_identifier(sub_state)))
        block.append("%s}" % indent)
        return block

    def state_block(name, indent):
        if name in opened_composites:
            return composite_block(opened_composites[name], indent)
        return ["%s%s" % (indent, mermaid_identifier(name))]

    lines = ["stateDiagram-v2"]
    if T.INITIATE_DESIGN_TO_MAIN in names_drawn:
        lines.append("%s[*] --> %s" % (INDENT, mermaid_identifier(T.INITIATE_DESIGN_TO_MAIN)))
    # Declared before any edge names their states, so that Mermaid places
    # each state in its box or composite: boxes where their first state
    # stands in STATE_TABLE, then the composites in no box.
    boxes_placed = set()
    for state in T.STATE_TABLE:
        box = drawing.box_of_state.get(state.name)
        if box is not None and box not in boxes_placed:
            boxes_placed.add(box)
            lines.append('%sstate "row %s\'s from-states" as %s {'
                         % (INDENT, drawing.row_number_of_box[box], box))
            for member in drawing.box_states_by_box[box]:
                lines.extend(state_block(member, INDENT * 2))
            lines.append("%s}" % INDENT)
        elif box is None and state.name in opened_composites:
            lines.extend(composite_block(state, INDENT))
    for from_name, to_name, labels in root_edges:
        lines.append(edge_line(from_name, to_name, labels, INDENT))
    if T.ENDED in names_drawn:
        lines.append("%s%s --> [*]" % (INDENT, mermaid_identifier(T.ENDED)))
    return lines


def section_3_3_view_block_spans(design_text):
    """{view: (start, end)} of each view's block text, in DIAGRAM_VIEWS_DRAWN's
    order: from the line after the opening fence under the view's subheading
    to the start of the closing fence's line."""
    lines = design_text.splitlines(keepends=True)
    offsets, offset = [], 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    stripped = [line.rstrip("\n") for line in lines]
    if stripped.count(SECTION_3_3_HEADING_LINE) != 1:
        raise DesignDiagramBlockNotFound("no single %r heading" % SECTION_3_3_HEADING_LINE)
    heading = stripped.index(SECTION_3_3_HEADING_LINE)
    section_end = next((index for index in range(heading + 1, len(stripped))
                        if stripped[index].startswith(("# ", "## ", "### "))), len(stripped))
    section = range(heading + 1, section_end)
    fences = [index for index in section if stripped[index] == MERMAID_OPENING_FENCE_LINE]
    if len(fences) != len(T.DIAGRAM_VIEWS_DRAWN):
        raise DesignDiagramBlockNotFound("%d %s blocks under %r, not one for each of the %d views" % (
            len(fences), MERMAID_OPENING_FENCE_LINE, SECTION_3_3_HEADING_LINE,
            len(T.DIAGRAM_VIEWS_DRAWN)))
    spans = {}
    for view in T.DIAGRAM_VIEWS_DRAWN:
        subheading_line = SECTION_3_3_VIEW_SUBHEADING_LINES[view]
        subheadings = [index for index in section if stripped[index] == subheading_line]
        if len(subheadings) != 1:
            raise DesignDiagramBlockNotFound("no single %r under %r" % (
                subheading_line, SECTION_3_3_HEADING_LINE))
        for index in range(subheadings[0] + 1, section_end):
            if stripped[index].startswith("#"):
                break
            if stripped[index] == MERMAID_OPENING_FENCE_LINE:
                closing = next((later for later in range(index + 1, section_end)
                                if stripped[later] == CLOSING_FENCE_LINE), None)
                if closing is None:
                    break
                spans[view] = (offsets[index + 1], offsets[closing])
                break
        if view not in spans:
            raise DesignDiagramBlockNotFound("no %s block closed by %s under %r" % (
                MERMAID_OPENING_FENCE_LINE, CLOSING_FENCE_LINE, subheading_line))
    return spans


def design_text_with_generated_diagrams(design_text, transition_table=None):
    spans = section_3_3_view_block_spans(design_text)
    for view in sorted(spans, key=lambda view: spans[view][0], reverse=True):
        start, end = spans[view]
        block = "".join(line + "\n"
                        for line in state_diagram_view_mermaid_lines(view, transition_table))
        design_text = design_text[:start] + block + design_text[end:]
    return design_text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 when any view's block differs")
    parser.add_argument("--design-file", type=pathlib.Path, default=DESIGN_PATH)
    arguments = parser.parse_args(argv)

    current = arguments.design_file.read_text()
    generated = design_text_with_generated_diagrams(current)
    if arguments.check:
        if generated == current:
            return 0
        sys.stdout.writelines(difflib.unified_diff(
            current.splitlines(keepends=True), generated.splitlines(keepends=True),
            "%s (as it is)" % arguments.design_file, "%s (as generated)" % arguments.design_file))
        print("section 3.3's views are not what %s writes; run it without --check"
              % pathlib.Path(__file__).name, file=sys.stderr)
        return 1
    if generated != current:
        arguments.design_file.write_text(generated)
        print("rewrote section 3.3's views in %s" % arguments.design_file)
    else:
        print("section 3.3's views in %s are already what this script writes"
              % arguments.design_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
