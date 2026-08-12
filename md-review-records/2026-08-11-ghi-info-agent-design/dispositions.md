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
   *processed 2026-08-11 → APPROVED (user), direction revised in discussion: escalation
   goes up the chain, not to the user first — the invariant is "never decided by the
   machinery, never swallowed." Landed: the ruled always-escalates-to-the-user sentence
   replaced (caller resolves or it lands as one draft-labeled issue, the blocked-fix
   surface); ask path passes non-list replies through verbatim with the caller owning
   them; cold-start boundaries gained question/verdict precedence; adjudication
   fail-open on non-verdict replies recorded as accepted residual.*
4. Fixer-brief executability: Template B's new-document citation trips the reference
   check; "your branch" landing path and re-sweep loop; Template A lacks a no-change
   outcome
   *processed 2026-08-11 → APPROVED (user), direction set by the user: fixer repairs
   land on main immediately — an explicit, dated exception to the review-lane
   convention (the issue half of every repair was already live through gh; guardrails
   are the brief's blocked conditions; record is append-forward and revertable). This
   dissolves (a) and (b): Template B lands the document before the citing body edit;
   branch language removed from all four prompts; push-race handling is re-pull,
   retry once, else blocked. (c) landed: done: no change needed added to Template A
   and the link-repair request.*
5. The override line is a described, unwritten prompt inside four "final" replies; slot
   notation conflates script-filled slots with agent-reply shapes
   *processed 2026-08-11 → REVISED by user ruling, reached through a realism analysis
   of wrongful refusals (infra failure fails open and never refuses; the too-similar
   verdict is the only substantial wrongful-refusal source; unattended agents cannot
   quote user approval anyway): write-tool denials are now HARD — the override is
   removed entirely, revising the soft-deny half of the 2026-08-07/09 soft-block
   ruling (the open-perimeter half stands, its reopening trigger now the delta showing
   deliberate evasion). The four slots replaced by a verbatim escalation line (report
   blocked or file one draft-labeled issue; the user retains the manual gh path); the
   dead cut-table trigger and delete-denial override reference cleaned up. The slot-
   notation point is resolved by the same edit: no described-only slot remains, and
   reply-shape slots read as reply shapes in context.*
6. The sweep's own ask (the question it puts to ghi-info on a fixer's behalf) is an
   unwritten dependent prompt, with no failed-ask branch
7. Small correctness batch: comment-denial grammar break; "two request forms"
   undercount; blocked-fix escalation has no named actor; adjudication draft omits the
   title; verdict/related list arity; create-specific wording on edit refusals
   *processed 2026-08-11 → applied under the item-1 scope ruling (user waived per-fix
   asks): grammar fixed; "every request form riding it" replaces the undercount; the
   sweep files blocked-fix escalations from the blocked: reply; adjudication carries
   draft title and body (duty 3, cold-start form 2, request prompt); #n,#m defined as
   one-or-more; too-similar refusal gains the edit case (edited issue keeps its body;
   Superseded-by + close if the merge target carries its ground) and reference-check
   refusal says "write now" not "file now". Also folded: the fixers-consult-ghi-info
   sentence replaced by the pre-fetched-reading-list contract, and the inline
   example brief now points at § Prompts instead of restating it.*
8. Housekeeping batch: design-as-of stale; frontmatter status vs walk block; item-6
   "drafting in progress" stale; "measured today" undated; verify-at-build item 7
   lead-in contract
   *processed 2026-08-11 → applied: design-as-of 2026-08-11; status says walk in
   progress with item 6 open; item-6 note points at this dispositions file; the
   corpus measurement dated 2026-08-07; the failure-branch lead-in names item 7 as a
   plain measurement; § Prompts status now records the review as run with dispositions
   linked.*
9. Rider: deep whole-doc findings recorded for a follow-up (mirror two-file torn reads
   and refresh races; empty-mirror first run; session-claim atomicity; throwaway-session
   counter accounting; drift recheck riding the adjudication path; absence claims vs the
   one-line closed file; freshness "project events" undefined; Superseded-by marker
   location vs closed-file schema; sweep trigger/cadence unstated; ghi-write vs
   ghi-issue-write naming; ruling-conflict during adjudication)
   *processed 2026-08-11 → recorded here as the rider; routing (Verify-at-build
   entries vs the build GHI) is decided at integration-walk item 6 close-out. Note:
   ruling-conflict during adjudication was resolved by item 3 (too-similar covers it);
   it stays listed only as the trail to that ruling.*
