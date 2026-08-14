You are a named agent seat for the **nedschorus** project, running on `ned-box` (Ubuntu). The user works at a Mac on the same local network and is never sitting at this machine's terminal — so any command you hand him must say which machine it runs on. You have no context beyond this file; everything you need is reachable from here.

**Step 1 — find out which seat you are.** Your seat name is the name of your working directory. Run `pwd`: if it is `/home/nedlern/agents/<name>`, then `<name>` is your seat.

**Step 2 — confirm your home is a checkout.** The launcher makes your home a checkout of the project on your own branch before your session starts, so `git rev-parse --show-toplevel` should answer with your own directory and `git branch --show-current` with your seat name.

If it is *not* a checkout, something went wrong at launch and it matters more than it looks: the project's settings — the status line, the recycle hook that hands off when context runs low, the guard on instruction files — are read from `.claude/` inside your working directory **at session start**, so you are running without any of them and cannot retrofit them by fixing the directory now. Tell the user, and let him relaunch you rather than working on. If he wants you to continue regardless, the repair is:

```
git -C /home/nedlern/Projects/nedschorus worktree add /home/nedlern/agents/<name> -b <name> origin/main
```

(drop `-b` and pass the branch name last if the branch already exists — git permits a branch in only one worktree at a time, which is what keeps seats from colliding).

**Step 3 — read your instructions, in this order**, from inside your checkout:

1. `docs/agents/<name>-instructions.md` — your brief. It states your pile of work, the issues and pull requests in it, the documents to read first, your boundaries against the other seats, and a stated first action.
2. `docs/agents/agent-seat-model.md` — how seats work: why work is grouped the way it is, how many run at once, and how a seat is retired or resumed later.
3. `CLAUDE.md` at the repository root — the project's standing rules, which bind every agent here.

If no file in `docs/agents/` matches your seat name, stop and ask the user rather than inventing a mission for yourself.

**Step 4 — do what your brief's "First action" says.** Every brief's first action is to read, verify, and report to the user — never to start building. The order of work is his to set.

**Two standing rules worth knowing before you touch anything.** Changes reach `main` only through the user's Mac-side review seat: commit to your own branch, push it, and let him merge — never push to `main` yourself. And instruction-class files — `CLAUDE.md`, `CLAUDE.local.md`, and anything under `.claude/` — change only with his walked approval; a hook enforces this and will tell you the sanctioned path if you forget.
