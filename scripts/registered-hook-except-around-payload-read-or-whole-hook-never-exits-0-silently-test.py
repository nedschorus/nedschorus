#!/usr/bin/env python3
"""Fail when a hook's `except` around its payload read, or around the whole hook, exits 0
without printing anything.

A Claude Code hook that exits 0 with nothing printed lets the act go ahead, and nobody learns
that the hook failed and did not look. The Hooks section of
docs/nedsnodes-wiki/nedsnodes-how-a-program-reports-success-failure-and-findings-with-its-exit-code.md
says a hook never turns its own failure into a silent 0, and says what it does instead.

The hooks read are the Python files .claude/settings.json registers, found as
nn-systems/general-tools/claude-code-registered-hook-rule-id-pattern-hook-files-list-and-source-scan-common.py
finds them; a file settings.json does not register is never run as a hook.

Each hook's syntax tree is read, not run. A `try` is checked when its body reads stdin, as
`sys.stdin` or a name `stdin`, or when it sits at module level, outside every function, and its
body exits or calls a function the hook defines, as a `try` around `sys.exit(main())` does. Its `except` exits 0 silently
when its body makes no call but `sys.exit`, `exit`, `quit`, `os._exit` or `SystemExit` with 0 or
nothing, raises nothing but such a `SystemExit`, and returns no nonzero whole number. Whatever
else it does, such as `return 0`, `return {}` or `payload = {}`, leaves the hook to carry on with
nothing to check. A body that makes any other call is taken to report, so the tree cannot see an
`except` whose call prints nothing, nor one that sets a flag the hook prints later. Two more
cases it does not handle: an `except` that defines a local function which prints but is never
called, then returns 0, is taken to report; and an allowlist entry, keyed by hook and exception,
also excuses a second silent `except` for the same exception in the same hook.

Run: python3 scripts/registered-hook-except-around-payload-read-or-whole-hook-never-exits-0-silently-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import ast
import importlib.util
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
SUITE = "scripts/" + Path(__file__).name
SETTINGS = REPOSITORY / ".claude" / "settings.json"
EXIT_CODE_PAGE = (
    "docs/nedsnodes-wiki/nedsnodes-how-a-program-reports-success-failure-and-findings-with-its-exit-code.md")

_rule_ids_spec = importlib.util.spec_from_file_location(
    "claude_code_registered_hook_rule_id_pattern_hook_files_list_and_source_scan_common",
    REPOSITORY / "nn-systems" / "general-tools"
    / "claude-code-registered-hook-rule-id-pattern-hook-files-list-and-source-scan-common.py")
rule_ids = importlib.util.module_from_spec(_rule_ids_spec)
_rule_ids_spec.loader.exec_module(rule_ids)

_rule_failure_lines_spec = importlib.util.spec_from_file_location(
    "rule_enforcing_nc_test_suite_failure_message_closing_lines_text_common",
    REPOSITORY / "nn-systems" / "general-tools"
    / "rule-enforcing-nc-test-suite-failure-message-closing-lines-text-common.py")
RULE_FAILURE_LINES = importlib.util.module_from_spec(_rule_failure_lines_spec)
_rule_failure_lines_spec.loader.exec_module(RULE_FAILURE_LINES)

SILENT_EXIT_0_FAILURE_LINE_TEMPLATE = (
    "{file}:{line}: this hook exits 0 without a word when {exception} is raised, so its own "
    "failure is silent. Report it as the Hooks section of " + EXIT_CODE_PAGE + " says.")
ALLOWLIST_ENTRY_STALE_FAILURE_LINE_TEMPLATE = (
    "{file}: the allowlist in " + SUITE + " holds this hook for {exception}, but {why}. "
    "Remove the entry from the allowlist.")
NO_SUCH_SILENT_EXCEPT_REASON = (
    "no `except` around its payload read or the whole hook exits 0 without a word for it")
NOT_A_HOOK_REASON = "the file is not a hook this suite reads"

# Hooks that still exit 0 silently, keyed by (hook path, exception as the failure line names it),
# each with what its `except` does. An entry leaves when its hook is fixed: a case below fails
# on an entry that no longer matches a silent `except`.
SILENT_EXIT_0_HOOKS_AWAITING_FIX = {
    ("nn-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py",
     "json.JSONDecodeError or ValueError"):
        "main() returns 0 when stdin is not JSON, so no push is checked and nobody is told",
    ("nn-systems/general-tools/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook.py",
     "json.JSONDecodeError or ValueError or OSError"):
        "main() returns 0 when stdin cannot be read as JSON, so the edit is not inspected and "
        "nobody is told",
    ("nn-systems/general-tools/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook.py",
     "Exception"):
        "the `try` around sys.exit(main()) exits 0 on any crash, so the edit is not inspected "
        "and nobody is told",
    ("scripts/checkout-freshness-catch-up.py", "json.JSONDecodeError or UnicodeDecodeError"):
        "a payload that is not JSON is replaced with an empty one and the hook carries on, so "
        "the checkout of the agent-session is not looked at and nobody is told",
    ("scripts/file-name-collision-warning-hook.py",
     "json.JSONDecodeError or ValueError or OSError"):
        "main() returns 0 when stdin cannot be read as JSON, so no collision is looked for and "
        "nobody is told",
    ("scripts/handoff-context-threshold-hook.py", "json.JSONDecodeError or UnicodeDecodeError"):
        "hook_payload_from_stdin() returns an empty payload when stdin is not JSON, so the "
        "context is not measured and nobody is told",
    ("scripts/new-shared-names-reminder-hook.py",
     "json.JSONDecodeError or ValueError or OSError"):
        "main() returns 0 when stdin cannot be read as JSON, so no new name is looked for and "
        "nobody is told",
}

EXIT_CALL_NAMES = {"sys.exit", "exit", "quit", "os._exit", "SystemExit"}
SCOPE_NODE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def hook_paths():
    """Repository-relative paths of the hooks this suite reads, sorted."""
    return sorted(set(rule_ids.registered_hook_paths(SETTINGS)))


def nodes_outside_nested_scopes(statements):
    """Every node under the statements, without descending into a function, lambda or class."""
    stack = list(statements)
    while stack:
        node = stack.pop()
        yield node
        stack.extend(child for child in ast.iter_child_nodes(node)
                     if not isinstance(child, SCOPE_NODE_TYPES))


def reads_stdin(statements):
    for node in nodes_outside_nested_scopes(statements):
        if (isinstance(node, ast.Attribute) and node.attr == "stdin"
                and isinstance(node.value, ast.Name) and node.value.id == "sys"):
            return True
        if isinstance(node, ast.Name) and node.id == "stdin":
            return True
    return False


def is_zero_or_nothing(arguments):
    return not arguments or (isinstance(arguments[0], ast.Constant)
                             and arguments[0].value in (0, None))


def is_exit_call(node):
    return isinstance(node, ast.Call) and ast.unparse(node.func) in EXIT_CALL_NAMES


def exits_0_without_a_word(handler):
    for node in nodes_outside_nested_scopes(handler.body):
        if isinstance(node, ast.Call):
            if not is_exit_call(node) or not is_zero_or_nothing(node.args):
                return False
        elif isinstance(node, ast.Raise):
            raised = node.exc
            if not (is_exit_call(raised) or (isinstance(raised, ast.Name)
                                              and raised.id == "SystemExit")):
                return False
        elif (isinstance(node, ast.Return) and isinstance(node.value, ast.Constant)
              and isinstance(node.value.value, int) and node.value.value not in (0, False)):
            return False
    return True


def exception_text(handler):
    """The exception the failure line names: `any exception` for a bare `except:`, and the
    names of a tuple joined with `or`."""
    if handler.type is None:
        return "any exception"
    if isinstance(handler.type, ast.Tuple):
        return " or ".join(ast.unparse(name) for name in handler.type.elts)
    return ast.unparse(handler.type)


def runs_the_hook(statements, module_function_names):
    """Whether the statements exit or call a function the module defines, as `main()`."""
    return any(isinstance(node, ast.Call) and (
        is_exit_call(node) or (isinstance(node.func, ast.Name)
                               and node.func.id in module_function_names))
        for node in nodes_outside_nested_scopes(statements))


def checked_tries(statements, at_module_level, module_function_names):
    """Each `try` that reads stdin, or sits at module level and runs the hook."""
    for statement in statements:
        if isinstance(statement, SCOPE_NODE_TYPES):
            yield from checked_tries(statement.body, False, module_function_names)
            continue
        if isinstance(statement, ast.Try) or type(statement).__name__ == "TryStar":
            around_whole_hook = at_module_level and runs_the_hook(
                statement.body, module_function_names)
            if around_whole_hook or reads_stdin(statement.body):
                yield statement
        nested = [*(getattr(statement, field, None) or [] for field in ("body", "orelse", "finalbody")),
                  *(handler.body for handler in getattr(statement, "handlers", None) or []),
                  *(case.body for case in getattr(statement, "cases", None) or [])]
        for block in nested:
            yield from checked_tries(block, at_module_level, module_function_names)


def silent_exit_0_excepts(source):
    """[(line, exception text)] for each `except` in the source that exits 0 without a word."""
    found = []
    module = ast.parse(source)
    module_function_names = {node.name for node in ast.walk(module)
                             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for statement in checked_tries(module.body, True, module_function_names):
        for handler in statement.handlers:
            if exits_0_without_a_word(handler):
                found.append((handler.lineno, exception_text(handler)))
    return sorted(set(found))


def failure_lines(hook_sources, allowlist):
    """The failure lines for {hook path: source}, against the allowlist."""
    lines = []
    found_keys = set()
    for path, source in sorted(hook_sources.items()):
        for line, exception in silent_exit_0_excepts(source):
            found_keys.add((path, exception))
            if (path, exception) not in allowlist:
                lines.append(SILENT_EXIT_0_FAILURE_LINE_TEMPLATE.format(
                    file=path, line=line, exception=exception))
    for path, exception in sorted(allowlist):
        if (path, exception) in found_keys:
            continue
        why = NO_SUCH_SILENT_EXCEPT_REASON if path in hook_sources else NOT_A_HOOK_REASON
        lines.append(ALLOWLIST_ENTRY_STALE_FAILURE_LINE_TEMPLATE.format(
            file=path, exception=exception, why=why))
    return lines


def failure_message(lines):
    closing = [RULE_FAILURE_LINES.guarded_file_fix_failure_message_line_pointing_to_approval_page_and_guard_refusal(path)
               for path in sorted({line.split(":", 1)[0] for line in lines})
               if path.startswith(".claude/")]
    return "\n".join(lines + closing
                     + [RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE])


# --- the rule, against fixtures ---

SILENT_PAYLOAD_READ_HOOK = """\
import json, sys

def main():
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        return 0
    print(payload)
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""
REPORTING_PAYLOAD_READ_HOOK = """\
import json, sys

def main():
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError) as error:
        print(f"the hook could not read its input: {error}", file=sys.stderr)
        return 1
    print(payload)
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""
SILENT_BARE_EXCEPT_WHOLE_HOOK = """\
import sys

def main():
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except:
        sys.exit(0)
"""
REPORTING_WHOLE_HOOK = """\
import sys

def main():
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"the hook failed: {error}", file=sys.stderr)
        sys.exit(0)
"""
EMPTY_PAYLOAD_SUBSTITUTED_HOOK = """\
import json, sys

def payload_from(stdin):
    try:
        return json.load(stdin)
    except json.JSONDecodeError:
        return {}
"""
NONZERO_EXIT_HOOK = """\
import json, sys
try:
    payload = json.load(sys.stdin)
except ValueError:
    sys.exit(1)
"""
RERAISING_HOOK = """\
import json, sys
try:
    payload = json.load(sys.stdin)
except ValueError:
    raise
"""
RETURN_1_HOOK = """\
import json, sys

def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""
MODULE_LEVEL_IMPORT_FALLBACK = """\
try:
    import yaml
except ImportError:
    yaml = None
"""
MODULE_LEVEL_SETTING_FALLBACK = """\
import os
try:
    LIMIT = int(os.environ["LIMIT"])
except (KeyError, ValueError):
    LIMIT = 50
"""

check("a silent `return 0` around the payload read gives the failure line, word for word",
      failure_lines({"fixture-hook.py": SILENT_PAYLOAD_READ_HOOK}, {}) == [
          "fixture-hook.py:6: this hook exits 0 without a word when json.JSONDecodeError or "
          "ValueError is raised, so its own failure is silent. Report it as the Hooks section of "
          "docs/nedsnodes-wiki/nedsnodes-how-a-program-reports-success-failure-and-findings-with-its-exit-code.md "
          "says."],
      failure_lines({"fixture-hook.py": SILENT_PAYLOAD_READ_HOOK}, {}))
check("an `except` around the payload read that prints before it exits passes",
      failure_lines({"fixture-hook.py": REPORTING_PAYLOAD_READ_HOOK}, {}) == [],
      failure_lines({"fixture-hook.py": REPORTING_PAYLOAD_READ_HOOK}, {}))
check("a bare `except:` around the whole hook that exits 0 silently names `any exception`",
      silent_exit_0_excepts(SILENT_BARE_EXCEPT_WHOLE_HOOK) == [(9, "any exception")],
      silent_exit_0_excepts(SILENT_BARE_EXCEPT_WHOLE_HOOK))
check("an `except` around the whole hook that prints before it exits 0 passes",
      silent_exit_0_excepts(REPORTING_WHOLE_HOOK) == [],
      silent_exit_0_excepts(REPORTING_WHOLE_HOOK))
check("an `except` that hands back an empty payload, with no word, fails",
      silent_exit_0_excepts(EMPTY_PAYLOAD_SUBSTITUTED_HOOK) == [(6, "json.JSONDecodeError")],
      silent_exit_0_excepts(EMPTY_PAYLOAD_SUBSTITUTED_HOOK))
check("an `except` around the payload read that exits nonzero passes",
      silent_exit_0_excepts(NONZERO_EXIT_HOOK) == [], silent_exit_0_excepts(NONZERO_EXIT_HOOK))
check("an `except` around the payload read that re-raises, so the hook crashes nonzero, passes",
      silent_exit_0_excepts(RERAISING_HOOK) == [], silent_exit_0_excepts(RERAISING_HOOK))
check("an `except` around the payload read that returns 1 to sys.exit, printing nothing, passes",
      silent_exit_0_excepts(RETURN_1_HOOK) == [], silent_exit_0_excepts(RETURN_1_HOOK))
check("a module-level `try` around an import, which calls nothing, is not read as the whole hook",
      silent_exit_0_excepts(MODULE_LEVEL_IMPORT_FALLBACK) == [],
      silent_exit_0_excepts(MODULE_LEVEL_IMPORT_FALLBACK))
check("a module-level `try` around a setting, which calls no function the hook defines, is not "
      "read as the whole hook",
      silent_exit_0_excepts(MODULE_LEVEL_SETTING_FALLBACK) == [],
      silent_exit_0_excepts(MODULE_LEVEL_SETTING_FALLBACK))
check("an allowlisted silent `except` passes",
      failure_lines({"fixture-hook.py": SILENT_PAYLOAD_READ_HOOK},
                    {("fixture-hook.py", "json.JSONDecodeError or ValueError"): "awaiting a fix"})
      == [], "the allowlist entry did not excuse the hook")
fixed_lines = failure_lines({"fixture-hook.py": REPORTING_PAYLOAD_READ_HOOK},
                            {("fixture-hook.py", "json.JSONDecodeError or ValueError"): "fixed"})
check("an allowlisted hook that no longer exits 0 silently fails, so its entry leaves the list",
      fixed_lines == [ALLOWLIST_ENTRY_STALE_FAILURE_LINE_TEMPLATE.format(
          file="fixture-hook.py", exception="json.JSONDecodeError or ValueError",
          why=NO_SUCH_SILENT_EXCEPT_REASON)], fixed_lines)
gone_lines = failure_lines({}, {("gone-hook.py", "Exception"): "awaiting a fix"})
check("an allowlist entry for a file that is not a hook fails",
      gone_lines == [ALLOWLIST_ENTRY_STALE_FAILURE_LINE_TEMPLATE.format(
          file="gone-hook.py", exception="Exception", why=NOT_A_HOOK_REASON)], gone_lines)
guarded_message = failure_message([".claude/guard-hooks/x.py:3: a finding", "scripts/y.py:4: a finding"])
check("a finding in a file the instruction-file guard protects says how its fix is approved, and "
      "only for that file",
      ".claude/guard-hooks/x.py is protected by the instruction-file guard" in guarded_message
      and "scripts/y.py is protected" not in guarded_message, guarded_message)

# --- the rule, against the hooks of this checkout ---

HOOK_PATHS = hook_paths()
check("the registered hooks read include hooks from scripts/, nn-systems/ and .claude/guard-hooks/",
      {"scripts/handoff-context-threshold-hook.py",
       "nn-systems/skills/emergency-stop/emergency-stop-file-shown-and-push-and-merge-refusal-hook.py",
       ".claude/guard-hooks/instruction-file-guard.py"} <= set(HOOK_PATHS), HOOK_PATHS)
sources = {path: (REPOSITORY / path).read_text(encoding="utf-8") for path in HOOK_PATHS}
lines = failure_lines(sources, SILENT_EXIT_0_HOOKS_AWAITING_FIX)
print(f"read {len(HOOK_PATHS)} hooks; {len(SILENT_EXIT_0_HOOKS_AWAITING_FIX)} allowlisted "
      f"`except`s in {len({path for path, _ in SILENT_EXIT_0_HOOKS_AWAITING_FIX})} hooks")
check("no hook exits 0 without a word in an `except` around its payload read or the whole hook, "
      "beyond the allowlist, and every allowlist entry is still needed",
      not lines, "\n" + failure_message(lines))

if failures:
    print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("\nall cases passed")
