#!/usr/bin/env python3
"""Tests for scripts/transcript-mirror-to-log-store.py: the layout, the two
sources, never --delete, the live-tree exits, the lock, and the remote
invocation. LOCAL mode runs the real rsync into a scratch store; REMOTE mode
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

STUB_RECORDER = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["MIRROR_TEST_ARGV_LOG"], "a") as log:
    log.write(json.dumps(sys.argv) + "\\n")
if sys.argv[0].endswith("ssh") and "wc -l" in " ".join(sys.argv):
    print(os.environ.get("MIRROR_TEST_STORE_COUNT", "0"))
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


def run_mirror(home, destination, extra_env=None):
    env = dict(os.environ)
    env[SOURCE_HOME_VARIABLE] = str(home)
    env[DESTINATION_VARIABLE] = destination
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(MIRROR)], capture_output=True,
                          text=True, check=False, env=env)


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
              "-a" in c and "ssh -o BatchMode=yes -o ConnectTimeout=10" in c
              and c[-1] == f"{RULED_DESTINATION}/{machine}/{name}/"
              and c[-2] == f"{home / '.claude' / name}/"
              for c, name in zip(rsync_calls, ("projects", "handoffs"))),
          str(rsync_calls))
    check("rsync is never asked to delete or to write in place",
          not any(flag in c for c in rsync_calls for flag in ("--delete", "--inplace")))
    check("every ssh call runs in batch mode with a connect timeout",
          ssh_calls and all("BatchMode=yes" in c for c in ssh_calls), str(ssh_calls))

    argv_log.unlink()
    result = run_mirror(home, RULED_DESTINATION, dict(remote_env, MIRROR_TEST_RSYNC_EXIT="24"))
    check("rsync exit 24, files vanished mid-run, is a mirrored line with a note, exit 0",
          result.returncode == 0 and result.stdout.count("vanished mid-run") == 2, result.stdout)
    argv_log.unlink()
    result = run_mirror(home, RULED_DESTINATION, dict(remote_env, MIRROR_TEST_RSYNC_EXIT="255"))
    check("rsync exit 255 is FAILED naming ned-box unreachable, exit 1",
          result.returncode == 1 and result.stdout.count("FAILED:") == 2
          and "ned-box unreachable" in result.stdout, result.stdout)
    check("the destination constant in the script is the ruled one",
          f'LOG_STORE_TRANSCRIPTS_DESTINATION = "{RULED_DESTINATION}"' in MIRROR.read_text())

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
