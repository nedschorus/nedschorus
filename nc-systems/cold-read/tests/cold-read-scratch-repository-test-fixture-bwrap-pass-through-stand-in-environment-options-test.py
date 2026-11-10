#!/usr/bin/env python3
"""Tests for the bwrap stand-in in cold-read-scratch-repository-test-fixture.py.

The stand-in lets suites whose program starts bwrap run inside the
nc-test-sandbox. It confines nothing, but it must apply the options that
change what the command sees, so a sandbox prefix that relies on one behaves
under the stand-in as under the real bwrap. These cases pin the environment
options: --clearenv empties the environment where it stands, a later
--setenv still holds, --unsetenv drops one variable, and an option the
stand-in does not know fails the run.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_fixture_spec = importlib.util.spec_from_file_location(
    "cold_read_scratch_repository_test_fixture",
    Path(__file__).resolve().parent / "cold-read-scratch-repository-test-fixture.py")
fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(fixture)

PRINT_ENVIRONMENT = "import os, json; print(json.dumps(dict(os.environ)))"


class FakeBwrapEnvironmentOptions(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.bwrap = fixture.install_fake_sandbox_programs(Path(self.scratch.name)) / "bwrap"

    def tearDown(self):
        self.scratch.cleanup()

    def run_bwrap(self, *options):
        environment = dict(os.environ, FAKE_BWRAP_TEST_MARKER="present")
        environment.pop("FAKE_SANDBOX_PROGRAM_ARGV_LOG", None)
        return subprocess.run([str(self.bwrap), *options, sys.executable, "-c", PRINT_ENVIRONMENT],
                              env=environment, capture_output=True, text=True, timeout=60)

    def environment_seen(self, *options):
        result = self.run_bwrap(*options)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_without_clearenv_the_command_sees_the_callers_environment(self):
        self.assertEqual(self.environment_seen().get("FAKE_BWRAP_TEST_MARKER"), "present")

    def test_clearenv_empties_the_environment(self):
        seen = self.environment_seen("--clearenv")
        self.assertNotIn("FAKE_BWRAP_TEST_MARKER", seen)
        self.assertNotIn("HOME", seen)

    def test_setenv_after_clearenv_still_holds(self):
        seen = self.environment_seen("--clearenv", "--setenv", "HOME", "/sandbox-home")
        self.assertEqual(seen.get("HOME"), "/sandbox-home")
        self.assertNotIn("FAKE_BWRAP_TEST_MARKER", seen)

    def test_setenv_before_clearenv_is_cleared(self):
        seen = self.environment_seen("--setenv", "HOME", "/sandbox-home", "--clearenv")
        self.assertNotIn("HOME", seen)

    def test_unsetenv_drops_one_variable(self):
        seen = self.environment_seen("--unsetenv", "FAKE_BWRAP_TEST_MARKER")
        self.assertNotIn("FAKE_BWRAP_TEST_MARKER", seen)
        self.assertIn("PATH", seen)

    def test_an_unknown_option_fails_the_run(self):
        result = self.run_bwrap("--no-such-bwrap-option")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown to this test stand-in", result.stderr)


if __name__ == "__main__":
    unittest.main()
