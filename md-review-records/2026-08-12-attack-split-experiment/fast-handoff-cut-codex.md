<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh attack=cut doc=fast-handoff isolation=instruction-pinned document set -->

# Cut report

Scope was limited to the three supplied files. I did not follow the GitHub, historical-git, or other document references; where a ruling’s underlying record is unavailable, I rely only on its quoted description here.

## 1. Remove task pre-seeding and its validation subsystem

**WHAT** — Delete cross-session copying of `~/.claude/tasks/<session-id>`, the successor task-count prompt, schema probes, and mandatory post-upgrade canaries. Restore task-shaped work from the durable queues instead.

**WHY** — The design declares that durable state already lives elsewhere:

> “git is the long-term record and the restore-after-problem source” and “Handoffs are operational, machine-local, disposable.” ([design:16](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:16))

It then admits that task pre-seeding:

> “rides undocumented harness internals” and requires “re-run both canaries after every Claude Code upgrade,” while “the backstop if an upgrade breaks it is the queues (task-shaped work belongs in GHIs by the artifact rules).” ([design:38](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:38))

That is a containment case: loss of an undocumented task cache is recoverable from the declared durable task store. Making the fallback the normal path removes an upgrade-sensitive subsystem and a recurring operator obligation.

The strongest defense is the live trial, which proved that “four sessions sharing one carried task store” could drain work ([design:93](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:93)). But that proves the version-specific hack worked once; it does not justify maintaining duplicate task authorities indefinitely.

**LOST** — Exact ephemeral TaskList IDs, status, and dependency arrays are no longer preserved. Successors may need to reconstruct a local execution breakdown from GitHub issues. If real task-shaped work is intentionally allowed to exist only in TaskList, contrary to the quoted artifact rule, reject this cut. Otherwise priority 1 gains: operation no longer depends on undocumented storage or upgrade canaries.

This also presses against the user-approved description that the program gives the successor “everything except one piece” ([skill:3](/home/nedlern/agents/choirmaster/.claude/skills/handoff/SKILL.md:3)); that phrase would need narrowing. The walk record explicitly declined promising task carry in the skill, however, because “nothing in this skill asks the agent to touch its tasks” ([walk record:14](/home/nedlern/agents/choirmaster/docs/drafts/handoff-skill-draft.md:14)).

**CONSEQUENCES** —

- Delete recycle step 4 and the task-count clause in step 6 ([design:38](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:38), [design:40](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:40)).
- The adoption trial’s “carried 50 task records” claim becomes historical evidence for a removed feature ([design:62](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:62)).
- Remove pre-seed canaries and task count from the Supervisor and Ignition build rows ([design:77](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:77)).
- The task-dependent trial setup, criteria, and inconsistency check cease to validate the surviving design ([design:87](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:87), [design:91](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:91), [design:100](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:100)).
- Remove `pre-seed` and `task count` from the duplicate component inventory ([design:111](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:111)).
- Remove both task-storage/schema facts ([design:125](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:125)).
- Delete the pre-seed canaries and ignition task-count assertion from the Supervisor tests ([design:135](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:135)).
- Delete the pre-seed known hole ([design:140](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:140)).

## 2. Remove the statusline relay and side file

**WHAT** — Have the Stop hook compute threshold state from the newest assistant transcript record it already reads. Delete `handoff-statusline-context-relay.py` and its side file.

**WHY** — Two mechanisms are both presented as the auto-trigger’s data source:

> “The transcript is read only by the Stop hook… the newest assistant record is all that matters.” ([design:45](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:45))

versus:

> “The statusline script receives `.context_window.remaining_percentage`… [and] writes it to a side file. The Stop hook reads that file.” ([design:49](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:49))

The verified facts decide which should survive:

> “A headless (`claude -p`) session NEVER runs the status line, so the relay file is never written” ([design:122](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:122))

and:

> “context used is therefore computable from the transcript alone, in any session.” ([design:123](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:123))

The relay is the less capable duplicate.

**LOST** — Interactive sessions lose a directly supplied percentage and instead depend on the model-to-context-window mapping. That mapping must remain current. In exchange, one path works for both interactive and headless sessions and removes stale-side-file failure.

**CONSEQUENCES** —

- Replace the entire side-file Auto-trigger paragraph ([design:49](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:49)).
- Remove the relay script from the Auto-trigger build row; its stated 14-case suite count will change ([design:78](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:78)).
- “The statusline relay + Stop hook” becomes “the Stop hook” ([design:110](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:110)).
- The statusline/Stop-stdin fact becomes unused rationale, and the relay-file fact becomes historical deletion evidence ([design:121](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:121)).
- The described test “threshold crossing fires the skill exactly once” remains valid; only undisclosed relay-specific cases behind the 14-case count become stale.

## 3. Remove the supervisor’s post-termination `restart? y/n` prompt

**WHAT** — Make `--dont-restart` a definitive “capture and do not relaunch” instruction. If consultation is requested, the retiring agent obtains the answer before writing the handoff. Delete the supervisor’s interactive prompt and its terminal-dependent semantics.

**WHY** — The nominal rule says:

> “the supervisor prompts `restart? y/n` instead of auto-relaunching.” ([design:30](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:30))

But the current headless behavior is already different:

> “the supervisor takes the non-relaunch branch rather than calling `input()`.” ([design:143](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:143))

And an agent-started supervisor is detached, so its output goes to a log rather than the watched terminal ([design:64](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:64)). Consultation after killing the only conversational agent is therefore unreliable precisely on the bootstrap path.

This collides with the walked and approved live skill text, which says to add the flag “when the user asked to be consulted before a relaunch” ([skill:11](/home/nedlern/agents/choirmaster/.claude/skills/handoff/SKILL.md:11)). It requires a new ruling, not a silent rewrite.

**LOST** — In a supervisor-parent terminal, the user loses the chance to decide after capture but before launch. They instead decide immediately beforehand. This costs nothing on automatic handoffs and adds no recurring human step; consultation was already explicitly requested.

**CONSEQUENCES** —

- Rewrite the `dont-restart` field definition as a definitive no-relaunch flag ([design:30](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:30)).
- Delete “the `dont-restart` y/n gate” from the component inventory ([design:111](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:111)).
- Replace the `dont-restart` y/n tests with one definitive non-relaunch path ([design:135](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:135)).
- Delete the closed EOF/prompt hole ([design:143](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:143)).
- Change live skill step 2. The superseded walk record should remain historical, but the new ruling must explicitly supersede its approved wording ([walk record:41](/home/nedlern/agents/choirmaster/docs/drafts/handoff-skill-draft.md:41)).

## 4. Remove the queue-status line

**WHAT** — Delete queue depth/oldest-item computation and printing from every recycle.

**WHY** — The design only says the supervisor:

> “Prints one automated queue-status line” for “rot-visibility.” ([design:39](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:39))

The ignition prompt does not include it, the skill does not require anyone to inspect it, and no test asserts a reaction. On the detached path it is written to the supervisor log ([design:64](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:64)). Nothing is forced to decide or act.

The only recorded ownership says “memory maintenance is the boss’s drain per the #32 Q1 ruling,” which argues for the existing drain—not a second passive detector. I could not inspect that linked ruling under the supplied-file constraint; if it specifically mandates recycle-time output, this finding collides with it.

**LOST** — A watching human loses incidental queue telemetry. The queues and their boss-owned drain remain. No recurring manual replacement should be introduced.

**CONSEQUENCES** —

- Delete recycle step 5 ([design:39](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:39)).
- Remove `queue-status line` from the supervisor synopsis ([design:111](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:111)).
- No described test covers this output.

## 5. Remove `--boundary-quote`

**WHAT** — Delete the extractor’s manual boundary-quote interface and its test. Keep the mechanical word-floor mode for recycling and line-count mode for the separately named dead-session recovery use.

**WHY** — The user ruling removed retiring-agent boundary judgment:

> “the retiring agent exercises no judgment over what its successor receives” and the “boundary field” died. ([design:28](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:28))

Yet the same sentence preserves `--boundary-quote` as “a manual override only,” while the later component inventory contradictorily calls it “boundary-quote mode (recycling)” ([design:107](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:107)). No cycle step or skill invokes it. Its only concrete consumer is its own test.

The simplest existing replacement for manual recovery is the retained line-count mode plus the full-JSONL pointer.

**LOST** — An operator loses exact semantic-boundary selection by quoted text and must select by line count or inspect the JSONL. This is builder-maintenance simplification at the cost of a rare manual convenience.

**CONSEQUENCES** —

- Delete the final `--boundary-quote` clause from the field description ([design:28](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:28)).
- Remove boundary-quote mode from the extractor synopsis ([design:107](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:107)).
- Delete the `boundary-quote start` extractor test ([design:134](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:134)).

## 6. Retain only the current handoff and extract

**WHAT** — Delete the rule retaining a predecessor pair. When the next handoff is safely written, remove the previously current pair.

**WHY** — The governing rule calls handoffs “machine-local, disposable” and identifies git as the restore source ([design:16](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:16)). Each extract also contains the full JSONL pointer ([design:37](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:37)). Nothing reads the extra predecessor pair.

The writer’s counter calculation still has the current handoff and the supervisor’s consumed state; it does not require the one-before-current artifact.

**LOST** — One convenient generation of forensic material. The underlying transcript and git history remain, so failure is contained rather than prevented through duplicate retention.

**CONSEQUENCES** —

- Change “keeps the current and predecessor” to current only ([design:41](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:41)).
- Replace the “local retention old+new” supervisor test with current-only cleanup ([design:135](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:135)).

## 7. Delete the second component inventory and stale component count

**WHAT** — Use the recycle cycle plus build-status table as the sole component/status homes. Delete “Components (the build)” as a second inventory and delete “Four of the five components…” Unique surviving invariants should live where they act, not in another inventory.

**WHY** — The status introduction says “Four of the five components” and that the skill still needs to land ([design:72](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:72)); the immediately following table has six rows, marks the skill built, and concludes:

> “Every component is now built, tested, and walked.” ([design:83](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:83))

The later inventory introduces further drift: it names `extract_convo.py`, while the build table names `scripts/handoff-extract-conversation.py`, and it assigns boundary-quote mode to recycling despite the earlier mechanical-floor ruling. This is exactly the failure mode the walk record identified when it cut a second procedural copy because it “had gone stale twice in one day” ([walk record:24](/home/nedlern/agents/choirmaster/docs/drafts/handoff-skill-draft.md:24)).

**LOST** — A compact synopsis. Unique constraints currently stranded there—atomic writer output, empty-next-step refusal, noise classifications, and parser tolerances—must be deliberately promoted to the cycle or tests if they remain normative. Priority 2 pays for this cut: one inventory is easier to understand and cannot disagree with itself.

**CONSEQUENCES** —

- Delete the stale status sentence at line 72.
- Delete the complete second inventory ([design:105](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md:105)).
- No test description becomes false merely from removing the duplicate home. Tests affected by substantive cuts are already enumerated above.

## Leanness certification

I examined and found these mechanisms already minimal after the cuts above:

- **Supervisor-owned kill/extract/relaunch:** the simpler replacement—agent self-exit—is explicitly unavailable, while `--resume` restores the context being shed.
- **Verbatim mechanical conversation tail:** compaction loses non-uniform value, carrying the whole session defeats recycling, and human boundary judgment was already removed. The full-JSONL pointer is the smallest containment for an undersized tail.
- **Single writer command with a next-step file:** direct field writing caused a demonstrated newline-truncation defect; inline arguments mangle shell content; splitting liveness into another command recreates an agent procedure that can be partially executed.
- **Restart counter plus consumed marker:** mtime alone cannot distinguish an already-consumed handoff after restart. The marker has an explicit exactly-once consumer and test.
- **ID-keyed transcript lookup:** latest-by-mtime has a named two-session race; the UUID key is the simplest discriminator available.
- **Supervisor liveness check and per-agent lock:** the skill and threshold hook both consume liveness, while the lock prevents the concrete double-kill/double-launch failure. Replacing either with a remembered human check would worsen operation.
- **The live skill’s core shape:** “write only the successor’s first action, run one script, obey its result” is already the smallest procedure that preserves the one genuinely non-computable input.