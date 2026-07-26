Issue: https://github.com/nedschorus/nedschorus/issues/26

# The dynamic agent-team model

Boss-designed 2026-07-25 (outer walk item 16); supersedes the org-chart possibility formerly captured in [pair #10](10-working-ideas-and-research-backlog.md) § Agent organization questions. Design capture, not a build plan: each agent class earns existence when a real need exposes it; expected development horizon is months, incremental. Two commissioned research legs are pending (see § Research), and this document is amended when they land.

## The goal: context engineering

Provide every agent exactly the context it needs, without burdening or interrupting it with extraneous context or tasks. Every design choice below serves that goal, and it continues NC's existing discipline (zero-context-reader artifacts, handoffs, progressive skill disclosure, self-contained gatekeeper requests).

## The standing principle: every agent needs oversight, all the time

Four months and a billion legacy tokens taught one structural lesson: agents cannot see their own flaws, limits, or judgment errors. The mechanism is structural, not moral — the context that makes an agent effective at its task is the same finite attention that crowds out the system view, and self-review from inside that context inherits every assumption that produced the error. One agent cannot hold a complex system and its task in view simultaneously; it tunnels on the task, the file, the bug. Therefore oversight comes from a **differently-contexted observer** — the one arrangement that demonstrably worked in the legacy fleet (fresh-context and cross-runtime reviews repeatedly caught what self-review never did).

## The three tiers

1. **Task-scoped worker agents.** Named by role (tester, designer, planner), numbered when several of one role run in parallel (tester-1, tester-2). Task-scoped; a long task extends over multiple sessions through handoffs. Each is customized for its task by its own CLAUDE.md, skills, and prompts. The SDLC lifecycle roles (prototyper, builder, sweeper, grower, maintainer) are **skills these workers carry, not agents** — a hat, not a person; the nine candidate skills ([nedschorus#15](https://github.com/nedschorus/nedschorus/issues/15)–[#23](https://github.com/nedschorus/nedschorus/issues/23)) are the skill set's seed.
2. **Domain-knowledge agents, on tap.** Long-lived *domains* (the GHIs, the wiki, Claude, Codex, the Mac, each major subsystem), short *tasks* (answer a question, maintain the domain). They exist to fill the gap the oversight principle names: workers cannot hold the whole system's knowledge while working. Lifecycle states **active / idle / exited**, switched cheaply by script. Whether idle experts can be woken reliably on the Claude runtime rides on the **Monitor-tool verification probe** (pending, § Open); until verified, exited-by-default with on-demand spawn is the fallback — the expert's real asset is its curated domain files, which a fresh spawn loads in seconds.
3. **Skills and single-purpose agents.** Deployed as subagents: do the skill or task, shut down.

**Continuity and the boss's interface:** like a real team, continuity through a long task or project is the boss paired with a **Project Manager agent** (likely a Claude+Codex pair). The boss interacts directly with PMs; PMs orchestrate the tiers.

## The sparring pair

A cross-runtime pair (Claude + Codex) that alternates between cooperation and competition — sparring: you fight each other specifically to make each other better, and the deliverable is the reconciliation, never the victory.

- **Cooperating (default): driver and navigator.** Every Claude writing code or docs gets a Codex navigator behind it, and vice versa — continuous background review, the pair-programming split without the turn-taking humans need (agents tolerate the background role). This makes the legacy fleet's proven terminal-review catch (dual-runtime legs finding different defects) *continuous*.
- **Competing (hard or big tasks): N-version teams.** Two teams, one Claude-led, one Codex-led, build from the same spec; at each SDLC phase boundary they compare work products and produce a best-of-both reconciliation. The classic name is **N-version programming** (1970s–80s fault-tolerance engineering). Its classic caution travels with it: the Knight–Leveson experiment showed independent *human* teams make correlated errors — everyone stumbles on the same hard spots. Cross-runtime LLM teams have genuinely different training (real decorrelation, measured in the legacy dual-leg data) but the diversity is partial (overlapping corpora) — so reserve the pattern for high-stakes work and **measure** whether the reconciled product beats the better team's output alone.

## Oversight mechanics: the spy and the filtered stream

- A cheap, fast **spy** agent (naming candidates: spy — boss-leaning; lookout) watches working agents and notifies the relevant domain expert when its attention is warranted. The expert wakes, reviews the situation, and decides *for itself* whether to intervene. Cheap context absorbs the volume; expensive context spends only on signal.
- **The watching surface is the session file** — literally what the agent saw and did, in order — read through a small adapter (one parser to fix when the format shifts).
- **The filter is the design's core:** observers read the **intent stream** — the agent's thinking, the user messages, the display messages — and *not* the tool traffic. Failures live in the intent stream (wrong beliefs, unjustified claims, drifting intent); volume lives in the tool traffic. The observer's judgment survives *because* it knows less — context asymmetry as a designed artifact.
- **The spot-check refinement:** confident narration can be false, so observers have the *ability* to pull a specific file or tool result on demand when a claim is load-bearing. Default: the filtered river. On suspicion: ground truth.
- The spy's two tunables — miss rate and spam rate — get the same trigger/anti-trigger eval discipline as skills ([nedschorus#23](https://github.com/nedschorus/nedschorus/issues/23)).
- Spies could run as long-lived subagents of the primary to ease communication between primary and helpers — a mechanics option, undecided.
- **The observer's stance (boss-ruled 2026-07-25) — the injection/poisoning mitigation:** the observer (spy or domain expert) is primed in its own CLAUDE.md that the watched agent is **untrustworthy about itself — blind to its own faults — and holds only rudimentary knowledge of the observer's domain**. The stance is **protective, never antagonistic**: the observer's mission is to guard the watched agent *from its own limitations* — literally to cover its back, because like a human, an agent cannot defend against what comes from behind its attention. The distrust is aimed at the watched agent's self-narrative, and it is exercised on that agent's behalf. Domain experts are additionally guardians of their domain — hyper-aware, taught to be bullshit detectors: a generalist does not get away with confident nonsense inside the expert's field. And the pair's contexts stay **loosely entangled** — do not intertwine observer and observed for long stretches before flushing contexts, so the observer never marinates in the watched agent's narrative long enough to be captured by it. (Humans fall to exactly this — dazzle-by-confident-BS is not an LLM-specific failure.)

## Naming (ruled and candidate)

- **sparring pair** — ruled (boss, 2026-07-25).
- **navigator** — the paired second (standard pair-programming term); boss alternative: "cover-my-back".
- **spy** — the cheap watcher (boss-leaning); alternative: lookout.

## Research (pending; this document amends on arrival)

Two deliberately independent legs, commissioned 2026-07-25, on multi-agent LLM team architectures that measurably beat a single agent (named patterns, numbers-bearing evidence, correlated-error data, oversight architectures, honest framework evals; the umbrella concept's term of art — likely "collective intelligence"):

- CDX leg: cvp work order, postal `1696104:39` — LANDED 2026-07-25 as [`nc-queue/2026-07-25-multi-agent-team-research-cdx-leg.md`](../../nc-queue/2026-07-25-multi-agent-team-research-cdx-leg.md) (cvp reply 1649465:2).
- Claude leg: an independent deep-research run — LANDED 2026-07-25 as [`nc-queue/2026-07-25-multi-agent-team-research-claude-leg.md`](../../nc-queue/2026-07-25-multi-agent-team-research-claude-leg.md); comparison and model amendment wait for the CDX leg.

Reports land as `nc-queue/` notes; comparing them is itself a live trial of the sparring-pair pattern. The boss's prior: published evidence is demo-heavy and thin — the legs confirm or refute.

## Open

1. Monitor-tool idle-wake verification probe (gates warm-idle experts; MEASURED-when-run).
2. First pilot: one sparring pair on one real task (candidate: alongside the step-7 git-gatekeeper build), measured before any wider rollout.
3. Spy stream-filter composition (exact message types in/out) — decided at pilot, not before.
4. Whether spies run as subagents of the primary or free-standing — decided at pilot.
