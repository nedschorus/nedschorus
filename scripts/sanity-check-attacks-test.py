#!/usr/bin/env python3
"""Tests for sanity-check-attacks.py — the worktree write detector, the record
directory claim, and the prompt-body boundary.

The detector's only value is being trustworthy about whether a codex cell
wrote to the worktree, and every hole in it is silent by construction. Each
case below builds a scratch repository, snapshots it, simulates a cell write,
and asserts the write is named. The three holes under test were found
reviewing PRs #98 and #102:

  - a file already dirty before the run, rewritten by a cell (label
    comparison misses it; content hashes catch it)
  - a wholly-untracked directory, which porcelain collapses to one entry, so
    anything a cell writes under it is invisible without -uall
  - a non-ASCII pathname, which git C-quotes without -z, producing a path
    that matches nothing on disk and fingerprints as "absent" on both sides

Run: python3 scripts/sanity-check-attacks-test.py
"""

import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile

RUNNER_SCRIPT = pathlib.Path(__file__).with_name("sanity-check-attacks.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def load_runner():
    spec = importlib.util.spec_from_file_location("sanity_check_attacks", RUNNER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {completed.stderr.strip()}")
    return completed.stdout


def new_repo(root):
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "test")
    (root / "tracked.md").write_text("original\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "initial")
    return root


def main():
    runner = load_runner()
    snapshot = runner.worktree_snapshot
    strays = getattr(runner, "stray_paths", None)
    if strays is None:
        def strays(baseline, now):
            return sorted(path for path in set(now) | set(baseline)
                          if now.get(path) != baseline.get(path))

    # Case 1: a file already dirty before the run, rewritten by a cell.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "tracked.md").write_text("dirty before the run\n", encoding="utf-8")
        baseline = snapshot(repo)
        (repo / "tracked.md").write_text("a cell wrote this\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("already-dirty file rewritten by a cell is detected",
              "tracked.md" in found, f"stray list was {found}")

    # Case 2: a file written under a directory that was already untracked.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "untracked-dir").mkdir()
        (repo / "untracked-dir" / "already-here.md").write_text("x\n", encoding="utf-8")
        baseline = snapshot(repo)
        (repo / "untracked-dir" / "cell-wrote-this.md").write_text("y\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("file written under an already-untracked directory is detected",
              "untracked-dir/cell-wrote-this.md" in found, f"stray list was {found}")

    # Case 3: a non-ASCII pathname, which git C-quotes unless -z is used.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        unicode_name = "dirty-ünicode.md"
        (repo / unicode_name).write_text("original\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "add unicode file")
        (repo / unicode_name).write_text("dirty before the run\n", encoding="utf-8")
        baseline = snapshot(repo)
        (repo / unicode_name).write_text("a cell wrote this\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("rewrite of a non-ASCII pathname is detected",
              unicode_name in found,
              f"stray list was {found}; baseline was {baseline}")

    # Case 4: a cell stages an already-dirty file. Staging changes the index
    # status without changing the file's bytes, so a content fingerprint alone
    # sees nothing — `git add` is exactly the write the detector exists to
    # catch, and the label comparison this replaced did catch it.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "tracked.md").write_text("dirty before the run\n", encoding="utf-8")
        baseline = snapshot(repo)
        git(repo, "add", "tracked.md")
        found = strays(baseline, snapshot(repo))
        check("an already-dirty file staged by a cell is detected",
              "tracked.md" in found, f"stray list was {found}; baseline was {baseline}")

    # Case 5: a quiet run reports nothing.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "untracked-dir").mkdir()
        (repo / "untracked-dir" / "already-here.md").write_text("x\n", encoding="utf-8")
        baseline = snapshot(repo)
        found = strays(baseline, snapshot(repo))
        check("a run that writes nothing produces no stray", found == [],
              f"stray list was {found}")

    # Case 6: a staged rename must not desynchronize the field walk. Under -z
    # the origin path is its own field, so a parser expecting " -> " consumes
    # one field too few and mistakes the origin path for the next entry.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "zz-last.md").write_text("tail\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "add tail file")
        git(repo, "mv", "tracked.md", "renamed.md")
        baseline = snapshot(repo)
        (repo / "zz-last.md").write_text("a cell wrote this\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("a write after a staged rename is still detected",
              "zz-last.md" in found, f"stray list was {found}; baseline was {baseline}")

    # Case 7: two runs starting together must not be handed the same record
    # directory. A look-then-create claim passes both when neither has written
    # its first report yet, and the second run overwrites the first.
    records_root = getattr(runner, "RECORDS_ROOT", None)
    with tempfile.TemporaryDirectory() as scratch:
        runner.RECORDS_ROOT = pathlib.Path(scratch) / "sanity-check-records"
        first = runner.fresh_record_dir("same-target")
        second = runner.fresh_record_dir("same-target")
        check("a second run for the same target and date gets its own directory",
              first != second, f"both runs got {first}")
        check("the second directory is suffixed", second.name.endswith("-2"),
              f"second directory was {second}")
    if records_root is not None:
        runner.RECORDS_ROOT = records_root

    # The prompt-body boundary. The marker replaced a bare `---` rule, which is
    # ordinary markdown: a horizontal rule anywhere above the intended split
    # silently truncated the prompt, and nothing failed.
    with tempfile.TemporaryDirectory() as scratch:
        scratch_dir = pathlib.Path(scratch)
        marker = runner.PROMPT_BODY_MARKER
        heading = runner.PROMPT_BODY_FIRST_LINE

        def prompt_file(name, text):
            path = scratch_dir / name
            path.write_text(text, encoding="utf-8")
            runner.ATTACK_PROMPT_FILES["cut"] = path
            return path

        def split_fails(name, text):
            prompt_file(name, text)
            import contextlib
            import io
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    runner.prompt_body("cut")
            except SystemExit as exc:
                # The documented contract: an unusable invocation exits 2.
                return exc.code == 2
            return False

        good = f"# Header\n\nStatus: names the {marker} line inline.\n\n{marker}\n\n{heading}\n\nBody text.\n"
        prompt_file("good.md", good)
        body = runner.prompt_body("cut")
        check("a header naming the marker inline still splits at the marker line",
              body.startswith(heading) and "Status:" not in body,
              f"body began {body[:60]!r}")

        check("a prompt with no marker line is refused",
              split_fails("none.md", f"# Header\n\n{heading}\n\nBody.\n"))
        check("a prompt with two marker lines is refused",
              split_fails("two.md", f"# Header\n\n{marker}\n\n{heading}\n\n{marker}\n\nBody.\n"))
        check("a body not opening with the expected heading is refused",
              split_fails("wrong.md", f"# Header\n\n{marker}\n\nStray line.\n\n{heading}\n"))

        rules = f"# Header\n\n---\n\nStatus text.\n\n---\n\n{marker}\n\n{heading}\n\nBody.\n"
        prompt_file("rules.md", rules)
        body = runner.prompt_body("cut")
        check("horizontal rules above the marker no longer move the split",
              body.startswith(heading) and "Status text." not in body,
              f"body began {body[:60]!r}")

    # The quote scan: a verbatim quote is silent, words in no tracked file warn.
    import contextlib
    import io
    runner_scan = load_runner()
    corpus = (runner_scan.normalized_for_quote_match(
        "the gate records every legacy import cleanly"),)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        runner_scan.quote_scan(corpus, 'It says "records every legacy import cleanly" here.', "q1")
    check("a verbatim quote raises no warning", buffer.getvalue() == "",
          f"output was {buffer.getvalue()!r}")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        runner_scan.quote_scan(corpus, 'It says "words that appear in no file at all" here.', "q2")
    check("a quote found nowhere warns",
          "quote found in no tracked file" in buffer.getvalue(),
          f"output was {buffer.getvalue()!r}")

    # The print modes: each surface arrives on stdout, and the requester
    # surface carries both of its sources.
    import subprocess as sp
    requester = sp.run([str(RUNNER_SCRIPT), "--print", "requester"],
                       capture_output=True, text=True)
    check("--print requester emits the docstring and the requester section",
          requester.returncode == 0
          and "second review instrument" in requester.stdout
          and "Writing the problem statement" in requester.stdout,
          f"rc={requester.returncode}")
    cell_view = sp.run([str(RUNNER_SCRIPT), "--print", "cut",
                        "--target", "docs/agents/sanity-checker-cut-attack-prompt.md"],
                       capture_output=True, text=True)
    check("--print cut emits the assembled cell prompt",
          cell_view.returncode == 0
          and cell_view.stdout.startswith("## Your assignment")
          and "Document under review:" in cell_view.stdout,
          f"rc={cell_view.returncode}, began {cell_view.stdout[:40]!r}")

    # The three standing prompts must each split cleanly.
    runner_fresh = load_runner()
    for attack in runner_fresh.ATTACKS:
        body = runner_fresh.prompt_body(attack)
        check(f"the standing {attack} prompt splits at its marker",
              body.startswith(runner_fresh.PROMPT_BODY_FIRST_LINE),
              f"body began {body[:60]!r}")

    print()
    if failures:
        print(f"{len(failures)} failing case(s): {', '.join(failures)}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
