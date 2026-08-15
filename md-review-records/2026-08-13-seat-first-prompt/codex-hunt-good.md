<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/seat-first-prompt.md -->

1. “The user works at a Mac on the same local network and is never sitting at this machine's terminal”

   “Never” is an unlimited claim about future user behavior. An ordinary counterexample is the user accessing `ned-box` locally through its console or a KVM. The command-labeling rule can remain applicable, but this factual premise cannot be guaranteed and may cause an agent to discount contrary information from the user. Confidence: unsure — this may be a deliberately maintained operating invariant, but the file states no boundary or enforcement that makes “never” reliable.

2. “You have no context beyond this file; everything you need is reachable from here.”

   The first clause is literally false in the stated execution context: the checkout’s `CLAUDE.md`, platform instructions, and tool context also exist. It supports incompatible readings—either “no prior project/task context” or “disregard every other source of context.” The second clause conflicts with the later missing-brief case, where the mission must be obtained from the user, and with the undefined “walked approval” procedure. An agent may discard binding context or assume an unresolved concept must somehow be inferable. Confidence: sure.

3. “Your seat name is the name of your working directory. Run `pwd`: if it is `/home/nedlern/agents/<name>`, then `<name>` is your seat.”

   This seat-discovery mechanism defines only its successful branch. If `pwd` returns a subdirectory, a symlinked path, or any path outside that exact pattern, the file neither derives a seat nor tells the agent to stop. Step 2 can still find a valid checkout, leaving `<name>` unresolved and making the seat-specific brief path unexecutable. Confidence: sure.

4. “**Step 2 — confirm your home is a checkout.** The launcher makes your home a checkout of the project on your own branch before your session starts”

   “Your home” conflicts with the ordinary Unix meaning of `$HOME`, which is `/home/nedlern`, while the intended checkout appears to be the current directory `/home/nedlern/agents/<name>`. The launcher changes the working directory but does not redefine `$HOME`. The later phrase “your own directory” does not resolve this. A literal reader may inspect the wrong directory or misunderstand which path the launcher owns. Confidence: sure.

5. “The launcher makes your home a checkout of the project on your own branch before your session starts” and “`docs/agents/agent-seat-model.md` — how seats work”

   The explicitly designated seat model says the opposite: “The launcher creates that home as an **empty directory, not a checkout**; the first-prompt file has the agent make it one on its first run.” The referenced launcher script agrees with this prompt rather than that model, so the authoritative context supplied by this file contains irreconcilable startup descriptions. Under the model’s description, every correct first launch looks like the failure described here and can enter a relaunch loop. Confidence: sure.

6. “`git rev-parse --show-toplevel` should answer with your own directory and `git branch --show-current` with your seat name.” / “If it is *not* a checkout, something went wrong at launch”

   Step 2 checks three conditions: a checkout exists, its top level is the intended directory, and its branch matches the seat. The failure procedure covers only the first. A different repository, a wrong branch, or a detached HEAD is still “a checkout,” so the agent receives no stopping point or next action and may read or change the wrong branch. Confidence: sure.

7. “If he wants you to continue regardless, the repair is:”

   “The repair” has two incompatible scopes. It may mean repairing the missing checkout, or repairing the session’s missing project settings. The preceding sentence says the latter “cannot” be retrofitted, while the unlabeled command immediately following can look like it does exactly that. An agent may continue believing the hooks and status configuration are now active when only the filesystem checkout has changed. Confidence: unsure — “continue regardless” hints that the settings remain absent, but the object of “repair” is never stated.

8. “drop `-b` and pass the branch name last if the branch already exists”

   Applied mechanically to the displayed command, dropping only `-b` leaves both `<name>` and `origin/main`; moving `<name>` last produces another invalid argument order. The intended Git form requires deciding that `origin/main` is replaced, not merely moving or appending the branch name, but the sentence never says that. The two plausible literal transformations fail differently. Confidence: sure.

9. “git permits a branch in only one worktree at a time, which is what keeps seats from colliding”

   Git’s restriction is not absolute: `git worktree add --force` can override the ordinary checked-out-branch refusal. It also prevents only simultaneous ordinary checkout of the same branch; seats on separate branches can still make conflicting changes or race remote operations. Treating this as the mechanism that keeps seats from all forms of collision overstates both the invariant and its coverage. Confidence: sure.

10. “**Step 3 — read your instructions, in this order**” followed by the brief first and `docs/agents/agent-seat-model.md` second

   The `fleet` brief explicitly says, “Read [the seat model](agent-seat-model.md) first.” A `fleet` agent cannot obey both orders: it must read the brief before discovering the brief’s instruction that the model was supposed to be read first. Confidence: sure.

11. “It states your pile of work, the issues and pull requests in it, the documents to read first, your boundaries against the other seats, and a stated first action.”

   This generic description is false for briefs the prompt can select. `sidebar-instructions.md` expressly says that seat owns nothing and lists no issues or pull requests; several other briefs do not contain both issues and pull requests. A zero-context agent may conclude that a valid brief is incomplete or that it has missed an unstated work inventory. Confidence: sure.

12. “Every brief's first action is to read, verify, and report to the user”

   `sidebar-instructions.md` instead says: “Greet the user briefly and ask what he needs. No status report, no inventory, no plan.” It requires neither reading nor verification and expressly excludes a status report. The universal description therefore conflicts with one of the briefs this prompt directs agents to obey. Confidence: sure.

13. “The order of work is his to set.”

   “Order of work” can mean user-selected priority among feasible items or literal sequencing of all work. The latter conflicts with briefs that declare dependency ordering, notably the gatekeeper’s “road, in order,” where downstream steps wait on the evidence format. Taken literally, the user could select work whose stated prerequisites are absent. Confidence: unsure — “order” may be intended only as backlog priority, but that limitation is unstated.

14. “Changes reach `main` only through the user's Mac-side review seat: commit to your own branch, push it, and let him merge”

   This duplicates the checkout rule for how changes reach `main` but omits its temporal limitation and conflicts with its permanent mechanism. `CLAUDE.md` says: “How a change reaches main: the git-gatekeeper (`scripts/git-gatekeeper.py check-in` …) is the permanent path” and then identifies Mac-side review as only the interim lane “Until its credential work lands.” Calling the interim lane a standing “only” path makes this prompt stale as soon as the gatekeeper activates. “Let him merge” also leaves the executor ambiguous between the user personally and the Mac-side agent that `CLAUDE.md` says performs the merge. Confidence: sure.

15. “instruction-class files — `CLAUDE.md`, `CLAUDE.local.md`, and anything under `.claude/`”

   “Anything” is broader than the actual defined guard scope. The referenced guard explicitly identifies `.claude/worktrees/` and `.claude/jobs/` as carve-outs that are working space rather than instruction machinery. A file under either is an ordinary counterexample. The statement can make agents seek approval for temporary harness state and falsely believe all such paths are guarded. Confidence: sure.

16. “change only with his walked approval”

   “Walked approval” is project-specific terminology with no definition or executable procedure in this file: it does not state what a walk consists of, what constitutes approval, what artifact records it, or when the process ends. Some seat briefs mention a `.walk-approved` marker, but the generic prompt does not ensure that every seat receives that explanation, and the hook’s message appears only after an attempted protected edit. A zero-context agent cannot knowingly comply before editing. Confidence: sure.

17. “a hook enforces this and will tell you the sanctioned path if you forget”

   The hook does not enforce the stated rule generally. Its own source calls it a “Soft block, not a wall”; its settings invoke it only for `Edit`, `Write`, and `NotebookEdit`, so an ordinary shell redirection or `sed -i` write bypasses it. It also accepts any nonempty `.walk-approved` marker without verifying that its contents came from the user. In those cases it neither enforces approval nor tells the agent anything. “Sanctioned path” is additionally ambiguous between a filesystem path and a workflow. Confidence: sure.

clean sections: none
