#!/usr/bin/env python3
"""Tests for pull-request-mutation-testing-survivors.py.

Run: python3 scripts/pull-request-mutation-testing-survivors-test.py
Prints one line per case and exits non-zero if any case fails.

No case runs the real cosmic-ray. Each case builds a scratch repository with
a base commit and a head commit, and points --cosmic-ray-venv at a fake venv
whose cosmic-ray and cr-filter-git record every call and behave as the
case's plan file says.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    str(Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py")))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRIPT = Path(__file__).with_name("pull-request-mutation-testing-survivors.py")
CONTROL_DIRECTORY_VARIABLE = "PULL_REQUEST_MUTATION_TESTING_SURVIVORS_TEST_CONTROL_DIR"

FAKE_COSMIC_RAY_SOURCE = f'''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys

control = pathlib.Path(os.environ["{CONTROL_DIRECTORY_VARIABLE}"])
plan = json.loads((control / "plan.json").read_text())
tool = pathlib.Path(sys.argv[0]).name
arguments = sys.argv[1:]
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                      text=True).stdout.strip()
with (control / "calls.log").open("a") as log:
    log.write(json.dumps({{"tool": tool, "arguments": arguments,
                          "cwd": os.getcwd(), "head": head}}) + "\\n")
if tool == "cr-filter-git":
    sys.exit(plan.get("filter_exit", 0))
command = arguments[0]
if command == "baseline":
    (control / "config.toml").write_text(pathlib.Path(arguments[-1]).read_text())
    if "--session-file" in arguments:
        session = arguments[arguments.index("--session-file") + 1]
        pathlib.Path(session).write_text("baseline")
    sys.exit(plan.get("baseline_exit", 0))
if command == "init":
    pathlib.Path(arguments[2]).write_text("session")
    sys.exit(0)
if command == "exec":
    sys.exit(plan.get("exec_exit", 0))
if command == "dump":
    if pathlib.Path(arguments[1]).read_text() == "baseline":
        lines = plan.get("baseline_dump", [[{{"job_id": "baseline", "mutations": []}},
                                             {{"worker_outcome": "normal", "output": "",
                                              "test_outcome": "survived", "diff": None}}]])
    else:
        lines = plan.get("dump", [])
    for line in lines:
        print(json.dumps(line))
    sys.exit(0)
sys.exit(9)
'''

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(repository, *arguments):
    completed = subprocess.run(["git", "-C", str(repository), *arguments],
                               capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def scratch_repository(directory, head_files):
    """A repository with a base commit and a head commit adding head_files."""
    repository = Path(directory) / "repository"
    repository.mkdir()
    git(repository, "init", "-q", "-b", "main")
    git(repository, "config", "user.email", "test@example.invalid")
    git(repository, "config", "user.name", "mutation survivors test")
    (repository / "README").write_text("base\n")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "base")
    base = git(repository, "rev-parse", "HEAD")
    for path, text in head_files.items():
        (repository / path).parent.mkdir(parents=True, exist_ok=True)
        (repository / path).write_text(text)
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "head")
    head = git(repository, "rev-parse", "HEAD")
    return repository, base, head


def advance_base_past_merge_base(repository, merge_base):
    """Commit on a branch cut from the merge base, so the base tip is not the merge base."""
    git(repository, "branch", "advanced-base", merge_base)
    git(repository, "worktree", "add", "-q", str(repository.parent / "base-checkout"),
        "advanced-base")
    (repository.parent / "base-checkout" / "LATER").write_text("later on the base\n")
    git(repository.parent / "base-checkout", "add", "-A")
    git(repository.parent / "base-checkout", "commit", "-q", "-m", "later on the base")
    git(repository, "worktree", "remove", str(repository.parent / "base-checkout"))
    return git(repository, "rev-parse", "advanced-base")


def fake_venv(directory, plan):
    venv = Path(directory) / "venv"
    (venv / "bin").mkdir(parents=True)
    for tool in ("cosmic-ray", "cr-filter-git"):
        path = venv / "bin" / tool
        path.write_text(FAKE_COSMIC_RAY_SOURCE)
        path.chmod(0o755)
    control = Path(directory) / "control"
    control.mkdir()
    (control / "plan.json").write_text(json.dumps(plan))
    (control / "calls.log").write_text("")
    return venv, control


def calls(control):
    return [json.loads(line) for line in
            (control / "calls.log").read_text().splitlines() if line]


def run_script(repository, control, *flags, path_override=None,
               extra_environment=None):
    environment = dict(os.environ)
    environment[CONTROL_DIRECTORY_VARIABLE] = str(control)
    if path_override is not None:
        environment["PATH"] = path_override
    environment.update(extra_environment or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--checkout", str(repository),
         "--recorded-inputs-directory", str(control / "recordings"), *flags],
        capture_output=True, text=True, check=False, env=environment, timeout=120)


def worktrees_of(repository):
    return [line for line in git(repository, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")]


def work_item(path, line, operator, job_id):
    return {"job_id": job_id, "mutations": [{
        "module_path": path, "operator_name": operator, "occurrence": 0,
        "start_pos": [line, 4], "end_pos": [line, 9], "operator_args": {}}]}


def result(test_outcome, worker_outcome="normal", diff=None):
    return {"worker_outcome": worker_outcome, "output": "", "test_outcome": test_outcome,
            "diff": diff}


HEAD_FILES = {
    "scripts/thing.py": "def double(x):\n    return x + x\n",
    "scripts/thing-test.py": "import sys\nsys.exit(0)\n",
}

SURVIVOR_DIFF = ("--- mutation diff ---\n--- a/scripts/thing.py\n+++ b/scripts/thing.py\n"
                 "@@ -1,2 +1,2 @@\n-    return x + x\n+    return x * x\n")


def run_cases():
    # ------------------------------------------------------------------
    # The config written, the worktree used, and survivors parsed.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Mul", "a"),
             result("survived", diff=SURVIVOR_DIFF)],
            [work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Sub", "b"),
             result("killed")],
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "c"),
             result("incompetent")],
            [work_item("scripts/thing.py", 1, "core/AddNot", "d"),
             result(None, worker_outcome="skipped")],
            [work_item("scripts/thing.py", 1, "core/AddNot", "e"), None],
        ]})
        advanced_base = advance_base_past_merge_base(repository, base)
        completed = run_script(repository, control, "--head", head, "--base", advanced_base,
                               "--cosmic-ray-venv", str(venv),
                               "--python", "/usr/bin/python3",
                               "--mutant-timeout-seconds", "45")
        out = completed.stdout
        config = (control / "config.toml").read_text() if (control / "config.toml").exists() else ""
        recorded = calls(control)
        check("survivors found: exit 1", completed.returncode == 1,
              f"rc={completed.returncode} out={out} err={completed.stderr}")
        check("the config names the changed file as the module path",
              'module-path = "scripts/thing.py"' in config, config)
        check("the config's test command runs the sibling suite through sh -c, "
              "because cosmic-ray runs it without a shell",
              "test-command = \"sh -c '/usr/bin/python3 -u scripts/thing-test.py'\"" in config,
              config)
        check("the config sets the git filter's branch to the merge base, not the base's tip",
              f'branch = "{base}"' in config
              and "[cosmic-ray.filters.git-filter]" in config, config)
        check("the config uses the local distributor and the given timeout",
              'name = "local"' in config and "timeout = 45.0" in config, config)
        check("cosmic-ray runs baseline, its dump, init, cr-filter-git, exec and dump, in order",
              [c["tool"] if c["tool"] == "cr-filter-git" else c["arguments"][0]
               for c in recorded]
              == ["baseline", "dump", "init", "cr-filter-git", "exec", "dump"],
              json.dumps(recorded))
        check("cosmic-ray runs in a worktree at the head, not in the checkout",
              recorded and all(c["head"] == head and Path(c["cwd"]).resolve()
                               != repository.resolve() for c in recorded),
              json.dumps(recorded))
        check("the suite itself is not mutated",
              "MUTATING  scripts/thing.py" in out and "MUTATING  scripts/thing-test.py" not in out,
              out)
        check("a survivor is printed with its file, line and operator",
              "SURVIVED  scripts/thing.py:2 core/ReplaceBinaryOperator_Add_Mul" in out, out)
        check("a survivor's diff is printed under it, indented",
              "    +    return x * x" in out, out)
        check("killed and errored mutants are not printed as survivors",
              out.count("SURVIVED") == 1, out)
        check("an incompetent mutant is printed as ERRORED with its file, line and operator",
              "ERRORED   scripts/thing.py:2 core/NumberReplacer" in out, out)
        check("the summary counts killed, survived and errored, leaving out "
              "skipped and unrun mutants",
              "SUMMARY: 3 mutants on changed lines of 1 file(s): 1 killed, 1 survived, "
              "1 errored, 1 not run; 0 changed file(s) with no suite" in out, out)
        check("the worktree is removed after a run",
              len(worktrees_of(repository)) == 1
              and not Path(recorded[0]["cwd"]).exists(), worktrees_of(repository))

    # ------------------------------------------------------------------
    # Every mutant killed: exit 0.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        check("every mutant killed: exit 0", completed.returncode == 0,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")],
            [work_item("scripts/thing.py", 2, "core/AddNot", "b"), None]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        check("a mutant that was never run makes the exit 1, though none survived",
              completed.returncode == 1 and "1 not run" in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout}")

    # ------------------------------------------------------------------
    # A survivor alone makes the exit 1; errored mutants make it 1; a
    # no-test result, where cosmic-ray found nothing to mutate, does not.
    # ------------------------------------------------------------------
    for case_name, dump, wanted_exit, wanted_text in [
        ("a survivor alone makes the exit 1",
         [[work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Mul", "a"),
           result("survived", diff=SURVIVOR_DIFF)]],
         1, "1 survived"),
        ("a mutant whose worker raised is ERRORED and makes the exit 1",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           result("incompetent", worker_outcome="exception")],
          [work_item("scripts/thing.py", 2, "core/NumberReplacer", "b"),
           result("killed")]],
         1, "1 errored"),
        ("a mutant whose suites could not be launched is ERRORED and makes the exit 1",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           result("incompetent")]],
         1, "1 errored"),
        ("a worker that raised is ERRORED even with a killed test outcome",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           result("killed", worker_outcome="exception")]],
         1, "1 errored"),
        ("a worker that ended abnormally is ERRORED, not SURVIVED, with a survived test outcome",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           result("survived", worker_outcome="abnormal")]],
         1, "0 survived, 1 errored"),
        ("a worker that ended abnormally is ERRORED even with a killed test outcome",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           result("killed", worker_outcome="abnormal")]],
         1, "1 errored"),
        ("a no-test result beside a killed mutant leaves the exit 0",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")],
          [work_item("scripts/thing.py", 1, "core/AddNot", "b"),
           result(None, worker_outcome="no-test")]],
         0, "1 killed, 0 survived, 0 errored, 0 not run"),
    ]:
        with tempfile.TemporaryDirectory() as scratch_name:
            repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
            venv, control = fake_venv(scratch_name, {"dump": dump})
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv))
            check(case_name,
                  completed.returncode == wanted_exit and wanted_text in completed.stdout,
                  f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # ------------------------------------------------------------------
    # A baseline cosmic-ray passes although its suites never launched:
    # exit 2, nothing mutated.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"baseline_dump": [
            [{"job_id": "baseline", "mutations": []},
             {"worker_outcome": "normal", "output": "FileNotFoundError: sh",
              "test_outcome": "incompetent", "diff": None}]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        recorded = calls(control)
        check("a baseline whose suites could not be launched exits 2 and quotes why",
              completed.returncode == 2
              and "could not be run on the unmutated head" in completed.stderr
              and "FileNotFoundError: sh" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        check("after a baseline whose suites could not be launched no mutant is run",
              [c["arguments"][0] for c in recorded] == ["baseline", "dump"],
              json.dumps(recorded))

    # ------------------------------------------------------------------
    # A renamed-and-changed file is mutated under its new name.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository = Path(scratch_name) / "repository"
        repository.mkdir()
        git(repository, "init", "-q", "-b", "main")
        git(repository, "config", "user.email", "test@example.invalid")
        git(repository, "config", "user.name", "mutation survivors test")
        old_text = "".join(f"VALUE_{n} = {n}\n" for n in range(20))
        (repository / "scripts").mkdir()
        (repository / "scripts" / "old_name.py").write_text(old_text)
        git(repository, "add", "-A")
        git(repository, "commit", "-q", "-m", "base")
        base = git(repository, "rev-parse", "HEAD")
        git(repository, "mv", "scripts/old_name.py", "scripts/thing.py")
        (repository / "scripts" / "thing.py").write_text(
            old_text.replace("VALUE_3 = 3", "VALUE_3 = 33"))
        (repository / "scripts" / "thing-test.py").write_text("import sys\nsys.exit(0)\n")
        git(repository, "add", "-A")
        git(repository, "commit", "-q", "-m", "head")
        head = git(repository, "rev-parse", "HEAD")
        status = git(repository, "diff", "--name-status", base, head)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 4, "core/NumberReplacer", "a"), result("killed")]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        config = (control / "config.toml").read_text() if (control / "config.toml").exists() else ""
        check("a renamed-and-changed file is mutated under its new name",
              any(line.startswith("R") and line.endswith("\tscripts/thing.py")
                  for line in status.splitlines())
              and "MUTATING  scripts/thing.py" in completed.stdout
              and 'module-path = "scripts/thing.py"' in config
              and completed.returncode == 0,
              f"status={status!r} rc={completed.returncode} out={completed.stdout}")

    # ------------------------------------------------------------------
    # An inherited GIT_DIR does not point the git commands at another
    # repository.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        other = Path(scratch_name) / "other"
        other.mkdir()
        git(other, "init", "-q", "-b", "main")
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv),
                               extra_environment={"GIT_DIR": str(other / ".git")})
        check("an inherited GIT_DIR naming another repository does not redirect the run",
              completed.returncode == 0 and "MUTATING  scripts/thing.py" in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # ------------------------------------------------------------------
    # Suites chosen from the suite runner's recordings.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        files = dict(HEAD_FILES)
        files["scripts/reader-test.py"] = "import sys\nsys.exit(0)\n"
        files["scripts/failed-reader-test.py"] = "import sys\nsys.exit(0)\n"
        files["scripts/other-file-reader-test.py"] = "import sys\nsys.exit(0)\n"
        repository, base, head = scratch_repository(scratch_name, files)
        venv, control = fake_venv(scratch_name, {"dump": []})
        root = git(repository, "rev-list", "--max-parents=0", "HEAD")
        recordings = control / "recordings" / root[:16]
        recordings.mkdir(parents=True)
        (recordings / "scripts__reader-test.py.json").write_text(json.dumps(
            {"exit": 0, "reads": {"scripts/thing.py": "blob"}}))
        (recordings / "scripts__other-file-reader-test.py.json").write_text(json.dumps(
            {"exit": 0, "reads": {"scripts/elsewhere.py": "blob"}}))
        (recordings / "scripts__failed-reader-test.py.json").write_text(json.dumps(
            {"exit": 1, "reads": {"scripts/thing.py": "blob"}}))
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        config = (control / "config.toml").read_text() if (control / "config.toml").exists() else ""
        check("a suite whose passing recording reads the file is run on its mutants",
              "scripts/reader-test.py" in config and "scripts/thing-test.py" in config,
              config)
        check("a suite whose recording does not read the file is not run on its mutants",
              "other-file-reader-test.py" not in config, config)
        check("a suite whose recorded run did not pass is not chosen from that recording",
              "failed-reader-test.py" not in config, config)

    # ------------------------------------------------------------------
    # A changed file with no suite is reported, not silently skipped.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(
            scratch_name, {"scripts/lonely.py": "VALUE = 1\n"})
        venv, control = fake_venv(scratch_name, {"dump": []})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        check("a changed file with no suite is named and makes the exit 1",
              completed.returncode == 1 and "NO SUITE  scripts/lonely.py" in completed.stdout
              and "1 changed file(s) with no suite" in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout}")
        check("cosmic-ray is not run for a file with no suite", calls(control) == [],
              json.dumps(calls(control)))

    # ------------------------------------------------------------------
    # cosmic-ray missing.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        _, control = fake_venv(scratch_name, {})
        empty_venv = Path(scratch_name) / "empty-venv"
        (empty_venv / "bin").mkdir(parents=True)
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(empty_venv))
        check("cosmic-ray missing from the given venv: exit 2, saying how to install it",
              completed.returncode == 2
              and "pip install cosmic-ray" in completed.stderr
              and "--cosmic-ray-venv" in completed.stderr
              and str(empty_venv / "bin") in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        git_directory = str(Path(subprocess.run(["which", "git"], capture_output=True,
                                                text=True).stdout.strip()).parent)
        completed = run_script(repository, control, "--head", head, "--base", base,
                               path_override=git_directory)
        check("cosmic-ray missing from PATH with no venv given: exit 2, naming PATH",
              completed.returncode == 2 and "is not on PATH" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        check("no worktree is made when cosmic-ray is missing",
              len(worktrees_of(repository)) == 1, worktrees_of(repository))

    # ------------------------------------------------------------------
    # The baseline fails: exit 2, nothing mutated, worktree removed.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"baseline_exit": 1})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        recorded = calls(control)
        check("a failing baseline exits 2 and says the suites fail on the unmutated head",
              completed.returncode == 2 and "fail on the unmutated head" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        check("after a failing baseline no mutant is run",
              [c["arguments"][0] for c in recorded] == ["baseline"], json.dumps(recorded))
        check("the worktree is removed after a failing baseline",
              len(worktrees_of(repository)) == 1, worktrees_of(repository))

    # ------------------------------------------------------------------
    # A cosmic-ray step fails mid-run: exit 2 and the worktree is removed.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"exec_exit": 3})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        recorded = calls(control)
        check("a failing cosmic-ray exec exits 2 and names the step",
              completed.returncode == 2 and "cosmic-ray exec" in completed.stderr
              and "exit 3" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        check("the worktree is removed after a failed step",
              len(worktrees_of(repository)) == 1
              and recorded and not Path(recorded[0]["cwd"]).exists(),
              worktrees_of(repository))

    # ------------------------------------------------------------------
    # The head cannot be checked out: exit 2.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {})
        completed = run_script(repository, control, "--head", "0" * 40, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        check("a head that is not a commit exits 2 and says which step failed",
              completed.returncode == 2 and "git rev-parse" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        # A file where git keeps its worktree records makes `git worktree add` fail.
        worktrees_record = repository / ".git" / "worktrees"
        worktrees_record.write_text("")
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        worktrees_record.unlink()
        check("a worktree that cannot be made exits 2 and names the step",
              completed.returncode == 2 and "git worktree add" in completed.stderr
              and "SUMMARY" not in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # ------------------------------------------------------------------
    # Bad invocations.
    # ------------------------------------------------------------------
    completed = subprocess.run([sys.executable, str(SCRIPT), "--head", "abc"],
                               capture_output=True, text=True, check=False)
    check("--head without --base exits 2 and says why",
          completed.returncode == 2 and "--head needs --base" in completed.stderr,
          completed.stderr)
    completed = subprocess.run([sys.executable, str(SCRIPT), "--pull-request", "1",
                                "--base", "main"],
                               capture_output=True, text=True, check=False)
    check("--base with --pull-request exits 2 and says why",
          completed.returncode == 2 and "--base goes with --head" in completed.stderr,
          completed.stderr)


if __name__ == "__main__":
    run_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
