---
status: draft for the user's walk
design-as-of: 2026-08-07
---

# ghi-gatekeeper — plan for the user's walk

How agents work with GitHub issues in nedschorus: one program for every issue write, and the `ghi-write` skill for the judgment the program cannot make. Modelled on [git-gatekeeper-design.md](../cross-project/git-gatekeeper-design.md), which is the specification for the same shape on the git side.

**Scope reading, stated for correction:** "all GHI access" is taken here as all issue *writes*. Reads stay direct — `gh issue view` and `gh issue list` are how searching works, and gating them would make the search-first rule expensive to obey. If the intent was reads too, this plan changes at § The job.

This is a design, not a build commitment. `scripts/git-gatekeeper.py` is itself designed and not yet built; nothing here schedules against it.

## Walk order (opened 2026-08-07, new-vp session 3a11d08f)

1. Purpose and the bar, including the writes-only scope reading
2. The job — one door and its verbs
3. Why this cannot be a credential gate: the three enforcement legs
4. Constructive guarantees and the checks the program runs
5. The reply form, the error catalog, and how a repeat write is recognized
6. What stays judgment — and the consequence for the `ghi-write` walk
7. Version 1 cuts and sequencing

## The job

One program, `scripts/ghi-gatekeeper.py`, is the only way an issue write happens. Agents invoke it directly; no agent has a relay role in another's writes. For each request it does one of two things: **performs the write**, or **refuses and teaches the fix** — the same three-part refusal as the git gate (named error, specific facts, exact next action written for an agent to execute).

Four verbs, matching the writes the revision convention distinguishes:

```
ghi-gatekeeper.py file     --title "<title>" --body-file <path>
                           [--acknowledged <issue-number> ...]
ghi-gatekeeper.py revise   --issue <n> --body-file <path>
ghi-gatekeeper.py comment  --issue <n> --event instance-outcome | completion | ruling-challenge
                           --body-file <path>
ghi-gatekeeper.py label    --issue <n> --add draft | --remove draft
```

Bodies are always files, never inline arguments — an inline body with backticks is mangled by the shell before the program ever sees it.

There is no verb that revises through a comment. The failure the commission names — clarifications stacked as comments, or a second issue filed where an edit serves — is not refused at the gate so much as inexpressible at it.

## Why this cannot be a credential gate

The git gate's guarantee rests on branch protection: one credential can push, so the program holding it is the only door. Issues have no server-side counterpart — as git-gatekeeper-design.md records, the repository is public, so opening and commenting need no repository permission. The gate is therefore enforced by three weaker legs, and the threat model stays cooperative — the same honest-singleton framing the git design uses, not an external-attacker analysis:

1. **Pre-tool hooks in both runtimes** deny raw issue writes and name the gate in the refusal. In Claude Code this is a `PreToolUse` hook: `matcher` filters by tool name, the `if` field filters arguments with permission-rule syntax (`Bash(gh issue *)`), and the hook returns `hookSpecificOutput.permissionDecision: "deny"` with a `permissionDecisionReason` the agent reads (verified 2026-08-07, https://code.claude.com/docs/en/hooks). Codex has pre-tool hooks as well; its field names are verified at build, not assumed here. Hook coverage is pattern enumeration — `gh issue`, `gh api` against the issues endpoint, and any MCP GitHub tool — and each path missed is a silent hole.
2. **The dedicated-identity rung**, as on the git side: agent sessions hold no issue-write credential, and the gate holds the only one. Whether this closes fully on a public repository is verified at build — an agent holding any GitHub account can comment on a public issue, so this rung may bound the residual rather than remove it.
3. **A footer-absence audit**, mirroring the git side's trailer-absence audit: scan issues for bodies lacking the gate's footer and file a `draft` issue naming them. The residual is detected, not prevented.

## Constructive guarantees and the checks

Made true by construction:

- **A duplicate cannot be filed unseen.** `file` runs the search itself before writing. Matches are printed, and the write refuses until the agent names the ones it considered with `--acknowledged`. The search-first rule stops being a rule an agent might skip.
- **The provenance footer cannot be missing.** The program writes it, never the agent.
- **A revision cannot arrive as a comment.** `comment` requires an event kind from the fixed catalog; there is no free-form comment path.

Checked, and refused with the fix:

- **Every reference opens from the reader's seat.** A bare repository-relative path or bare filename in the body refuses; in-repo paths are verified present on main; cross-repo references must be full URLs.
- **A revision must change something.** A body identical to the current one refuses rather than producing an empty edit.

## The reply and the record

Replies mirror the git gate: `filed #<n>`, `revised #<n>`, `commented #<n>`, or a named refusal with nonzero exit. Records are GitHub plus the invoking session's ordinary transcript — no side files, no separate log.

A footer written by the program carries the session origin and a digest of the write, so a resubmitted identical `file` answers `already-filed #<n>` instead of producing a second issue, derived from GitHub itself with no local state. **Open for the walk:** whether a digest line belongs in a public issue body at all, or whether repeat detection should rest on the title-and-search path instead.

Named endings, three-part teaching form: `unknown-issue`, `missing-title`, `missing-body`, `empty-revision`, `unnamed-event`, `unacknowledged-match`, `bare-reference`, `unopenable-reference`, `github-unreachable`, `auth-failed`; answers `filed`/`revised`/`commented`/`already-filed`.

## What stays judgment

The gate takes the checkable half. `ghi-write` keeps what no program can decide: routing by state (queue, GHI, MD-GHI pair, or bare MD), and the zero-context-reader three-test check.

**Consequence for the paused `ghi-write` walk** ([ghi-write-skill-draft.md](ghi-write-skill-draft.md), item 2): with the gate and its hooks in place, an agent about to write an issue is stopped by the hook whether or not the skill triggered, so undertriggering on the write path stops mattering. The residual undertriggering risk sits entirely on the routing trigger, which no hook can reach because no tool call exists at that moment.

## Version 1 cuts

| Cut | Why | Grows back when |
|---|---|---|
| Similarity-scored duplicate detection | `gh` search terms plus named acknowledgment is enough while volume is small | Acknowledgment proves to be rubber-stamped |
| Absence-claim receipt checking | Detecting "no X exists" in prose is fuzzy; the rule stays in the skill | An unverified absence claim ships wrong |
| Revision-diff review | The edit history already preserves before and after | A revision destroys content that mattered |
| Gating reads | Search must stay cheap or the search-first rule is not obeyed | Never |
| Routing and the three-test check | Judgment, not mechanism | Never — they live in the skill |

## Sequencing

Both gates share the refusal form and could share one teaching-refusal module; that sharing is noted, not designed. The git gate is the earlier build slice, and nothing here depends on this gate existing for `ghi-write` to be written — the skill stands alone, and the gate makes half of it enforced rather than instructed.
