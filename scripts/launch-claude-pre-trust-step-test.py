#!/usr/bin/env python3
"""Tests for the launchers' pre-trust step: the write that pre-answers
Claude's one-time folder-trust dialog by adding the seat directory to
~/.claude.json.

That file is the HARNESS's live state file, not the launchers' own: running
sessions write it while a launch is happening (its mtime was observed
changing mid-session on the Mac, 2026-09-08). Until that day both launchers
read it whole and wrote it back by truncating the file and streaming JSON
into it, which gives a concurrent harness read a torn file — and a fresh
session that reads torn JSON can stop at the very dialog this step exists to
skip. Both twins now write a temporary sibling and os.replace it into place.

These cases MEASURE that, on the file the write actually produces, rather
than reading the launchers' source for the word "replace":

  - the inode pair is the deterministic proof that the target is never
    observed truncated: a truncating write keeps the inode (it opens the
    target itself), a replace changes it (the target path is never opened
    for writing at all, so there is no moment at which a reader could see
    it short);
  - a write sabotaged partway (RLIMIT_FSIZE via `ulimit -f 0`, which a full
    disk reaches by the same errno) must leave the original file
    byte-identical, and must leave its temporary beside the target rather
    than in TMPDIR — os.replace is atomic only within one filesystem;
  - two controls give the harness teeth, by running the shapes the fix
    rejects: the pre-fix truncate-in-place shape, which empties the file
    under that same failure, and an open(...).write() form, whose buffered
    flush error CPython ignores at deallocation, so it publishes an EMPTY
    state file and still exits 0 (measured 2026-09-08 — the reason the
    launchers use Path.write_text).

Both twins are covered here, the way scripts/launch-claude-update-step-test.sh
covers the update step in both: the Mac twin by running the real launcher,
and the box twin by capturing the string it hands ssh and replaying it
through a real /bin/sh, so the box-side program is tested as it ARRIVES —
after the single-quote parse it crosses (P1). Every external participant is
stubbed and HOME is a throwaway directory: no seat starts, no session
updates, and nothing ssh's anywhere. The one participant deliberately NOT
stubbed is python3 -c, which is the code under test; the stub execs the real
interpreter for that call and answers exit 0 for every other.

Run: python3 scripts/launch-claude-pre-trust-step-test.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MAC_LAUNCHER = Path(__file__).with_name("launch-claude-mac")
UBUNTU_LAUNCHER = Path(__file__).with_name("launch-claude-ubuntu")

ARGUMENT_BOUNDARY = "=== argument boundary ===\n"
CALL_BOUNDARY = "=== call boundary ===\n"

# The two write shapes the launchers must NOT use, kept here as controls so
# the sabotage this suite injects is shown to discriminate rather than
# assumed to. Both take the seat directory as argv[1], exactly as the real
# programs do.
PRE_FIX_TRUNCATING_WRITE = '''import json, os, sys
path = os.path.expanduser("~/.claude.json")
settings = json.load(open(path)) if os.path.exists(path) else {}
target = os.path.abspath(os.path.expanduser(sys.argv[1]))
settings.setdefault("projects", {}).setdefault(target, {})["hasTrustDialogAccepted"] = True
json.dump(settings, open(path, "w"), indent=2)'''

SWALLOWED_FLUSH_WRITE = '''import json, os, sys, tempfile
path = os.path.expanduser("~/.claude.json")
settings = json.load(open(path)) if os.path.exists(path) else {}
target = os.path.abspath(os.path.expanduser(sys.argv[1]))
settings.setdefault("projects", {}).setdefault(target, {})["hasTrustDialogAccepted"] = True
handle, temporary = tempfile.mkstemp(dir=os.path.dirname(path))
os.close(handle)
open(temporary, "w", encoding="utf-8").write(json.dumps(settings, indent=2))
os.replace(temporary, path)'''

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def write_stub(directory: Path, name: str, body: str):
    path = directory / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


def seeded_state(existing_seat: str) -> dict:
    """A stand-in for the harness's own state file: the keys a real one
    carries beside `projects` (an account block among them — this file holds
    credentials, which is why the step preserves its mode), plus one project
    already trusted. All values are obviously fake."""
    return {
        "numStartups": 41,
        "oauthAccount": {"accountUuid": "not-a-real-uuid"},
        "projects": {
            existing_seat: {"hasTrustDialogAccepted": True,
                            "history": ["an earlier session"]},
        },
        "tipsHistory": {"queue-tip": 3},
    }


class PreTrustSandbox:
    """One sandbox: stubs, a throwaway HOME, an agents root outside HOME, and
    a decoy TMPDIR that the write must never touch."""

    def __init__(self, root: Path):
        self.home = root / "home"
        self.home.mkdir(parents=True)
        self.agents = root / "agents"
        self.agents.mkdir()
        self.workdir = root / "workdir"
        self.workdir.mkdir()
        self.captures = root / "captures"
        self.captures.mkdir()
        self.decoy_tmpdir = root / "decoy-tmpdir"
        self.decoy_tmpdir.mkdir()
        self.stubs = root / "stubs"
        self.stubs.mkdir()
        self.state_file = self.home / ".claude.json"
        # python3: every call is recorded argument by argument (the Mac
        # twin's program is multi-line, so a line-per-argument capture could
        # not be parsed back), and a `-c` call — the pre-trust write, the one
        # thing under test — is handed to the REAL interpreter. Every other
        # python3 the launchers run (the supervisor, clean-worktrees,
        # checkout-freshness-catch-up) answers exit 0.
        write_stub(self.stubs, "python3",
                   'for argument in "$@"; do\n'
                   '  printf \'%s\\n=== argument boundary ===\\n\' "$argument" '
                   '>> "$PRE_TRUST_CAPTURES/python3-calls.txt"\n'
                   'done\n'
                   'printf \'=== call boundary ===\\n\' '
                   '>> "$PRE_TRUST_CAPTURES/python3-calls.txt"\n'
                   'if [ "${1:-}" = "-c" ]; then\n'
                   '  exec "$PRE_TRUST_REAL_PYTHON3" "$@"\n'
                   'fi\n'
                   'exit 0\n')
        # has-session answers "no session" so the launch proceeds on the
        # seat's own socket; new-session records its argv and returns,
        # without running the pane command — the seat's own contents are
        # another suite's subject (launch-claude-mac-test.py).
        write_stub(self.stubs, "tmux",
                   'for argument in "$@"; do\n'
                   '  case "$argument" in (has-session) exit 1;; esac\n'
                   'done\n'
                   'printf \'%s\\n\' "$@" '
                   '>> "$PRE_TRUST_CAPTURES/tmux-argv.txt"\n'
                   'exit 0\n')
        write_stub(self.stubs, "ssh",
                   'printf \'%s\\n\' "$@" > "$PRE_TRUST_CAPTURES/ssh-argv.txt"\n'
                   'exit 0\n')
        for quiet_stub in ("claude", "git", "timeout"):
            write_stub(self.stubs, quiet_stub, "exit 0\n")

    # --- state file ----------------------------------------------------
    def seed_state_file(self, existing_seat: str, mode: int = 0o600) -> str:
        """Write a stand-in harness state file and return its exact bytes."""
        content = json.dumps(seeded_state(existing_seat), indent=2)
        self.state_file.write_text(content, encoding="utf-8")
        self.state_file.chmod(mode)
        return content

    def facts(self) -> dict:
        """Everything a case asks about the state file, in one reading."""
        if not self.state_file.exists():
            return {"exists": False}
        status = self.state_file.stat()
        content = self.state_file.read_text(encoding="utf-8")
        try:
            parsed = json.loads(content)
        except ValueError:
            parsed = None
        return {"exists": True, "inode": status.st_ino,
                "mode": status.st_mode & 0o777, "content": content,
                "parsed": parsed}

    def temporary_leftovers(self) -> list:
        """Any temporary sibling of the state file still on disk."""
        return sorted(path.name for path in self.home.glob(".claude.json.*"))

    def decoy_contents(self) -> list:
        return sorted(path.name for path in self.decoy_tmpdir.iterdir())

    # --- running the launchers -----------------------------------------
    def launcher_environment(self, agents_root) -> dict:
        """agents_root None leaves NEDSCHORUS_AGENTS_ROOT unset, so the
        launcher's own ~/agents default applies."""
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("NEDSCHORUS_", "LAUNCH_CLAUDE_",
                                              "CLAUDE_CODE_"))}
        environment["PATH"] = f"{self.stubs}:{environment.get('PATH', '')}"
        environment["HOME"] = str(self.home)
        environment["TMPDIR"] = str(self.decoy_tmpdir)
        environment["NEDSCHORUS_AGENT_BOX"] = "stub-box"
        if agents_root is not None:
            environment["NEDSCHORUS_AGENTS_ROOT"] = agents_root
        environment["LAUNCH_CLAUDE_UPDATE_TIMEOUT_SECONDS"] = "5"
        environment["PRE_TRUST_CAPTURES"] = str(self.captures)
        environment["PRE_TRUST_REAL_PYTHON3"] = sys.executable
        return environment

    def run_mac_launcher(self, seat_name: str, agents_root=None):
        """The Mac cases pin the agents root OUTSIDE the sandbox HOME, so a
        seat directory can never be mistaken for the state file's own."""
        if agents_root is None:
            agents_root = str(self.agents)
        return subprocess.run(
            [str(MAC_LAUNCHER), seat_name, "--no-attach"],
            capture_output=True, text=True, check=False,
            env=self.launcher_environment(agents_root), cwd=str(self.workdir))

    def run_ubuntu_replay(self, seat_name: str, agents_root=None):
        """The box twin: launcher -> the string it hands ssh -> that string
        run by a real /bin/sh, which is where the box-side program's own
        parse (P1) actually happens. agents_root defaults to UNSET here, on
        purpose: the box's own ~/agents is what a real launch uses, and the
        trusted key then proves the box resolved ~ box-side (inside this
        sandbox's HOME) rather than this Mac resolving it first."""
        launched = subprocess.run(
            [str(UBUNTU_LAUNCHER), seat_name, "--no-attach"],
            capture_output=True, text=True, check=False,
            env=self.launcher_environment(agents_root), cwd=str(self.workdir))
        capture = self.captures / "ssh-argv.txt"
        remote = (capture.read_text(encoding="utf-8").splitlines()[-1]
                  if capture.is_file() else "")
        replayed = subprocess.run(
            ["/bin/sh", "-c", remote], capture_output=True, text=True,
            check=False, env={
                "PATH": f"{self.stubs}:/usr/bin:/bin:/usr/sbin:/sbin",
                "HOME": str(self.home),
                "TMPDIR": str(self.decoy_tmpdir),
                "PRE_TRUST_CAPTURES": str(self.captures),
                "PRE_TRUST_REAL_PYTHON3": sys.executable,
            }, cwd=str(self.workdir))
        return launched, remote, replayed

    # --- the program as it arrived, and re-running it under a failure ---
    def arrived_trust_program(self):
        """The `-c` program text and its argument, as the interpreter
        received them — after every shell parse between the launcher and the
        write."""
        capture = self.captures / "python3-calls.txt"
        if not capture.is_file():
            return None, None
        for call in capture.read_text(encoding="utf-8").split(CALL_BOUNDARY):
            arguments = [piece for piece in call.split(ARGUMENT_BOUNDARY)
                         if piece]
            arguments = [piece[:-1] if piece.endswith("\n") else piece
                         for piece in arguments]
            if len(arguments) == 3 and arguments[0] == "-c":
                return arguments[1], arguments[2]
        return None, None

    def run_trust_program(self, program: str, seat_directory: str,
                          sabotage: bool = False):
        """Run a pre-trust program against this sandbox's HOME. With
        sabotage, RLIMIT_FSIZE is zero, so the first byte written to any
        regular file fails (EFBIG) — the same errno a full disk gives, and
        the failure lands after the read and before the replace."""
        script = 'exec "$0" -c "$1" "$2"'
        if sabotage:
            script = "ulimit -f 0; " + script
        return subprocess.run(
            ["/bin/sh", "-c", script, sys.executable, program, seat_directory],
            capture_output=True, text=True, check=False,
            env={"PATH": f"{self.stubs}:/usr/bin:/bin",
                 "HOME": str(self.home),
                 "TMPDIR": str(self.decoy_tmpdir)},
            cwd=str(self.workdir))


def project_entry(facts: dict, seat_directory: str) -> dict:
    """One project's entry in the state file, or {}: a missing entry must
    fail its case with a detail printed, never raise out of the suite."""
    projects = (facts.get("parsed") or {}).get("projects") or {}
    return projects.get(seat_directory, {})


def is_trusted(facts: dict, seat_directory: str) -> bool:
    return project_entry(facts, seat_directory).get(
        "hasTrustDialogAccepted") is True


def project_names(facts: dict) -> list:
    return sorted((facts.get("parsed") or {}).get("projects") or {})


def expected_bytes(existing_seat: str, new_seat: str) -> str:
    """What the step must write: the seeded state with one project added,
    formatted exactly as the pre-fix write formatted it (indent=2, no
    trailing newline). The fix changed HOW the file is written, not what."""
    settings = seeded_state(existing_seat)
    settings["projects"][new_seat] = {"hasTrustDialogAccepted": True}
    return json.dumps(settings, indent=2)


def main() -> int:
    with tempfile.TemporaryDirectory(
            prefix="launch-claude-pre-trust-step-test-") as scratch:
        root = Path(scratch)

        # --- 1. Mac twin, a machine with no state file yet ----------------
        sandbox = PreTrustSandbox(root / "mac-fresh")
        launched = sandbox.run_mac_launcher("seat-fresh")
        facts = sandbox.facts()
        seat_directory = str(sandbox.agents / "seat-fresh")
        check("mac, fresh HOME: the launcher ran and trusted the seat directory",
              launched.returncode == 0 and facts["exists"]
              and is_trusted(facts, seat_directory),
              (launched.returncode, launched.stderr[:300],
               project_names(facts)))
        # A NEW file now comes from mkstemp, so it is 0600 rather than the
        # umask-derived 0644 the pre-fix open(path, "w") produced. Asserted
        # rather than left to chance: the harness's own file was measured at
        # 0600 (this Mac, 2026-09-08) and it holds credentials, so tighter is
        # the direction to be pinned in.
        check("mac, fresh HOME: the new state file is created 0600",
              facts.get("mode") == 0o600, facts.get("mode"))
        check("mac, fresh HOME: no temporary file is left beside it",
              sandbox.temporary_leftovers() == [],
              sandbox.temporary_leftovers())

        # --- 2. Mac twin, an existing state file: everything else in it
        # survives, byte for byte, and the file is REPLACED rather than
        # truncated — which the inode is what proves.
        sandbox = PreTrustSandbox(root / "mac-existing")
        existing_seat = "/an/earlier/seat"
        before_content = sandbox.seed_state_file(existing_seat, mode=0o640)
        before = sandbox.facts()
        launched = sandbox.run_mac_launcher("seat-keeps")
        facts = sandbox.facts()
        seat_directory = str(sandbox.agents / "seat-keeps")
        check("mac, existing file: the harness's other keys all survive",
              launched.returncode == 0 and facts["parsed"] is not None
              and facts["parsed"].get("numStartups") == 41
              and facts["parsed"].get("oauthAccount") == {
                  "accountUuid": "not-a-real-uuid"}
              and facts["parsed"].get("tipsHistory") == {"queue-tip": 3}
              and project_entry(facts, existing_seat) == {
                  "hasTrustDialogAccepted": True,
                  "history": ["an earlier session"]},
              (launched.returncode, facts.get("content", "")[:300]))
        check("mac, existing file: the new seat is added beside them",
              is_trusted(facts, seat_directory),
              (project_names(facts), facts.get("content", "")[:300]))
        check("mac, existing file: the bytes are what the pre-fix write "
              "produced (indent=2, no trailing newline)",
              facts.get("content") == expected_bytes(existing_seat,
                                                     seat_directory),
              repr(facts.get("content", ""))[:400])
        check("mac, existing file: the file is REPLACED, not truncated "
              "(the inode changed, so the target was never opened for writing)",
              facts.get("inode") != before["inode"],
              (before["inode"], facts.get("inode")))
        check("mac, existing file: the state file's mode is preserved (0640)",
              facts.get("mode") == 0o640, oct(facts.get("mode") or 0))
        check("mac, existing file: no temporary file is left beside it",
              sandbox.temporary_leftovers() == [],
              sandbox.temporary_leftovers())
        check("mac, existing file: nothing was written through TMPDIR",
              sandbox.decoy_contents() == [], sandbox.decoy_contents())
        mac_program, mac_argument = sandbox.arrived_trust_program()
        check("mac: the pre-trust write is a python3 -c program taking the "
              "seat directory as its argument",
              mac_program is not None and "os.replace" in mac_program
              and mac_argument == seat_directory,
              (mac_argument, (mac_program or "")[:120]))

        # --- 3. Mac twin, the write sabotaged partway ---------------------
        # The program is re-run as the interpreter received it, with
        # RLIMIT_FSIZE at zero: the read succeeds, the payload write fails.
        # The original file must be untouched, and the temporary must be a
        # sibling of the target — os.replace is atomic only within one
        # filesystem, so a temporary left to TMPDIR would not be a fix at all.
        sandbox = PreTrustSandbox(root / "mac-sabotaged")
        before_content = sandbox.seed_state_file("/an/earlier/seat")
        before = sandbox.facts()
        sabotaged = sandbox.run_trust_program(mac_program, "/some/seat/home",
                                              sabotage=True)
        facts = sandbox.facts()
        check("mac, sabotaged: the write fails loudly (non-zero exit)",
              sabotaged.returncode != 0,
              (sabotaged.returncode, sabotaged.stderr[-200:]))
        check("mac, sabotaged: the state file is byte-identical and its inode "
              "unchanged — no reader could have seen it truncated",
              facts["exists"] and facts["content"] == before_content
              and facts["inode"] == before["inode"],
              (facts.get("content", "")[:120], before["inode"],
               facts.get("inode")))
        leftovers = sandbox.temporary_leftovers()
        check("mac, sabotaged: the temporary sits beside the state file, "
              "never in TMPDIR",
              sandbox.decoy_contents() == []
              and all(name.endswith(".launch-claude-writing")
                      for name in leftovers),
              (leftovers, sandbox.decoy_contents()))

        # --- 4. The controls: the two write shapes the fix rejects, run
        # against the same sabotage, so this suite is shown to have teeth.
        sandbox = PreTrustSandbox(root / "control-truncating")
        before_content = sandbox.seed_state_file("/an/earlier/seat")
        before = sandbox.facts()
        sandbox.run_trust_program(PRE_FIX_TRUNCATING_WRITE, "/some/seat/home",
                                  sabotage=True)
        facts = sandbox.facts()
        check("control: the pre-fix truncate-in-place shape EMPTIES the state "
              "file under the same failure (the sabotage discriminates)",
              facts["exists"] and facts["content"] == ""
              and facts["inode"] == before["inode"],
              (repr(facts.get("content", ""))[:120], facts.get("inode"),
               before["inode"]))

        sandbox = PreTrustSandbox(root / "control-swallowed-flush")
        before_content = sandbox.seed_state_file("/an/earlier/seat")
        control = sandbox.run_trust_program(SWALLOWED_FLUSH_WRITE,
                                            "/some/seat/home", sabotage=True)
        facts = sandbox.facts()
        check("control: an open(...).write() temporary publishes an EMPTY "
              "state file and still exits 0 (why the twins use write_text)",
              control.returncode == 0 and facts["exists"]
              and facts["content"] == "",
              (control.returncode, repr(facts.get("content", ""))[:120]))

        # --- 5. Box twin: the program as it ARRIVES on the box ------------
        # It crosses the box login shell's parse (P1) inside SINGLE quotes,
        # so it may carry no single quote of its own; and the whole chain is
        # replayed by a real /bin/sh, with the real interpreter running the
        # write against a sandboxed HOME.
        sandbox = PreTrustSandbox(root / "box-existing")
        existing_seat = "/an/earlier/seat"
        sandbox.seed_state_file(existing_seat, mode=0o640)
        before = sandbox.facts()
        launched, remote, replayed = sandbox.run_ubuntu_replay("seat-box")
        facts = sandbox.facts()
        box_seat_directory = f"{sandbox.home}/agents/seat-box"
        check("box: the launcher reached ssh with a remote command",
              launched.returncode == 0 and bool(remote),
              (launched.returncode, launched.stderr[:200]))
        check("box: the remote command parses and runs (P1 exit 0)",
              replayed.returncode == 0,
              (replayed.returncode, replayed.stderr[-300:]))
        box_program, box_argument = sandbox.arrived_trust_program()
        check("box: the program arrives intact and carries no single quote "
              "of its own (P1 splices it between single quotes)",
              box_program is not None and "os.replace" in box_program
              and "'" not in box_program,
              (box_program or "")[:160])
        check("box: the seat directory is trusted with the box's own $HOME "
              "resolved box-side",
              is_trusted(facts, box_seat_directory)
              and box_argument == box_seat_directory,
              (box_argument, project_names(facts)))
        check("box: the harness's other keys survive the box-side write",
              facts["parsed"] is not None
              and facts["parsed"].get("numStartups") == 41
              and project_entry(facts, existing_seat) == {
                  "hasTrustDialogAccepted": True,
                  "history": ["an earlier session"]},
              facts.get("content", "")[:300])
        check("box: the box-side write REPLACES the file (the inode changed)",
              facts.get("inode") != before["inode"],
              (before["inode"], facts.get("inode")))
        check("box: the state file's mode is preserved (0640)",
              facts.get("mode") == 0o640, oct(facts.get("mode") or 0))
        check("box: no temporary is left beside the state file, and nothing "
              "went through TMPDIR",
              sandbox.temporary_leftovers() == []
              and sandbox.decoy_contents() == [],
              (sandbox.temporary_leftovers(), sandbox.decoy_contents()))

        # --- 6. Box twin, the arrived program sabotaged -------------------
        sandbox = PreTrustSandbox(root / "box-sabotaged")
        before_content = sandbox.seed_state_file("/an/earlier/seat")
        before = sandbox.facts()
        sabotaged = sandbox.run_trust_program(box_program, "/some/box/seat",
                                              sabotage=True)
        facts = sandbox.facts()
        check("box, sabotaged: the write fails loudly (non-zero exit)",
              sabotaged.returncode != 0,
              (sabotaged.returncode, sabotaged.stderr[-200:]))
        check("box, sabotaged: the state file is byte-identical and its inode "
              "unchanged",
              facts["exists"] and facts["content"] == before_content
              and facts["inode"] == before["inode"],
              (facts.get("content", "")[:120], before["inode"],
               facts.get("inode")))
        check("box, sabotaged: the temporary sits beside the state file, "
              "never in TMPDIR",
              sandbox.decoy_contents() == []
              and all(name.endswith(".launch-claude-writing")
                      for name in sandbox.temporary_leftovers()),
              (sandbox.temporary_leftovers(), sandbox.decoy_contents()))

        # --- 7. Box twin, an agents root with an apostrophe and a $: the
        # trusted key must be byte-intact. The pre-trust program is spliced
        # into the same single-quoted region the seat path crosses, so this
        # is where a quoting mistake in the step would surface as a trusted
        # directory that is not the seat's.
        sandbox = PreTrustSandbox(root / "box-apostrophe-root")
        apostrophe_root = f"{sandbox.home}/agent's $fleet"
        launched, remote, replayed = sandbox.run_ubuntu_replay(
            "seat-odd", agents_root=apostrophe_root)
        facts = sandbox.facts()
        check("box, apostrophe-and-$ agents root: the trusted key is the "
              "seat directory, byte-intact",
              replayed.returncode == 0
              and is_trusted(facts, f"{apostrophe_root}/seat-odd"),
              (replayed.returncode, replayed.stderr[-200:],
               project_names(facts)))

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
