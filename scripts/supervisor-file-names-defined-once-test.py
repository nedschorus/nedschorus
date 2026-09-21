#!/usr/bin/env python3
"""The supervisor's state, lock and handoff file names have one definition
each, and this test keeps it that way.

Five programs need the path of a seat's supervisor state file: the supervisor
itself, the recovery tool, resupervise-seat.py, the login restart and the
handoff writer. Until 2026-09-19 each built the name from its own f-string --
eleven sites across the five, plus a second copy of the suffix constant in
scripts/restart-live-seats-at-login.py -- so a rename had eleven places to
find and nothing that failed when it missed one. The suffixes now live in
nc-systems/handoff/handoff-supervisor.py alone, and the path is composed only by its
supervisor_state_path(), supervisor_lock_path() and supervisor_state_paths()
(user-ruled 2026-09-19, walk
file-naming-and-location-standards-cold-read-findings, item 4: reduce each
repeated name to one definition).

The handoff file's own name joined them on 2026-09-20 (user-ruled that day,
walk md-skills-seat-open-decisions-2026-09-20, item 2). Four programs need it
-- the supervisor waits on it, the handoff writer writes it, the recovery tool
and resupervise-seat.py read it -- and eight sites across the four built it by
hand, one of them a local `suffix` variable in the writer holding the suffix
and globbing with it. Missing one site on a rename is silent and reads as the
opposite of what happened: the supervisor writes <seat>-handoff.md, the
recovery tool looks for the old name, finds nothing, and reports a seat that
handed off cleanly as one that died leaving no handoff. HANDOFF_FILE_SUFFIX
now lives in nc-systems/handoff/handoff-supervisor.py with the other two, and
the path is composed only by its handoff_file_path() and
handoff_file_paths(). Item 4 above did not cover this name: the ruling it
carried out named the state file, the cold-read-record names and the
walk-file endings, and the handoff name was recorded on the file-naming wiki
page as its own unruled topic until item 2 ruled it.

The supervisor and the writer both left scripts/ for nc-systems/handoff/ on
2026-09-20. The first version of that change named the supervisor explicitly
beside the scripts/ glob and left the writer out, which is the silent pass
production_scripts() warns about below: the writer stopped being parsed, and
its three cases went on passing by finding nothing in a file they no longer
read (finding 2 of the review of pull request [The handoff system moves into
nc-systems/handoff/, except what a live seat holds]
(https://github.com/nedschorus/nedschorus/pull/578), 2026-09-21; measured
that day -- a hand-built name added to the writer failed nothing). The set
of scripts read is derived from the layout now, and
PROGRAMS_THAT_NEED_THESE_FILE_NAMES fails loudly when a program this suite
exists to watch is not among them -- a hand-added entry per move is the same
defect waiting for the third move.

This reads each script's syntax tree rather than its lines, after two rounds
of the earlier line-matching version being wrong in both directions. Matching
text could not tell a comment from code: a comment containing an apostrophe
and the file name failed the suite, while the same comment without the
apostrophe passed. It also could not see a composition spread over two lines,
or one written with str.format instead of an f-string. The tree has no
comments in it at all, does not care where a line ends, and says what each
expression is, so all three go away together rather than one regex at a time.

Every case reads the tree, including the one that counts where the suffix
constants are defined. That one kept its line regex for a round while the
rest moved, which is how a duplicate definition written
SUPERVISOR_STATE_FILE_SUFFIX = ("-supervisor-state.json") came to pass a
suite that the plain form still failed -- the regex wanted a quote straight
after the `=` and saw a parenthesis. Half a guard reading the tree and half
reading lines is worse than either, because the two halves exempt and count
different things; suffix_definition_assignments() below is now the one
answer both halves use.

What counts as composing a name, and so fails -- the same four shapes for
each of the three names:

- a string that contains the file name, wherever it appears
- an f-string with any suffix constant in a replacement field
- any suffix constant on one side of a `+`, or appended with `+=`
- any suffix constant passed to .format(), positionally or by keyword

What does not: taking a name apart, as agent_name_from_supervisor_file() does
with endswith() and len(); a docstring that writes the pattern out for a
reader; and the bodies of the composing helpers, whose whole job this is.
Their line ranges come from the tree, so a helper renamed without being
renamed in COMPOSING_HELPERS below fails a case rather than silently
exempting whatever takes its place.

Three more ways to build the name are out of scope on purpose, because no
agent in this project has written any of them: "".join(...), `%` formatting,
and assigning the constant to a local variable and composing from that. The
last has no cheap answer at all -- following a value through a function needs
more than one node in hand. The list grows when one of them is written, not
before; what it must never do is claim coverage the code does not have, which
is how the keyword form of .format() went uncaught for a round.

Test files keep their literals on purpose: that literal is the assertion, and
it is what fails loudly if the name is ever changed.

Run: python3 scripts/supervisor-file-names-defined-once-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIRECTORY = REPO_ROOT / "scripts"
# Production code lives in two places since nc-systems/ was made: scripts/,
# and one directory per system. Tests sit a level deeper, in
# nc-systems/<system>/tests/, so the system glob reaches production code only.
NC_SYSTEMS_DIRECTORY = REPO_ROOT / "nc-systems"
# The supervisor and the writer moved into nc-systems/handoff/ on 2026-09-20.
# The supervisor is still named here because it is the one file allowed to
# define the suffixes and to compose the paths, which two cases below ask
# about by name; which files are READ is derived, not named.
SUPERVISOR_SCRIPT = NC_SYSTEMS_DIRECTORY / "handoff" / "handoff-supervisor.py"
# The programs that need these names, by file name, wherever they live. The
# docstring above names them: the supervisor, the recovery tool,
# resupervise-seat.py, the login restart and the handoff writer. A program
# that is moved somewhere this suite does not read fails the membership case
# rather than quietly dropping out of every other one.
PROGRAMS_THAT_NEED_THESE_FILE_NAMES = ("handoff-supervisor.py",
                                       "handoff-write-and-check-supervisor.py",
                                       "recover-crashed-seats.py",
                                       "resupervise-seat.py",
                                       "restart-live-seats-at-login.py")
# The functions that compose the names, and so the only code allowed to.
# handoff_file_path is deliberately not named handoff_path: that name is
# already the SupervisorSettings property, so the helper case below would
# collect two FunctionDefs under it and the property's body -- one of the eight
# sites this guard was extended for -- would be exempted as a helper.
COMPOSING_HELPERS = ("supervisor_state_path", "supervisor_lock_path",
                     "supervisor_state_paths", "handoff_file_path",
                     "handoff_file_paths")
# The three file names, as they read on disk. This is a copy, so the last
# check below reads the same three out of handoff-supervisor.py and compares.
# Until 2026-09-21 nothing did, and a copy nothing anchors goes stale at
# exactly the moment it matters: rename a constant's value and this tuple
# still hunts the OLD spelling, finds nothing, and a fresh hand-built copy of
# the NEW one passes every case. The eleven-sites defect this guard exists to
# prevent would come back invisible, and the guard would go on printing PASS
# until the rename after that.
SPELLED_OUT_NAMES = ("-supervisor-state.json", "-supervisor.lock",
                     "-handoff.md")
# The constants that hold them.
SUFFIX_CONSTANTS = frozenset({"SUPERVISOR_STATE_FILE_SUFFIX",
                              "SUPERVISOR_LOCK_FILE_SUFFIX",
                              "HANDOFF_FILE_SUFFIX"})

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def production_scripts():
    """Every script a seat runs -- test files excluded.

    Derived from the layout, both places production code lives, rather than
    globbing scripts/ and naming each moved file after it. A named file is
    only ever as current as the last move someone remembered it in, and
    forgetting one is silent here in the worst way: the cases below all take
    the form "nothing in these files composes a name", so a file that stops
    being read stops being able to fail them. That is what happened to the
    writer for the length of one review round.
    """
    found = (list(SCRIPTS_DIRECTORY.glob("*.py"))
             + list(NC_SYSTEMS_DIRECTORY.glob("*/*.py")))
    return sorted(path for path in found
                  if not path.name.endswith("-test.py"))


def names_a_suffix_constant(node):
    """True when this expression is one of the suffix constants.

    Both `SUPERVISOR_STATE_FILE_SUFFIX` and the qualified
    `supervisor.SUPERVISOR_STATE_FILE_SUFFIX` count: a program that reaches
    for the constant through the imported module is composing the name just
    as surely as one that holds its own copy.
    """
    if isinstance(node, ast.Name):
        return node.id in SUFFIX_CONSTANTS
    if isinstance(node, ast.Attribute):
        return node.attr in SUFFIX_CONSTANTS
    return False


def docstring_nodes(tree):
    """Every docstring in the module, by identity.

    A docstring writes the file name out for a reader -- the supervisor's own
    explains that a state file and a lock file are named after the agent --
    and explaining a name is not composing one.
    """
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            found.add(id(body[0].value))
    return found


def suffix_definition_assignments(tree):
    """Every assignment of a SUFFIX_CONSTANTS name in the module.

    Both questions this test asks about a definition are answered from this
    one list: which string is allowed to spell the name out, and which
    scripts define the constants at all. They used to be answered separately
    -- a line regex counted the definitions while the tree exempted their
    values -- and the two disagreed about what a definition looks like. The
    regex wanted a quote straight after the `=`, so a second copy written
    SUPERVISOR_STATE_FILE_SUFFIX = ("-supervisor-state.json"), or split over
    two lines, was exempted by the tree and never counted by the regex, and
    passed the whole suite. Reading both from this list makes that
    disagreement impossible: whatever is exempt here is counted here, so a
    definition outside handoff-supervisor.py fails however it is written.
    """
    return [node for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name)
                    and target.id in SUFFIX_CONSTANTS
                    for target in node.targets)]


def defined_suffix_values(tree):
    """The strings the suffix constants are actually assigned, from the tree.

    Read rather than restated, so SPELLED_OUT_NAMES cannot drift from what
    handoff-supervisor.py says. A definition written any of the ways
    suffix_definition_assignments() accepts is read here the same way, and a
    definition whose value is not a plain string literal comes back as None,
    which the check below counts and names rather than comparing. It counts
    rather than drops because the comparison cannot see such a definition at
    all: three readable values that match SPELLED_OUT_NAMES pass it however
    many unreadable definitions sit beside them -- and a duplicate written
    later in the file is the one the supervisor runs with (measured
    2026-09-21).
    """
    values = []
    for node in suffix_definition_assignments(tree):
        value = node.value
        values.append(value.value
                      if isinstance(value, ast.Constant)
                      and isinstance(value.value, str) else None)
    return values


def exempt_lines_and_helpers(tree, path):
    """The lines the composing helpers occupy, and which were found."""
    if path != SUPERVISOR_SCRIPT:
        return set(), []
    exempt, found = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in COMPOSING_HELPERS:
            found.append(node.name)
            exempt.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return exempt, found


def composing_sites(path):
    """Every place in `path` that builds either file name.

    Returns the sites, the composing helpers found, and whether this script
    defines the suffix constants -- all from the one parse.
    """
    # filename= so an unparseable script names itself. Without it the
    # SyntaxError reads File "<unknown>", line 1, and this suite appears
    # to report a fault in a file it has no other relationship with --
    # it parses every production script, so the one at fault is not
    # identified by being the only one parsed (reviewer of PR 549).
    tree = ast.parse(path.read_text(), filename=str(path))
    exempt_lines, helpers = exempt_lines_and_helpers(tree, path)
    definitions = suffix_definition_assignments(tree)
    allowed = docstring_nodes(tree) | {id(node.value) for node in definitions}
    sites = []

    def report(node, how):
        line = getattr(node, "lineno", 0)
        if line not in exempt_lines:
            sites.append(f"{path.name}:{line} ({how})")

    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in allowed
                and any(name in node.value for name in SPELLED_OUT_NAMES)):
            report(node, "the name spelled out")
        elif isinstance(node, ast.JoinedStr):
            if any(isinstance(part, ast.FormattedValue)
                   and names_a_suffix_constant(part.value)
                   for part in node.values):
                report(node, "an f-string built from the suffix constant")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if names_a_suffix_constant(node.left) or names_a_suffix_constant(node.right):
                report(node, "the suffix constant concatenated")
        elif isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
            # `name += SUFFIX` composes the name as surely as `name + SUFFIX`,
            # and is a different node type, so the `+` case above never saw it.
            if names_a_suffix_constant(node.value):
                report(node, "the suffix constant appended with +=")
        elif isinstance(node, ast.Call):
            # Keyword arguments count as much as positional ones: the call
            # "{a}{s}".format(a=agent, s=SUFFIX) builds exactly the name
            # .format(agent, SUFFIX) builds.
            arguments = list(node.args) + [keyword.value
                                           for keyword in node.keywords]
            if (isinstance(node.func, ast.Attribute) and node.func.attr == "format"
                    and any(names_a_suffix_constant(argument)
                            for argument in arguments)):
                report(node, "the suffix constant passed to .format()")
    return sites, helpers, bool(definitions)


scripts_read = production_scripts()
composing = []
helpers_found = []
defining = []
for script in scripts_read:
    sites, helpers, defines_the_suffixes = composing_sites(script)
    composing.extend(sites)
    helpers_found.extend(helpers)
    if defines_the_suffixes:
        defining.append(script.name)

# Asked first, because it is the question every case below assumes an answer
# to. Each of them reports what it found in the scripts that were read; none
# of them can say anything about a script that was not.
names_read = {script.name for script in scripts_read}
programs_not_read = [name for name in PROGRAMS_THAT_NEED_THESE_FILE_NAMES
                     if name not in names_read]
check("every program that needs these names is among the scripts read",
      not programs_not_read,
      f"{programs_not_read} not found under scripts/ or nc-systems/*/ -- a "
      f"program this suite exists to watch has moved somewhere it does not "
      f"read, and the cases below now pass on it by finding nothing")

check("no production script composes any of the three file names itself",
      not composing,
      "composed at " + ", ".join(composing) + " -- call "
      "supervisor_state_path(), supervisor_lock_path(), "
      "supervisor_state_paths(), handoff_file_path() or "
      "handoff_file_paths() instead")

check("every composing helper was found in the syntax tree",
      sorted(helpers_found) == sorted(COMPOSING_HELPERS),
      f"found {sorted(helpers_found)} in {SUPERVISOR_SCRIPT.name}, expected "
      f"{sorted(COMPOSING_HELPERS)}; a helper that is renamed must be renamed "
      f"in COMPOSING_HELPERS here, or its body stops being checked")

supervisor_defined_names = defined_suffix_values(
    ast.parse(SUPERVISOR_SCRIPT.read_text(encoding="utf-8"),
              filename=str(SUPERVISOR_SCRIPT)))

unreadable_definitions = supervisor_defined_names.count(None)
readable_definitions = sorted(value for value in supervisor_defined_names
                              if value is not None)
# A definition this guard cannot read is absent from readable_definitions, so
# the two lists differ whether or not a value was renamed: a remedy keyed on
# `readable_definitions != sorted(SPELLED_OUT_NAMES)` still tells an unreadable
# definition to mirror a rename that never happened (measured 2026-09-21).
# Evidence of a rename is a readable value SPELLED_OUT_NAMES does not list, or
# a shortfall bigger than the unreadable definitions can account for.
readable_values_contradict_spelled_out_names = (
    bool(set(readable_definitions) - set(SPELLED_OUT_NAMES))
    or (len(set(SPELLED_OUT_NAMES) - set(readable_definitions))
        > unreadable_definitions))

check("the names this guard hunts are the supervisor's own, not a stale copy",
      # The count, not the comparison, is what sees a definition this guard
      # cannot read: a duplicate SUPERVISOR_STATE_FILE_SUFFIX = ("-supervisor"
      # + "-state.json") beside the three plain ones is the live value -- the
      # last assignment wins -- while the three readable ones still match, and
      # the comparison alone passed that suite green (measured 2026-09-21).
      # readable_definitions filters None out, so no None reaches sorted().
      not unreadable_definitions
      and readable_definitions == sorted(SPELLED_OUT_NAMES),
      f"{SUPERVISOR_SCRIPT.name} defines {readable_definitions}"
      # Each remedy states only the cause that fired. The rename remedy used
      # to be appended whatever happened, and an agent obeying it after an
      # unreadable definition edits SPELLED_OUT_NAMES instead of the value --
      # greening the suite with a name no case hunts any more, the defect
      # this check exists to prevent (reviewer of this branch, 2026-09-21).
      + (f", and {unreadable_definitions} more whose value is not a plain "
         f"string literal, which this guard cannot read -- write the value as "
         f"a plain string literal" if unreadable_definitions else "")
      + (f"; SPELLED_OUT_NAMES here says {sorted(SPELLED_OUT_NAMES)} -- mirror "
         f"a rename into SPELLED_OUT_NAMES, or this guard hunts a name nothing "
         f"uses" if readable_values_contradict_spelled_out_names else ""))

check("the suffix constants are defined in one script",
      defining == [SUPERVISOR_SCRIPT.name],
      f"defined in {defining or 'no script'}, expected only "
      f"{SUPERVISOR_SCRIPT.name}")

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
