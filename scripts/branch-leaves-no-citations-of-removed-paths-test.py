#!/usr/bin/env python3
"""Fail while any file of this checkout cites a path its branch removed or renamed.

Runs scripts/dangling-path-citation-check.py --only-citations-of-removed-paths
against origin/main, on the commits only: a deletion or rename not yet
committed is not seen. Its findings name each citing line; correct each line
to the path's new name, or remove the citation. The check's exit code is this
suite's: 0 when nothing cites a removed path, 1 when a line does, and 2 when
the check could not run, such as when the checkout has no origin/main.

With --only-suites-whose-recorded-inputs-changed-since, scripts/run-all-test-suites.py
selects this suite whenever any file differs, a rename included, because the
check runs git diff on the checkout, which reads file contents.

Run: python3 scripts/branch-leaves-no-citations-of-removed-paths-test.py
"""
import importlib.util
import sys
from pathlib import Path

_check_spec = importlib.util.spec_from_file_location(
    "dangling_path_citation_check",
    Path(__file__).resolve().with_name("dangling-path-citation-check.py"))
dangling_path_citation_check = importlib.util.module_from_spec(_check_spec)
_check_spec.loader.exec_module(dangling_path_citation_check)

sys.exit(dangling_path_citation_check.main(
    ["--only-citations-of-removed-paths", "--base", "origin/main"]))
