#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/log-suffix-and-extension-file-classify-common.py.

The module's six suffixes and two extension lists must equal the ones
docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md names,
read from the page itself, and the classifier must sort file names by them.

Run: python3 nc-systems/general-tools/tests/log-suffix-and-extension-file-classify-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import os
import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = Path(os.environ.get(
    "LOG_SUFFIX_AND_EXTENSION_FILE_CLASSIFY_COMMON_MODULE_PATH",
    REPOSITORY_ROOT / "nc-systems" / "general-tools" / "log-suffix-and-extension-file-classify-common.py"))
PAGE_PATH = REPOSITORY_ROOT / "docs" / "nedschorus-wiki" / "nedschorus-file-naming-and-location-standards.md"
_spec = importlib.util.spec_from_file_location("log_suffix_and_extension_file_classify_common", MODULE_PATH)
classify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(classify)
kind = classify.log_suffix_and_extension_file_kind

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


def backticked_extensions(text):
    return re.findall(r"`(\.[a-z0-9]+)`", text)


# The page's lists, as the page writes them.
page = PAGE_PATH.read_text(encoding="utf-8")
section = page.split("## Filename suffixes", 1)[1].split("\n## ", 1)[0]
page_suffixes = re.findall(r"^\* `(-[a-z]+)`:", section, re.MULTILINE)
log_list = re.search(r"six suffixes above whose extension is (.*?) is a log,", section)
not_a_log_list = re.search(r"the extension of code, settings or a picture, (.*?), is not a log;", section)
check("the page's section lists six suffixes", len(page_suffixes) == 6, page_suffixes)
check("the page's sentence on log extensions is found", log_list is not None)
check("the page's sentence on extensions that are not logs is found", not_a_log_list is not None)
if log_list and not_a_log_list:
    page_log_extensions = backticked_extensions(log_list.group(1))
    page_not_a_log_extensions = backticked_extensions(not_a_log_list.group(1))
    check("the log extensions match the page, in its order",
          classify.LOG_SUFFIX_LOG_EXTENSIONS == tuple(page_log_extensions),
          (classify.LOG_SUFFIX_LOG_EXTENSIONS, page_log_extensions))
    check("the extensions that are not logs match the page, in its order",
          classify.LOG_SUFFIX_NOT_A_LOG_EXTENSIONS == tuple(page_not_a_log_extensions),
          (classify.LOG_SUFFIX_NOT_A_LOG_EXTENSIONS, page_not_a_log_extensions))
check("the suffixes match the page, in its order",
      classify.LOG_SUFFIXES == tuple(page_suffixes), (classify.LOG_SUFFIXES, page_suffixes))

# Each suffix with each listed extension.
for suffix in classify.LOG_SUFFIXES:
    for extension in classify.LOG_SUFFIX_LOG_EXTENSIONS:
        name = f"docs/x/run{suffix}{extension}"
        check(f"log: {name}", kind(name) == classify.LOG, kind(name))
    for extension in classify.LOG_SUFFIX_NOT_A_LOG_EXTENSIONS:
        name = f"scripts/run{suffix}{extension}"
        check(f"not a log: {name}", kind(name) == classify.NOT_A_LOG, kind(name))

CASES = {
    "plain-notes.md": classify.NOT_A_LOG,
    "run-log-notes.md": classify.NOT_A_LOG,
    "catalog.md": classify.NOT_A_LOG,
    "run-nbd.md": classify.NOT_A_LOG,
    "docs/issues/142-draft-md-prompt-research-report.md": classify.LOG,
    "a.b-log.json": classify.LOG,
    "run-report.csv": classify.UNLISTED,
    "run-report.MD": classify.UNLISTED,
    "run-log": classify.UNLISTED,
    "dir-log/plain.md": classify.NOT_A_LOG,
}
for name, expected in CASES.items():
    check(f"{expected}: {name}", kind(name) == expected, kind(name))
check("a pathlib path is read by its name", kind(Path("a") / "b-capture.txt") == classify.LOG)

print(f"\n{failures} failure(s)")
sys.exit(1 if failures else 0)
