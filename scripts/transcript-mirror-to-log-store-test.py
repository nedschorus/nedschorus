#!/usr/bin/env python3
"""Tests for scripts/transcript-mirror-to-log-store.py: the layout, the two
sources, never --delete, the live-tree exits, the lock, the remote
invocation, and --failures-only, the quiet mode cron runs it in. LOCAL mode runs the real rsync into a scratch store; REMOTE mode
records what stub ssh and rsync were asked. Nothing here touches ned-box or
the real ~/.claude: the source home is overridden too.

Run: python3 scripts/transcript-mirror-to-log-store-test.py   (exit 0 = all passed)
"""

import fcntl
import json
import os
import pathlib
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
MIRROR = SCRIPTS_DIR / "transcript-mirror-to-log-store.py"
DESTINATION_VARIABLE = "TRANSCRIPT_MIRROR_DESTINATION"
SOURCE_HOME_VARIABLE = "TRANSCRIPT_MIRROR_SOURCE_HOME"
RULED_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts"
RSYNC_SSH_TRANSPORT = ("ssh -o BatchMode=yes -o ConnectTimeout=10"
                       " -o ServerAliveInterval=15 -o ServerAliveCountMax=4")
SERVER_ALIVE_OPTIONS = ("ServerAliveInterval=15", "ServerAliveCountMax=4")

STUB_RECORDER = """#!/usr/bin/env python3
import json, os, sys
if sys.argv[0].endswith("rsync") and "--version" in sys.argv:
    print(os.environ.get("MIRROR_TEST_RSYNC_VERSION_LINE", "rsync  version 3.4.1  protocol version 32"))
    sys.exit(0)
with open(os.environ["MIRROR_TEST_ARGV_LOG"], "a") as log:
    log.write(json.dumps(sys.argv) + "\\n")
if sys.argv[0].endswith("ssh") and "wc -l" in " ".join(sys.argv):
    print(os.environ.get("MIRROR_TEST_STORE_COUNT", "0"))
if sys.argv[0].endswith("rsync") and os.environ.get("MIRROR_TEST_RSYNC_STDERR"):
    sys.stderr.write(os.environ["MIRROR_TEST_RSYNC_STDERR"] + "\\n")
if sys.argv[0].endswith("ssh") and "mkdir -p" in " ".join(sys.argv) and os.environ.get("MIRROR_TEST_SSH_MKDIR_EXIT"):
    sys.stderr.write(os.environ.get("MIRROR_TEST_SSH_STDERR", "") + "\\n")
    sys.exit(int(os.environ["MIRROR_TEST_SSH_MKDIR_EXIT"]))
sys.exit(int(os.environ.get("MIRROR_TEST_RSYNC_EXIT", "0")) if sys.argv[0].endswith("rsync") else 0)
"""

failures = []


def check(case_name, condition, detail=""):
    print(f"{'ok' if condition else 'FAIL'}: {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


def make_home(root: pathlib.Path) -> pathlib.Path:
    home = root / "home"
    projects = home / ".claude" / "projects" / "-Users-el-agents-MD-skills"
    projects.mkdir(parents=True)
    (projects / "aaaa.jsonl").write_text('{"turn": 1}\n')
    (projects / "memory").mkdir()
    (projects / "memory" / "MEMORY.md").write_text("- a memory\n")
    handoffs = home / ".claude" / "handoffs"
    handoffs.mkdir()
    (handoffs / "MD-skills-dialog-0001.md").write_text("# dialog\n")
    return home


def run_mirror(home, destination, extra_env=None, args=()):
    env = dict(os.environ)
    env[SOURCE_HOME_VARIABLE] = str(home)
    env[DESTINATION_VARIABLE] = destination
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(MIRROR), *args], capture_output=True,
                          text=True, check=False, env=env)


QUIET = ("--failures-only",)


with tempfile.TemporaryDirectory(prefix="transcript-mirror-test-") as scratch_name:
    scratch = pathlib.Path(scratch_name).resolve()
    home = make_home(scratch)
    store = scratch / "store" / "transcripts"
    machine = "ned-box" if os.uname().nodename.split(".")[0] == "ned-box" else "mac"

    # --- Local mode, real rsync ---------------------------------------------
    result = run_mirror(home, str(store))
    lines = result.stdout.splitlines()
    check("one pass exits 0 with one line per source, both opening mirrored:",
          result.returncode == 0 and len(lines) == 2
          and all(line.startswith("mirrored: ") for line in lines),
          result.stdout + result.stderr)
    check("transcripts land under transcripts/<machine>/projects/ in Claude Code's own layout",
          (store / machine / "projects" / "-Users-el-agents-MD-skills" / "aaaa.jsonl").is_file())
    check("the memory store rides along inside projects/",
          (store / machine / "projects" / "-Users-el-agents-MD-skills" / "memory" / "MEMORY.md").is_file())
    check("handoffs land under transcripts/<machine>/handoffs/",
          (store / machine / "handoffs" / "MD-skills-dialog-0001.md").is_file())
    check("each line carries the local and store counts",
          "local 2 files, store 2 files" in lines[0] and "local 1 files, store 1 files" in lines[1],
          result.stdout)

    # A transcript grows and a session's scratch directory disappears: the
    # grown file is re-sent, the vanished one stays in the store.
    (home / ".claude" / "projects" / "-Users-el-agents-MD-skills" / "aaaa.jsonl").write_text(
        '{"turn": 1}\n{"turn": 2}\n')
    scratch_project = home / ".claude" / "projects" / "-private-tmp-scratch"
    scratch_project.mkdir()
    (scratch_project / "bbbb.jsonl").write_text('{"turn": 1}\n')
    run_mirror(home, str(store))
    (scratch_project / "bbbb.jsonl").unlink()
    scratch_project.rmdir()
    result = run_mirror(home, str(store))
    check("a grown transcript is re-sent whole",
          (store / machine / "projects" / "-Users-el-agents-MD-skills" / "aaaa.jsonl").read_text()
          == '{"turn": 1}\n{"turn": 2}\n')
    check("a transcript deleted locally stays in the store: never --delete",
          (store / machine / "projects" / "-private-tmp-scratch" / "bbbb.jsonl").is_file())
    check("the counts then differ and both are printed, neither asserted",
          result.returncode == 0 and "local 2 files, store 3 files" in result.stdout, result.stdout)

    # A source that does not exist is noted, not failed.
    bare_home = scratch / "bare-home"
    (bare_home / ".claude").mkdir(parents=True)
    result = run_mirror(bare_home, str(scratch / "store-bare"))
    check("a missing source directory is noted and the run still exits 0",
          result.returncode == 0 and result.stdout.count("nothing to mirror") == 2, result.stdout)

    # The lock: a second run while one holds it exits 3 and does nothing.
    lock_path = home / ".claude" / ".transcript-mirror.lock"
    with lock_path.open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        result = run_mirror(home, str(store))
    check("a run that finds the lock held exits 3 and says so",
          result.returncode == 3 and "another run holds" in result.stdout, result.stdout)

    # --failures-only: what cron runs every minute. A pass that mirrored
    # prints nothing; the lock held by a slower run is expected and silent.
    (home / ".claude" / "handoffs" / "MD-skills-dialog-0002.md").write_text("# dialog 2\n")
    result = run_mirror(home, str(store), args=QUIET)
    check("--failures-only: a pass that mirrored exits 0 and prints nothing on stdout or stderr",
          result.returncode == 0 and result.stdout == "" and result.stderr == "",
          repr(result.stdout + result.stderr))
    check("--failures-only still mirrors: the new handoff reached the store",
          (store / machine / "handoffs" / "MD-skills-dialog-0002.md").is_file())
    # A quiet pass writes nothing to the log, so the lock file's mtime,
    # rewritten as every run starts, is the record of when the mirror last ran.
    os.utime(lock_path, (1_000_000_000, 1_000_000_000))
    result = run_mirror(home, str(store), args=QUIET)
    check("--failures-only: a quiet pass still rewrites the lock file, whose mtime says when the mirror last ran",
          result.returncode == 0 and result.stdout == ""
          and lock_path.stat().st_mtime > 1_000_000_000 + 86_400,
          f"exit {result.returncode}, lock mtime {lock_path.stat().st_mtime}")
    result = run_mirror(bare_home, str(scratch / "store-bare"), args=QUIET)
    check("--failures-only: a missing source directory is not a failure and prints nothing, exit 0",
          result.returncode == 0 and result.stdout == "", result.stdout)
    with lock_path.open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        result = run_mirror(home, str(store), args=QUIET)
    check("--failures-only: a run that finds the lock held exits 3 and prints nothing",
          result.returncode == 3 and result.stdout == "" and result.stderr == "",
          repr(result.stdout + result.stderr))

    # --- Remote mode, stub ssh and rsync ------------------------------------
    stubs = scratch / "stub-bin"
    stubs.mkdir()
    for name in ("ssh", "rsync"):
        stub = stubs / name
        stub.write_text(STUB_RECORDER)
        stub.chmod(0o755)
    argv_log = scratch / "argv.jsonl"
    remote_env = {"PATH": f"{stubs}{os.pathsep}{os.environ.get('PATH', '')}",
                  "MIRROR_TEST_ARGV_LOG": str(argv_log), "MIRROR_TEST_STORE_COUNT": "3"}
    result = run_mirror(home, RULED_DESTINATION, remote_env)
    calls = [json.loads(line) for line in argv_log.read_text().splitlines()]
    rsync_calls = [c for c in calls if c[0].endswith("rsync")]
    ssh_calls = [c for c in calls if c[0].endswith("ssh")]
    check("remote mode exits 0 and reports both sources",
          result.returncode == 0 and result.stdout.count("mirrored:") == 2, result.stdout + result.stderr)
    check("two rsync calls, -a, over batch-mode ssh, into transcripts/<machine>/<source>/ on ned-box",
          len(rsync_calls) == 2 and all(
              "-a" in c and RSYNC_SSH_TRANSPORT in c
              and c[-1] == f"{RULED_DESTINATION}/{machine}/{name}/"
              and c[-2] == f"{home / '.claude' / name}/"
              for c, name in zip(rsync_calls, ("projects", "handoffs"))),
          str(rsync_calls))
    check("rsync is never asked to delete or to write in place",
          not any(flag in c for c in rsync_calls for flag in ("--delete", "--inplace")))
    check("every ssh call runs in batch mode with a connect timeout",
          ssh_calls and all("BatchMode=yes" in c for c in ssh_calls), str(ssh_calls))
    check("every ssh call, and rsync's ssh transport, gives up on a far end that stops answering",
          ssh_calls and all(option in c for c in ssh_calls for option in SERVER_ALIVE_OPTIONS)
          and all(option in c[c.index("-e") + 1] for c in rsync_calls for option in SERVER_ALIVE_OPTIONS),
          str(calls))

    # Files vanishing mid-run is exit 24 from GNU rsync (ned-box) and exit 23
    # from openrsync (the Mac's /usr/bin/rsync); each is a note on its own
    # implementation only, and the other implementation's code stays FAILED.
    GNU_VERSION_LINE = "rsync  version 3.4.1  protocol version 32"
    OPENRSYNC_VERSION_LINE = "openrsync: protocol version 29"
    argv_log.unlink()
    result = run_mirror(home, RULED_DESTINATION, dict(
        remote_env, MIRROR_TEST_RSYNC_VERSION_LINE=GNU_VERSION_LINE, MIRROR_TEST_RSYNC_EXIT="24"))
    check("GNU rsync exit 24, files vanished mid-run, is a mirrored line with a note, exit 0",
          result.returncode == 0 and result.stdout.count("vanished mid-run") == 2, result.stdout)
    argv_log.unlink()
    result = run_mirror(home, RULED_DESTINATION, dict(
        remote_env, MIRROR_TEST_RSYNC_VERSION_LINE=GNU_VERSION_LINE, MIRROR_TEST_RSYNC_EXIT="23"))
    check("GNU rsync exit 23, a partial transfer, is FAILED naming the exit, exit 1",
          result.returncode == 1 and result.stdout.count("FAILED:") == 2
          and "rsync exit 23" in result.stdout and "ned-box unreachable" not in result.stdout,
          result.stdout)
    argv_log.unlink()
    result = run_mirror(home, RULED_DESTINATION, dict(
        remote_env, MIRROR_TEST_RSYNC_VERSION_LINE=OPENRSYNC_VERSION_LINE, MIRROR_TEST_RSYNC_EXIT="23"))
    check("openrsync exit 23, files vanished mid-run, is a mirrored line with a note, exit 0",
          result.returncode == 0 and result.stdout.count("vanished mid-run") == 2, result.stdout)
    argv_log.unlink()
    result = run_mirror(home, RULED_DESTINATION, dict(
        remote_env, MIRROR_TEST_RSYNC_VERSION_LINE=OPENRSYNC_VERSION_LINE, MIRROR_TEST_RSYNC_EXIT="24"))
    check("openrsync exit 24 is not its vanished code and is FAILED naming the exit, exit 1",
          result.returncode == 1 and result.stdout.count("FAILED:") == 2
          and "rsync exit 24" in result.stdout and "ned-box unreachable" not in result.stdout,
          result.stdout)
    argv_log.unlink()
    result = run_mirror(home, RULED_DESTINATION, dict(remote_env, MIRROR_TEST_RSYNC_EXIT="255"))
    check("rsync exit 255 is FAILED naming ned-box unreachable, exit 1",
          result.returncode == 1 and result.stdout.count("FAILED:") == 2
          and "ned-box unreachable" in result.stdout, result.stdout)
    argv_log.unlink()
    result = run_mirror(home, RULED_DESTINATION, dict(
        remote_env, MIRROR_TEST_RSYNC_VERSION_LINE=GNU_VERSION_LINE, MIRROR_TEST_RSYNC_EXIT="24",
        MIRROR_TEST_RSYNC_STDERR="file has vanished: stub"), QUIET)
    quiet_calls = [json.loads(line) for line in argv_log.read_text().splitlines()]
    check("--failures-only: remote files vanished mid-run is exit 0 with nothing printed, rsync's stderr included",
          result.returncode == 0 and result.stdout == "" and result.stderr == "",
          repr(result.stdout + result.stderr))
    check("--failures-only: a pass that prints nothing does not ask ned-box for its file count",
          not any(c[0].endswith("ssh") and "wc -l" in " ".join(c) for c in quiet_calls)
          and sum(1 for c in quiet_calls if c[0].endswith("rsync")) == 2,
          str(quiet_calls))
    argv_log.unlink()
    result = run_mirror(home, RULED_DESTINATION, dict(
        remote_env, MIRROR_TEST_RSYNC_EXIT="255", MIRROR_TEST_RSYNC_STDERR="ssh: connect refused"), QUIET)
    check("--failures-only: rsync exit 255 still prints both FAILED lines naming ned-box unreachable, exit 1",
          result.returncode == 1 and result.stdout.count("FAILED:") == 2
          and "ned-box unreachable" in result.stdout and "mirrored:" not in result.stdout,
          result.stdout)
    check("--failures-only: a failed rsync's stderr still reaches the log",
          "ssh: connect refused" in result.stderr, repr(result.stderr))
    # ned-box unreachable at the start of a run: the mkdir ssh fails first,
    # so the preparation's FAILED line is the only one cron gets.
    argv_log.unlink()
    result = run_mirror(home, RULED_DESTINATION, dict(
        remote_env, MIRROR_TEST_SSH_MKDIR_EXIT="255",
        MIRROR_TEST_SSH_STDERR="ssh: connect to host ned-box port 22: Operation timed out"), QUIET)
    prepare_calls = [json.loads(line) for line in argv_log.read_text().splitlines()]
    check("--failures-only: ssh failing to prepare the store prints both could-not-prepare FAILED lines, exit 1, and rsync never runs",
          result.returncode == 1 and result.stdout.count("FAILED:") == 2
          and result.stdout.count("could not prepare") == 2 and "(exit 255)" in result.stdout
          and not any(c[0].endswith("rsync") for c in prepare_calls),
          result.stdout + str(prepare_calls))
    check("--failures-only: a failed preparation's ssh stderr still reaches the log",
          result.stderr.count("ssh: connect to host ned-box port 22: Operation timed out") == 2,
          repr(result.stderr))
    argv_log.unlink()
    result = run_mirror(home, RULED_DESTINATION, dict(
        remote_env, MIRROR_TEST_RSYNC_VERSION_LINE=GNU_VERSION_LINE, MIRROR_TEST_RSYNC_EXIT="23"), QUIET)
    check("--failures-only: GNU rsync exit 23 is still FAILED naming the exit, exit 1",
          result.returncode == 1 and result.stdout.count("FAILED:") == 2
          and "rsync exit 23" in result.stdout, result.stdout)
    check("the documented cron lines run every minute with --failures-only, the Mac's under Homebrew python3",
          "  Mac:     * * * * * /opt/homebrew/bin/python3 /Users/el/Projects/nedschorus/scripts/"
          "transcript-mirror-to-log-store.py --failures-only >>" in MIRROR.read_text()
          and "  ned-box: * * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/"
          "transcript-mirror-to-log-store.py --failures-only >>" in MIRROR.read_text())
    check("the destination constant in the script is the ruled one",
          f'LOG_STORE_TRANSCRIPTS_DESTINATION = "{RULED_DESTINATION}"' in MIRROR.read_text())

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
