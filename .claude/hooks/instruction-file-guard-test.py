#!/usr/bin/env python3
"""Tests for instruction-file-guard.py.

Run: python3 .claude/hooks/instruction-file-guard-test.py
Prints one line per case and exits non-zero if any case fails.

The hook resolves its approval marker from the session's own checkout (the
payload's cwd), never from $CLAUDE_PROJECT_DIR. Every case here therefore
runs with $CLAUDE_PROJECT_DIR pointing at a DECOY checkout carrying a stale
marker: any case that passes proves it passed without that variable, and the
decoy marker surviving every run is the forked-session regression assertion.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("instruction-file-guard.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_hook(decoy_project_directory: Path, session_cwd: Path, file_path: str,
             path_field: str = "file_path"):
    """Invoke the guard. path_field selects which tool_input key carries the
    target: Edit and Write use file_path, NotebookEdit uses notebook_path."""
    payload = json.dumps({"cwd": str(session_cwd), "tool_input": {path_field: file_path}})
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(decoy_project_directory))
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], input=payload,
        capture_output=True, text=True, check=False, env=environment,
    )


def make_checkout(root: Path):
    """A directory git would take for a repository: a .git directory holding
    HEAD. The guard does not count an empty .git (see the section on Codex
    sandbox debris below), so every checkout here carries one."""
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")


with tempfile.TemporaryDirectory() as temporary_directory:
    tmp = Path(temporary_directory)

    # The session's own checkout: a directory with a .git directory.
    workspace = tmp / "workspace"
    make_checkout(workspace)

    # The decoy the environment variable names: a different checkout holding
    # a stale, populated marker — the exact 2026-08-14 hazard.
    decoy = tmp / "decoy-main-checkout"
    make_checkout(decoy)
    decoy_marker = decoy / ".walk-approved"
    decoy_marker.write_text("stale approval from an unrelated session\n", encoding="utf-8")

    result = run_hook(decoy, workspace, str(workspace / "CLAUDE.md"))
    check("editing CLAUDE.md is blocked", result.returncode == 2, str(result.returncode))
    check("the block teaches the walk path", "get the user's approval" in result.stderr, result.stderr)
    check("the block names the override marker", ".walk-approved" in result.stderr, result.stderr)
    check("a stale marker in $CLAUDE_PROJECT_DIR does not authorize (forked-session regression)",
          decoy_marker.exists())

    result = run_hook(decoy, workspace, str(workspace / "sub" / "CLAUDE.local.md"))
    check("an identity file anywhere is blocked", result.returncode == 2)

    result = run_hook(decoy, workspace, str(workspace / ".claude" / "skills" / "new" / "SKILL.md"))
    check("creating under .claude/ is blocked (the creation gap)", result.returncode == 2)

    result = run_hook(decoy, workspace, str(workspace / ".claude" / "settings.json"))
    check("the hook's own wiring is protected", result.returncode == 2)

    result = run_hook(decoy, workspace, str(workspace / "docs" / "ordinary.md"))
    check("an ordinary file passes", result.returncode == 0, result.stderr)

    # The three carve-outs: harness working space, not machinery. Each was added
    # after a real write tripped the guard, and each is asserted against its
    # neighbours so a future widening cannot quietly take the protected paths
    # with it.
    result = run_hook(decoy, workspace, str(workspace / ".claude" / "jobs" / "ab12cd34" / "tmp" / "draft.txt"))
    check("a background job's scratch file passes", result.returncode == 0, result.stderr)

    result = run_hook(decoy, workspace, str(workspace / ".claude" / "worktrees" / "feature" / "src" / "app.py"))
    check("a file inside a worktree checkout passes", result.returncode == 0, result.stderr)

    result = run_hook(decoy, workspace, str(workspace / ".claude" / "worktrees" / "feature" / ".claude" / "settings.json"))
    check("a worktree's OWN .claude/ is still protected", result.returncode == 2)

    result = run_hook(decoy, workspace, str(workspace / ".claude" / "projects" / "-a-project" / "memory" / "fact.md"))
    check("the auto-memory is still protected", result.returncode == 2)

    result = run_hook(decoy, workspace, str(workspace / ".claude" / "jobs.json"))
    check("a file merely named jobs.json under .claude/ is still protected",
          result.returncode == 2)

    # The handoffs carve-out (2026-08-31). The write that earned it is the
    # retiring agent's own next-step draft, which the handoff skill prescribes
    # at ~/.claude/handoffs/<seat>-next-step-<stamp>.md.
    result = run_hook(decoy, workspace,
                      str(workspace / ".claude" / "handoffs" / "merge-lane-next-step-20260831-043554.md"))
    check("a seat's handoff next-step draft passes", result.returncode == 0, result.stderr)

    result = run_hook(decoy, workspace, str(workspace / ".claude" / "handoffs" / "merge-lane-handoff.md"))
    check("a seat's live handoff file passes", result.returncode == 0, result.stderr)

    result = run_hook(decoy, workspace, str(workspace / ".claude" / "handoffs.md"))
    check("a file merely named handoffs.md under .claude/ is still protected",
          result.returncode == 2)

    result = run_hook(decoy, workspace,
                      str(workspace / ".claude" / "handoffs" / "seat" / "CLAUDE.md"))
    check("a CLAUDE.md under the handoffs carve-out is still protected (basename rule)",
          result.returncode == 2)

    worktree = workspace / ".claude" / "worktrees" / "some-worktree"
    result = run_hook(decoy, workspace, str(worktree / "docs" / "ordinary.md"))
    check("an ordinary file in a worktree passes (the plumbing prefix is not the checkout's .claude)",
          result.returncode == 0, result.stderr)
    result = run_hook(decoy, workspace, str(worktree / ".walk-approved"))
    check("a worktree's own approval marker passes (the circular-block bug)",
          result.returncode == 0, result.stderr)
    result = run_hook(decoy, workspace, str(worktree / ".claude" / "hooks" / "some-hook.py"))
    check("a worktree's own .claude machinery is still blocked", result.returncode == 2)

    # Reusable prompts (2026-09-29): a file named -prompt.md or -instructions.md
    # anywhere in a checkout, except where drafts and working files are written.
    result = run_hook(decoy, workspace, str(workspace / "docs" / "agents" / "fleet-instructions.md"))
    check("a seat brief in docs/agents/ is blocked", result.returncode == 2)
    check("the block says it is a reusable prompt", "reusable prompt" in result.stderr, result.stderr)
    check("the block sends a one-off prompt to the scratchpad", "scratchpad" in result.stderr,
          result.stderr)
    result = run_hook(decoy, workspace, str(workspace / "docs" / "agents" / "seat-first-prompt.md"))
    check("a first prompt in docs/agents/ is blocked", result.returncode == 2)
    skills = workspace / "nc-systems" / "skills" / "cold-read"
    result = run_hook(decoy, workspace, str(skills / "defect-hunt-prompt.md"))
    check("a skill prompt under nc-systems/skills/ is blocked", result.returncode == 2)
    result = run_hook(decoy, workspace, str(skills / "docs" / "cold-read-cell-instructions.md"))
    check("a skill's instructions in its docs/ are blocked", result.returncode == 2)
    result = run_hook(decoy, workspace, str(workspace / "nc-systems" / "handoff" / "handoff-prompt.md"))
    check("a program's prompt beside it is blocked", result.returncode == 2)
    result = run_hook(decoy, workspace,
                      str(worktree / "docs" / "agents" / "fleet-instructions.md"))
    check("a reusable prompt inside a worktree checkout is still blocked", result.returncode == 2)
    result = run_hook(decoy, workspace, str(skills / "cold-read-grid.py"))
    check("a skill's code passes", result.returncode == 0, result.stderr)
    result = run_hook(decoy, workspace, str(workspace / "nc-systems" / "handoff" / "defect-hunt.md"))
    check("a prompt without either ending, outside the reviewed homes, passes (guarded by name only)",
          result.returncode == 0, result.stderr)
    result = run_hook(decoy, workspace, str(workspace / "docs" / "prompt-writing-notes.md"))
    check("a file merely mentioning prompt passes", result.returncode == 0, result.stderr)
    result = run_hook(decoy, workspace, str(workspace / "docs" / "agents" / "queue" / "new-instructions.md"))
    check("a draft in docs/agents/queue/ passes", result.returncode == 0, result.stderr)
    result = run_hook(decoy, workspace, str(workspace / "docs" / "issues" / "queue" / "x-prompt.md"))
    check("a draft in docs/issues/queue/ passes", result.returncode == 0, result.stderr)
    result = run_hook(decoy, workspace, str(workspace / "nc-queue" / "x-prompt.md"))
    check("a note in nc-queue/ passes", result.returncode == 0, result.stderr)
    result = run_hook(decoy, workspace, str(workspace / "docs" / "drafts" / "x-instructions.md"))
    check("a draft in docs/drafts/ passes", result.returncode == 0, result.stderr)
    result = run_hook(decoy, workspace, str(workspace / ".claude" / "jobs" / "ab12" / "tmp" / "x-prompt.md"))
    check("a background job's scratch prompt passes", result.returncode == 0, result.stderr)
    outside = tmp / "scratchpad-outside-any-checkout"
    outside.mkdir()
    result = run_hook(decoy, workspace, str(outside / "subagent-prompt.md"))
    check("a one-off prompt outside any checkout passes", result.returncode == 0, result.stderr)
    marker = workspace / ".walk-approved"
    marker.write_text("y\n", encoding="utf-8")
    result = run_hook(decoy, workspace, str(workspace / "docs" / "agents" / "fleet-instructions.md"))
    check("an approved change to a reusable prompt passes once", result.returncode == 0, result.stderr)
    check("the marker is consumed by the prompt's pass", not marker.exists())

    # Reviewed documents (2026-09-30): an MD file the user reviews is known by
    # where it sits — docs/agents/, docs/nedschorus-wiki/, nc-systems/skills/ —
    # or, for a design, by its -design.md name wherever it sits. Drafts stay
    # free in the draft places; test-designs and design-contracts are left to
    # design-to-main's own acceptance states.
    reviewed_homes = [
        ("a doc in docs/agents/", workspace / "docs" / "agents" / "x.md"),
        ("a wiki page in docs/nedschorus-wiki/", workspace / "docs" / "nedschorus-wiki" / "x.md"),
        ("a skill's doc under nc-systems/skills/", skills / "docs" / "x.md"),
        ("a skill's design under nc-systems/skills/", skills / "docs" / "cold-read-design.md"),
        ("a skill MD without either prompt ending", skills / "defect-hunt.md"),
        ("a design GHI-MD in docs/issues/", workspace / "docs" / "issues" / "12-foo-design.md"),
        ("a landed design in its system's docs/",
         workspace / "nc-systems" / "handoff" / "docs" / "handoff-foo-design.md"),
        ("design-to-main's design", workspace / "docs" / "design-to-main" / "design-to-main-state-machine-design.md"),
        ("a design in a record-named directory below the checkout's top",
         workspace / "docs" / "cold-read-records" / "foo-design-2026-09-30" / "foo-design.md"),
    ]
    for label, target in reviewed_homes:
        result = run_hook(decoy, workspace, str(target))
        check(f"{label} is blocked", result.returncode == 2, str(result.returncode))
    result = run_hook(decoy, workspace, str(workspace / "docs" / "nedschorus-wiki" / "x.md"))
    check("the block says the user reviews every change here",
          "reviews every change" in result.stderr, result.stderr)
    check("the block names the marker", ".walk-approved" in result.stderr, result.stderr)
    check("the block sends a first draft to a draft place",
          "docs/drafts/" in result.stderr and "docs/nedschorus-wiki/queue/" in result.stderr,
          result.stderr)
    check("the block tells a subagent to report the change to the agent that dispatched it",
          "If he has not, show him the change and wait for his answer; if you are a subagent, "
          "report the change to the agent that dispatched you instead."
          in result.stderr.splitlines(), result.stderr)
    check("the block is one instruction per line", len(result.stderr.strip().splitlines()) == 4,
          result.stderr)
    draft_places = [
        ("a draft in docs/agents/queue/", workspace / "docs" / "agents" / "queue" / "x.md"),
        ("a draft in docs/nedschorus-wiki/queue/", workspace / "docs" / "nedschorus-wiki" / "queue" / "x.md"),
        ("a design draft in docs/issues/queue/", workspace / "docs" / "issues" / "queue" / "foo-design.md"),
        ("a design draft in docs/drafts/", workspace / "docs" / "drafts" / "foo-design.md"),
        ("a design draft in nc-queue/", workspace / "nc-queue" / "foo-design.md"),
    ]
    for label, target in draft_places:
        result = run_hook(decoy, workspace, str(target))
        check(f"{label} passes", result.returncode == 0, result.stderr)
    not_reviewed = [
        ("a system's doc that is not a design", workspace / "nc-systems" / "handoff" / "docs" / "x.md"),
        ("a test-design", workspace / "docs" / "issues" / "12-foo-test-design.md"),
        ("a design-contract", workspace / "docs" / "issues" / "12-foo-contract.md"),
        ("a skill's test-design under nc-systems/skills/", skills / "docs" / "cold-read-test-design.md"),
        ("a skill's design-contract under nc-systems/skills/", skills / "docs" / "cold-read-contract.md"),
        ("a name ending design.md without the hyphen", workspace / "docs" / "issues" / "12-redesign.md"),
        ("a reviewed home's path below the checkout's top",
         workspace / "tools" / "docs" / "nedschorus-wiki" / "x.md"),
        ("a GHI-MD that is not a design", workspace / "docs" / "issues" / "12-foo.md"),
        ("a walk file", workspace / "docs" / "walk" / "x.md"),
        ("a skill's code", skills / "x.py"),
        ("a non-MD file in a reviewed home", workspace / "docs" / "nedschorus-wiki" / "diagram.png"),
        ("a design's frozen copy in a cold-read record",
         workspace / "cold-read-records" / "foo-design-2026-09-30" / "foo-design.md"),
        ("a design's frozen copy in a sanity-check record",
         workspace / "sanity-check-records" / "2026-09-30-foo-design" / "foo-design.md"),
        ("a design's frozen copy in an md-review record",
         workspace / "md-review-records" / "foo-design-2026-09-30" / "foo-design.md"),
    ]
    for label, target in not_reviewed:
        result = run_hook(decoy, workspace, str(target))
        check(f"{label} passes", result.returncode == 0, result.stderr)
    result = run_hook(decoy, workspace, str(workspace / "docs" / "agents" / "fleet-instructions.md"))
    check("a reusable prompt in a reviewed home keeps the reusable-prompt message",
          "reusable prompt" in result.stderr, result.stderr)
    reviewed_worktree = workspace / ".claude" / "worktrees" / "a-real-worktree"
    make_checkout(reviewed_worktree)
    result = run_hook(decoy, workspace, str(reviewed_worktree / "docs" / "nedschorus-wiki" / "x.md"))
    check("a reviewed document inside a worktree checkout is blocked", result.returncode == 2)
    result = run_hook(decoy, workspace, str(outside / "foo-design.md"))
    check("a design outside any checkout passes", result.returncode == 0, result.stderr)
    marker = workspace / ".walk-approved"
    marker.write_text("y\n", encoding="utf-8")
    result = run_hook(decoy, workspace, str(workspace / "docs" / "issues" / "12-foo-design.md"))
    check("an approved change to a reviewed document passes once", result.returncode == 0, result.stderr)
    check("the marker is consumed by the document's pass", not marker.exists())

    result = run_hook(decoy, workspace, "")
    check("a payload without a file path passes", result.returncode == 0)

    # The approval lane: the marker lives in the SESSION'S checkout.
    marker = workspace / ".walk-approved"
    marker.write_text("user approved: add the naming line (2026-08-07)\n", encoding="utf-8")
    result = run_hook(decoy, workspace, str(workspace / "CLAUDE.md"))
    check("an approved change passes once", result.returncode == 0, result.stderr)
    check("the marker is consumed by the pass", not marker.exists())
    result = run_hook(decoy, workspace, str(workspace / "CLAUDE.md"))
    check("the next unapproved change is blocked again", result.returncode == 2)
    check("the decoy's stale marker still survives untouched", decoy_marker.exists())

    marker.write_text("   \n", encoding="utf-8")
    result = run_hook(decoy, workspace, str(workspace / "CLAUDE.md"))
    check("an empty marker does not approve", result.returncode == 2)
    marker.unlink()

    # A linked worktree marks its root with a .git FILE, not a directory.
    linked_worktree = tmp / "linked-worktree"
    linked_worktree.mkdir()
    (linked_worktree / ".git").write_text("gitdir: /somewhere/.git/worktrees/linked\n", encoding="utf-8")
    (linked_worktree / ".walk-approved").write_text("user approved: the worktree edit\n", encoding="utf-8")
    result = run_hook(decoy, linked_worktree, str(linked_worktree / "CLAUDE.md"))
    check("a linked worktree's root is found through its .git file", result.returncode == 0, result.stderr)

    # A session seated in no checkout at all: the marker falls back to the
    # target file's own repository root.
    nowhere = tmp / "not-a-checkout"
    nowhere.mkdir()
    result = run_hook(decoy, nowhere, str(workspace / "CLAUDE.md"))
    check("no-checkout session with no marker is blocked", result.returncode == 2)
    marker.write_text("user approved: the cross-tree edit\n", encoding="utf-8")
    result = run_hook(decoy, nowhere, str(workspace / "CLAUDE.md"))
    check("no-checkout session falls back to the target's repository marker",
          result.returncode == 0, result.stderr)
    check("the fallback marker is consumed", not marker.exists())

    # --- NotebookEdit carries its target in notebook_path (PR #86's review) ---
    # The guard is registered on NotebookEdit, so reading only file_path left
    # every notebook write unguarded — it saw no target and passed.
    result = run_hook(decoy, workspace, str(workspace / ".claude" / "notes.ipynb"),
                      path_field="notebook_path")
    check("a notebook write under .claude/ is blocked through notebook_path",
          result.returncode == 2, result.stderr)
    result = run_hook(decoy, workspace, str(workspace / "CLAUDE.md"),
                      path_field="notebook_path")
    check("a notebook write to an instruction file is blocked through notebook_path",
          result.returncode == 2, result.stderr)
    result = run_hook(decoy, workspace, str(workspace / "docs" / "ordinary.ipynb"),
                      path_field="notebook_path")
    check("an ordinary notebook still passes through notebook_path",
          result.returncode == 0, result.stderr)

    # --- The session's checkout decides, even when the target has one too ----
    # The discriminating case PR #86's review found missing: BOTH roots exist
    # and BOTH hold a marker, so an implementation resolving from the target
    # instead of the session still passes every other case in this file.
    other_checkout = tmp / "another-checkout"
    make_checkout(other_checkout)
    other_marker = other_checkout / ".walk-approved"
    other_marker.write_text("approval belonging to the other checkout\n", encoding="utf-8")
    session_marker = workspace / ".walk-approved"
    session_marker.write_text("user approved: the cross-checkout edit\n", encoding="utf-8")
    result = run_hook(decoy, workspace, str(other_checkout / "CLAUDE.md"))
    check("a write into another checkout is approved by the SESSION's marker",
          result.returncode == 0, result.stderr)
    check("the session's marker is the one consumed", not session_marker.exists())
    check("the target checkout's own marker is left untouched", other_marker.exists())
    other_marker.unlink()

    # --- A working directory that no longer exists must refuse, not fall back -
    # A seat whose worktree was removed under it still sends its old cwd. The
    # fallback is for a session seated OUTSIDE any checkout, which is a real
    # place; a vanished directory is a broken payload, and falling back let it
    # spend a marker sitting in the target's repository.
    vanished = tmp / "removed-worktree"
    make_checkout(vanished)
    vanished_target_marker = workspace / ".walk-approved"
    vanished_target_marker.write_text("user approved: something else entirely\n",
                                      encoding="utf-8")
    import shutil as _shutil
    _shutil.rmtree(vanished)
    result = run_hook(decoy, vanished, str(workspace / "CLAUDE.md"))
    check("a session whose working directory no longer exists is refused",
          result.returncode == 2, result.stderr)
    check("the refusal says the working directory is the problem",
          "working directory" in result.stderr, result.stderr)
    check("a marker in the target's repository is NOT spent by that refusal",
          vanished_target_marker.exists())
    vanished_target_marker.unlink(missing_ok=True)

    # --- An empty .git is not a checkout (Codex sandbox debris) ---------------
    # A `:workspace` Codex run on ned-box leaves an empty /tmp/.git, and a
    # guard that counted any .git took /tmp for a checkout: PR 765's head run
    # and main's run after PR 800 failed this file's cases for that alone.
    # debris_root stands in for /tmp.
    debris_root = tmp / "tmp-with-codex-sandbox-debris"
    (debris_root / ".git").mkdir(parents=True)
    scratch_under_debris = debris_root / "a-subagent-scratchpad"
    scratch_under_debris.mkdir()
    result = run_hook(decoy, workspace, str(scratch_under_debris / "subagent-prompt.md"))
    check("a one-off prompt under an empty .git passes, being outside any checkout",
          result.returncode == 0, result.stderr)
    marker = workspace / ".walk-approved"
    marker.write_text("user approved: the edit from a scratch session\n", encoding="utf-8")
    result = run_hook(decoy, scratch_under_debris, str(workspace / "CLAUDE.md"))
    check("a session under an empty .git falls back to the target's repository marker",
          result.returncode == 0, result.stderr)
    check("that fallback marker is consumed", not marker.exists())
    marker.unlink(missing_ok=True)

    # A .git directory holding HEAD still marks a checkout, as a .git file does
    # (the linked-worktree case above).
    head_checkout = tmp / "checkout-whose-git-holds-head"
    make_checkout(head_checkout)
    (head_checkout / ".walk-approved").write_text("user approved: the head-checkout edit\n",
                                                  encoding="utf-8")
    result = run_hook(decoy, head_checkout, str(head_checkout / "CLAUDE.md"))
    check("a .git directory holding HEAD marks a checkout", result.returncode == 0, result.stderr)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
