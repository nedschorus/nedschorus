#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/claude-code-headless-print-mode-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py.

Run: python3 nc-systems/general-tools/tests/claude-code-headless-print-mode-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "claude_code_headless_print_mode_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "claude-code-headless-print-mode-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")
command_line_prefix = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(command_line_prefix)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


started = command_line_prefix.claude_code_headless_print_mode_command_line_prefix_build("dontAsk")
check("the command starts claude in print mode, with -p second so a prompt may follow the list",
      started[:2] == ["claude", "-p"], started)
check("the command keeps the account's claude.ai connectors out with --strict-mcp-config",
      "--strict-mcp-config" in started, started)
check("the command names the permission mode the caller chose",
      started[started.index("--permission-mode") + 1] == "dontAsk"
      and started.count("--permission-mode") == 1, started)
check("the command is exactly those five words",
      started == ["claude", "-p", "--strict-mcp-config", "--permission-mode", "dontAsk"], started)

given_program = command_line_prefix.claude_code_headless_print_mode_command_line_prefix_build("plan", "/opt/fake/claude")
check("a caller's program path replaces claude, and the rest is unchanged",
      given_program == ["/opt/fake/claude", "-p", "--strict-mcp-config", "--permission-mode", "plan"],
      given_program)
check("each call returns a new list, so a caller appending to one changes no other",
      command_line_prefix.claude_code_headless_print_mode_command_line_prefix_build("dontAsk")
      is not command_line_prefix.claude_code_headless_print_mode_command_line_prefix_build("dontAsk"))

print()
if failures:
    print(f"{failures} case(s) failed")
    sys.exit(1)
print("all cases passed")
