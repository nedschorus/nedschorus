#!/usr/bin/env python3
"""Test the Gemini launcher with fake agy and sandbox commands, without model calls.

Checks CLI forwarding, sandbox mount order and profiles, model discovery,
closed stdin, logging, every failure handler and process-group deadlines.
Sandbox argument tests do not claim that a host supports sandbox execution.
Run directly with Python; unittest exits nonzero on a failed assertion.
"""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROGRAM = Path(__file__).with_name("run-gemini-task-from-brief.py")
spec = importlib.util.spec_from_file_location("gemini_task", PROGRAM)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

FAKE_AGY = r'''#!PYTHON
import json, os, pathlib, signal, sys, time
args = sys.argv[1:]
mode = os.environ.get("FAKE_AGY_MODE", "report")
with open(os.environ["FAKE_CALLS"], "a") as f:
    f.write(json.dumps([os.getcwd(), args, sys.stdin.read()]) + "\n")
print("agy stderr", file=sys.stderr, flush=True)
if mode == "needs-key" and not os.environ.get("GEMINI_API_KEY"):
    print("GEMINI_API_KEY environment variable is not set", flush=True)
    sys.exit(3)
if args == ["models"]:
    if mode == "models-fail":
        sys.exit(4)
    if mode != "models-sleep":
        print("Available models:\n  gemini-4-argon-high\n  gemini-3.8-flash-medium", flush=True)
        sys.exit(0)
if mode in ("sleep", "models-sleep"):
    child = os.fork()
    if child == 0:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        pathlib.Path(os.environ["FAKE_CHILD"]).write_text(str(os.getpid()))
        time.sleep(120)
        os._exit(0)
    time.sleep(120)
print("agy stdout", flush=True)
report = pathlib.Path(os.environ["FAKE_REPORT"])
if mode == "fail":
    report.write_text("partial output")
    sys.exit(7)
if mode == "remove-report":
    report.unlink()
elif mode != "no-report":
    report.write_text("one\ntwo\nthree\n")
'''

FAKE_SANDBOX = r'''#!PYTHON
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_SANDBOX_CALLS"], "a") as f:
    f.write(json.dumps(args) + "\n")
pos = args.index("agy")
os.execvp("agy", args[pos:])
'''


class GeminiTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gemini-task-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.checkout = self.base / "checkout"
        self.checkout.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        for name, content in (("agy", FAKE_AGY), ("bwrap", FAKE_SANDBOX),
                              ("sandbox-exec", FAKE_SANDBOX)):
            script = self.bin / name
            script.write_text(content.replace("#!PYTHON", "#!" + sys.executable))
            script.chmod(0o755)
        self.brief = self.base / "brief.md"
        self.brief.write_text("---\nRead README.md.\nWrite three lines.\n")
        self.report = self.checkout / "report.md"
        self.log = self.base / "output.log"
        self.calls = self.base / "calls"
        self.sandbox_calls = self.base / "sandbox-calls"
        self.child = self.base / "child"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        HOME=str(self.home), FAKE_CALLS=str(self.calls),
                        FAKE_REPORT=str(self.report), FAKE_CHILD=str(self.child),
                        FAKE_SANDBOX_CALLS=str(self.sandbox_calls))
        self.args = ["-C", str(self.checkout), "--brief", str(self.brief), "-o", str(self.report),
                     "--run-log", str(self.log)]

    def run_cli(self, mode="report", extra=(), **kwargs):
        return subprocess.run([sys.executable, str(PROGRAM), *self.args, *extra],
                              env=dict(self.env, FAKE_AGY_MODE=mode),
                              capture_output=True, text=True, timeout=25, **kwargs)

    def test_cli(self):
        first, second = self.base / "first folder", self.base / "second"
        first.mkdir()
        second.mkdir()
        result = self.run_cli(extra=("--sandbox", "workspace-write", "--writable-root", str(first),
                                    "--writable-root", str(second), "--network", "--effort", "medium",
                                    "-m", "gemini-3.8-flash-medium", "--deadline-minutes", "10"),
                              input="caller stdin must not reach agy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"report: {self.report}\n")
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(calls[0], [str(self.checkout), ["models"], ""])
        cwd, args, stdin = calls[1]
        self.assertEqual((cwd, stdin), (str(self.checkout), ""))
        self.assertTrue(args[-1].startswith(self.brief.read_text()))
        self.assertIn(str(self.report), args[-1])
        for flag, value in (("--model", "gemini-3.8-flash-medium"), ("--effort", "medium"),
                            ("--print-timeout", "600s"), ("--output-format", "text")):
            self.assertEqual(args[args.index(flag) + 1], value)
        self.assertIn("--dangerously-skip-permissions", args)
        self.assertEqual([args[i+1] for i, arg in enumerate(args) if arg == "--add-dir"],
                         list(map(str, (self.checkout, first, second))))
        self.assertIn("agy stdout", self.log.read_text())
        self.assertEqual(self.log.read_text().count("agy stderr"), 2)
        prefixes = [json.loads(line) for line in self.sandbox_calls.read_text().splitlines()]
        self.assertEqual(prefixes[0][:prefixes[0].index("agy")], prefixes[1][:prefixes[1].index("agy")])

    def test_defaults(self):
        self.args = self.args[:-2]
        with patch.dict(os.environ, self.env), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runner.main(self.args), 0)
        args = json.loads(self.calls.read_text().splitlines()[1])[1]
        self.assertEqual(args[args.index("--model") + 1], "gemini-4-argon-high")
        self.assertNotIn("--effort", args)
        self.assertTrue(self.report.with_name(self.report.name + ".run.log").is_file())

    def test_sandbox_mode_decides_whether_checkout_is_writable(self):
        outside_report = self.base / "log-store" / "report.md"
        self.args[self.args.index("-o") + 1] = str(outside_report)
        self.env["FAKE_REPORT"] = str(outside_report)
        for mode, writable in (("read-only", [outside_report]),
                               ("workspace-write", [outside_report, self.checkout])):
            with self.subTest(mode=mode):
                self.sandbox_calls.unlink(missing_ok=True)
                result = self.run_cli(extra=("--sandbox", mode))
                self.assertEqual(result.returncode, 0, result.stderr)
                prefix = json.loads(self.sandbox_calls.read_text().splitlines()[-1])
                if sys.platform == "darwin":
                    checkout_rule = f'(require-not (subpath {json.dumps(str(self.checkout))}))'
                    self.assertEqual(checkout_rule in prefix[1], mode == "workspace-write")
                else:
                    self.assertEqual([prefix[i + 1] for i, arg in enumerate(prefix) if arg == "--bind"],
                                     list(map(str, writable)))

    def test_key_file_supplies_gemini_api_key_or_names_its_problem(self):
        self.env.pop("GEMINI_API_KEY", None)
        self.env["FAKE_AGY_MODE"] = "needs-key"
        key_file = self.base / "gemini-api.key"
        key_file.write_text("test-key\n")
        with patch.dict(os.environ, self.env, clear=True), \
                patch.object(runner.agy_cell, "GEMINI_API_KEY_FILE", key_file), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runner.main(self.args), 0)
        key_file.unlink()
        with patch.dict(os.environ, self.env, clear=True), \
                patch.object(runner.agy_cell, "GEMINI_API_KEY_FILE", key_file), \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(runner.main(self.args), 1)
        self.assertIn("agy exited 3", stderr.getvalue())
        self.assertIn(f"{key_file} gave no key", stderr.getvalue())
        self.assertIn(f"set GEMINI_API_KEY, or put the key in {key_file}", stderr.getvalue())

    def test_unknown_model_stops_before_task(self):
        result = self.run_cli(extra=("-m", "gemini-4-argon"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown model", result.stderr)
        self.assertIn("gemini-4-argon-high", result.stderr)
        self.assertIn("gemini-3.8-flash-medium", result.stderr)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)

    def test_nonzero_exits(self):
        for mode, stage, code in (("models-fail", "listing models", 4), ("fail", "running the task", 7)):
            with self.subTest(mode=mode):
                result = self.run_cli(mode)
                self.assertEqual(result.returncode, 1)
                self.assertIn(stage, result.stderr)
                self.assertIn(f"agy exited {code}", result.stderr)
                self.assertNotIn("report:", result.stdout)

    def test_no_report_and_empty_report_do_not_accept_stale_content(self):
        for mode in ("no-report", "remove-report"):
            with self.subTest(mode=mode):
                self.report.write_text("stale report")
                result = self.run_cli(mode)
                self.assertEqual(result.returncode, 1)
                self.assertIn("wrote no report", result.stderr)
                self.assertIn(str(self.log), result.stderr)
                self.assertNotIn("report:", result.stdout)

    def test_deadline_kills_children_during_discovery_and_task(self):
        for mode in ("models-sleep", "sleep"):
            with self.subTest(mode=mode):
                result = self.run_cli(mode, extra=("--deadline-minutes", "0.03"))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("deadline passed", result.stderr)
                pid = int(self.child.read_text())
                # Linux can retain a dead orphan as a zombie until PID 1 reaps it.
                state = Path(f"/proc/{pid}/stat")
                if sys.platform.startswith("linux") and state.exists():
                    self.assertEqual(state.read_text().split(") ")[-1][0], "Z")
                else:
                    with self.assertRaises(ProcessLookupError):
                        os.kill(pid, 0)

    def test_bad_arguments(self):
        for extra in (("--deadline-minutes", "nan"), ("--deadline-minutes", "0"),
                      ("--sandbox", "invalid"), ("--writable-root", str(self.base)),
                      ("-C", str(self.base / "absent")),
                      ("--run-log", str(self.brief)), ("-o", str(self.brief)),
                      ("--sandbox", "workspace-write", "--writable-root", str(self.base / "absent"))):
            with self.subTest(extra=extra):
                self.assertEqual(self.run_cli(extra=extra).returncode, 2)
        result = subprocess.run([sys.executable, str(PROGRAM), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--network", result.stdout)

    def test_file_failures(self):
        self.brief.unlink()
        self.assertIn("reading the brief", self.run_cli().stderr)
        self.brief.write_bytes(b'\xff')
        self.assertEqual(self.run_cli().returncode, 1)
        self.brief.write_text("   ")
        self.assertIn("brief is empty", self.run_cli().stderr)
        self.brief.write_text("task")
        self.log.mkdir()
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("preparing report", result.stderr)

    def test_missing_sandbox(self):
        for program in (None, "no-such-sandbox"):
            with patch.object(runner.agy_cell, "credential_sandbox_program", return_value=program), \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(runner.main(self.args), 1)
                self.assertIn("required sandbox", stderr.getvalue())

    def test_start_failure(self):
        with patch.object(runner.agy_cell, "credential_sandbox_prefix", return_value=["/no/such/bwrap"]), \
                patch.object(runner.shutil, "which", return_value="bwrap"), \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(runner.main(self.args), 1)
            self.assertIn("listing models", stderr.getvalue())

    def test_sandbox_arguments_and_credential_denial_order(self):
        common = runner.agy_cell.common
        with patch.object(common, "credential_directories_present", return_value=["/credentials"]), \
                patch.object(common, "credential_files_found_now", return_value=["/data/.env"]), \
                patch.object(common, "reviewer_program_login_files", return_value=["/codex/auth.json"]) as login:
            prefix = runner.agy_cell.credential_sandbox_prefix("linux", writable_paths=[
                (self.report, False), (self.base, True)], network=False)
            self.assertEqual(prefix, ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--bind", str(self.report),
                                     str(self.report), "--bind", str(self.base), str(self.base),
                                     "--unshare-net", "--tmpfs", "/credentials", "--ro-bind", "/dev/null",
                                     "/data/.env", "--ro-bind", "/dev/null", "/codex/auth.json"])
            login.assert_called_with(except_program="agy", only_present=True)
            legacy = runner.agy_cell.credential_sandbox_prefix("linux")
            self.assertEqual(legacy[:4], ["bwrap", "--dev-bind", "/", "/"])
            self.assertNotIn("--unshare-net", legacy)
        prefix = runner.agy_cell.credential_sandbox_prefix("darwin", writable_paths=[
            (Path('/report"file'), False), (Path("/data"), True)], network=False)
        self.assertEqual(prefix[:2], ["sandbox-exec", "-p"])
        self.assertIn('(require-not (literal "/report\\"file"))', prefix[2])
        self.assertIn('(require-not (subpath "/data"))', prefix[2])
        self.assertIn('(deny network*)', prefix[2])
        self.assertIn('(deny file-read* file-write*', prefix[2])
        self.assertEqual(runner.agy_cell.credential_sandbox_prefix("darwin"),
                         ["sandbox-exec", "-p", runner.agy_cell.sandbox_exec_profile()])


if __name__ == "__main__":
    unittest.main(verbosity=2)
