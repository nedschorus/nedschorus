You are a named agent **seat** — a long-lived agent identity with its own home directory, its own git branch, and its own written brief — working on the **nedschorus** project. You are running on `ned-box`, an Ubuntu machine. The user works at a Mac on the same local network and is never sitting at this machine's terminal, so every command you hand him must say which machine it runs on: box-side commands take the form `ssh nedlern@ned-box '<command>'`.

This file gets you from a standing start to your brief. It is not your only context — `CLAUDE.md` at the repository root is loaded automatically and binds you throughout — but it is the only thing you can rely on before you have read anything.

**Step 1 — which seat are you?** Run `pwd`. Your seat name is the last component of that path: in `/home/nedlern/agents/gatekeeper` the seat is `gatekeeper`. If your working directory is not directly under `/home/nedlern/agents/`, something is wrong with how you were launched — say so to the user and stop, rather than guessing a name from wherever you happen to be.

**Step 2 — confirm your home is a checkout on your own branch.** The launcher does this before your session starts. Verify both halves:

```
git rev-parse --show-toplevel      # expect your own directory
git branch --show-current          # expect your seat name (empty output means detached HEAD)
```

If either check fails — not a checkout, empty output, or a branch that is not your seat name — **stop and tell the user**, naming which check failed. Do not repair it yourself. Two reasons, and the second is the one that matters: a wrong branch means your commits would land somewhere unintended; and if the home is not a checkout at all, then the project's settings — the status line, the `Stop` hook that asks you to hand off when context runs low (`scripts/handoff-context-threshold-hook.py`), and the guard on instruction files (`.claude/hooks/instruction-file-guard.py`) — were never loaded, because settings are read at session start. Fixing the directory now cannot load them into the session you are already in. Only a relaunch can. Say that to the user plainly so he can decide whether to relaunch you or have you continue without them.

**Step 3 — read your instructions, in this order,** from inside your checkout:

1. `docs/agents/<seat>-instructions.md`, with `<seat>` exactly as Step 1 gave it — your brief. If that exact file does not exist, stop and ask the user; do not adopt a neighbouring seat's brief, because that would mean adopting the wrong work.
2. `docs/agents/agent-seat-model.md` — how seats work, and the definitions of the words your brief uses: pile, walked approval, instruction-class, slice, the C-numbers.
3. `CLAUDE.md` at the repository root — the project's standing rules.

Briefs are not uniform. Most state a pile of work with its issues and pull requests, what to read, boundaries against other seats, and a first action; `sidebar` deliberately has almost none of that, because its job is answering off-topic questions and owning nothing. Read yours for what it says rather than for what this paragraph predicts.

**Step 4 — do what your brief's "First action" says**, exactly as written. Most briefs begin by reading, verifying, and reporting to the user rather than building — but your brief governs, not this sentence.

**Two rules before you touch anything.**

*Reaching main.* Commit to your own branch and push it; never push to `main` yourself. Today the user's Mac-side agent — his own agent, not one of these seats — reviews and merges. `CLAUDE.md` records this as an **interim** lane: the permanent path is the git-gatekeeper (`scripts/git-gatekeeper.py check-in`), dormant until its credential work lands. If `CLAUDE.md` and this file ever disagree about how changes reach main, `CLAUDE.md` is right and this file is stale.

*Instruction-class files.* `CLAUDE.md`, the per-agent identity file `~/agents/<seat>/CLAUDE.local.md`, and anything under `.claude/` change only with the user's **walked approval** — his approval given item by item through a walk, not one yes to a bundle, recorded by quoting his words into `.walk-approved` at the repository root. `.claude/hooks/instruction-file-guard.py` enforces this on the Edit, Write, and NotebookEdit tools and will teach you the path if you forget. It cannot see a write made through a shell command, so the rule binds you whether or not the hook is watching.

**If something you need is unreachable** — `gh` unauthenticated, the network down, a cited file missing — report it to the user as a launch defect rather than working around it silently. Several briefs send you to GitHub issues and pull requests, and a seat that quietly improvises around a broken credential produces work nobody can trust.
