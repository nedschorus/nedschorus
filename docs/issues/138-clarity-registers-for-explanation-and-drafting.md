# Clarity registers for explanation and drafting — pair document for [nedschorus#138](https://github.com/nedschorus/nedschorus/issues/138)

The user has typed some form of "I don't understand", "too much", or "explain assuming zero context" thousands of times. Two registers fail: live explanation to the user, and instruction text drafted for zero-context agents. Each item below that changes a file names the file, the pull request whose diff is the change's exact before/after, and the actor the text governs. The decisions were made in a walk on 2026-08-22, closed the same day; its marks are below.

Grounding observation (2026-08-22): when the user asks a question, the answering explanation is routinely clearer than the drafted rule text it explains — the question supplies the frame, the explanation starts from a concrete case, and conversational register spends words where clarity costs them. The fixes install that register where each actor is forced to read it. The zero-context reader's report already contains an explaining-register restatement of any text it reviews; today that restatement is used only for verification and thrown away.

## Walk order

1. Purpose: the bar the decisions are judged by — each fix names its home and actor,
   fires without the user asking, and is small enough to live-iterate.
   *processed 2026-08-22 → accepted (purpose item; the three-test bar stands).*
2. The project output style: exact style text, home, activation, and its reach
   (chat register, fleet-wide via checked-in settings). Cites [nedschorus#29](https://github.com/nedschorus/nedschorus/issues/29) item 4
   (research: per-agent styles) as related, not duplicated.
   *processed 2026-08-22 → REVISED then accepted: the user rewrote three rules —
   standard-SDLC-terms-never-invented replaced define-every-term (defining
   standard terms at a technical reader is condescension; invented vocabulary is
   the real failure); short-and-dense named as joint failure modes, replacing the
   two-short-replies preference; before/after shown with whatever surrounding
   context a naive reader needs. Trigger broadened to any clarify request.
   Carried by [nedschorus#156](https://github.com/nedschorus/nedschorus/pull/156) as
   `.claude/output-styles/zero-context-explanation.md` plus the fleet-wide
   `outputStyle` key in `.claude/settings.json` (instruction-file guard passed
   via its approval-marker lane). Actor: every Claude Code session in this
   repository, which reads the style at session start.*
3. walk-me-through amendment: every item written for a reader with no conversation
   history (before/after: the diff of [nedschorus#155](https://github.com/nedschorus/nedschorus/pull/155)).
   *processed 2026-08-22 → accepted with the walk-scope clause (pre-walk history
   off-limits; same-walk items leanable with a one-phrase reminder — the
   zero-context reader caught that an unscoped ban forces repetition). Landed in
   the Language paragraph of `.claude/skills/walk-me-through/SKILL.md`, carried
   by [nedschorus#155](https://github.com/nedschorus/nedschorus/pull/155). Actor: the agent presenting a walk.*
4. walk-me-through amendment: adopt the zero-context reader's restatement where it
   is clearer than the drafted text (before/after: the diff of [nedschorus#155](https://github.com/nedschorus/nedschorus/pull/155)).
   *processed 2026-08-22 → accepted as revise-toward, on the reader's own
   correction of the rule (a restatement is describing-voice; verbatim adoption
   would change voice and drop specifics). Landed in the zero-context-read
   paragraph of `.claude/skills/walk-me-through/SKILL.md`, carried by
   [nedschorus#155](https://github.com/nedschorus/nedschorus/pull/155). Actor: the agent presenting a walk, before it shows
   an item that proposes instruction text.*
5. CLAUDE.md drafting bullet: exact text, and when it lands (now, or pointing at
   md-write once built).
   *processed 2026-08-22 → accepted for CLAUDE.md and landed as the drafting bullet in `CLAUDE.md`, carried by [nedschorus#157](https://github.com/nedschorus/nedschorus/pull/157). The
   AGENTS.md half RULED past the presented options: converted to a pointer at
   CLAUDE.md with the user's qualifier (Claude references typically apply to
   Codex unless Claude-specific with no Codex equivalent), on his nedlern
   precedent — the local nedlern copy carries no AGENTS.md, so the qualifier is
   as he restated it. The unprobed-pointer risk is an accepted residual in the
   conversion commit with its reopening trigger (a codex review violating a
   CLAUDE.md rule). CLAUDE.md's stale same-rule-in-AGENTS.md parenthetical
   dropped in the same commit. The dissolved duplicate content was verified
   present in CLAUDE.md first; the bullet-copy half of the recommendation became
   moot. Actors: any agent drafting instruction text (the bullet); the Codex
   runtime, which reads AGENTS.md (the pointer).*
6. Routing: the drafting register into md-write's commissioned build (founding plan
   step 1; ghi-write's unbuilt sibling); "draft-md" rejected as a name collision.
   *processed 2026-08-22 → REVISED by the user, reversing the presented routing:
   the skill is draft-md ("md-write sounds like a final product"), and the stages
   stay deliberately separate — draft-md produces, md-review checks, the user
   walks near-final MDs; md-write's commission keeps the disposition machinery
   (pair search, NEW/REVISE/REPLACE/REMOVE), so the names are two jobs, not a
   collision. Build issue filed: [nedschorus#142](https://github.com/nedschorus/nedschorus/issues/142), carrying the scope boundary and
   the zero-context-reader-rule migration question; timing his — end of this walk
   or soon after. Issue [nedschorus#138](https://github.com/nedschorus/nedschorus/issues/138)'s body edited to match (its draft-md-rejected line
   was stale on arrival).*
7. The explain skill: hold with a reopen condition, or build now.
   *processed 2026-08-22 → accepted: HELD. The output style covers the one-shot
   explaining register and the walk skill covers multi-part material; the skill
   would add only an invocation name — machinery with no observed failure
   post-style. Reopen condition recorded on the issue: clarify-corrections still
   typed at one-shot explanations under the active style; those failures become
   the design evidence. WALK CLOSED 2026-08-22: all seven items processed;
   captures in `.claude/output-styles/zero-context-explanation.md` and
   `.claude/settings.json` (carried by [nedschorus#156](https://github.com/nedschorus/nedschorus/pull/156)),
   `.claude/skills/walk-me-through/SKILL.md`, `CLAUDE.md`, `AGENTS.md`, issues
   [nedschorus#138](https://github.com/nedschorus/nedschorus/issues/138) and [nedschorus#142](https://github.com/nedschorus/nedschorus/issues/142), the latter's
   pair document `docs/issues/142-draft-md-skill-design-notes.md` (carried by
   [nedschorus#160](https://github.com/nedschorus/nedschorus/pull/160)), and this anchor.*
