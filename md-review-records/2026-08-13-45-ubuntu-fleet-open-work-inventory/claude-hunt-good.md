<!-- provenance: runtime=claude model=claude-opus-5 effort=high cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-ubuntu-fleet-open-work-inventory.md -->

No YAML frontmatter is present in this file (and none of the sibling `docs/issues/queue/*.md` files carry any, so that is convention, not a defect). Findings below are in document order.

---

### Preamble (line 3)

**1. "Operational snapshot, not a standing design — the PR and issue rows go stale as they land; the thread map and the context-file paths stay useful."**

This exempts the thread map from staleness, but § 5's thread map has a **State** column carrying exactly the perishable facts the sentence just disclaimed: "live; PR #57 open", "live, blocked on the ruling above", "retired; handoff consumed". Those rot on the same schedule as the PR rows — faster, since a session can retire mid-day. A future agent who takes the preamble at its word will trust "live" against `ea663864` and act on a dead session. Confidence: sure.

**2. "Operational snapshot" (same sentence) — no expiry, refresh owner, or discard rule.**

The file declares itself perishable but never says who re-takes the snapshot, on what trigger, or at what point a reader should stop believing it and re-derive from the box. A reader six weeks out has no way to tell whether they are holding a current map or an archaeological one, and the file gives no test. This is a stated mechanism (snapshot-with-staleness) with the failure case — "the snapshot is now wrong" — neither handled nor explicitly discarded. Confidence: sure.

**3. The file never states its own disposition.**

Every sibling in `docs/issues/queue/` opens with an explicit disposition line — e.g. `45-session-seat-and-isolation-riders.md`: "Queued for [nedschorus#45] … Each item below was discussed and left undone deliberately — none is in flight." This file says only "Snapshot taken 2026-08-13 for [nedschorus#45] … to divide the box's open work among a small number of named agents." It never says what a reader is supposed to *do* with it, who acts on it, or what state ends its life in the queue. It directs work in §§ 2, 3, 5, 6a and 7 without ever naming a completion condition for the document as a whole. Confidence: sure that the disposition is absent; unsure only whether the convention is mandatory here.

**4. "the box" — used throughout (lines 3, 9, 89, 91, 96), never identified.**

The definite article promises a prior introduction that does not exist. The title says "Ubuntu fleet", which gets a reader close, but the file never names the host, so instructions like "run on the box" cannot be turned into a command by an agent holding only this file. It matters most in § 6a, where the same commands could plausibly be run on the Mac and would silently do the wrong thing. Confidence: sure the term is undefined here; unsure how much harm, since the machine is nameable from the wider environment.

---

### § 0 — State as of 2026-08-13, late evening

**5. Overlapping, never-distinguished vocabulary: seat / stream / thread / agent / session / job.**

Line 9 says "Two seats are running"; § 1's column is "**Owner stream**" with values `choirmaster`, `a third stream`, `gatekeeper-walk-fork`; § 5's column is "**Thread**" with a separate "**Job**" column of hex IDs; § 7 is titled "Proposed split into named **agents**" but its first line reads "Three **seats**". Nothing in the file says whether these are synonyms or distinct kinds. The concrete harm: § 1 assigns PR #57 to the stream `gatekeeper-walk-fork`, § 5 names the same work "gatekeeper + launchers (this stream)", and § 7 assigns PR #57 to the seat `gatekeeper` — three names, and a reader cannot confirm they are one thing or discover that they are three. Confidence: sure. Note the irony against line 11, below.

**6. "both past their first action."**

"First action" is used as a term of art (a specific, named thing a launched session does) but is never defined and no procedure for it appears in this file. A reader cannot tell whether "past their first action" means "the session has produced any output at all", "the seeded first prompt has been consumed", or something narrower — and therefore cannot check the claim or reproduce the state for a third seat. Confidence: sure.

**7. "The gatekeeper seat has reported and is waiting on a ruling" — and § 5's "blocked on the ruling above", and § 2.3's user gates.**

Three separate uses of "ruling" with the definite article and no definition of what a ruling is, who issues it, or what form it takes. Worse, they are different rulings: § 2 catalogues three decisions waiting on the user, none of which is "whatever the gatekeeper seat reported"; § 5 row `ea663864` says "blocked on the ruling above" where "above" points at § 2.1, not at the gatekeeper's. A reader trying to unblock the fleet cannot enumerate the outstanding rulings, because one of them (the gatekeeper's) is described only as "has reported" — the content of the report is nowhere in this file. Confidence: sure.

**8. "**Every seat document has been md-reviewed**, twelve in all" — "seat document" is undefined and the count is unverifiable.**

The file never says what qualifies as a seat document or where the twelve live. `docs/agents/` in this checkout holds nine `.md` files, so a reader who guesses the obvious location cannot reconcile the count and does not know whether they are missing three documents or miscounting. Compounding it: "23 findings on the gatekeeper brief, 28 on the seat model, 30 on the sanity-checker brief, 26 on the fleet brief, with 'clean sections: none' on each of **the first four**" — only four are ever named, so "the first four" implies an ordering of twelve that the reader cannot see, and the remaining eight documents' review outcomes are never stated. Confidence: sure.

**9. "The corrections are in PR #58." — #58 is absent from § 1, which claims to list the open PRs.**

§ 1 is titled "Open pull requests" and closes "**All five** are open and awaiting the Mac-side review-and-merge seat." But #58 is open at snapshot time — § 6a depends on it repeatedly ("still in PR #58", "Once #58 merges"). So the file simultaneously asserts a complete list of five open PRs and describes a sixth open PR. A reader working from § 1 alone — e.g. to hand the Mac seat its review queue — will drop the single most consequential PR on the box. Confidence: sure.

**10. PR #58's branch is never named in the file that tells you to check it out.**

§ 6a line 95 instructs `git worktree add ~/agents/<seat> -b <seat> seat-launch-first-prompt`, and `seat-launch-first-prompt` appears exactly once, with no statement that it is #58's branch. § 1's table gives branch names for every other PR. A reader who needs to confirm the worktree source, or to find #58 from a branch name (or vice versa), has no link between the two. Confidence: sure.

**11. "the seat-first-prompt's repair command could not work — `git worktree add` refuses a non-empty path, and its 'drop `-b`' variant was an invalid invocation, on the branch-already-exists path that any relaunched seat takes."**

The file records this failure as fixed ("is now corrected") but never states what the corrected command is or where to read it, so the knowledge is unusable here. More seriously, it directly undermines two later instructions in this same file: § 6a step 1 prescribes `git worktree add ~/agents/<seat> -b <seat> …`, which is the invocation that fails on the branch-already-exists path; and § 6a's closing remedies both say *relaunch* ("relaunch it from the PR branch rather than resetting to main", "the seats should be relaunched from the merged main") — and a relaunched seat is precisely the case line 12 says the invocation cannot survive. An agent obeying the remedy hits the documented failure. Confidence: sure this is a conflict; unsure only whether the launcher's own logic silently sidesteps `git worktree add` in that case, which the file does not say.

**12. "**Still owed:** a second-pass review of the documents that changed *after* their first review — applying findings can introduce new ones — starting with `seat-first-prompt.md`, `agent-seat-model.md` and `gatekeeper-instructions.md`."**

Two problems. (a) No stopping point: the stated rationale — applying findings introduces new findings — is recursive, so a second pass generates a third, and the file gives no convergence rule ("stop when a pass yields no findings", "one extra pass and ship", anything). An agent handed this cannot know when it is done. (b) "starting with" names three of an unbounded set: the full set is "the documents that changed after their first review", which the file never enumerates and provides no way to compute (there is no list of which of the twelve were amended). Also, the three are given as bare filenames with no directory, unlike § 6a which uses `docs/agents/seat-first-prompt.md`. Confidence: sure.

---

### § 1 — Open pull requests

**13. "| a third stream |" as an Owner stream value.**

This is not a name — it is a placeholder that cannot be resolved. No third stream is identified anywhere in the file: § 5 lists seven threads and § 7 proposes three seats, and none of them is introduced as "the third stream". PR #55 therefore has no findable owner, and PR #55 is a gatekeeper PR ("audit compares account names case-insensitively; #49 review rulings folded into the slice plan") that § 7 later hands to the `gatekeeper` seat — so the table and § 7 disagree about its ownership. Confidence: sure.

**14. "They do not conflict: different files, different branches."**

Absolute claim, and the stated justification is partly a non-reason: different branches guarantee nothing about merge conflicts — two branches editing one file conflict precisely because they are different branches. Only "different files" would carry the claim, and the file offers no evidence for it; #51 ("walk choice items are proposals; md-review delivers piecemeal") and #52 ("fast-handoff sanity-check findings applied, design doc gutted") both touch skill and review rules and are plausible co-editors. The claim also cannot survive the file's own staleness caveat: any push to any of the five branches can falsify it. And it is scoped to five PRs when six are open (see finding 9), so it says nothing about #58 — which § 6a shows touches `docs/agents/` broadly. Confidence: sure the claim is broader than supportable; unsure whether the five actually conflict today.

**15. "the Mac-side review-and-merge seat" — a second, incompatible sense of "seat", and a competing name for an actor CLAUDE.md already names.**

Everywhere else in this file, a seat is a box-side agent home: "both in `~/agents/<seat>` on their own branches" (line 9), "Each seat gets its own agent home" (line 110). Here "seat" denotes something on the Mac with no agent home in `~/agents/`. The reader gets two senses of a load-bearing term with no signal that they differ.

Against the checkout's CLAUDE.md, this is also a duplicate name for one actor. CLAUDE.md: "the interim lane applies: commit to the working branch, push it, and **the user's Mac-side agent** reviews and merges." This file: "awaiting **the Mac-side review-and-merge seat**." Two names for the same role means a grep for either finds only half the material. Confidence: sure.

---

### § 2 — Decisions waiting on the user

**16. "whether the sanity-checker joins the md-review grid as three stance attacks (cut, mechanization, fresh-eyes) across Fable and gpt-5.6-sol at xhigh."**

The decision cannot be evaluated from this file: "the md-review grid" appears with the definite article and is never defined, "stance attacks" is undefined, "xhigh" is unexplained, and `gpt-5.6-sol` is an unexplained identifier. A reader asked to present this ruling to the user cannot state what is being decided or what either outcome costs. The evidence path (`md-review-records/2026-08-12-attack-split-experiment/scorecard.md`) partly rescues it, but the file's own summary is not self-supporting. Confidence: sure.

**17. "the split beat the unsplit baseline" stated inside an item framed as an open question.**

If the split won on the evidence, the file does not say what remains undecided — cost, seat count, scheduling, something else. A reader cannot tell whether the user is being asked to ratify a settled result or to weigh a trade the file never names. Confidence: sure the ambiguity exists; unsure what the intended open variable is.

**18. "Job `ea663864` has been blocked on this ruling." vs. "This is the question `ea663864` asked and never got answered."**

Item 1 says the job is blocked on ruling 1; item 2 says the job's actual outstanding question is ruling 2 (ordering). Both cannot be the thing blocking it, and § 5's row for `ea663864` says only "blocked on the ruling above" — which, read from § 5, points at whichever of the two the reader picks. Unblocking `ea663864` therefore has no determinate answer. Confidence: sure.

**19. "the walked-approval evidence format" — used undefined, in the same file that flags this exact word as a defect.**

Line 11 states: "the briefs used *pile*, *walked approval*, *instruction-class*, *slice* and the C-numbers as if established, and none was defined anywhere. The seat model now defines them once." § 2.3 then uses *walked-approval* and *slice* ("build slice 6") as if established, and does not point to the seat model — which is itself named only as the bare filename `agent-seat-model.md` in line 13, with no path. The file diagnoses the disease and reproduces it. Confidence: sure.

**20. "then build slice 6 (the review-evidence check), then the credential work. Until then the gate stays dormant."**

"Until then" has no determinate antecedent: it could mean until the credential work lands (the last item), until slice 6 lands, or until all three land. The three readings give different answers to "can the gate be turned on now?". The checkout's CLAUDE.md fixes it one way — "Until its credential work lands (activation waits on build slice 6), the gate is dormant" — but a reader working from this file alone cannot derive that, and the file does not cite CLAUDE.md. Confidence: sure.

**21. "the gatekeeper" as an agent seat vs. the git-gatekeeper program defined in CLAUDE.md.**

CLAUDE.md defines it as a program: "the git-gatekeeper (`scripts/git-gatekeeper.py check-in` — specification: `docs/cross-project/git-gatekeeper-design.md`) is the permanent path — one program, one credential, one door". This file uses `gatekeeper` as the name of a running agent seat ("The gatekeeper seat has reported", "`gatekeeper` and `sanity-checker` are running"), a stream ("gatekeeper-walk-fork"), a document ("the gatekeeper brief"), and the program itself ("The gatekeeper spec's …", "the gate stays dormant"). One word, four referents, and the file never separates them. "The gatekeeper's remaining road" in § 2.3 is the program; "the gatekeeper seat" in § 0 is the agent — a reader who conflates them will think a running session *is* the gate. Confidence: sure.

---

### § 3 — Un-triaged novel findings

**22. "Surfaced beyond both ground-truth sets" and "the cells read archived snapshots".**

"Both ground-truth sets" and "the cells" both arrive with the definite article on first mention and are never introduced. A reader cannot tell what the two ground-truth sets are, why there are two, or what a cell is — and the sentence's whole load-bearing claim ("novel", "needing verification") rests on them. This blocks the very triage the section is asking for. Confidence: sure.

**23. "The gatekeeper spec's 'when a test suite exists, the tests run here' never fired, though the suite now exists — so the gate runs no checks today."**

"The gate runs no checks today" is broader than the premise supports, and conflicts with the surrounding file and CLAUDE.md. § 2.3 already says the gate is dormant — a dormant gate running no checks is not a finding — so the sentence is either restating the known state or claiming a distinct bug, and the reader cannot tell which. As an absolute it also has an ordinary counterexample from CLAUDE.md: "`audit` checks main's live protection against the design" is a check the gatekeeper runs. Confidence: sure the claim is over-broad; unsure which of the two readings was meant.

**24. "No gate-edits-the-gate guard."**

A noun phrase with no verb, no owner, and no definition. The reader is not told what the guard would prevent (an agent editing `scripts/git-gatekeeper.py` and then routing that edit through the gatekeeper it just changed, presumably), what the current behaviour is, or whether this is a bug report, a proposal, or a note. It cannot be triaged as written. Confidence: sure.

**25. "A writer-stamps-the-pin proposal, to stop agents hand-writing 40-character SHAs."**

"The pin" is undefined and appears nowhere else in the file, so the coined name `writer-stamps-the-pin` is not self-documenting — a reader cannot recover what is pinned, who the writer is, or what stamping does. It is also a poor search key: the phrase exists only here, so grepping it finds nothing that explains it. Confidence: sure.

**26. "The wedged-but-light session: stalls below the recycle threshold with no watchdog."**

"The recycle threshold" is undefined in this file and the reader is given no value, no owner, and no way to observe it, so "below the threshold" is unmeasurable. "Wedged-but-light" is coined here and used nowhere else. As written the item cannot be verified against current code, which § 3's own preamble requires before any walk. Confidence: sure.

---

### § 4 — Open issues, grouped

**27. "Twenty-four open." — thirty issues are then listed.**

Counting the bullets: Fleet and sessions 6 (#45, #50, #34, #37, #27, #40); Review and skills 11 (#24, #23, #22, #21, #20, #19, #18, #17, #38, #36, #26); GHI and tooling 4 (#46, #41, #42, #39); Doctrine and research 9 (#44, #35, #33, #32, #31, #30, #29, #28, #25). Total 30, not 24. The stated purpose of the section is "for splitting", so an agent sizing the work — or checking that the split in § 7 covers everything — starts from a number six short of the list directly beneath it. Confidence: sure (arithmetic on the file's own list).

**28. § 4 enumerates 30 issues; § 7 assigns 14 and never says what happens to the other 16.**

§ 7 gives `gatekeeper` "#45, #50, #34", `reviewer` "#17–#23", and `ghi` "#46, #41, #42, #39". That leaves #37, #27, #40 from the fleet group, #24, #38, #36, #26 from review-and-skills, and the entire nine-issue "Doctrine and research" group unowned — with no statement that they are deliberately deferred, dropped, or held for a fourth seat. A reader who reads § 7 as the plan will conclude the fleet's work is covered when half of it is not. Confidence: sure.

---

### § 5 — Thread map

**29. "A new session can be pointed at any of these regardless of which agent name it runs under (see § 6)."**

Taken literally against § 6, this is not possible for the transcript column. § 6 offers exactly two mechanisms: `--first-prompt-file <path>`, which "reads that file as the new session's **first prompt**", and copying a handoff file. The transcripts in this table are 3.6 MB JSONL files (the file says so: "(3.6 MB)", "3.67 MB"). Neither mechanism can consume one — a multi-megabyte JSONL is not a prompt. § 6 line 85 repeats the impossible instruction: "point the new session at the `-dialog-` extract **or the transcript** instead". The file defines a store (transcripts as durable context) and a delivery mechanism (first-prompt-file), and leaves the case where the two are incompatible entirely unaddressed. Confidence: sure the two sections cannot both be obeyed as written.

**30. Row `sanity-checker` / `d9eda3ec` — "retired; handoff written" — contradicts § 0 and § 6a.**

§ 0 line 9: "**Two seats are running** on the box: `gatekeeper` and `sanity-checker` … the sanity-checker seat is triaging its four findings and writing queue documents to route them." § 6a repeats it. § 5 says the sanity-checker is retired. The file gives the reader no marker that these are two different things bearing one name (an older thread whose transcript sits under `-home-nedlern-agents-choirmaster/`, and a seat launched 2026-08-13 into `~/agents/sanity-checker`). An agent trying to reach the sanity-checker will either resurrect a dead thread or assume the live seat's work is already finished. The same collision applies to `gatekeeper`: § 5's row is "gatekeeper + launchers (this stream)" in the `gatekeeper-walk-fork-continuation` worktree, while § 0/§ 6a describe a `gatekeeper` seat in `~/agents/gatekeeper` — different checkouts, one name. Confidence: sure.

**31. Row `login session` — "never had a task; delete" — contradicts "Transcripts are the durable context," and is not executable.**

The section's opening sentence establishes transcripts as the thing worth keeping; this row orders one destroyed. Beyond the tension: the instruction names no actor, no procedure, and no object — the transcript file, the directory `~/.claude/projects/-home-nedlern/`, or some session record elsewhere. It also gives a glob, `3d8bf995-*.jsonl`, not a filename, so an agent obeying it deletes whatever the glob happens to match. Deletion is irreversible and the file provides no confirmation step. Confidence: sure.

**32. Row `tmux seat` — "duplicate of the choirmaster stream; resolve against `ea663864`."**

"Resolve" is undefined here: there is no procedure for reconciling two transcripts, no statement of what a resolved state looks like, and no stopping point. It is also unclear what a "duplicate" means for a session — same work, same checkout, forked from it, or literally the same session seen twice. An agent handed this row cannot start, and cannot tell when it is finished. Confidence: sure.

**33. Three transcript paths are globs, not paths: `d9eda3ec-*.jsonl`, `3d8bf995-*.jsonl`, `f741668d-*.jsonl`.**

The other four rows give complete filenames. The column is headed "Transcript (context)" and the section calls these "the context-file paths" that "stay useful", but a glob is not a path — it requires a resolution step the file does not mention, and it silently changes behaviour if it matches more than one file (which, per finding 31, is a deletion instruction in one case). Confidence: sure.

---

### § 5 — Complete transcript sweep (2026-08-13)

**34. "All 35 transcripts over 30 KB were read" then "**Everything else is accounted for.**"**

The sweep declares a floor (30 KB) and then declares completeness. Transcripts under 30 KB were never read, and the file neither counts them nor states that they are safe to ignore, so the two sentences cannot both be true as written: "everything else" means "everything else above the floor". A future agent auditing fleet coverage will read this as an exhaustive census and stop looking. The mechanism (a size-filtered sweep) leaves its own excluded set unstated and undiscarded. Confidence: sure.

**35. "**Two unowned threads with real content.**" — the second bullet is five sessions in a different project.**

The bullet reads: "A second project entirely: **nedsmessenger** … five sessions from 2026-08-03/04 totalling ~4 MB". Five sessions is not one thread, and the file elsewhere uses "thread" for a single lineage with a single job ID (§ 5's table). The heading's count is therefore wrong on the file's own vocabulary, and a reader planning ownership will budget one handoff where six are needed. Confidence: sure the count and the noun disagree; unsure only whether "thread" was meant loosely as "topic".

**36. "Whether that project is still live is the user's call" — a user decision raised outside § 2.**

§ 2 is titled "Decisions waiting on the user" and enumerates three. This is a fourth, buried in a sweep subsection, and it is never cross-referenced from § 2. An agent draining § 2 will present three decisions and leave nedsmessenger unresolved indefinitely, which is exactly the accumulation failure the preamble says the document exists to stop. Confidence: sure.

**37. "Preserved handoffs and dialog extracts, all under `~/.claude/handoffs/`: the choirmaster and gatekeeper-walk-fork handoffs plus **their numbered generations**, and matching `-dialog-` files."**

The naming convention for "numbered generations" and for `-dialog-` files is never given — the file supplies the exact form for the current handoff (`~/.claude/handoffs/<agent>-handoff.md`, § 6) but nothing that lets a reader construct or predict a generation filename, and no example. § 6 then instructs pointing a new session at "the `-dialog-` extract", which the reader cannot name. "All under" is also an absolute that the file gives no basis for. Confidence: sure the convention is missing.

---

### § 6 — How to give a new agent someone else's handoff

**38. "The supervisor reads `~/.claude/handoffs/<agent>-handoff.md`" — "the supervisor" is never identified.**

Definite article, first mention, and it is the central actor of the entire section (it reads the handoff, receives the pass-through, "reverts to ordinary ignition", and in § 6a runs the branch sync). The file never says what the supervisor is — a script, a process, a role — nor where it lives, nor how it is invoked. Every instruction in §§ 6 and 6a that says "the supervisor does X" is therefore unverifiable and unfixable by a reader holding only this file. Confidence: sure.

**39. "and then reverts to ordinary ignition."**

"Ignition" is coined here, used once, and never defined. The reader cannot tell what the session does after consuming the first-prompt file — resume a handoff, idle, run a standard opening sequence — and therefore cannot predict whether seeding a session from another thread's context will be immediately overwritten by whatever "ordinary ignition" does. As a search term it is a dead end: one occurrence, no definition. Confidence: sure.

**40. "Two supported ways around that, both already built."**

Closed enumeration. § 6a then does something that is not cleanly either of them — it pre-creates the worktree so the launcher's own home-creation is skipped, then feeds `--first-prompt-file` a path inside the seat's *own* checkout rather than "another thread's handoff, its dialog extract, or a purpose-written brief". The claim of exactly two ways is at minimum incomplete as a description of the file's own practice. Confidence: unsure — this may be intended as "two ways to see *another agent's* handoff" specifically, in which case the count holds and only the phrasing misleads.

**41. "`cp ~/.claude/handoffs/<old>-handoff.md ~/.claude/handoffs/<new>-handoff.md` before launching `<new>`" — the collision case is unhandled.**

If `<new>` already has a handoff (which is the normal state for any name that has run before — § 5 shows several such files exist, plus "their numbered generations"), this `cp` overwrites it without warning and destroys the successor context for that name. The file states the mechanism and never mentions the case. The failure is silent and irreversible, and it is most likely to happen exactly when a reader is reusing an established seat name. Confidence: sure.

**42. "a handoff written by a *forked* session describes that session's state when it wrote the handoff, not the fork point."**

The property described is true of every handoff, not only forked ones — a handoff always describes the writer's state at writing time. Restricting it to forks implies that a non-forked session's handoff has some other property, which the file does not state and which is not true. A reader will under-apply the warning: they will trust a non-forked predecessor's handoff to describe a point it does not describe. "Fork point" is also never defined here; the preamble's "forks were used to park context for later" is the only gloss and does not define it. Confidence: sure about the over-narrow scope; unsure whether the author meant "forked" to carry a specific mechanism this file doesn't name.

**43. "point the new session at the `-dialog-` extract or the transcript instead, **and say in the first prompt** which part of the history is the subject."**

Under mechanism 1, the file *is* the first prompt — there is no separate channel in which to "say" anything. So the two halves of the sentence cannot both be done with `--first-prompt-file`. Under mechanism 2 the same problem holds: the copied handoff is the whole input. The file describes no third channel for adding an instruction alongside a pointed-at file. Confidence: sure.

---

### § 6a — Seats launched 2026-08-13, and how

**44. "status line present (which is the tell that project settings loaded, and therefore that the recycle hook and the instruction-file guard loaded too)."**

The inference does not hold as stated. A visible status line evidences that the status-line setting was applied; "and therefore" extends that to two other mechanisms without argument. Settings can be merged from multiple files, and a hook can be present in configuration and still fail to run. The harm is specific and quiet: this is offered as the *verification step* for a launched seat, so a seat that renders a status line but never fires its recycle hook passes the check and then runs past the recycle threshold unrecycled — which is, per § 3, already a known failure mode on this box ("stalls below the recycle threshold with no watchdog"). "The recycle hook" and "the instruction-file guard" are also both undefined in this file. Confidence: sure the inference is stated too strongly; unsure whether it happens to be true of this particular settings layout.

**45. "They were **not** launched by the documented recipe, because that recipe cannot work yet."**

"The documented recipe" — definite article, never located. The file says what the recipe reads (`docs/agents/seat-first-prompt.md`) but not where the recipe itself is written, so a reader told to "undo" the workaround once #58 merges cannot find the thing to revert to. Confidence: sure.

**46. "Launching from main would have booted both seats into the pre-review documents — the ones carrying **twenty to thirty findings each**."**

The file supplies four finding counts (23, 28, 30, 26) for four named documents out of "twelve in all" (line 10). "Each" generalises the range to all the seat documents on the strength of four samples, and the file gives the reader no way to check it. Confidence: sure the range is asserted beyond the evidence in the file.

**47. "`git worktree add ~/agents/<seat> -b <seat> seat-launch-first-prompt`" and "`sh scripts/launch-claude-mac <seat> --no-attach --first-prompt-file /home/nedlern/agents/<seat>/…`" — no working directory is stated.**

Both commands are relative to a repository checkout (`git worktree add` must run inside one; `scripts/launch-claude-mac` is a relative path), and the file never says which checkout on the box, though it discusses several: the box's checkout of main, `~/agents/<seat>`, and the `gatekeeper-walk-fork-continuation` worktree. Run from the wrong one, `git worktree add` creates a worktree of a different clone or fails outright. The second command mixes a relative script path with an absolute prompt path in one line, which reads as if the cwd does not matter. Confidence: sure.

**48. "The launcher skips creating a home that is already a checkout, so this simply pre-empts it."**

This is asserted behaviour of an unnamed program (the launcher is named one line later, `scripts/launch-claude-mac`, but this claim is about the behaviour, with no source given), and it is the load-bearing assumption of the whole two-step workaround. If it is wrong — or changes — step 2 does something other than what step 1 anticipated. Nothing in the file lets a reader confirm it before running the commands. Confidence: unsure — the behaviour may well be documented in the launcher itself, but this file gives no pointer to where.

**49. "`launch-claude-mac` … The Mac twin runs locally on the box and is mechanically identical to the Ubuntu launcher minus the SSH hop."**

The name says Mac; the sentence says it runs on the box. A reader who greps for how the box launches seats will not search "mac", and a reader who sees `launch-claude-mac` in a transcript will reasonably conclude the command was run on the Mac — the file's own preamble makes machine confusion its central worry, and CLAUDE.md's environment makes "wrong computer" a live failure mode. The file does not say which machine the *name* refers to (the launcher's origin? the seat it creates? the calling convention?), leaving all three readings open. Confidence: sure the description supports incompatible readings.

**50. "the supervisor's branch sync will report it as *ahead of main* and change nothing."**

"Branch sync" is introduced here as a mechanism with behaviour ("report", "change nothing", "fast-forward normally") but is never defined: when it runs, what it operates on, what it does in each of the ahead/behind/diverged cases. Since the whole "Consequence to expect" paragraph and the trap in the following paragraph are predictions of this mechanism's behaviour, none of them can be checked or debugged from this file. Confidence: sure.

**51. "Once #58 merges, those branches become strictly behind and fast-forward normally."**

Two reachable cases are left unaddressed, and one of them is created by this document itself.

(a) If #58 is merged by squash or rebase rather than a merge that preserves its commits, the seat branches will hold commits with different SHAs than main's, so they will be *diverged*, not "strictly behind", and they will not fast-forward. The file names no merge policy anywhere — and per CLAUDE.md the merge is performed by a Mac-side agent, not by anything this document controls.

(b) The seats are working: § 0 says "the sanity-checker seat is triaging its four findings and writing queue documents", and § 6a says each seat has "its own branch". Any commit a seat makes puts its branch ahead of main on its own account, so after #58 merges it is diverged, not behind, and again will not fast-forward. This is not a corner case — it is the expected behaviour of a working seat.

In both cases the file's stated conclusion — "No action is needed", "the reset is then unnecessary, because the branch fast-forwards on its own" — is wrong, and the reader has been explicitly told not to reset. Confidence: sure.

**52. "No action is needed unless #58 is changed **substantially** before merging, in which case the seats should be relaunched from the merged main."**

"Substantially" is an undefined threshold with no judge and no test — a reader cannot determine whether a given change to #58 crosses it, and the two branches of the decision (do nothing / relaunch both seats) are very different in cost. Confidence: sure.

**53. Two different relaunch sources for overlapping conditions.**

Line 98: "the seats should be relaunched from **the merged main**." Line 100: "If a seat must be cleaned before that, relaunch it from **the PR branch** rather than resetting to main." The conditions are stated as disjoint ("#58 changed substantially before merging" vs. "a seat must be cleaned before that"), but both are pre-merge situations and a reader facing a substantially-changed #58 that also needs a clean seat gets contradictory instructions — and "the merged main" does not exist yet in the pre-merge case the sentence is scoped to. Neither instruction says how to relaunch a seat whose worktree and branch already exist, which is the failure recorded in line 12. Confidence: sure.

**54. "**A trap to answer before saying yes to it.**"**

"It" has no antecedent — the referent (the `git reset --hard origin/main` proposal) is introduced in the *next* sentence. A reader scanning headings sees a warning about an unnamed thing. Minor as prose, but this bolded line is the section's alert marker, and it does not say what is being warned about. Confidence: sure.

**55. "a later session in that seat would read the versions carrying twenty-three findings."**

Twenty-three is the count for the gatekeeper brief specifically (line 10: "23 findings on the gatekeeper brief"); here it is attached to "the versions", plural — the whole of that checkout's `docs/agents/`. The other named counts are 28, 30 and 26. A reader will carry away the wrong magnitude for the revert's blast radius. Confidence: sure.

---

### § 7 — Proposed split into named agents

**56. "**Proposed** split" — two of the three seats are already running, per §§ 0 and 6a.**

§ 0: "**Two seats are running** on the box: `gatekeeper` and `sanity-checker`". § 6a documents exactly how they were launched, on 2026-08-13, the day of this snapshot. § 7 then presents `gatekeeper` as a proposal awaiting adoption and closes "Start with two if three is too many at once; the third can wait." A reader cannot tell whether § 7 is a plan to execute, a record of a plan already partly executed, or a superseded draft — and the difference determines whether they launch a `gatekeeper` seat that already exists. Confidence: sure.

**57. The running fleet and the proposed fleet do not reconcile.**

Running: `gatekeeper`, `sanity-checker`. Proposed: `gatekeeper`, `reviewer`, `ghi`. `sanity-checker` is not among the three, and § 7 hands "the sanity-checker grid-seat decision" to `reviewer` — so the seat named `sanity-checker`, currently live and "triaging its four findings and writing queue documents", has no place in the split and its in-flight work has no destination. Whether `reviewer` is meant to be `sanity-checker` renamed, a fourth seat, or a replacement is never stated. Confidence: sure.

**58. "Three seats, chosen so **no two touch the same files or branches**."**

The absolute fails on the file's own assignments. `gatekeeper` gets "the gatekeeper's remaining road … plus PR #55 and PR #57", and `reviewer` gets "the novel-findings triage" — but § 3's novel findings are gatekeeper findings: "The gatekeeper spec's 'when a test suite exists, the tests run here' never fired" and "No gate-edits-the-gate guard" land in `docs/cross-project/git-gatekeeper-design.md` and `scripts/git-gatekeeper.py`, which are `gatekeeper`'s files. Separately, `gatekeeper` gets issue #45 — this document — while `reviewer` owns work described in it. Confidence: sure.

**59. "Each seat gets its own agent home and therefore its own branch, which is what keeps them from colliding."**

The causal chain is wrong on the file's own evidence. An agent home does not produce a branch: § 6a shows the branch had to be created by hand, `git worktree add ~/agents/<seat> **-b <seat>** …`, as a deliberate step outside the launcher. And separate branches do not prevent collisions — they defer them to merge time, which is where collisions actually hurt; § 1 already has all work converging on main through one Mac-side reviewer. A reader who believes this sentence will skip the file-partition check that finding 58 shows is actually needed. Confidence: sure.

**60. "**`ghi`**" as a seat name, and "GHI" as a section heading.**

The file never expands GHI. § 4's heading "GHI and tooling" groups #46 (ghi-info), #41, #42, #39, and § 7 names a seat `ghi` — three letters, no gloss anywhere in the file, and not a word a reader can search meaningfully (it will match `ghi` inside unrelated identifiers). CLAUDE.md does not define it either. A future agent cannot tell what the seat's remit is beyond the four issue numbers listed. Confidence: sure the expansion is absent from this file's context.

**61. "Context: the ghi design documents already in the repo."**

No path, no filenames, no count — and this is the seat's entire context allocation, where the other two seats get specific transcript IDs and handoff paths. A launched `ghi` seat cannot find its own starting material. Confidence: sure.

**62. "Start with two if three is too many at once; the third can wait."**

"Too many" has no criterion (box load? user attention? branch count?), and "the third" is undefined — the list is unordered, so a reader cannot tell which two to start with or which one waits. Combined with finding 56, an agent obeying this cannot determine any concrete action. Confidence: sure.

---

clean sections: none

