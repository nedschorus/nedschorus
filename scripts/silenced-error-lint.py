#!/usr/bin/env python3
"""Flag places a diff silences an error channel it may later trust.

The failure shape this hunts, seen four times on 2026-08-19/20 in four
different authors' work: an error silenced, then the result trusted. The
instances: `2>/dev/null` on a freshening pull that then launched a stale
copy silently; a suppressed `git checkout` stderr that turned a dirty
index into a wrong review finding; a test guard whose success condition
held while the thing under test failed; a fail-first case that crashed
instead of failing and was almost reported as a clean result. Prose did
not stop the fourth author, who had spent the day naming the pattern —
hence this program (user-ruled 2026-08-19: prose yields to code).

What it flags, line by line, in the files or diff it is given:

  - `2>/dev/null` and `2>&-` in shell text (including shell strings
    inside Python and inside YAML/JSON command registrations);
  - `stderr=subprocess.DEVNULL` and `stderr=DEVNULL` in Python.

What it deliberately does not flag: `check=False` — this codebase uses
it pervasively and correctly, inspecting returncode afterward, and
telling those apart needs judgment, not a grep. The reviewer reading
this lint's hits supplies the judgment: each hit is either justified in
place or is the bug.

Exit codes: 0 no hits; 1 hits printed (one per line: path, line number,
the line); 2 bad invocation. A caller gating on this treats 1 as "a
human reads the hits", never as an automatic refusal.

Usage:
  scripts/silenced-error-lint.py FILE [FILE ...]
  git diff BASE..HEAD | scripts/silenced-error-lint.py --diff
"""

import argparse
import pathlib
import re
import sys

SILENCED_STDERR = re.compile(
    r"2>\s*/dev/null"      # shell: discard stderr
    r"|2>&-"               # shell: close stderr
    r"|stderr\s*=\s*(?:subprocess\.)?DEVNULL"  # python: discard stderr
)


def hits_in_text(text: str, path_label: str, only_added_lines: bool = False):
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if only_added_lines:
            if not line.startswith("+") or line.startswith("+++"):
                continue
        if SILENCED_STDERR.search(line):
            found.append((path_label, number, line.strip()))
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Flag silenced-stderr patterns in files or a diff.",
        epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("files", nargs="*", help="files to scan")
    parser.add_argument("--diff", action="store_true",
                        help="read a unified diff on stdin and scan only its added lines")
    arguments = parser.parse_args(argv)

    if arguments.diff == bool(arguments.files):
        print("silenced-error-lint: pass files, or --diff with a diff on stdin — not both, not neither",
              file=sys.stderr)
        return 2

    found = []
    if arguments.diff:
        found = hits_in_text(sys.stdin.read(), "(diff added lines)", only_added_lines=True)
    else:
        for name in arguments.files:
            path = pathlib.Path(name)
            if not path.is_file():
                print(f"silenced-error-lint: no such file: {name}", file=sys.stderr)
                return 2
            found.extend(hits_in_text(path.read_text(encoding="utf-8", errors="replace"), name))

    for path_label, number, line in found:
        print(f"{path_label}:{number}: {line}")
    if found:
        print(f"silenced-error-lint: {len(found)} silenced-stderr line(s) — each is either "
              "justified in place or is the bug", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
