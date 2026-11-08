# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-05)

Assertions of the overview that the claim check against commit d08dc058fd63a331f346678ce36f067e533aa856 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/13f5a0f276a83d4a68bf40cd0a301b0278599b54-2026-11-05T22-06-08-886798Z.md. Regular maintenance fixes them in the overview.

## E2 — possible problem: an assertion of the overview is contradicted

Claim: `<seat>-handoff-NNNN.md` holds copies of consumed session-handoffs, kept by handoff-supervisor.py, which keeps the two newest generations of these and of the dialog files.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - handoff-supervisor.py copies a consumed session-handoff to `<seat>-handoff-NNNN.md` only when the dialog extraction succeeded.
> - nc-systems/handoff/handoff-supervisor.py:2156-2165 `extracted = extract_dialog(...) if not extracted: ... return None, None` comes before `shutil.copy2(settings.handoff_path, settings.handoff_directory / f"{settings.agent}-handoff-{generation:04d}.md",)`
> - When extraction fails, the handoff is consumed (:2611 `state["consumed_counter"] = counter_from(handoff_fields)`) with no numbered copy.
> - The two-generation part is supported: :287 `GENERATIONS_KEPT = 2`, :2166-2167 prune_old_generations for -dialog and -handoff.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: `<seat>-leftovers-prompt-listing-counts.json` counts how many first prompts have listed each leftover. handoff-supervisor.py writes and reads it at each launch, keeping only the entries listed that time.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The counts file is read and rewritten only at a launch that lists at least one leftover.
> - nc-systems/handoff/handoff-supervisor.py:1625-1627 `leftovers = "\n\n".join(part for part in leftover_parts if part); if not leftovers: return prompt`: this return comes before leftovers_with_prompt_listing_counts (:1600-1612), which reads and rewrites the file.
> - So at a launch with nothing to list, the file is neither read nor written, and entries from an earlier launch survive.
State: open
