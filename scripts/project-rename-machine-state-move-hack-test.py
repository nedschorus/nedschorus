#!/usr/bin/env python3
"""Cases for scripts/project-rename-machine-state-move-hack.py.

Every case builds a fake home under a temporary directory, with a real git reference-checkout and worktrees, and passes every path root to the program by flag, with the process list, crontab and systemctl replaced by fakes through the program's environment variables. --machine is always passed, since this suite runs on both machines. Nothing here reads or writes the real home, ~/.claude, a reference-checkout or the log-store."""

import contextlib
import fcntl
import io
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).resolve().with_name("project-rename-machine-state-move-hack.py")

FAKE_SYSTEMCTL = """import sys, pathlib
fakes = pathlib.Path(sys.argv[1])
arguments = sys.argv[2:]
with open(fakes / "systemctl-calls.txt", "a") as log:
    log.write(" ".join(arguments) + "\\n")
if arguments[0] == "is-active":
    active = (fakes / "active-units.txt").read_text().split()
    print("active" if arguments[1] in active else "inactive")
    sys.exit(0 if arguments[1] in active else 3)
if arguments[0] == "daemon-reload":
    sys.exit(int((fakes / "daemon-reload-exit.txt").read_text()))
"""

failures = []


def expect(name, condition, detail=""):
    print(f"{'ok  ' if condition else 'FAIL'} {name}")
    if not condition:
        failures.append(name)
        if detail:
            print("     " + detail.replace("\n", "\n     "))


def git(*arguments, cwd=None):
    result = subprocess.run(["git"] + list(arguments), cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} failed: {result.stderr}")
    return result.stdout


def derived_key(path):
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


class Fixture:
    """A fake machine: <root>/home with a checkout, worktrees, a log-store, ~/.claude, ~/.config and units."""

    def __init__(self, machine="ned-box"):
        self.machine = machine
        self.base = Path(os.path.realpath(tempfile.mkdtemp(prefix="project-rename-move-test-")))
        self.root = self.base / "tree"
        self.home = self.root / "home"
        self.fakes = self.base / "fakes"
        self.journal = self.base / "journal" / "journal.jsonl"
        for directory in (self.home, self.fakes, self.journal.parent):
            directory.mkdir(parents=True)
        self.git_home = self.base / "git-home"
        self.git_home.mkdir()
        (self.git_home / ".gitconfig").write_text(
            "[user]\n\tname = test\n\temail = test@example.invalid\n[init]\n\tdefaultBranch = main\n")
        self.projects = self.home / "Projects"
        self.checkout = self.projects / "nedschorus"
        self.claude = self.home / ".claude"
        self.config = self.home / ".config"
        self.units = self.config / "systemd" / "user"
        self.launch_agents = self.home / "Library" / "LaunchAgents"
        if machine == "mac":
            self.log_store_parent = self.root / "volume"
            self.log_store = self.log_store_parent / "nedsnodes-logs"
        else:
            self.log_store_parent = self.home
            self.log_store = self.home / "nedschorus-logs"
        (self.fakes / "processes.txt").write_text("/sbin/launchd\n/Applications/Claude.app/Contents/MacOS/Claude\nzsh\n")
        (self.fakes / "crontab.txt").write_text("# a comment naming /nowhere\n0 7 * * * /usr/bin/true\n")
        (self.fakes / "active-units.txt").write_text("")
        (self.fakes / "daemon-reload-exit.txt").write_text("0")
        (self.fakes / "systemctl.py").write_text(FAKE_SYSTEMCTL)
        self.build()

    def environment(self):
        environment = dict(os.environ)
        environment["HOME"] = str(self.git_home)
        environment["GIT_CONFIG_NOSYSTEM"] = "1"
        environment["PROJECT_RENAME_MOVE_PROCESS_LIST_COMMAND"] = f"cat {self.fakes / 'processes.txt'}"
        environment["PROJECT_RENAME_MOVE_CRONTAB_LIST_COMMAND"] = f"cat {self.fakes / 'crontab.txt'}"
        environment["PROJECT_RENAME_MOVE_SYSTEMCTL_COMMAND"] = f"{sys.executable} {self.fakes / 'systemctl.py'} {self.fakes}"
        return environment

    def build(self):
        os.environ["HOME"] = str(self.git_home)
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
        checkout = self.checkout
        checkout.mkdir(parents=True)
        git("init", "-q", cwd=checkout)
        (checkout / "scripts" / "hooks").mkdir(parents=True)
        (checkout / "scripts" / "hooks" / "pre-commit").write_text("#!/bin/sh\n")
        unit = checkout / "nn-systems" / "nn-shared-database" / "nn-shared-database-service.service"
        unit.parent.mkdir(parents=True)
        unit.write_text("[Service]\n")
        (checkout / "README.md").write_text("readme\n")
        git("add", ".", cwd=checkout)
        git("commit", "-q", "-m", "first", cwd=checkout)
        git("config", "--local", "core.hooksPath", str(checkout / "scripts" / "hooks"), cwd=checkout)
        self.worktrees = {
            "inside-checkout": checkout / ".claude" / "worktrees" / "wt1",
            "worktrees-directory": self.projects / "nedschorus-worktrees" / "wt2",
            "outside": self.home / "agents" / "seat1",
        }
        if self.machine == "ned-box":
            self.worktrees["inside-log-store"] = self.log_store / "seats" / "x" / "wt3"
        for index, (name, path) in enumerate(self.worktrees.items()):
            path.parent.mkdir(parents=True, exist_ok=True)
            git("worktree", "add", "-q", "-b", f"branch-{index}", str(path), cwd=checkout)
        self.log_store.mkdir(parents=True, exist_ok=True)
        if self.machine == "mac":
            (self.log_store_parent / "nedschorus-logs").symlink_to("nedsnodes-logs")
        projects = self.claude / "projects"
        live = [checkout] + list(self.worktrees.values())
        self.dead_worktree = checkout / ".claude" / "worktrees" / "removed-long-ago"
        for path in live + [self.dead_worktree]:
            (projects / derived_key(path)).mkdir(parents=True)
            (projects / derived_key(path) / "session.jsonl").write_text(json.dumps({"cwd": str(path)}) + "\n")
        mirror = self.log_store / "agent-session-files-by-machine" / self.machine
        for path in [checkout, self.worktrees["inside-checkout"], self.dead_worktree]:
            (mirror / "projects" / derived_key(path)).mkdir(parents=True)
            (mirror / "projects" / derived_key(path) / "session.jsonl").write_text("copy\n")
        for tasks in (self.claude / "tasks", mirror / "tasks"):
            (tasks / "nedschorus-seat1-tasks").mkdir(parents=True)
            (tasks / "nedschorus-seat1-tasks" / "1.json").write_text("{}\n")
            (tasks / "other-tasks").mkdir()
        (self.claude / ".transcript-mirror.lock").write_text("")
        store = self.log_store / "guarded-file-versions-and-approvals" / self.machine
        self.store = store
        checkout_tree = store / str(checkout).lstrip("/")
        for relative in ("docs/nedschorus-wiki/nedschorus-glossary.md", "docs/nedschorus-wiki/other-page.md",
                         "nc-systems/handoff/x.py", "nc-queue/item.md", ".claude/worktrees/wt1/nc-systems/y.py", "CLAUDE.md"):
            (checkout_tree / relative).mkdir(parents=True)
            (checkout_tree / relative / "log").write_text("entry\n")
        seat_tree = store / str(self.worktrees["outside"]).lstrip("/") / "docs" / "nedschorus-wiki" / "nedschorus-glossary.md"
        seat_tree.mkdir(parents=True)
        (seat_tree / "log").write_text("seat\n")
        if self.machine == "ned-box":
            log_store_tree = store / str(self.log_store).lstrip("/") / "seats" / "x" / "wt3" / "nc-systems" / "z.py"
            log_store_tree.mkdir(parents=True)
            (log_store_tree / "log").write_text("entry\n")
        (self.config / "nedschorus").mkdir(parents=True)
        (self.config / "nedschorus" / "token").write_text("secret\n")
        self.claude_json = self.home / ".claude.json"
        self.claude_json.write_text(json.dumps({
            "projects": {str(checkout): {"allowedTools": []}, str(self.worktrees["outside"]): {},
                         str(checkout) + "-old-backup": {}},
            "githubRepoPaths": {"nedschorus/nedschorus": [str(checkout)]},
            "note": f"see {self.log_store_parent / 'nedschorus-logs'}/seats",
            "count": 3}, indent=2) + "\n")
        self.authorized_keys = self.home / ".ssh" / "authorized_keys"
        self.authorized_keys.parent.mkdir(mode=0o700)
        self.authorized_keys.write_text(
            f'command="/usr/bin/python3 {checkout}/scripts/mac-request-from-ned-box-forced-command.py",no-pty '
            f"ssh-ed25519 AAAAkey nedlern@ned-box {checkout}/not-in-the-command\n"
            "ssh-ed25519 AAAAother someone@elsewhere\n")
        os.chmod(self.authorized_keys, 0o600)
        self.units.mkdir(parents=True)
        (self.units / "default.target.wants").mkdir()
        old_unit = checkout / "nc-systems" / "nc-shared-database" / "nc-shared-database-service.service"
        if self.machine == "ned-box":
            (self.units / "nc-shared-database-service.service").symlink_to(old_unit)
            (self.units / "default.target.wants" / "nc-shared-database-service.service").symlink_to(old_unit)
        (self.units / "unrelated.service").write_text("[Service]\nExecStart=/usr/bin/true\n")
        (self.units / "localsearch-3.service").symlink_to("/dev/null")
        self.launch_agents.mkdir(parents=True)
        (self.launch_agents / "com.example.other.plist").write_text("<plist/>\n")
        (self.launch_agents / "com.nedschorus.mount-ned-box-home-share.plist").write_text("<plist/>\n")

    def flags(self):
        return ["--machine", self.machine, "--home", str(self.home), "--log-store-parent", str(self.log_store_parent),
                "--launch-agents-dir", str(self.launch_agents), "--journal", str(self.journal)]

    def run(self, *mode):
        command = [sys.executable, str(PROGRAM)] + list(mode) + self.flags()
        result = subprocess.run(command, capture_output=True, text=True, env=self.environment())
        return result.returncode, result.stdout + result.stderr

    def snapshot(self):
        entries = {}
        for directory, subdirectories, files in os.walk(self.root):
            for name in subdirectories + files:
                path = Path(directory) / name
                relative = str(path.relative_to(self.root))
                status = os.lstat(path)
                if stat.S_ISLNK(status.st_mode):
                    entries[relative] = ("link", os.readlink(path))
                elif stat.S_ISDIR(status.st_mode):
                    entries[relative] = ("dir", stat.S_IMODE(status.st_mode))
                else:
                    entries[relative] = ("file", stat.S_IMODE(status.st_mode), hashlib.sha256(path.read_bytes()).hexdigest())
            subdirectories[:] = [name for name in subdirectories if not (Path(directory) / name).is_symlink()]
        return entries

    def git_status_works(self, path):
        return subprocess.run(["git", "-C", str(path), "status", "--porcelain"], capture_output=True,
                              env=self.environment()).returncode == 0

    def cleanup(self):
        for directory, subdirectories, _ in os.walk(self.base):
            for name in subdirectories:
                path = Path(directory) / name
                if not path.is_symlink():
                    os.chmod(path, 0o755)
        shutil.rmtree(self.base, ignore_errors=True)


def snapshot_difference(before, after):
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(key for key in set(before) & set(after) if before[key] != after[key])
    return f"added {added[:8]}\nremoved {removed[:8]}\nchanged {changed[:8]}"


def run_apply_check_rollback_on_ned_box():
    fixture = Fixture("ned-box")
    try:
        before = fixture.snapshot()
        code, output = fixture.run("--check")
        expect("ned-box: --check before --apply says it would proceed", code == 0 and "--apply would proceed" in output, output)
        expect("ned-box: --check changes nothing", fixture.snapshot() == before,
               snapshot_difference(before, fixture.snapshot()))
        code, output = fixture.run("--apply")
        expect("ned-box: --apply succeeds", code == 0 and "applied" in output, output)
        home, claude = fixture.home, fixture.claude
        new_checkout = home / "Projects" / "nedsnodes"
        new_log_store = home / "nedsnodes-logs"
        expect("step 1: the checkout is renamed and a relative symlink is left at the old path",
               new_checkout.is_dir() and os.readlink(fixture.checkout) == "nedsnodes")
        expect("step 1: the worktrees directory is renamed, with no symlink left",
               (home / "Projects" / "nedsnodes-worktrees" / "wt2").is_dir()
               and not os.path.lexists(home / "Projects" / "nedschorus-worktrees"))
        new_worktrees = [new_checkout / ".claude" / "worktrees" / "wt1", home / "Projects" / "nedsnodes-worktrees" / "wt2",
                         home / "agents" / "seat1", new_log_store / "seats" / "x" / "wt3"]
        expect("step 1: git status works in every worktree at its new path",
               all(fixture.git_status_works(path) for path in new_worktrees + [new_checkout]))
        gitdir = (home / "agents" / "seat1" / ".git").read_text()
        expect("step 1: a worktree's .git file points into the new checkout", str(new_checkout / ".git") in gitdir, gitdir)
        hooks = git("-C", str(new_checkout), "config", "--local", "--get", "core.hooksPath").strip()
        expect("step 1: core.hooksPath names the new checkout", hooks == str(new_checkout / "scripts" / "hooks"), hooks)
        expect("step 2: the log-store is renamed and a relative symlink is left",
               new_log_store.is_dir() and os.readlink(fixture.log_store) == "nedsnodes-logs")
        store = new_log_store / "guarded-file-versions-and-approvals" / "ned-box"
        new_tree = store / str(new_checkout).lstrip("/")
        expect("step 3: the guarded-file store's checkout tree is renamed, with its wiki, nc-systems and nc-queue",
               (new_tree / "docs" / "nedsnodes-wiki" / "nedsnodes-glossary.md" / "log").is_file()
               and (new_tree / "docs" / "nedsnodes-wiki" / "other-page.md" / "log").is_file()
               and (new_tree / "nn-systems" / "handoff" / "x.py" / "log").is_file()
               and (new_tree / "nn-queue" / "item.md" / "log").is_file()
               and (new_tree / ".claude" / "worktrees" / "wt1" / "nn-systems" / "y.py" / "log").is_file()
               and not (store / str(fixture.checkout).lstrip("/")).exists())
        expect("step 3: the guarded-file store's log-store tree is renamed",
               (store / str(new_log_store).lstrip("/") / "seats" / "x" / "wt3" / "nn-systems" / "z.py" / "log").is_file())
        expect("step 3: a seat checkout's store entries keep their names",
               (store / str(home / "agents" / "seat1").lstrip("/") / "docs" / "nedschorus-wiki" / "nedschorus-glossary.md").is_dir())
        projects = claude / "projects"
        renamed_keys = [derived_key(new_checkout), derived_key(new_worktrees[0]), derived_key(new_worktrees[1]),
                        derived_key(new_worktrees[3])]
        expect("step 4: each live key is renamed to the name Claude Code derives for the new path",
               all((projects / key).is_dir() for key in renamed_keys), str(sorted(os.listdir(projects))))
        expect("step 4: the key of a removed worktree and of a seat checkout stay",
               (projects / derived_key(fixture.dead_worktree)).is_dir()
               and (projects / derived_key(home / "agents" / "seat1")).is_dir())
        mirror = new_log_store / "agent-session-files-by-machine" / "ned-box"
        expect("step 4: mirror copies of live keys are renamed and a removed worktree's copy stays",
               (mirror / "projects" / derived_key(new_checkout)).is_dir()
               and (mirror / "projects" / derived_key(new_worktrees[0])).is_dir()
               and (mirror / "projects" / derived_key(fixture.dead_worktree)).is_dir())
        expect("step 5: task lists and their mirror copies are renamed; other lists stay",
               (claude / "tasks" / "nedsnodes-seat1-tasks" / "1.json").is_file()
               and (mirror / "tasks" / "nedsnodes-seat1-tasks").is_dir()
               and (claude / "tasks" / "other-tasks").is_dir())
        expect("step 6: ~/.config/nedschorus is renamed and a symlink left",
               (fixture.config / "nedsnodes" / "token").is_file() and os.readlink(fixture.config / "nedschorus") == "nedsnodes")
        rewritten = json.loads(fixture.claude_json.read_text())
        backups = list(home.glob(".claude.json.before-project-rename-*"))
        expect("step 7: ~/.claude.json's paths and repository are rewritten; a lookalike path is not",
               set(rewritten["projects"]) == {str(new_checkout), str(home / "agents" / "seat1"), str(fixture.checkout) + "-old-backup"}
               and rewritten["githubRepoPaths"] == {"nedsnodes/nedsnodes": [str(new_checkout)]}
               and rewritten["note"] == f"see {new_log_store}/seats" and rewritten["count"] == 3, json.dumps(rewritten))
        expect("step 7: the backup holds the original ~/.claude.json",
               len(backups) == 1 and backups[0].read_bytes() == before_file(fixture, before, ".claude.json", backups[0]))
        keys = fixture.authorized_keys.read_text()
        expect("step 7: authorized_keys has the new path inside command=\"...\" and nothing else on the line changes",
               keys == (f'command="/usr/bin/python3 {new_checkout}/scripts/mac-request-from-ned-box-forced-command.py",no-pty '
                        f"ssh-ed25519 AAAAkey nedlern@ned-box {fixture.checkout}/not-in-the-command\n"
                        "ssh-ed25519 AAAAother someone@elsewhere\n"), keys)
        key_backups = list(fixture.authorized_keys.parent.glob("authorized_keys.before-project-rename-*"))
        expect("step 7: authorized_keys keeps permissions 600 and its backup holds the original",
               stat.S_IMODE(os.stat(fixture.authorized_keys).st_mode) == 0o600 and len(key_backups) == 1
               and key_backups[0].read_bytes() == before_file(fixture, before, ".ssh/authorized_keys", key_backups[0]))
        new_unit_target = new_checkout / "nn-systems" / "nn-shared-database" / "nn-shared-database-service.service"
        expect("step 8: the unit links are renamed nn- and point at the nn- file in the new checkout",
               os.readlink(fixture.units / "nn-shared-database-service.service") == str(new_unit_target)
               and os.readlink(fixture.units / "default.target.wants" / "nn-shared-database-service.service") == str(new_unit_target)
               and not os.path.lexists(fixture.units / "nc-shared-database-service.service"))
        calls = (fixture.fakes / "systemctl-calls.txt").read_text()
        expect("step 8: daemon-reload ran once and no unit was started",
               calls.count("daemon-reload") == 1 and "start" not in calls, calls)
        code, output = fixture.run("--check")
        expect("--check after --apply: refuses a second --apply, and every worktree works",
               code == 0 and "a journal already exists" in output and "git lists 5; `git status` works in 5, fails in 0, and 0 have no directory" in output
               and "step 1: 0" in output and "step 4: 0" in output, output)
        code, output = fixture.run("--rollback")
        expect("--rollback succeeds", code == 0 and "rolled back" in output, output)
        after = fixture.snapshot()
        expect("--rollback restores the original tree exactly", after == before, snapshot_difference(before, after))
        expect("--rollback: git status works in every worktree at its old path",
               all(fixture.git_status_works(path) for path in list(fixture.worktrees.values()) + [fixture.checkout]))
        expect("--rollback renames the journal so it cannot run twice",
               not fixture.journal.exists() and list(fixture.journal.parent.glob("journal.jsonl.rolled-back-*")))
        code, output = fixture.run("--rollback")
        expect("--rollback after a finished --rollback says it finished and names the renamed journal, and exits 1",
               code == 1 and "nothing to roll back" in output and "--rollback already finished and renamed it to" in output
               and ".rolled-back-" in output, output)
        code, output = fixture.run("--check")
        expect("--check after a finished --rollback says the journal was rolled back, not that --apply never ran",
               "--rollback already finished and renamed it to" in output and "no --apply has run" not in output, output)
    finally:
        fixture.cleanup()


def before_file(fixture, before, relative_to_home, backup):
    """The original bytes of a file, checked against the snapshot's hash."""
    data = backup.read_bytes()
    key = str((fixture.home / relative_to_home).relative_to(fixture.root))
    return data if before[key][2] == hashlib.sha256(data).hexdigest() else b"differs"


def run_apply_and_rollback_on_mac():
    fixture = Fixture("mac")
    try:
        before = fixture.snapshot()
        code, output = fixture.run("--apply")
        expect("mac: --apply succeeds", code == 0, output)
        new_checkout = fixture.home / "Projects" / "nedsnodes"
        mirror = fixture.log_store / "agent-session-files-by-machine" / "mac"
        expect("mac: the checkout, the mac mirror copy and the mac store tree are renamed",
               new_checkout.is_dir() and (mirror / "projects" / derived_key(new_checkout)).is_dir()
               and (fixture.log_store / "guarded-file-versions-and-approvals" / "mac" / str(new_checkout).lstrip("/")
                    / "docs" / "nedsnodes-wiki").is_dir())
        expect("mac: the log-store, already renamed by ned-box, is left as it is",
               os.readlink(fixture.log_store_parent / "nedschorus-logs") == "nedsnodes-logs"
               and not (fixture.fakes / "systemctl-calls.txt").exists())
        code, output = fixture.run("--rollback")
        after = fixture.snapshot()
        expect("mac: --rollback restores the original tree exactly", code == 0 and after == before,
               output + snapshot_difference(before, after))
    finally:
        fixture.cleanup()


def refusal_case(name, arrange, expected_text, machine="ned-box"):
    fixture = Fixture(machine)
    try:
        held = arrange(fixture)
        before = fixture.snapshot()
        code, output = fixture.run("--apply")
        expect(f"refusal: {name}", code == 1 and "REFUSED, nothing changed" in output and expected_text in output, output)
        expect(f"refusal: {name}: nothing changed", fixture.snapshot() == before,
               snapshot_difference(before, fixture.snapshot()))
        if hasattr(held, "close"):
            held.close()
    finally:
        fixture.cleanup()


def hold_mirror_lock(fixture):
    handle = open(fixture.claude / ".transcript-mirror.lock", "a")
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return handle


def failing_crontab(fixture):
    environment_command = fixture.fakes / "crontab-fails.sh"
    environment_command.write_text("#!/bin/sh\necho 'crontab: permission denied' >&2\nexit 1\n")
    environment_command.chmod(0o755)
    fixture.environment = with_variable(fixture.environment, "PROJECT_RENAME_MOVE_CRONTAB_LIST_COMMAND", str(environment_command))


def failing_process_list(fixture):
    fixture.environment = with_variable(fixture.environment, "PROJECT_RENAME_MOVE_PROCESS_LIST_COMMAND", "false")


def with_variable(environment_function, name, value):
    def environment():
        environment = environment_function()
        environment[name] = value
        return environment
    return environment


def run_refusal_cases():
    refusal_case("a crontab line names the checkout",
                 lambda f: append(f.fakes / "crontab.txt", f"* * * * * python3 {f.checkout}/scripts/x.py\n"),
                 "1 crontab line(s) run from a moving path")
    refusal_case("a crontab line names the log-store",
                 lambda f: append(f.fakes / "crontab.txt", f"0 7 * * * ls {f.log_store}/seats\n"),
                 "1 crontab line(s) run from a moving path")
    refusal_case("the crontab cannot be read", failing_crontab, "the crontab could not be read: crontab: permission denied")
    refusal_case("a com.nedschorus LaunchAgent is installed",
                 lambda f: (f.launch_agents / "com.nedschorus.clean-worktrees.plist").write_text("<plist/>"),
                 "the LaunchAgent com.nedschorus.clean-worktrees of this project is installed")
    refusal_case("the mount LaunchAgent is not counted; any other com.nedschorus one is",
                 lambda f: (f.launch_agents / "com.nedschorus.mount-ned-box-home-share-x.plist").write_text("<plist/>"),
                 "the LaunchAgent com.nedschorus.mount-ned-box-home-share-x of this project", machine="mac")
    refusal_case("a com.nedsnodes LaunchAgent is installed, and its remedy is launchctl, which the installer's --remove cannot replace",
                 lambda f: (f.launch_agents / "com.nedsnodes.clean-worktrees.plist").write_text("<plist/>"),
                 "Run `launchctl bootout gui/$(id -u)/com.nedsnodes.clean-worktrees`, then delete")
    refusal_case("a systemd user unit names the checkout",
                 lambda f: (f.units / "restart-live-seats-at-login.service").write_text(f"ExecStart={f.checkout}/scripts/r.py\n"),
                 "install-restart-live-seats-at-login-systemd-unit.py --remove`")
    refusal_case("a systemd user unit links into the checkout",
                 lambda f: (f.units / "other.timer").symlink_to(f.checkout / "x.timer"),
                 "the systemd user unit other.timer names a moving path")
    refusal_case("a systemd user unit other than restart-live-seats is told to be disabled by name",
                 lambda f: (f.units / "other.timer").symlink_to(f.checkout / "x.timer"),
                 "`systemctl --user disable --now other.timer`")
    refusal_case("the transcript mirror lock is held", hold_mirror_lock, "is held: a transcript mirror run is copying")
    refusal_case("a Claude Code process runs",
                 lambda f: append(f.fakes / "processes.txt", "claude\n/Users/x/.local/bin/claude\n"),
                 "2 Claude Code process(es)")
    refusal_case("the process list cannot be read", failing_process_list, "the process list could not be read")
    refusal_case("a step-8 unit is active",
                 lambda f: (f.fakes / "active-units.txt").write_text("nc-shared-database-service.service\n"),
                 "systemd user unit nc-shared-database-service.service is active")
    refusal_case("the new checkout path already exists",
                 lambda f: (f.home / "Projects" / "nedsnodes").mkdir(), "nedsnodes already exists, and step 1 would create it")
    refusal_case("a renamed project key already exists",
                 lambda f: (f.claude / "projects" / derived_key(f.home / "Projects" / "nedsnodes")).mkdir(),
                 "already exists, and step 4 would create it")
    refusal_case("a renamed store directory already exists in the log-store",
                 lambda f: (f.store / str(f.checkout).lstrip("/") / "docs" / "nedsnodes-wiki").mkdir(),
                 "already exists, and step 3 would create it")
    refusal_case("the checkout is on a branch named after main",
                 lambda f: git("-C", str(f.checkout), "switch", "-q", "-c", "topic"), "is not on main: it is on branch topic")
    refusal_case("the checkout is on a branch named before main",
                 lambda f: git("-C", str(f.checkout), "switch", "-q", "-c", "elsewhere"), "is not on main: it is on branch elsewhere")
    refusal_case("the checkout has a detached HEAD",
                 lambda f: git("-C", str(f.checkout), "switch", "-q", "--detach"), "is not on main: its HEAD is detached (fatal")
    refusal_case("the checkout has an uncommitted change to a tracked file",
                 lambda f: (f.checkout / "README.md").write_text("changed\n"), "has uncommitted changes to tracked files")
    refusal_case("git status fails in the checkout",
                 lambda f: (f.checkout / ".git" / "index").write_bytes(b"garbage"), "index")
    refusal_case("a journal already exists",
                 lambda f: f.journal.write_text(""), "a journal already exists")
    refusal_case("~/.claude.json is not JSON",
                 lambda f: f.claude_json.write_text("{not json"), "could not be read as JSON")
    refusal_case("the reference-checkout is not a git repository",
                 lambda f: shutil.rmtree(f.checkout / ".git"), "worktree list --porcelain` failed")
    refusal_case("a LaunchAgent's remedy names its own label in the launchctl command",
                 lambda f: (f.launch_agents / "com.nedschorus.clean-worktrees.plist").write_text("<plist/>"),
                 "`launchctl bootout gui/$(id -u)/com.nedschorus.clean-worktrees`")
    refusal_case("the held mirror lock's remedy gives the installer command",
                 hold_mirror_lock, "--remove --job transcript-mirror-to-log-store`")
    refusal_case("an active step-8 unit's remedy says how to tell the nightly backup is in",
                 lambda f: (f.fakes / "active-units.txt").write_text("nc-shared-database-service.service\n"),
                 "nc-shared-database-<today's UTC date>T<time>Z.sqlite3 with no .partial ending")
    refusal_case("a journal's remedy says to move aside one no --apply ran with",
                 lambda f: f.journal.write_text(""), f"move it aside, for example to ")
    refusal_case("a failed process list with no error output gives its exit code",
                 failing_process_list, "it printed no error, exit code 1")
    refusal_case("on the Mac, the log-store is not yet renamed",
                 lambda f: (f.log_store_parent / "nedschorus-logs").unlink() or os.rename(f.log_store, f.log_store_parent / "nedschorus-logs"),
                 "the log-store is not at", machine="mac")


def append(path, text):
    with open(path, "a") as handle:
        handle.write(text)


def run_no_crontab_is_not_a_refusal():
    fixture = Fixture("ned-box")
    try:
        script = fixture.fakes / "no-crontab.sh"
        script.write_text("#!/bin/sh\necho 'no crontab for test' >&2\nexit 1\n")
        script.chmod(0o755)
        fixture.environment = with_variable(fixture.environment, "PROJECT_RENAME_MOVE_CRONTAB_LIST_COMMAND", str(script))
        code, output = fixture.run("--check")
        expect("an empty crontab ('no crontab for ...', exit 1) is not a refusal",
               code == 0 and "--apply would proceed" in output, output)
    finally:
        fixture.cleanup()


def run_mid_run_failure_cases():
    fixture = Fixture("ned-box")
    try:
        before = fixture.snapshot()
        tasks = fixture.claude / "tasks"
        tasks_mode = stat.S_IMODE(os.stat(tasks).st_mode)
        os.chmod(tasks, 0o555)
        code, output = fixture.run("--apply")
        expect("a rename failing at step 5 stops --apply with the step and the journal named",
               code == 1 and "FAILED at step 5 (rename)" in output and "--rollback" in output and fixture.journal.exists(), output)
        entries = [json.loads(line) for line in fixture.journal.read_text().splitlines()]
        expect("the journal records the failed change before it was tried", entries[-1]["step"] == 5, str(entries[-1]))
        code, output = fixture.run("--rollback")
        os.chmod(tasks, tasks_mode)
        after = fixture.snapshot()
        expect("--rollback after a step-5 failure restores the original tree exactly",
               code == 0 and after == before, output + snapshot_difference(before, after))
    finally:
        fixture.cleanup()

    fixture = Fixture("ned-box")
    try:
        before = fixture.snapshot()
        (fixture.fakes / "daemon-reload-exit.txt").write_text("1")
        code, output = fixture.run("--apply")
        expect("a failing daemon-reload stops --apply at step 8", code == 1 and "FAILED at step 8 (daemon-reload)" in output, output)
        code, output = fixture.run("--rollback")
        expect("--rollback reports a daemon-reload that still fails, keeping the journal",
               code == 1 and "FAILED during --rollback" in output and fixture.journal.exists(), output)
        (fixture.fakes / "daemon-reload-exit.txt").write_text("0")
        code, output = fixture.run("--rollback")
        after = fixture.snapshot()
        expect("a second --rollback after the fault is fixed restores the original tree exactly",
               code == 0 and after == before, output + snapshot_difference(before, after))
    finally:
        fixture.cleanup()

    fixture = Fixture("ned-box")
    try:
        (fixture.checkout / ".git" / "worktrees" / "wt2" / "HEAD").write_text("garbage\n")
        before = fixture.snapshot()
        code, output = fixture.run("--apply")
        expect("a worktree whose git status fails after the repair stops --apply",
               code == 1 and "FAILED at step 2a (worktree-repair)" in output and "nedsnodes-worktrees/wt2" in output, output)
        code, output = fixture.run("--rollback")
        after = fixture.snapshot()
        expect("--rollback after the failed repair restores the original tree exactly",
               code == 0 and after == before, output + snapshot_difference(before, after))
    finally:
        fixture.cleanup()


def run_rollback_conflict_case():
    fixture = Fixture("ned-box")
    try:
        before = fixture.snapshot()
        code, output = fixture.run("--apply")
        expect("conflict case: --apply succeeds", code == 0, output)
        old_config = fixture.config / "nedschorus"
        old_config.unlink()
        old_config.mkdir()
        code, output = fixture.run("--rollback")
        expect("--rollback stops at a symlink it did not make, keeping the journal",
               code == 1 and "is not the one --apply made" in output and fixture.journal.exists(), output)
        old_config.rmdir()
        (fixture.home / "Projects" / "nedsnodes-worktrees").rename(fixture.home / "Projects" / "nedschorus-worktrees-moved")
        code, output = fixture.run("--rollback")
        expect("--rollback stops at a rename whose paths are in neither state",
               code == 1 and "cannot reverse the rename" in output and ": neither exists." in output, output)
        (fixture.home / "Projects" / "nedschorus-worktrees-moved").rename(fixture.home / "Projects" / "nedsnodes-worktrees")
        code, output = fixture.run("--rollback")
        after = fixture.snapshot()
        expect("a later --rollback skips what was already reversed and restores the original tree exactly",
               code == 0 and after == before, output + snapshot_difference(before, after))
    finally:
        fixture.cleanup()


def run_rollback_with_no_journal_ever_case():
    fixture = Fixture("ned-box")
    try:
        code, output = fixture.run("--rollback")
        expect("--rollback with no journal and none rolled back names the journal it looked for and the command for another one",
               code == 1 and f"no journal at {fixture.journal}" in output and "--journal, --claude-dir or --home" in output
               and f"python3 {PROGRAM} --rollback --journal <that journal>" in output
               and "each of those must be given with the same value" not in output, output)
    finally:
        fixture.cleanup()


def run_check_planning_failure_case():
    fixture = Fixture("ned-box")
    try:
        shutil.rmtree(fixture.checkout / ".git")
        code, output = fixture.run("--check")
        expect("--check reports a plan it cannot make and exits 1",
               code == 1 and "Planning failed" in output and "worktree list --porcelain` failed" in output, output)
    finally:
        fixture.cleanup()


def run_rollback_git_failure_case():
    fixture = Fixture("ned-box")
    try:
        before = fixture.snapshot()
        code, output = fixture.run("--apply")
        git_dir = fixture.home / "Projects" / "nedsnodes" / ".git"
        git_dir_mode = stat.S_IMODE(os.stat(git_dir).st_mode)
        os.chmod(git_dir, 0o555)
        code, output = fixture.run("--rollback")
        os.chmod(git_dir, git_dir_mode)
        expect("--rollback reports a git config that fails, keeping the journal",
               code == 1 and "restoring core.hooksPath" in output and fixture.journal.exists(), output)
        code, output = fixture.run("--rollback")
        after = fixture.snapshot()
        expect("a second --rollback after the git failure restores the original tree exactly",
               code == 0 and after == before, output + snapshot_difference(before, after))
    finally:
        fixture.cleanup()


def run_partial_backup_case():
    fixture = Fixture("ned-box")
    ssh = fixture.authorized_keys.parent
    ssh_mode = stat.S_IMODE(os.stat(ssh).st_mode)
    try:
        original = fixture.authorized_keys.read_bytes()
        os.chmod(ssh, 0o500)
        code, output = fixture.run("--apply")
        expect("a backup that cannot be made stops --apply at step 7", code == 1 and "FAILED at step 7 (rewrite-file)" in output, output)
        entries = [json.loads(line) for line in fixture.journal.read_text().splitlines()]
        backup = Path(entries[-1]["backup"])
        os.chmod(ssh, ssh_mode)
        backup.write_bytes(original[:10])
        code, output = fixture.run("--rollback")
        expect("--rollback leaves a file whose backup was never recorded complete, naming the partial backup",
               code == 0 and fixture.authorized_keys.read_bytes() == original and backup.exists()
               and "partial backup" in output, output)
    finally:
        os.chmod(ssh, ssh_mode)
        fixture.cleanup()

    fixture = Fixture("ned-box")
    try:
        code, output = fixture.run("--apply")
        entries = [json.loads(line) for line in fixture.journal.read_text().splitlines()]
        backup = Path(next(entry["backup"] for entry in entries
                           if entry["kind"] == "rewrite-file" and entry["path"] == str(fixture.claude_json)))
        rewritten = fixture.claude_json.read_bytes()
        backup.write_text("{}\n")
        code, output = fixture.run("--rollback")
        expect("--rollback refuses a backup that no longer matches its recorded SHA-256, keeping the journal",
               code == 1 and "no longer matches" in output and fixture.claude_json.read_bytes() == rewritten
               and fixture.journal.exists(), output)
    finally:
        fixture.cleanup()

    fixture = Fixture("ned-box")
    try:
        code, output = fixture.run("--apply")
        entries = [json.loads(line) for line in fixture.journal.read_text().splitlines()]
        backup = Path(next(entry["backup"] for entry in entries
                           if entry["kind"] == "rewrite-file" and entry["path"] == str(fixture.claude_json)))
        rewritten = fixture.claude_json.read_bytes()
        backup.unlink()
        code, output = fixture.run("--rollback")
        expect("--rollback refuses a recorded-complete backup that is missing, keeping the rewritten file and the journal",
               code == 1 and "is missing" in output and fixture.claude_json.read_bytes() == rewritten
               and fixture.journal.exists(), output)
    finally:
        fixture.cleanup()

    fixture = Fixture("ned-box")
    try:
        code, output = fixture.run("--apply")
        entries = [json.loads(line) for line in fixture.journal.read_text().splitlines()]
        backup = Path(next(entry["backup"] for entry in entries
                           if entry["kind"] == "rewrite-file" and entry["path"] == str(fixture.claude_json)))
        original = backup.read_bytes()
        fixture.claude_json.write_bytes(original)
        backup.unlink()
        code, output = fixture.run("--rollback")
        expect("--rollback skips a missing backup when the file already holds the backed-up content",
               code == 0 and fixture.claude_json.read_bytes() == original, output)
    finally:
        fixture.cleanup()


def run_unreadable_store_directory_case():
    fixture = Fixture("ned-box")
    unreadable = fixture.store / str(fixture.checkout).lstrip("/") / "nc-systems"
    mode = stat.S_IMODE(os.stat(unreadable).st_mode)
    try:
        os.chmod(unreadable, 0)
        before = fixture.snapshot()
        code, output = fixture.run("--apply")
        expect("a store directory the walk cannot read refuses --apply before any change",
               code == 1 and "REFUSED, nothing changed" in output and "cannot read" in output
               and str(unreadable) in output and fixture.snapshot() == before, output)
    finally:
        os.chmod(unreadable, mode)
        fixture.cleanup()


def run_missing_worktree_directory_case():
    fixture = Fixture("ned-box")
    try:
        missing = fixture.worktrees["outside"]
        shutil.rmtree(missing)
        code, output = fixture.run("--check")
        expect("--check names a worktree git lists whose directory is missing",
               code == 0 and f"MISSING: {missing}" in output and "and 1 have no directory" in output, output)
        before = fixture.snapshot()
        code, output = fixture.run("--apply")
        expect("--apply refuses while a listed worktree's directory is missing, naming the prune command",
               code == 1 and "REFUSED, nothing changed" in output and f"git lists the worktree {missing}" in output
               and f"`git -C {fixture.checkout} worktree prune`" in output and fixture.snapshot() == before, output)
        git("-C", str(fixture.checkout), "worktree", "prune")
        code, output = fixture.run("--apply")
        expect("--apply proceeds once the missing worktree is pruned", code == 0 and "applied" in output, output)
    finally:
        fixture.cleanup()


def load_program():
    spec = importlib.util.spec_from_file_location("project_rename_machine_state_move_hack", PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_backup_that_differs_stops_apply_case():
    fixture = Fixture("ned-box")
    program = load_program()
    real_copy = shutil.copy2
    saved_environment = dict(os.environ)

    def copy_that_corrupts(source, target, **keywords):
        real_copy(source, target, **keywords)
        with open(target, "ab") as handle:
            handle.write(b" ")

    try:
        original = fixture.claude_json.read_bytes()
        os.environ.update(fixture.environment())
        program.shutil.copy2 = copy_that_corrupts
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = program.main(["--apply", "--machine", fixture.machine, "--home", str(fixture.home),
                                 "--log-store-parent", str(fixture.log_store_parent),
                                 "--launch-agents-dir", str(fixture.launch_agents), "--journal", str(fixture.journal)])
        text = output.getvalue()
        expect("a backup that differs from its file stops --apply at step 7 before the file is rewritten",
               code == 1 and "differs from" in text and "--apply stopped here" in text
               and fixture.claude_json.read_bytes() == original, text)
    finally:
        program.shutil.copy2 = real_copy
        os.environ.clear()
        os.environ.update(saved_environment)
        fixture.cleanup()


def run_dangling_unit_warning_case():
    fixture = Fixture("ned-box")
    try:
        git("-C", str(fixture.checkout), "rm", "-q", "-r", "nn-systems")
        git("-C", str(fixture.checkout), "commit", "-q", "-m", "no nn unit yet")
        code, output = fixture.run("--apply")
        expect("--apply warns when a re-made unit link points at a file that is not there",
               code == 0 and "WARNING:" in output and "nn-shared-database-service.service" in output, output)
    finally:
        fixture.cleanup()


def rollback_command(fixture):
    return f"python3 {PROGRAM} --rollback --journal {fixture.journal}"


def run_recorded_command_cases():
    fixture = Fixture("ned-box")
    try:
        tasks = fixture.claude / "tasks"
        tasks_mode = stat.S_IMODE(os.stat(tasks).st_mode)
        os.chmod(tasks, 0o555)
        code, output = fixture.run("--apply")
        os.chmod(tasks, tasks_mode)
        expect("a failed --apply prints the exact --rollback command, with the journal it wrote",
               code == 1 and f"To reverse them, run: {rollback_command(fixture)}" in output
               and "the same flags" not in output, output)
        entries = [json.loads(line) for line in fixture.journal.read_text().splitlines()]
        recorded = entries[0].get("arguments", [])
        expect("--apply records its path flags, each with its value, as the journal's first entry",
               entries[0]["kind"] == "arguments" and "--journal" in recorded
               and recorded[recorded.index("--journal") + 1] == str(fixture.journal)
               and recorded[recorded.index("--home") + 1] == str(fixture.home)
               and recorded[recorded.index("--machine") + 1] == "ned-box", str(entries[0]))
        code, output = fixture.run("--check")
        expect("--check with a journal shows the exact --rollback command and the command the --apply ran as",
               rollback_command(fixture) in output
               and f"python3 {PROGRAM} --apply " in output and f"--home {fixture.home}" in output, output)
        code, output = fixture.run("--rollback")
        expect("--rollback after the failed --apply succeeds", code == 0, output)
    finally:
        fixture.cleanup()

    fixture = Fixture("ned-box")
    try:
        code, output = fixture.run("--apply")
        expect("recorded-command conflict case: --apply succeeds", code == 0, output)
        old_config = fixture.config / "nedschorus"
        old_config.unlink()
        old_config.mkdir()
        (fixture.config / "nedsnodes" / "kept").write_text("x\n")
        code, output = fixture.run("--rollback")
        expect("--rollback that stops prints the exact command to run it again, not 'the same path flags'",
               code == 1 and f"run: {rollback_command(fixture)}" in output and "same path flags" not in output, output)
    finally:
        fixture.cleanup()

    fixture = Fixture("ned-box")
    try:
        code, output = fixture.run("--check")
        expect("--check numbers the worktree repair as step 2a, as the docstring does",
               "step 2a: " in output and "(--check counts these with step 1)" not in output, output)
        code, output = fixture.run("--apply")
        code, output = fixture.run("--rollback")
        older = fixture.journal.with_name(fixture.journal.name + ".rolled-back-20000101T000000Z")
        older.write_text("")
        code, output = fixture.run("--rollback")
        newest = sorted(fixture.journal.parent.glob(fixture.journal.name + ".rolled-back-*"))[-1]
        expect("with several rolled-back journals, 'already finished' names the newest and says it is the newest",
               code == 1 and str(newest) in output and "the newest of 2" in output, output)
    finally:
        fixture.cleanup()


def failed_apply_from(fixture, program, cwd, flags):
    """Runs --apply of the program at `program` from `cwd`, made to fail at step 5, after step 1 has moved the checkout."""
    tasks = fixture.claude / "tasks"
    tasks_mode = stat.S_IMODE(os.stat(tasks).st_mode)
    os.chmod(tasks, 0o555)
    result = subprocess.run([sys.executable, str(program), "--apply"] + flags, cwd=cwd, capture_output=True,
                            text=True, env=fixture.environment())
    os.chmod(tasks, tasks_mode)
    return result.returncode, result.stdout + result.stderr


def printed_rollback(output):
    marker = "To reverse them, run: "
    lines = [line for line in output.splitlines() if line.startswith(marker)]
    return lines[-1][len(marker):] if lines else None


def run_printed(command, cwd, fixture):
    result = subprocess.run(shlex.split(command), cwd=cwd, capture_output=True, text=True, env=fixture.environment())
    return result.returncode, result.stdout + result.stderr


def run_printed_rollback_command_cases():
    fixture = Fixture("ned-box")
    try:
        def relative(path):
            return os.path.relpath(path, fixture.base)
        flags = ["--machine", "ned-box", "--home", relative(fixture.home), "--log-store-parent",
                 relative(fixture.log_store_parent), "--launch-agents-dir", relative(fixture.launch_agents),
                 "--journal", relative(fixture.journal)]
        code, output = failed_apply_from(fixture, PROGRAM, fixture.base, flags)
        command = printed_rollback(output)
        recorded = json.loads(fixture.journal.read_text().splitlines()[0]).get("arguments", [])
        expect("relative path flags are journaled and printed as absolute paths",
               code == 1 and command is not None and f"--journal {fixture.journal}" in command
               and recorded[recorded.index("--home") + 1] == str(fixture.home), output)
        code, output = run_printed(command, "/", fixture)
        expect("the printed --rollback command, run from another directory, reverses the relative-flag --apply",
               code == 0 and not fixture.journal.exists(), output)
    finally:
        fixture.cleanup()

    fixture = Fixture("ned-box")
    try:
        started_at = fixture.checkout / "scripts" / PROGRAM.name
        started_at.parent.mkdir(exist_ok=True)
        shutil.copy2(PROGRAM, started_at)
        code, output = failed_apply_from(fixture, started_at, fixture.base, fixture.flags())
        command = printed_rollback(output)
        moved_to = fixture.projects / "nedsnodes" / "scripts" / PROGRAM.name
        expect("a program started from the checkout that step 1 moves prints its path under the renamed checkout",
               code == 1 and command is not None and shlex.split(command)[1] == str(moved_to), output)
        code, output = run_printed(command, fixture.base, fixture)
        expect("that printed --rollback command runs and reverses the --apply",
               code == 0 and started_at.exists() and not fixture.journal.exists(), output)
    finally:
        fixture.cleanup()

    fixture = Fixture("ned-box")
    try:
        spaced = fixture.base / "dir with space" / PROGRAM.name
        spaced.parent.mkdir()
        shutil.copy2(PROGRAM, spaced)
        code, output = failed_apply_from(fixture, spaced, fixture.base, fixture.flags())
        command = printed_rollback(output)
        expect("a program path with a space is quoted in the printed --rollback command",
               code == 1 and command is not None and shlex.split(command)[1] == str(spaced), output)
        code, output = run_printed(command, fixture.base, fixture)
        expect("the quoted command runs and reverses the --apply", code == 0 and not fixture.journal.exists(), output)
    finally:
        fixture.cleanup()


def run_journal_under_moved_root_and_journaled_rollback_flags_cases():
    fixture = Fixture("ned-box")
    try:
        flags = fixture.flags()
        flags[flags.index("--journal") + 1] = "move.jsonl"
        result = subprocess.run([sys.executable, str(PROGRAM), "--check"] + flags, cwd=fixture.log_store,
                                capture_output=True, text=True, env=fixture.environment())
        expect("--check reports the journal under a moved root",
               "--apply would REFUSE" in result.stdout and "which --apply moves" in result.stdout, result.stdout)
        before = fixture.snapshot()
        result = subprocess.run([sys.executable, str(PROGRAM), "--apply"] + flags, cwd=fixture.log_store,
                                capture_output=True, text=True, env=fixture.environment())
        output = result.stdout + result.stderr
        expect("--apply refuses a relative --journal that resolves under the log-store it moves",
               result.returncode == 1 and "REFUSED, nothing changed" in output
               and f"is under {fixture.log_store}, which --apply moves" in output, output)
        expect("that refusal changes nothing", fixture.snapshot() == before,
               snapshot_difference(before, fixture.snapshot()))
    finally:
        fixture.cleanup()

    fixture = Fixture("ned-box")
    try:
        started_at = fixture.checkout / "scripts" / PROGRAM.name
        shutil.copy2(PROGRAM, started_at)
        result = subprocess.run([sys.executable, str(started_at), "--apply"] + fixture.flags(), cwd=fixture.base,
                                capture_output=True, text=True, env=fixture.environment())
        expect("journaled-flags case: --apply with non-default --home succeeds", result.returncode == 0,
               result.stdout + result.stderr)
        moved_to = fixture.projects / "nedsnodes" / "scripts" / PROGRAM.name
        before = fixture.snapshot()
        other_home = fixture.base / "other-home"
        code, output = run_printed(f"python3 {moved_to} --rollback --journal {fixture.journal} --home {other_home}",
                                   fixture.base, fixture)
        expect("--rollback refuses a path flag that differs from the one --apply journaled, naming both",
               code == 1 and "REFUSED, nothing changed" in output
               and f"--home: given {other_home}, recorded {fixture.home}" in output
               and f"run: python3 {moved_to} --rollback --journal {fixture.journal}" in output, output)
        expect("that refusal changes nothing", fixture.snapshot() == before and fixture.journal.exists(),
               snapshot_difference(before, fixture.snapshot()))
        (fixture.fakes / "daemon-reload-exit.txt").write_text("1")
        code, output = run_printed(f"python3 {moved_to} --rollback --journal {fixture.journal}", fixture.base, fixture)
        marker = "Once the cause is fixed, run: "
        lines = [line[len(marker):] for line in output.splitlines() if line.startswith(marker)]
        printed = shlex.split(lines[-1])[1] if lines else None
        expect("a --rollback given only --journal, started under the new checkout and failing after it moved the "
               "checkout back, prints the program's path under the old checkout, from the journaled --home",
               code == 1 and printed == str(started_at) and started_at.exists(), output)
        (fixture.fakes / "daemon-reload-exit.txt").write_text("0")
        code, output = run_printed(lines[-1] if lines else "false", fixture.base, fixture)
        expect("that printed command finishes the --rollback", code == 0 and not fixture.journal.exists(), output)
    finally:
        fixture.cleanup()


if __name__ == "__main__":
    run_apply_check_rollback_on_ned_box()
    run_apply_and_rollback_on_mac()
    run_refusal_cases()
    run_no_crontab_is_not_a_refusal()
    run_mid_run_failure_cases()
    run_rollback_conflict_case()
    run_dangling_unit_warning_case()
    run_check_planning_failure_case()
    run_rollback_with_no_journal_ever_case()
    run_rollback_git_failure_case()
    run_partial_backup_case()
    run_unreadable_store_directory_case()
    run_missing_worktree_directory_case()
    run_backup_that_differs_stops_apply_case()
    run_recorded_command_cases()
    run_printed_rollback_command_cases()
    run_journal_under_moved_root_and_journaled_rollback_flags_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
