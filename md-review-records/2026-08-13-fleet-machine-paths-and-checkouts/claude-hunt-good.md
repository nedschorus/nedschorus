<!-- provenance: runtime=claude model=claude-opus-5 effort=high cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/cross-project/fleet-machine-paths-and-checkouts.md -->

Read both files in full and verified the file's factual claims against the box (worktree list, `~/.claude/handoffs`, `scripts/`, the cited test, `git-gatekeeper.py`). No edits made.

## Findings

**1. Frontmatter `verified-as-of: 2026-08-13` vs. the Mac section's disclaimer**
> `verified-as-of: 2026-08-13`
> …"the remaining rows follow the same conventions and **have not been inspected from the box**."

The frontmatter makes a document-wide verification claim; the Mac section admits three of its four rows are unverified convention. The Ubuntu section separately re-states "Verified 2026-08-13." — so within the file, "verified" means two different scopes. Harm: an agent trusting the frontmatter treats `/Users/el/agents/<name>`, `/Users/el/Projects/nedschorus/.claude/worktrees/<name>`, and `/Users/el/.claude/handoffs/…` as checked facts and hands the user a path that may not exist on his Mac — precisely the failure the document exists to prevent. Nothing in the file says which rows the frontmatter date covers. Sure.

**2. "every … lives on each machine" overstates the tables' coverage**
> "Where **every** working copy, agent home, and handoff file lives on **each machine** of the nedschorus fleet"

Counterexamples inside the file itself: the Mac table has no rows for user-level instructions or auto-memory, both of which the Ubuntu table lists; and neither table lists supervisor lock or state files, though the file later names "supervisor locks" as per-machine state. Verified on the box: `~/.claude/handoffs/` also holds `choirmaster-supervisor-state.json` and `choirmaster-supervisor.lock`, which the tables never mention. Harm: an agent treating the tables as exhaustive concludes an unlisted artifact doesn't exist, or that it is safe to delete the handoffs directory's contents. Sure.

**3. "this rule" has no antecedent that is stated as a rule**
> "The user-level instruction file on the box (`/home/nedlern/.claude/CLAUDE.md`) carries the short form of **this rule** for every session; this document is the full map behind it."

The preceding paragraph states an observation ("Naming the machine is not pedantry here"), never an imperative. A reader cannot tell whether the rule is "name the machine when giving a command", "run pulls on the box", or something broader, and therefore cannot tell what this document is the "full map" of. Harm: an agent asked to keep the two files in sync has no way to know which part of the short form this file is responsible for. Sure that the antecedent is missing; unsure how much it matters given the CLAUDE.md text is loaded per-session.

**4. "Nothing but git branches crosses between them" is contradicted three ways inside the file's own context**
> "**Nothing but git branches crosses between them**, and only when pushed — worktrees, handoff files, locks, and credentials are per-machine and **never travel**."

(a) The command table has the Mac typing `ssh nedlern@ned-box 'git -C ~/Projects/nedschorus pull'` and running `launch-claude-ubuntu <name>` to "Reach a named agent on the box" — commands, terminal I/O, and an interactive agent session cross between the machines. (b) The file explicitly references `/home/nedlern/.claude/CLAUDE.md`, which states "The Mac mounts this box's home as `/Volumes/nedhome/...`" — so the box's handoff files, locks, and worktrees are directly readable from the Mac; they do travel, over a filesystem mount. Harm: an agent obeying this literally will reject a correct plan ("read the box's handoff file from the Mac", "ssh across to check state") as impossible, and will assume any state seen on one machine cannot have originated on the other. Sure.

**5. "The Mac runs agents only when the work needs to be where the user is" vs. the merge seat**
> "The Mac runs agents **only** when the work needs to be where the user is — its browser session, its keychain, its GUI, or files that exist only there. The Mac is **also the review-and-merge seat**."

The very next sentence gives a standing Mac agent role whose stated cause is branch protection, not user presence — a counterexample to the "only" in the same paragraph, unless "its keychain" is silently meant to cover the merge credential, which the file does not say. Harm: an agent deciding where to place work has two incompatible rules for the same decision. Sure that the two sentences conflict; unsure whether "keychain" was intended to absorb the case.

**6. `NedLern` is undefined, and the inference to "from the Mac" rests on an unstated premise**
> "branch protection admits only `NedLern`, so merges to `main` happen from the Mac."

`NedLern` appears once, with no statement of what kind of identity it is (GitHub account? SSH key? the user himself?), where it is configured, or how to check it. The "so" does not follow from anything in the file: admitting only `NedLern` implies merges happen from the Mac only if that identity's credential exists nowhere else, which the file never asserts. Harm: an agent that later obtains a `NedLern` credential on the box cannot tell whether merging from the box is forbidden or merely not yet arranged.

This also sits against the checkout's CLAUDE.md, which defines a different permanent answer to the same question:
> CLAUDE.md: "How a change reaches main: the git-gatekeeper … is the permanent path — one program, one credential, one door; agents never push to main. Until its credential work lands (activation waits on build slice 6), the gate is dormant and the interim lane applies … the user's Mac-side agent reviews and merges."
> this file: "The Mac is also the review-and-merge seat: branch protection admits only `NedLern`, so merges to `main` happen from the Mac."

This file states the Mac-seat arrangement as an unconditional property of branch protection, with no mention of the gatekeeper, the dormancy, or the interim/permanent distinction. Harm: a future agent reading this file as the fleet map takes the interim lane for the permanent design and will not recognise that it expires when the gatekeeper's credential work lands. Sure.

**7. The one-worktree-per-branch rule is asserted as a guarantee it does not provide**
> "**Git allows a branch to be checked out in only one worktree at a time**, which is **the mechanism that keeps parallel agents from editing one branch's files: git refuses before they get the chance**."

Ordinary counterexamples: `git worktree add --force` overrides the check outright; a detached-HEAD worktree at the same commit gives a second editable copy of the same files with no refusal; and, most directly, git's check fires only at worktree-creation time — nothing stops two agents (or a background job and a session) from editing files inside one existing worktree, which is the ordinary way parallel work collides. Harm: an agent that believes git structurally prevents concurrent edits will skip the coordination that actually prevents them, and will misread a conflicting edit as impossible rather than as the expected outcome. Sure.

**8. "All working copies … are the same repository viewed at different branches" conflicts with agent homes being plain directories, and with the table's Branch column**
> "**All working copies on a machine are the same repository** viewed at different branches, sharing one object store through git worktrees."
> "**Agent homes** … Created by the launchers (**as a plain directory**) and made a checkout deliberately with `git worktree add` when the agent works on the repository."
> table: "Agent home — the founding seat | `/home/nedlern/agents/choirmaster` | `choirmaster`" and "Agent homes — general | `/home/nedlern/agents/<name>` | **per agent**"

A freshly-launched agent home is, by the file's own account, not a working copy and is on no branch — yet it is listed under "Three kinds of checkout" and the table assigns every one of them a branch. The file gives no way to tell which state a given home is in. Harm: an agent runs `git -C /home/nedlern/agents/<name> …` expecting the documented branch and gets a not-a-repository error, or assumes a home is safe to `git worktree remove` when it is an ordinary directory holding uncommitted files. (Observed on the box today, all three homes happen to be worktrees — which makes the discrepancy invisible until a new agent is launched.) Sure.

**9. "made a checkout deliberately with `git worktree add`" is not executable as written**
> "Created by the launchers (as a plain directory) and **made a checkout deliberately with `git worktree add`** when the agent works on the repository."

No actor (the launcher? the agent itself? the user?), no trigger point, no command form — from which checkout is `git worktree add` run, is the branch created or expected to exist, and what is it named relative to the agent name? Nor is there a way to test whether the step has already been done. Harm: the step is either skipped or performed inconsistently, producing agent homes on ad-hoc branch names that the table's "per agent" row then misdescribes. Sure.

**10. "This is what `git pull` updates" is false read literally**
> "**The main checkout** — the machine's primary working copy, parked on `main`. **This is what `git pull` updates**"

`git pull` updates whichever working copy it is run in; a task worktree or agent home updates the same way. The sentence reads as a property of the command rather than of where it is typed — which is the exact confusion the incident in the opening paragraph is about, where a `git pull` "intended for the Ubuntu checkout ran on the Mac instead". Harm: an agent infers that any `git pull` it runs has refreshed the main checkout, and reports the box current when it refreshed a task worktree's branch instead. Sure.

**11. "the instruction-file guard's worktree bug" is an unresolvable reference**
> "A stale main checkout means stale hooks, which is how **the instruction-file guard's worktree bug** outlived its fix by a day."

No path, no file, no issue number, no description of the bug or the guard. Nothing in this file or in CLAUDE.md defines "the instruction-file guard". Harm: an agent cannot check whether the bug or its fix still matters, cannot find the guard to inspect its current state, and cannot judge whether the staleness hazard being illustrated still exists. Sure.

**12. "removed when the job ends" contradicts "the directory afterwards is litter" and the prune row**
> "**Task worktrees** — disposable … created by the harness when a session isolates itself and **removed when the job ends**. Their value leaves as pushed commits; **the directory afterwards is litter**."
> command table: "Clear stale worktree registrations | either | `git … worktree prune`"

If removal is automatic at job end there is no "afterwards" and no litter to clear; if litter accumulates, removal is not automatic. Verified on the box: `/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation` is registered and populated right now, and holds untracked directories. Harm: an agent cannot tell whether cleanup is its responsibility, and either deletes a worktree another session is using or leaves growth it believes the harness handles. Sure.

**13. "Their value leaves as pushed commits" leaves the unpushed case unhandled**
> "**Their value leaves as pushed commits;** the directory afterwards is litter."

The mechanism is stated only for the success path. A task worktree that ends with uncommitted changes, with commits made but not pushed, or with a push rejected, is a reachable and ordinary case — and under the litter framing its directory is then discardable, taking the work with it. The file neither states what happens nor rules the case out. Harm: silent loss of work at exactly the moment it is hardest to notice, since the worktree name says nothing about its state. Sure.

**14. Task worktrees are nested inside the main checkout with no note of the consequence**
> "Task worktrees | `/home/nedlern/Projects/nedschorus/.claude/worktrees/<name>` | per job"

These directories sit inside the main checkout's own working tree. The file elsewhere treats the main checkout as the thing that must be kept clean and current ("This is what `git pull` updates", "A stale main checkout means stale hooks") without saying that its status output and any cleanup performed there now contain other agents' live worktrees. Harm: routine hygiene in the main checkout (`git clean -fd`, a status-based "is it clean?" gate, an aggressive stash) reaches into running task worktrees. Unsure only about whether git's own worktree-awareness already covers every such case; the reader is given nothing either way.

**15. The documented handoff filename pattern matches no file that exists**
> "Handoff files | `/home/nedlern/.claude/handoffs/<agent>-handoff.md` | —"

Verified on the box today: that directory contains `choirmaster-handoff-0003.md`, `choirmaster-handoff-0004.md`, `choirmaster-dialog-0003.md`, `choirmaster-handoff-retired-2026-08-14.md`, `ec9045a3-…-handoff-asked`, `choirmaster-supervisor-state.json`, `choirmaster-supervisor.lock`. Nothing named `<agent>-handoff.md` exists. The pattern omits the numbered sequence, the dialog and retired variants, the session-id-keyed file, and the supervisor state/lock — and the file gives no rule for which of them is current. Harm: an agent told to read "the handoff file" for an agent either finds nothing at the documented path, or picks an arbitrary one of five and resumes from a retired or superseded handoff. This is the row a successor session most needs, and it is under a `verified-as-of: 2026-08-13` header. Sure.

**16. The legacy-system row conflicts with the checkout's CLAUDE.md, and misuses the Branch column**
> this file: "Legacy reference system | `/home/nedlern/Projects/nedlern` | **absent on this box**"
> CLAUDE.md: "The legacy system at `~/Projects/nedlern` is read-only reference: **read anything there freely**; NOT: modify anything there or execute its code."

CLAUDE.md grants an unconditional read permission over a path this file says does not exist here (confirmed: no such directory). Neither file acknowledges the other's position, so an agent that follows CLAUDE.md and gets ENOENT cannot tell whether the checkout is broken, whether it is on the wrong machine, or whether the instruction is simply stale. Separately, the value "absent on this box" occupies the **Branch** column, whose other entries are branch names — so the table's column meaning does not hold for every row, and a reader or script consuming the Branch column gets prose. Sure.

**17. The `--import` paragraph is not executable from this file, and describes flags that do not exist in that form**
> "the git-gatekeeper's **`--import` machinery** refuses **`import-invalid`** ("not a readable git repository") until one exists, which is **a named refusal rather than a failure**. **Clone it only when an import is actually needed.**"

Four gaps. (a) No path to the gatekeeper or its specification is given in this file; the reader must already know it (CLAUDE.md happens to supply `scripts/git-gatekeeper.py` and `docs/cross-project/git-gatekeeper-design.md`, but this file does not point there). (b) There is no `--import <path>` flag; the actual interface is `--import none` or the triple `--import-commit`/`--import-source`/`--import-dest`, and the "not a readable git repository" refusal is raised against whatever `--import-source` names — not against `/home/nedlern/Projects/nedlern` specifically. As written, an agent expects the refusal to be tied to the legacy path and will misdiagnose the same refusal when it fires on some other source. (c) "a named refusal rather than a failure" — the distinction is doing the load-bearing reassurance work here and is defined nowhere in this file. (d) "Clone it only when an import is actually needed" gives no source to clone from, no destination beyond the table row, and no definition of "an import" — so the instruction cannot be carried out and has no test for when it applies. Sure on (b) (checked against `scripts/git-gatekeeper.py`); sure on (a), (c), (d) as stated.

**18. "pinned by the repository's own tests" is not what that test does**
> "The checkout path is **pinned by the repository's own tests** (`scripts/handoff-extract-conversation-test.py`); the remaining rows follow the same conventions"

Checked: the only occurrence is a check that `project_directory_for_working_directory(Path("/Users/el/Projects/nedschorus")).name == "-Users-el-Projects-nedschorus"`. That function is pure string mangling — it never touches the filesystem. The path is a sample input, not a constraint: if the Mac checkout moved tomorrow, the test would still pass, and it passes on the box where the path does not exist at all. So the one row presented as verified evidence is supported by evidence that proves nothing about the Mac's actual layout. Harm: the section's hedge ("have not been inspected") is read as applying only to the other three rows, when in fact no row here is confirmed. Sure.

**19. "either" is impossible for the launcher rows as given**
> "List agents running on a machine | **either** | run **the matching launcher** with no name"
> with launchers given only as `/Users/el/Projects/nedschorus/scripts/launch-claude-ubuntu` and `…/launch-claude-mac`

Both launcher commands are given as absolute Mac paths, which do not exist on the box; the box-side form (`/home/nedlern/Projects/nedschorus/scripts/…`) appears nowhere in the file. So "either" cannot be obeyed on the box using anything the file provides. Separately, "the matching launcher" is undefined: matching the machine you are typing on, or matching the machine whose agents you want listed? Those give different commands and different answers. Harm: an agent on the box runs a nonexistent path, or lists the wrong machine's agents and reports them as the other machine's. Sure.

**20. "Reach" vs. "Run" for two commands the file later says behave identically**
> "**Reach** a named agent on the box | Mac | `…/launch-claude-ubuntu <name>`"
> "**Run** a named agent on the Mac | Mac | `…/launch-claude-mac <name>`"
> "**Both launchers are attach-or-create**"

Two different verbs for one behaviour, in adjacent rows of the same table, invites the reading that `launch-claude-ubuntu` attaches to something already running while `launch-claude-mac` starts something new. Harm: an agent that wants to *start* an agent on the box concludes this row won't do it and looks for a command that does not exist. Sure the wording supports both readings; unsure whether any behavioural difference was in fact intended, which is itself the problem.

**21. "See every checkout and its branch" overstates what `worktree list` shows**
> "See **every checkout** and its branch | either | `git -C ~/Projects/nedschorus worktree list`"

It shows the registered worktrees of that one repository on that one machine. Excluded by the file's own account: an agent home still in the "plain directory" state, any second clone, and everything on the other machine — in a document whose central hazard is not knowing which machine you are looking at. Harm: an agent runs this, sees five rows, and reports it as the fleet's complete checkout inventory. Sure.

**22. No row for updating the Mac's own main checkout, or for a box-side session updating the box's**
> "Update the box's main checkout | **Mac** | `ssh nedlern@ned-box 'git -C ~/Projects/nedschorus pull'`"

The command table defines the mechanism for keeping checkouts current and covers exactly one of the three reachable cases. Missing and not discarded: how the Mac's main checkout gets updated (it is the merge seat, so it goes stale too), and how a session already running on the box updates the box's main checkout — for which the table's only offered form routes through `ssh` from the Mac. The file's opening incident is a pull landing on the wrong machine, so the reader most needs the machine-local forms spelled out. Harm: an agent on the box either invents a command or ssh's to itself; the Mac's staleness goes unaddressed by any documented step. Sure.

**23. "stale" is undefined, and `worktree prune` does not do what the litter framing implies**
> "**Clear stale worktree registrations** | either | `git -C ~/Projects/nedschorus worktree prune`"

Nothing states when a registration becomes stale, how to tell before running the command, or whether running it can affect a worktree another session is currently using. And `prune` removes *registrations* for directories that are already gone — it does not delete the leftover directories that the earlier "the directory afterwards is litter" sentence describes. So the file names a litter problem and offers a command that does not clear it, with no other cleanup step given. Harm: an agent runs `prune`, sees a clean result, and reports the litter handled while the directories remain. Sure.

**24. "duplicate agents are impossible three ways" is broader than the three mechanisms support**
> "Within one machine, **duplicate agents are impossible three ways** — tmux attaches by session name, the supervisor holds an exclusive per-agent lock (reclaimed if its holder died), and an agent's home directory is derived from its name rather than chosen."

All three guards live in the launcher path. The ordinary counterexample is starting a session by any other route — running the agent binary directly in `/home/nedlern/agents/<name>`, or a `tmux new-session` under a different session name — which trips none of them. Harm: an agent reasoning "a second copy is impossible" skips the check, and two sessions edit one agent home and one branch. Sure.

**25. "the supervisor" is undefined, unsearchable as written, and its reclaim has an unstated failure case**
> "**the supervisor** holds an exclusive per-agent lock (**reclaimed if its holder died**)"

(i) "the supervisor" is a bare common noun introduced without definition, path, or proper name; the actual artifacts are `scripts/handoff-supervisor.py`, `scripts/handoff-write-and-check-supervisor.py`, and `~/.claude/handoffs/<agent>-supervisor.lock` — none of which this file names, and none of which a reader would reach by searching for "supervisor" in this document alone. (g) The reclaim path's failure cases are neither stated nor discarded: a holder that is alive but unresponsive, and two launchers that both observe a dead holder and both reclaim. Since the file offers this lock as one of the three reasons duplication is "impossible", the unstated race is load-bearing. Harm: an agent cannot inspect, clear, or reason about the lock from this document, and trusts an exclusivity guarantee whose one described recovery path is where exclusivity is most likely to break. Sure.

**26. "the same name on both is simply two unrelated agents: no conflict" contradicts the cross-machine collision paragraph**
> "Across machines nothing is shared, so **the same name on both is simply two unrelated agents: no conflict**, only a label that cannot be told apart in a listing spanning both."
> "That is also the one real cross-machine collision surface — **two clones pushing the same branch name fight over one remote ref, whatever the agents are called**."

Combined with the table's convention that an agent home sits on the branch named after the agent (`/home/nedlern/agents/choirmaster` → `choirmaster`), same name on both machines produces same branch name on both machines — which is exactly the collision the later paragraph calls the one real one. The two sentences cannot both be acted on. Harm: an agent follows "no conflict", launches a same-named agent on the second machine, and the two seats overwrite each other's pushes on one remote ref — the highest-cost failure the document describes, licensed by the document. Sure.

**27. "nothing requires it" sits against the checkout's naming rule**
> this file: "Suffix names (`-mac`, `-ubuntu`) if you want them distinguishable at a glance; **nothing requires it**."
> CLAUDE.md: "When creating or inventing names … **Check newly invented names** with glob … or grep …. **If these checks return collisions or ambiguity, choose a more explicit name**, with 3 or 4 parts, not 1 or 2."

An agent name that already exists on the other machine is the collision-and-ambiguity case CLAUDE.md makes the trigger for a more explicit name; this file states the opposite as an explicit release ("nothing requires it") and reduces the consequence to legibility in a listing. Harm: an agent that would otherwise disambiguate reads this as project-specific permission not to, walking into finding 26. Sure.

**28. "the one real cross-machine collision surface" is narrower than the shared remote actually is**
> "That is also **the one real cross-machine collision surface** — two clones pushing the same branch name fight over one remote ref"

Ordinary counterexamples on the same shared remote: the `main` ref and its protection state, tags, and the GitHub issues and PRs that both machines' agents act on. And per the referenced `/home/nedlern/.claude/CLAUDE.md`, the Mac mounts the box's home directly, making every "does not cross" artifact — handoff files, supervisor locks, worktrees — reachable from the Mac. Harm: an agent uses this sentence to conclude that concurrent work on the two machines is safe as long as branch names differ, and skips coordination on shared issues, tags, or the box's on-disk agent state. Sure.

**29. "the main checkout needs its own pull" — whose?**
> "After a merge to `main`, **the main checkout** needs its own pull, and any long-lived agent branch needs `main` merged into it before that agent sees the change."

The file establishes two main checkouts, one per machine, and its entire premise is that leaving the machine unnamed is what caused the 2026-08-12 incident. This sentence — the document's closing operational instruction — names neither. Since the merge happens on the Mac, both checkouts need attention, and the singular "the main checkout" reads most naturally as one of them. Harm: exactly the original failure, reproduced by the document written to prevent it. Sure.

**30. "any long-lived agent branch needs `main` merged into it" is one method stated as the requirement, with no owner or stopping point**
> "any long-lived agent branch **needs `main` merged into it** before that agent sees the change."

Rebasing onto `main`, or re-branching from it, achieves the same result; taken literally the sentence forbids them, and is also false for a branch that already contains the change. It further names no actor (the agent itself? the launcher? the user?), no timing, and no handling of the ordinary case where the agent has uncommitted work in its home when the merge is due. Harm: an agent either blocks waiting for someone to do this, or performs a merge into a dirty working tree mid-task. Sure on the literal-reading and ownership gaps; unsure whether "needs … merged" was meant loosely as "needs to be brought up to date", which is itself the ambiguity.

**31. `status: reference` is an undefined vocabulary item** (unsure)
> `status: reference`

The file gives no key to this field: what other values exist, what obligations `reference` carries, or what would change the value. Harm: an agent asked to update or supersede this document cannot tell whether the status must change with it. I flag this with low confidence — it is plausibly a project-wide frontmatter convention documented elsewhere, and the instructions bar me from demanding a definition this file does not itself claim to own; I raise it only because the field appears here with no pointer.

**32. "the founding seat" is an undefined label in a table of otherwise mechanical rows** (unsure)
> "Agent home — **the founding seat** | `/home/nedlern/agents/choirmaster` | `choirmaster`"

"Founding seat" appears once, is defined nowhere, and does not say what is different about this home relative to the "general" row below it — whether it has special standing, must not be removed, or is merely the oldest. Harm: an agent cleaning up agent homes cannot tell whether this one is protected. Sure the term is undefined; unsure whether it carries any operational meaning at all, which is the ambiguity.

clean sections: none — findings fall in the frontmatter, the opening/preamble, "The two machines", "Three kinds of checkout, one repository", "Ubuntu — `ned-box`, user `nedlern`", "Mac — user `el`", "Commands, and the machine each runs on", and "What crosses between machines, and what does not".

