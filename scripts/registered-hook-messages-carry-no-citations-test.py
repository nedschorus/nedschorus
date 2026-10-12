#!/usr/bin/env python3
"""Fail when a message a registered hook hands an agent cites a ruling, a date,
an issue or pull request number, or a GitHub pull or issue link.

CLAUDE.md keeps quotations of the user, rulings, dates and citations out of the
text a program hands an agent: the agent needs the reason and the instruction,
and a citation only says who decided and when. The suite reads the hooks
.claude/settings.json registers, and in each the module-level string
constants, or tuples of strings, whose names are in capitals and end in one
of the suffixes the agent-facing-message collector recognizes,
nc-systems/general-tools/python-source-agent-facing-string-collector-common.py.
It reads only those: across all programs and tests a citation pattern also
matches dates and issue numbers that are data, while in hook messages every
match so far was a citation.

A hook that declares no such constant fails too, so a message built inline
cannot escape the check. A message that needs one of these forms as data goes
in EXEMPTIONS, named by hook and constant.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

_date_pattern_spec = importlib.util.spec_from_file_location(
    "citation_and_history_marker_tests_date_pattern_common",
    Path(__file__).resolve().with_name("citation-and-history-marker-tests-date-pattern-common.py"))
_date_pattern = importlib.util.module_from_spec(_date_pattern_spec)
_date_pattern_spec.loader.exec_module(_date_pattern)

REPOSITORY = Path(__file__).resolve().parent.parent
SETTINGS = REPOSITORY / ".claude" / "settings.json"

_collector_spec = importlib.util.spec_from_file_location(
    "python_source_agent_facing_string_collector_common",
    REPOSITORY / "nc-systems" / "general-tools" / "python-source-agent-facing-string-collector-common.py")
collector = importlib.util.module_from_spec(_collector_spec)
_collector_spec.loader.exec_module(collector)

CITATION_PATTERNS = {
    "date": _date_pattern.DATE_MARKER_PATTERN,
    "ruling": re.compile(r"\b(?:user-)?ruled\b", re.IGNORECASE),
    "issue or pull request number": re.compile(
        r"\bnedschorus#\d+\b|(?<![\w&])#\d+\b"
        r"|\b(?:PR|GHI|pull request|issue)\s+#?\d+\b", re.IGNORECASE),
    "GitHub pull or issue link": re.compile(r"github\.com/[^\s\"']+/(?:pull|issues)/\d+"),
}

# (hook path, constant name) pairs whose citation-shaped text is data.
EXEMPTIONS = set()

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def registered_hook_paths():
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    paths = []
    for event_matchers in settings.get("hooks", {}).values():
        for matcher in event_matchers:
            for hook in matcher.get("hooks", []):
                for word in hook.get("command", "").split():
                    word = word.replace('"$CLAUDE_PROJECT_DIR"/', "").replace(
                        "$CLAUDE_PROJECT_DIR/", "").strip("\"'")
                    if word.endswith(".py") and word not in paths:
                        paths.append(word)
    return paths


def is_message_name(name):
    return name.isupper() and collector.variable_name_has_agent_facing_message_suffix(name)


def message_texts(module):
    """{constant name: its text} for the module's message constants."""
    texts = {}
    for name, value in vars(module).items():
        if not is_message_name(name):
            continue
        if isinstance(value, str):
            texts[name] = value
        elif isinstance(value, (tuple, list)) and value and all(
                isinstance(part, str) for part in value):
            texts[name] = "\n".join(value)
    return texts


def citations_in(text):
    return [(kind, match.group(0)) for kind, pattern in CITATION_PATTERNS.items()
            for match in pattern.finditer(text)]


def load_hook(relative_path):
    path = REPOSITORY / relative_path
    module_name = "registered_hook_" + re.sub(r"\W", "_", relative_path)
    specification = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


# The patterns, on texts whose answer is known.
for text in ("this exact failure corrupted a command on 2026-08-17",
             "(user-ruled before)", "rule: nedschorus#27", "evidence on #37",
             "fixed by PR 931", "see GHI 913", "issue #46 holds it",
             "https://github.com/nedschorus/nedschorus/pull/931",
             "https://github.com/nedschorus/nedschorus/issues/913",
             "answered at 2026-09-19T04:00:31Z", "on 2026-09-07/08", "on 2026-08-10-11"):
    check(f"a citation is caught: {text}", citations_in(text) != [], text)
for text in ("gh issue close <number> --reason completed",
             "tmux display-message -p -t seat '#{session_attached}'",
             "quote his approval words into {marker} at the checkout root",
             "run git rebase origin/main, which will stop on this file",
             "the file can be cited by its basename",
             "read 2026-09-19T04:00:31Z.log and logs/2026-09-19T04:00:31Z/x",
             "read 2026-08-10-11.md and 2026-10-14/x"):
    check(f"a message with no citation passes: {text}", citations_in(text) == [],
          citations_in(text))

hook_paths = registered_hook_paths()
check(".claude/settings.json registers hooks for this suite to read", len(hook_paths) > 5,
      hook_paths)
for relative_path in hook_paths:
    try:
        module = load_hook(relative_path)
    except Exception as error:
        check(f"{relative_path} loads", False, f"{type(error).__name__}: {error}")
        continue
    texts = message_texts(module)
    check(f"{relative_path} declares its messages as named constants", texts != {},
          f"no module-level constant ending in one of {collector.AGENT_STRING_NAME_SUFFIXES}")
    for name, text in sorted(texts.items()):
        if (relative_path, name) in EXEMPTIONS:
            continue
        found = citations_in(text)
        check(f"{relative_path} {name} carries no citation", found == [],
              f"citations found: {found}")

for relative_path, name in sorted(EXEMPTIONS):
    check(f"exemption {relative_path} {name} names a registered hook",
          relative_path in hook_paths, hook_paths)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
