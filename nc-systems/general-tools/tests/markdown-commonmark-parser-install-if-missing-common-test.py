#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/markdown-commonmark-parser-install-if-missing-common.py.

The importer and the installer are test doubles, and the install state lives in a
scratch directory, so nothing is installed. One case runs in a subprocess with stand-in
markdown-it-py and mdurl packages on its path.

Run: python3 nc-systems/general-tools/tests/markdown-commonmark-parser-install-if-missing-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

MODULE_PATH = (Path(__file__).resolve().parents[1]
               / "markdown-commonmark-parser-install-if-missing-common.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


specification = importlib.util.spec_from_file_location(
    "markdown_commonmark_parser_install_if_missing_common", str(MODULE_PATH))
parser_common = importlib.util.module_from_spec(specification)
specification.loader.exec_module(parser_common)

# A missing markdown-it-py is installed through the shared install module, in a scratch state
# directory; the importer and the installer are test doubles, so nothing is installed.
real_install_state_directory = parser_common.INSTALL_STATE_DIRECTORY
with tempfile.TemporaryDirectory() as install_scratch:
    parser_common.INSTALL_STATE_DIRECTORY = Path(install_scratch) / "install-state"
    install_state = {"installs": 0}

    class FakeMarkdownIt:
        def __init__(self, preset):
            self.preset = preset

        def enable(self, rule):
            return (self.preset, rule)

    def importer_after_install():
        if not install_state["installs"]:
            raise ImportError("No module named 'markdown_it'")
        return FakeMarkdownIt

    def counting_installer():
        install_state["installs"] += 1
        return "Successfully installed markdown-it-py-3.0.0"
    parser_built = parser_common.markdown_parser(importer_after_install, counting_installer, lambda: 1000.0)
    check("a missing markdown-it-py is installed once, then the parser is built",
          install_state["installs"] == 1 and parser_built == ("commonmark", "table"),
          (install_state, parser_built))

    def importer_never():
        raise ImportError("No module named 'markdown_it'")

    def failing_installer():
        raise parser_common.python_libraries_pinned_requirements_install_if_missing_then_import_common().PythonLibrariesPinnedRequirementsInstallOrImportFailed(
            "pip: network is unreachable")
    try:
        parser_common.markdown_parser(importer_never, failing_installer, lambda: 2000.0)
        raised = None
    except parser_common.MarkdownParserMissing as error:
        raised = error
    check("a failed install raises MarkdownParserMissing with what the install printed",
          raised is not None and "network is unreachable" in raised.install_output, raised)
    def recording_runner(command, **kwargs):
        recording_runner.kwargs = kwargs
        return subprocess.CompletedProcess(command, 0, "", "")
    parser_common.install_pinned_python_libraries(recording_runner)
    check("the install gives pip the module's install timeout",
          recording_runner.kwargs.get("timeout") == parser_common.INSTALL_TIMEOUT_SECONDS,
          recording_runner.kwargs)

    # A newer markdown-it-py whose dependency is missing fails partway through its import and
    # leaves its submodules, and the newer mdurl it loaded first, loaded; the pinned copies
    # installed next must not be mixed with them.
    newer_site = Path(install_scratch) / "newer-site"
    pinned_site = Path(install_scratch) / "pinned-site"
    for site_directory, version, init_source in (
            (newer_site, "newer", "from markdown_it.helper import version\n"
                                  "import mdurl\n"
                                  "import mdurl_missing_for_this_test\n"),
            (pinned_site, "pinned", "from markdown_it.helper import version\n"
                                    "import mdurl\n"
                                    "class MarkdownIt:\n"
                                    "    def __init__(self, preset):\n"
                                    "        self.preset = preset\n"
                                    "    def enable(self, rule):\n"
                                    "        return version + '/' + mdurl.version\n")):
        (site_directory / "markdown_it").mkdir(parents=True)
        (site_directory / "mdurl").mkdir(parents=True)
        (site_directory / "mdurl" / "__init__.py").write_text(f"version = {version!r}\n",
                                                              encoding="utf-8")
        (site_directory / "markdown_it" / "__init__.py").write_text(init_source, encoding="utf-8")
        (site_directory / "markdown_it" / "helper.py").write_text(f"version = {version!r}\n",
                                                                  encoding="utf-8")
    half_import_code = (
        "import importlib.util, sys\n"
        "from pathlib import Path\n"
        "module_path, newer, pinned, state = sys.argv[1:5]\n"
        "sys.path.insert(0, newer)\n"
        "spec = importlib.util.spec_from_file_location('parser_common', module_path)\n"
        "parser_common = importlib.util.module_from_spec(spec); spec.loader.exec_module(parser_common)\n"
        "parser_common.INSTALL_STATE_DIRECTORY = Path(state)\n"
        "def installer():\n"
        "    sys.path.remove(newer); sys.path.insert(0, pinned)\n"
        "    return 'installed'\n"
        "print(parser_common.markdown_parser(installer=installer, clock=lambda: 1000.0))\n")
    half_import = subprocess.run(
        [sys.executable, "-I", "-c", half_import_code, str(MODULE_PATH), str(newer_site),
         str(pinned_site), str(Path(install_scratch) / "half-import-state")],
        capture_output=True, text=True, timeout=60, check=False)
    check("after a newer markdown-it-py failed partway through its import, the parser is built "
          "from the installed markdown-it-py and mdurl alone",
          half_import.returncode == 0 and half_import.stdout.strip() == "pinned/pinned",
          (half_import.returncode, half_import.stdout, half_import.stderr[-400:]))
parser_common.INSTALL_STATE_DIRECTORY = real_install_state_directory

print("all cases passed" if not failures else f"{len(failures)} case(s) failed")
sys.exit(1 if failures else 0)
