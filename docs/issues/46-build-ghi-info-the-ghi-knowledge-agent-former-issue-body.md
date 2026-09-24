---
issue: "[Build ghi-info — the GHI knowledge agent](https://github.com/nedschorus/nedschorus/issues/46)"
---

# Build ghi-info — the GHI knowledge agent

Build the ghi-info system per its landed design — the pair document docs/issues/46-ghi-info-agent-design.md: the GHI mirror and refresh script, the ghi-info-ask wrapper, the issue-write tool and its redirect hook, the maintenance sweep and fixer spawning, and the seat on the box.

The model-per-role open question — ghi-info, fixers, adjudication; Claude or Codex; fable, opus, sonnet — rides this build, settled empirically.

Build considerations beyond the design: the md-review rider, md-review-records/2026-08-11-ghi-info-agent-design/dispositions.md item 9. The design's § Verify at build lists the assumptions to test, each with its failure branch.

**Layer 1 landed (2026-08-12):** the `ghi-write` skill — the stack's front-loading layer — is live at [.claude/skills/ghi-write/SKILL.md](https://github.com/nedschorus/nedschorus/blob/main/.claude/skills/ghi-write/SKILL.md) (ask-first step 1, single fallback ladder, two-event comment catalog; closed GHI [Build ghi-write (step-1 founding skill): trigger on creating or revising a GHI; enforce edit-don't-comment-or-duplicate](https://github.com/nedschorus/nedschorus/issues/13)). **Build cleanup rider:** the skill's How-to carries an interim comment sentence — "Until GHI [Build ghi-info — the GHI knowledge agent](https://github.com/nedschorus/nedschorus/issues/46) builds the tool, plain `gh issue comment` naming the event kind is the interim path" — that this build deletes when the write tool ships.

## Ruled 2026-09-15: the GHI body becomes the link, and the write tool's rules

Two walks at the reboot-test seat (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-write-cap-ghi-382-and-pr-379-decisions-minutes.md` and `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-md-pair-updates-reach-every-agent-minutes.md`). Requirements on the write tool `scripts/ghi-issue-write.py`, a fix here rather than a new issue:

- **A GHI's body is the link to its paired MD under `docs/issues/` and nothing else.** One copy of every fact: GitHub holds the state (open, closed, labels), the MD holds the content. A closed GHI's MD stays where it is. Scale at ruling: 95 open issues, 46 already paired.
- ~~**The tool's pull request for a GHI-MD change merges without waiting on a person**~~ **REVERSED 2026-09-20, see below.**, through the approving identity GHI [Deferred: main-gatekeeper activation shape 2 — a reviewer attached to the gate and an approving identity of its own](https://github.com/nedschorus/nedschorus/issues/357) gives the gatekeeper. A raw push is refused: `main` has required reviews, enforced for admins, with push restrictions.
- **The tool works in the ghi-info checkout.** Before a write it fetches and fast-forwards; if the checkout is dirty or will not fast-forward, the write refuses. A read may fall back to stale disk; a write never does.
- **Refuse on conflict**, as `scripts/ghi-issue-body-edit.py` does today under the 2026-09-08 ruling — no retry, no lock, no merge; show the diff, hand it back. That guard is absorbed here.
- **Paths under `docs/issues/` only.** A GHI-MD changes only through the tool; the matching gate rule is on GHI [Deferred: main-gatekeeper activation shape 2 — a reviewer attached to the gate and an approving identity of its own](https://github.com/nedschorus/nedschorus/issues/357).
- **Reads:** an agent reads GHI-MDs from its worktree; when the Stop hook names one as stale, `git show origin/main:docs/issues/<file>` before citing it. Goes into the ghi-write skill text.
- **The GHI-MD is cold-read before the issue links to it** (user-ruled 2026-09-16 at the merge-lane seat: "These MD files should be cold read"). The fast cold read, as the cold-read skill gives a document of this kind. This also settles the 2026-09-04 direction that ghi-write's prose outputs get a cold read like every other node's.
- **The issue's title is generated from its GHI-MD**, from the MD's first heading, by the write tool rather than typed by an agent, so the two cannot disagree (user-ruled 2026-09-16 at the merge-lane seat: "the titles should be generated from them").




## Ruled 2026-09-19/20: the design is link-only, and what the build slices are

Walked at the reboot-test seat, seven items, each approved on its own; minutes at `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-info-design-write-path-becomes-link-only-minutes.md`. The design document is revised to match in PR [ghi-info design: the write path becomes link-only](https://github.com/nedschorus/nedschorus/pull/554). Requirements this build carries that the design does not state on its own:

- **The mirror inlines, and only open issues.** `scripts/ghi-mirror-refresh.py` writes each open issue's paired files in place of its body. It stops there: a link found inside a file is not followed, or the mirror becomes the transitive closure of the corpus. A closed issue's files are never inlined — forgetting closed work is what the two-file split is for. Measured 2026-09-19: the 23 paired files of open issues are 565,000 characters, the 81 open bodies 321,000, and a mirror inlining files for all 81 open issues about 810,000 characters, near 200,000 tokens. This must land before or with the write tool, since the tool is what makes bodies links.
- **The growth path, recorded not built.** When the open corpus outgrows the window — the regrowth trigger this design already names — the shape is several `ghi-info` agents each holding a slice of the corpus, asked in parallel and their answers combined. Older slices change rarely, so most refreshes touch one agent. One agent is enough at today's size.
- **The corpus migration is its own build-slice**, after the write tool exists. Measured 2026-09-19: 81 open issues, 20 with a paired file, so 61 need one written. Until an issue is migrated it keeps its prose body and is read as it stands.
- **Every issue gets a file and a pull request.** A two-line issue needs a markdown document and a merge. The tool makes that cheap by merging its own pull requests without a person, but the cost is not zero, and it is the price of one copy of every fact.
- **The tool's write scope follows the pairing, not a fixed directory.** The 2026-09-15 rule "paths under `docs/issues/` only" cannot hold alongside the 2026-09-18 ruling that a design and its component-contract move into the component's directory when code starts: confined to `docs/issues/`, the tool could neither perform that move nor edit the design afterwards. It writes to any path holding a file paired with an issue, and nowhere else. The matching gate rule on GHI [Deferred: main-gatekeeper activation shape 2 — a reviewer attached to the gate and an approving identity of its own](https://github.com/nedschorus/nedschorus/issues/357) needs the same widening.
- **Still unsettled, decide before the build:** whether the author runs the GHI-MD's cold read before invoking the tool, or the tool runs it between filing the issue and writing the body's links.



## Reversed 2026-09-20: the tool's pull requests go through merge-lane like every other change

The 2026-09-15 rule above put the gatekeeper's own approving identity on this build's critical path, because nothing else can merge to main without a person. That identity belongs to GHI [Deferred: main-gatekeeper activation shape 2 — a reviewer attached to the gate and an approving identity of its own](https://github.com/nedschorus/nedschorus/issues/357), which is deferred and unbuilt, so the tool could open its pull request and never merge it. Put to the user 2026-09-20 as the one thing blocking the build. His answer: "like every other change seems fine. why is that even a question".

**Ruled: the write tool's pull requests are merged by merge-lane exactly as every other pull request is.** No approving identity of its own, and nothing on this build waits for the gatekeeper's activation.

Why the cost is small, measured 2026-09-20 rather than estimated:

- merge-lane merged 49 pull requests in the preceding 24 hours, and 69 issues were created in the preceding 30 days, about 2.3 a day. Issue filings add roughly 5% to the lane's load; counting edits to paired files it stays well under a fifth.
- A GHI-MD is prose under `docs/`, which CLAUDE.md's review-scope rule makes silent to reviewers. So the lane reads nothing and merges. The review this was feared to create does not happen.

**Accepted consequence:** an agent cannot finish filing an issue until the lane merges its file, so between lane sessions an issue exists with a placeholder body and a link that does not yet resolve. The create sequence is already resumable, so the agent reruns the tool and it continues from the failed step.

The matching rule on GHI [Deferred: main-gatekeeper activation shape 2 — a reviewer attached to the gate and an approving identity of its own](https://github.com/nedschorus/nedschorus/issues/357) is corrected in the same pass.
