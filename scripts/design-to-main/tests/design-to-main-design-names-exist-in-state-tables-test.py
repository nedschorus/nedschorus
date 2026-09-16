#!/usr/bin/env python3
"""Every backticked name in the design-to-main state-machine design is a
name the code defines.

User-ruled 2026-09-16, the eleventh design walk
(design-state-tables-source-of-truth-and-checker), item 5: a test reads the
design's prose and checks that every backticked state, sub-state, verdict,
counter and state-exit field exists in the code's name sets; backticked
tokens containing a dot or a slash (file names, paths) are skipped.

It reads the design from the checkout it runs in: the whole file but its
front matter and its fenced blocks (the state-exit example and section
3.3's generated diagram), and from it every inline code span. A token is
then, in this order:
- skipped, when it cannot be a name (SKIPPED_TOKEN_RULES: a dot or slash,
  a suffix, a template, a Mermaid identifier, a commit-trailer key);
- read value by value, when it is a comma-separated list (`script, prompt`);
- read as its name, when it is an evidence directory's (`<name>-<n>`);
- passed, when it is a name the state tables module defines
  (machine_names_in_the_state_tables_module), a name another module of
  the machine defines as a literal (MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE,
  whose literals are checked in those files), or a word the allowlist
  gives a reason for (BACKTICKED_TOKENS_THAT_ARE_NOT_MACHINE_NAMES);
- carried, when it is a known mismatch awaiting the user's ruling
  (KNOWN_MISMATCHES_AWAITING_A_RULING);
- and otherwise a failure: a name in the design the code does not have.

What it does not catch:
- a mechanism described in prose with no row behind it;
- a section 7 ceiling number that disagrees with COUNTER_TABLE;
- a name that is not backticked: section 7's counters are bold and section
  3.2's Counter column is plain text, so a misspelled counter there passes;
- a name used in the wrong class (a verdict written where a state belongs);
  the row pairing test (design-to-main-design-rows-pair-with-state-tables-test.py)
  reads sections 3.1 and 3.2 by class, and nothing reads the rest.

Run: python3 scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py
"""

import importlib.util
import pathlib
import re
import unittest

MACHINE_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = MACHINE_DIRECTORY.parent.parent
DESIGN_PATH = REPOSITORY_ROOT / "docs" / "design-to-main" / "design-to-main-state-machine-design.md"


def load_state_tables_module():
    spec = importlib.util.spec_from_file_location(
        "design_to_main_state_tables", MACHINE_DIRECTORY / "design-to-main-state-tables.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T = load_state_tables_module()


def machine_names_in_the_state_tables_module(tables):
    """The names the state tables module defines, by class: the four the
    ruling names, and the values those carry or the run-state holds."""
    return {
        "state": {row.name for row in tables.STATE_TABLE},
        "sub-state": set(tables.COMPOSITE_STATE_OF_SUB_STATE),
        "verdict": {value for name, value in vars(tables).items() if name.startswith("V_")},
        "counter": set(tables.COUNTER_NAMES),
        "state-exit field": set(tables.STATE_EXIT_JSON_FIELDS),
        "work-stream or its position": {
            tables.IMPLEMENTATION_WORK_STREAM, tables.TEST_WORK_STREAM,
            tables.READY_FOR_TEST_SUITE},
        "outcome": {value for name, value in vars(tables).items() if name.startswith("OUTCOME_")},
        "investigation-focus": {
            value for name, value in vars(tables).items() if name.startswith("FOCUS_")},
        "input an input-quick-check-failed names": {
            value for name, value in vars(tables).items() if name.startswith("INPUT_")},
        "refusal-class": {
            value for name, value in vars(tables).items() if name.startswith("REFUSAL_")},
        "coverage-type": set(tables.COVERAGE_TYPES_THAT_ARE_AGENT_INSTRUCTIONS)
                         | {tables.COVERAGE_TYPE_NO_TESTS},
    }


# Tokens that cannot be a machine name, each rule with what it skips.
SKIPPED_TOKEN_RULES = (
    # File names and paths (the ruling's own rule).
    ("contains a dot or a slash", lambda token: "." in token or "/" in token),
    # A suffix of names, not a name: `-writing`, `-acceptance-by-user`.
    ("starts with a hyphen", lambda token: token.startswith("-")),
    # A template: `reject <artifact>`, `<n>`, `Counter-<name>:`.
    ("contains an angle bracket", lambda token: "<" in token),
    # A Mermaid identifier (section 3.3's `design_writing`) or Python.
    ("contains an underscore", lambda token: "_" in token),
    # A commit trailer's key (`State:`, `Write: forced`) or the test-design's
    # `coverage-type:` line; a machine name has no colon.
    ("contains a colon", lambda token: ":" in token),
)

# A section 9 evidence directory, `<state or sub-state>-<n>`: its name is read.
EVIDENCE_DIRECTORY_NAME_PATTERN = re.compile(r"(?P<name>[A-Za-z-]+)-[0-9]+")

# Names another module of the machine defines as a string literal, not the
# state tables module: the file, and what the name is. The literal is
# checked in the file, so that an entry cannot outlive the name.
MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE = {
    "evidence-directory": ("design-to-main-state-machine.py",
                           "the state-package's key for the instance's evidence directory (section 2)"),
    "investigation-report": ("design-to-main-state-machine.py",
                             "the state-package's key for the investigation report's path "
                             "(sections 2 and 9)"),
    "tests-begun": ("design-to-main-run-state.py", "a run-state.json field (section 9)"),
    "reset": ("design-to-main-state-machine.py",
              "the user's ruling the machine reads in `rulings` (section 7)"),
}

# Backticked words that are not the machine's names, each with its reason.
BACKTICKED_TOKENS_THAT_ARE_NOT_MACHINE_NAMES = {
    "a": "the suffix of a refusal-clause-pair's first clause number (section 5.2)",
    "b": "the suffix of a refusal-clause-pair's second clause number (section 5.2)",
    "adjudicator": "a word scrubbed from the fleet glossary, cited as history",
    "nit": "the word the sixth walk restored, cited as history",
    "green": "the seat's old word for a passing suite, cited as history (section 2)",
    "red": "the seat's old word for a failing suite, cited as history (section 2)",
    "example": "the correct spelling in section 2's nit example",
    "exxample": "the misspelling in section 2's nit example",
    "main": "the branch",
    "reject": "the verdicts `reject <artifact>` named together, without their artifact (section 7)",
    "git log": "a git command the arbitrator runs (section 9)",
    "git show": "a git command the arbitrator runs (section 9)",
    "supersedes": "the notes' section 13 edge name, which a run does not use (section 9)",
    "script": "a coverage-type (section 2) the tables module does not name: the machine "
              "reads only the agent-instructions types and no-tests",
    "can-not-be-tested": "a no-tests reason, written in the test-design, which the machine "
                         "reads only for its coverage-type lines (section 2)",
    "do-not-know-how-to-test": "a no-tests reason (section 2), as can-not-be-tested",
    "no-tests-written": "a no-tests reason (section 2), as can-not-be-tested",
    "design-review": "a skill of this workflow, run outside the run (section 2)",
    "test-design-review": "a skill of this workflow, run outside the run (section 2)",
    "contract-review": "a skill of this workflow, run outside the run (section 2)",
    "unchecked": "a component-contract clause's declaration (section 5.2)",
    "component-consumer-supplies": "a component-contract clause group (section 5.2)",
    "world-requires": "a component-contract clause group (section 5.2)",
    "component-consumer-receives": "a component-contract clause group (section 5.2)",
    "world-changes": "a component-contract clause group (section 5.2)",
    "world-unchanged": "a component-contract clause group (section 5.2)",
    "network-down": "a gatekeeper error code, the gatekeeper's catalog (section 3.4)",
    "push-auth-failed": "a gatekeeper error code, the gatekeeper's catalog (section 3.4)",
    "workspace-io-error": "a gatekeeper error code, the gatekeeper's catalog (section 3.4)",
    "conflict": "a gatekeeper error code, the gatekeeper's catalog (section 3.4)",
    "main-moving-too-fast": "a gatekeeper error code, the gatekeeper's catalog (section 3.4)",
    "gatekeeper-source-refused": "a gatekeeper error code, the gatekeeper's catalog (section 3.4)",
    "malformed-field": "a gatekeeper error code, the gatekeeper's catalog (section 3.4)",
}

# Names in the design that no code defines, found when this test was
# written. They await the user's ruling (or the code that builds them);
# neither the design nor the code was changed to make this test pass. An
# entry the tables module now defines, or that any module of the machine
# now spells as a string literal, fails the test, so that it is removed
# (or moved to MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE).
KNOWN_MISMATCHES_AWAITING_A_RULING = {}


def design_prose_without_front_matter_and_fenced_blocks(design_text):
    if design_text.startswith("---\n"):
        design_text = design_text[design_text.index("\n---\n", 4) + len("\n---\n"):]
    return re.sub(r"^```[^\n]*\n.*?^```$", "", design_text, flags=re.S | re.M)


def inline_code_spans(prose):
    return re.findall(r"`([^`\n]+)`", prose)


def is_a_string_literal_in_machine_module(name, file_name):
    return '"%s"' % name in (MACHINE_DIRECTORY / file_name).read_text()


def names_to_check_in_token(token):
    """The names a backticked token stands for; none when it is skipped."""
    if any(applies(token) for _, applies in SKIPPED_TOKEN_RULES):
        return []
    names = [value.strip() for value in token.split(",")]
    return [EVIDENCE_DIRECTORY_NAME_PATTERN.fullmatch(name).group("name")
            if EVIDENCE_DIRECTORY_NAME_PATTERN.fullmatch(name) else name
            for name in names]


def backticked_names_the_code_does_not_define(design_text, name_classes):
    """Each name in the design's backticked tokens that is in no name class,
    not defined outside the tables module, and not allowlisted; known
    mismatches included."""
    known = set().union(*name_classes.values())
    known |= set(MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE)
    known |= set(BACKTICKED_TOKENS_THAT_ARE_NOT_MACHINE_NAMES)
    undefined = set()
    for token in inline_code_spans(design_prose_without_front_matter_and_fenced_blocks(design_text)):
        for name in names_to_check_in_token(token):
            if name not in known:
                undefined.add(name)
    return undefined


class TheDesignsNamesExistInTheCode(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.design_text = DESIGN_PATH.read_text()
        cls.name_classes = machine_names_in_the_state_tables_module(T)
        cls.undefined = backticked_names_the_code_does_not_define(cls.design_text, cls.name_classes)

    def test_every_backticked_name_in_the_design_is_defined_or_a_known_mismatch(self):
        self.assertEqual(self.undefined - set(KNOWN_MISMATCHES_AWAITING_A_RULING), set(),
                         "backticked in the design, defined by no code and on no list")

    def test_every_known_mismatch_is_still_one(self):
        self.assertEqual(set(KNOWN_MISMATCHES_AWAITING_A_RULING) - self.undefined, set(),
                         "no longer a mismatch: remove it from KNOWN_MISMATCHES_AWAITING_A_RULING")
        for name in KNOWN_MISMATCHES_AWAITING_A_RULING:
            for module_path in sorted(MACHINE_DIRECTORY.glob("*.py")):
                with self.subTest(name=name, module=module_path.name):
                    self.assertFalse(
                        is_a_string_literal_in_machine_module(name, module_path.name),
                        "now a literal in %s: move it to "
                        "MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE" % module_path.name)

    def test_a_name_defined_outside_the_tables_module_is_a_literal_in_the_file_it_cites(self):
        for name, (file_name, _what) in MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE.items():
            with self.subTest(name=name):
                self.assertTrue(is_a_string_literal_in_machine_module(name, file_name))

    def test_no_allowlisted_word_is_a_machine_name(self):
        known = set().union(*self.name_classes.values())
        self.assertEqual(set(BACKTICKED_TOKENS_THAT_ARE_NOT_MACHINE_NAMES) & known, set())
        self.assertEqual(set(MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE) & known, set())

    def test_the_prose_read_is_the_whole_design_but_its_fenced_blocks(self):
        prose = design_prose_without_front_matter_and_fenced_blocks(self.design_text)
        self.assertNotIn("stateDiagram-v2", prose)
        self.assertNotIn('"package-commit": ', prose)
        self.assertIn("### 3.2 The transitions", prose)
        self.assertIn("## 11. Not decided here", prose)
        self.assertIn("`test-suite-arbitrating`", prose)


class TheCheckerFailsOnANameTheCodeDoesNotHave(unittest.TestCase):
    """Copies of the design text, or of the code's names, with one thing changed."""

    @classmethod
    def setUpClass(cls):
        cls.design_text = DESIGN_PATH.read_text()
        cls.name_classes = machine_names_in_the_state_tables_module(T)

    def undefined_in(self, design_text, name_classes=None):
        return (backticked_names_the_code_does_not_define(
            design_text, self.name_classes if name_classes is None else name_classes)
                - set(KNOWN_MISMATCHES_AWAITING_A_RULING))

    def test_a_state_shaped_name_no_code_has_fails(self):
        text = self.design_text + "\nThe run then enters `test-design-approving`.\n"
        self.assertEqual(self.undefined_in(text), {"test-design-approving"})

    def test_a_verdict_shaped_name_no_code_has_fails(self):
        text = self.design_text.replace("`reject tests`", "`reject the tests`", 1)
        self.assertEqual(self.undefined_in(text), {"reject the tests"})

    def test_a_misspelled_state_exit_field_fails(self):
        text = self.design_text + "\nIt writes `held-rulings`.\n"
        self.assertEqual(self.undefined_in(text), {"held-rulings"})

    def test_a_name_the_code_no_longer_defines_fails(self):
        without_flaky_test = dict(self.name_classes)
        without_flaky_test["verdict"] = self.name_classes["verdict"] - {T.V_FLAKY_TEST}
        self.assertEqual(self.undefined_in(self.design_text, without_flaky_test), {T.V_FLAKY_TEST})

    def test_a_list_is_read_value_by_value(self):
        text = self.design_text + "\nIt emits `script, promt`.\n"
        self.assertEqual(self.undefined_in(text), {"promt"})

    def test_an_evidence_directory_is_read_as_its_state(self):
        text = self.design_text + "\nSee `implementation-writting-2`.\n"
        self.assertEqual(self.undefined_in(text), {"implementation-writting"})

    def test_paths_and_file_names_are_skipped(self):
        text = self.design_text + "\nSee `no-such-directory/` and `no-such-file.json`.\n"
        self.assertEqual(self.undefined_in(text), set())

    def test_a_name_inside_a_fenced_block_is_not_read(self):
        text = self.design_text + "\n```text\n`not-a-name-in-a-fence`\n```\n"
        self.assertEqual(self.undefined_in(text), set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
