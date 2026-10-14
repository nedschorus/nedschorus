#!/usr/bin/env python3
"""The checkout and git-tracking helpers the Markdown-edit hooks share are defined
in one module, and this test keeps it that way.

nc-systems/general-tools/edited-file-path-within-checkout-root-and-git-check-ignore-common.py
holds them. A copy defined in another program drifts from the module: one copy
reports a git failure, another reads the failure as "not tracked" and stays
silent. The test fails when any production script, in scripts/ or in an
nc-systems/<system>/ directory, defines a function or class under one of the
module's shared names, and when the module itself stops defining one, so a
rename inside the module cannot pass by hunting a name nothing defines.

Run: python3 scripts/edited-file-path-within-checkout-root-and-git-check-ignore-defined-once-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_MODULE = (REPO_ROOT / "nc-systems" / "general-tools"
                 / "edited-file-path-within-checkout-root-and-git-check-ignore-common.py")
SHARED_NAMES = ("enclosing_checkout_root", "checkout_relative_path", "git_would_track",
                "file_lines_at_head_unless_git_ignores_file", "GitIgnoreCheckFailed")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def production_scripts():
    """Every Python program in scripts/ and in each nc-systems/<system>/, test files excluded."""
    found = (list((REPO_ROOT / "scripts").glob("*.py"))
             + list((REPO_ROOT / "nc-systems").glob("*/*.py")))
    return sorted(path for path in found if not path.name.endswith("-test.py"))


def defined_shared_names(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name in SHARED_NAMES}


module_names = defined_shared_names(SHARED_MODULE)
check("the shared module defines every shared name",
      module_names == set(SHARED_NAMES),
      f"{SHARED_MODULE.relative_to(REPO_ROOT)} lacks {sorted(set(SHARED_NAMES) - module_names)}; "
      f"if a name was renamed there, rename it in SHARED_NAMES here")

copies = {}
for script in production_scripts():
    if script == SHARED_MODULE:
        continue
    names = defined_shared_names(script)
    if names:
        copies[str(script.relative_to(REPO_ROOT))] = sorted(names)
check("no other production script defines a shared name",
      not copies,
      "; ".join(f"{path} defines {', '.join(names)}" for path, names in sorted(copies.items()))
      + f" -- load them from {SHARED_MODULE.relative_to(REPO_ROOT)} instead")

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
