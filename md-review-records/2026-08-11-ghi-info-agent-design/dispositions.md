# Dispositions — md-review of docs/drafts/ghi-info-agent-design.md, 2026-08-11

Pass scoped by user ruling to the new § Prompts section (the section's own required
md-review before the design's status closes); the grid reviews whole documents, so
whole-doc findings landed too and are dispositioned per item 1's scope ruling.
Eight cells: {restate, defect-hunt} x {good, floor} x {claude, codex}. Restates were
faithful — no comprehension failures. Findings below are consolidated across the four
hunt reports; per-report texts are the sibling files in this directory.

## Walk order

1. Purpose and scope ruling — what these dispositions are for, the bar (a zero-context
   builder can build and review § Prompts), and whether whole-doc findings beyond the
   Prompts scope are dispositioned now or recorded as a rider
   *processed 2026-08-11 → APPROVED (user): Prompts findings dispositioned fully; cheap
   correctness fixes elsewhere taken (items 7–8); deeper whole-doc findings recorded as
   the item-9 rider, routed at close-out (Verify-at-build entries or the build GHI).*
2. The cold-start contradiction: "Never call GitHub" / "out-of-scope" vs request form 4's
   gh edits and document commits; ghi-info's unstated repo-checkout access
   *processed 2026-08-11 → APPROVED (user), revised in discussion: the write side needs
   no special instruction — the hook redirects gh writes seamlessly; the defect was the
   read-side rule written as a blanket ban. Landed in the cold-start prompt: the
   no-GitHub rule restated by purpose (answer from the mirror only; never fetch issue
   state), the out-of-scope boundary scoped to questions, and the repo-checkout
   sentence added.*
3. Escalate/out-of-scope replies have no stated consumer; on the adjudication path any
   non-verdict reply silently becomes fail-open
4. Fixer-brief executability: Template B's new-document citation trips the reference
   check; "your branch" landing path and re-sweep loop; Template A lacks a no-change
   outcome
5. The override line is a described, unwritten prompt inside four "final" replies; slot
   notation conflates script-filled slots with agent-reply shapes
6. The sweep's own ask (the question it puts to ghi-info on a fixer's behalf) is an
   unwritten dependent prompt, with no failed-ask branch
7. Small correctness batch: comment-denial grammar break; "two request forms"
   undercount; blocked-fix escalation has no named actor; adjudication draft omits the
   title; verdict/related list arity; create-specific wording on edit refusals
8. Housekeeping batch: design-as-of stale; frontmatter status vs walk block; item-6
   "drafting in progress" stale; "measured today" undated; verify-at-build item 7
   lead-in contract
9. Rider: deep whole-doc findings recorded for a follow-up (mirror two-file torn reads
   and refresh races; empty-mirror first run; session-claim atomicity; throwaway-session
   counter accounting; drift recheck riding the adjudication path; absence claims vs the
   one-line closed file; freshness "project events" undefined; Superseded-by marker
   location vs closed-file schema; sweep trigger/cadence unstated; ghi-write vs
   ghi-issue-write naming; ruling-conflict during adjudication)
