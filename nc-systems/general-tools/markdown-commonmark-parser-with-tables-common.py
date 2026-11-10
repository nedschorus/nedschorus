#!/usr/bin/env python3
"""A CommonMark parser with tables, built on markdown-it-py, which is installed when missing.

markdown-it-py is pinned in nc-systems/general-tools/python-libraries-pinned-requirements.txt;
when it is missing, markdown_parser installs the pinned file through the shared install
module, for the python3 the hooks run, and raises MarkdownParserMissing when that fails."""

import functools
import importlib.util
import time
from pathlib import Path

# PostToolUse hooks run under a 30-second timeout; a cached wheel installs in about a second.
INSTALL_TIMEOUT_SECONDS = 8
INSTALL_STATE_DIRECTORY = Path.home() / ".cache" / "nedschorus-markdown-commonmark-parser-install"


class MarkdownParserMissing(Exception):
    """markdown-it-py cannot be imported, and installing it failed; install_output says how."""

    def __init__(self, install_output):
        super().__init__(install_output)
        self.install_output = install_output


@functools.cache
def python_libraries_pinned_requirements_install_if_missing_then_import_common():
    """Return the shared install module, loaded by path when first needed."""
    specification = importlib.util.spec_from_file_location(
        "python_libraries_pinned_requirements_install_if_missing_then_import_common",
        Path(__file__).resolve().with_name(
            "python-libraries-pinned-requirements-install-if-missing-then-import-common.py"))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def import_markdown_it():
    """Return the MarkdownIt class, raising ImportError when markdown-it-py is missing."""
    from markdown_it import MarkdownIt
    return MarkdownIt


def markdown_parser(importer=import_markdown_it, installer=None, clock=time.time):
    """Return a CommonMark parser with tables, installing markdown-it-py when it is missing.

    markdown-it-py and mdurl are written only in Python, so once their half-imported modules
    are dropped, this process imports the installed copy and never needs a new process.

    installer defaults to the shared module's pip install of the pinned file, with this
    module's install timeout.

    Raises MarkdownParserMissing when markdown-it-py is missing and installing it failed.
    """
    try:
        markdown_it_class = importer()
    except ImportError:
        install = python_libraries_pinned_requirements_install_if_missing_then_import_common()
        if installer is None:
            installer = functools.partial(install.pinned_requirements_pip_install, INSTALL_TIMEOUT_SECONDS)
        try:
            markdown_it_class = install.python_libraries_pinned_requirements_install_if_missing_then_import(
                importer, installer, clock, lambda: False, INSTALL_STATE_DIRECTORY, ("markdown_it", "mdurl"))
        except install.PythonLibrariesPinnedRequirementsInstallOrImportFailed as error:
            raise MarkdownParserMissing(error.install_output) from error
    return markdown_it_class("commonmark").enable("table")
