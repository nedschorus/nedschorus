---
issue: "[Write the sanity-checker-overview wiki page: the system map for future editors (user-wanted 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/130)"
---

# Write the sanity-checker-overview wiki page: the system map for future editors (user-wanted 2026-08-22)

The sanity-checker system is growing past what its parts self-describe: three audit prompt files with STANDING headers, a runner whose docstring is the operating-rules home, a records-directory discipline, a leak scan, a quote scan — and two ruled additions in flight that add structure: a shared-paragraph file spliced in by a runner-side include (user-ruled 2026-08-22), and a fourth audit (GHI [Add a fourth sanity-check audit: hidden dependencies, untestable claims, criteria vs intent (user-ruled 2026-08-21)](https://github.com/nedschorus/nedschorus/issues/121)). The user's direction (2026-08-22): long-lived, hard-to-figure-out editing instructions are exactly what belongs in this project's wiki, so future agents know how to edit the system safely.

The deliverable: one wiki page — working name `sanity-checker-overview` (the user's other candidate, `sanity-checker-readme`, loses on the naming rule: "readme" is generic where "overview" says what it is). It maps the parts and how they fit — which file owns which rules, what the body marker and the include marker do, how a prompt edit safely travels (md-review, walk, STANDING header), where reports land and when they are deleted — written for a zero-context future editor, pointing at the authoritative homes rather than duplicating their rules (the docstring stays the operating-rules home; the page is the map, not a second home).

Timing: write it only after the include build and the fourth audit land, so it documents the settled shape instead of going stale on arrival. Destination per the artifact-lifecycle rule: wiki-bound; route through `docs/wiki/queue/` or straight to the wiki home at the drain's discretion.

Search receipt: `gh issue list --state all --search "sanity-checker overview"` (2026-08-22) returned nothing; `docs/wiki/` holds only `queue/`; `scripts/ghi-info-ask.py` is absent from this checkout.

— filed from session https://claude.ai/code/session_01F9s9L5vPfehGRgrDHoc4Pk (doctrine-queue-drain seat)
