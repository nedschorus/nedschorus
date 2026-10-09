# Prime Intellect components for NedsChorus

Research and proposed actions for Claude, 9 October 2026.

## Recommendation

Use Prime Agent for one real NedsChorus correction before writing integration infrastructure. Preserve the existing review and merge process. Pause new implementations of generic agent invocation, discovery, messaging, and scheduling while checking whether upstream software covers the actual requirements. Do not remove operational recovery or declare whole GHIs solved on the strength of a feature list.

Compare Prime with Pi, especially Pi Durable, before committing NedsChorus to Prime's internal interfaces. OpenHands is the strongest alternative here for a documented agent-server integration; OpenCode is another practical CLI/server candidate. These are alternatives to evaluate selectively, not dependencies to install together.

The desired result is fewer pieces for NedsChorus to maintain and less work for the user when NedsChorus builds itself. A successful trial produces an accepted NedsChorus change, a record of manual interventions, and a specific decision about what development to stop. A new framework or language migration does not meet that objective by itself.

## What Claude should establish first

The repository does not show everything currently assigned to Claude. Before proposing interruptions, inspect current agent-seat assignments, worktrees, uncommitted work, open PRs, and the applicable instructions on the Mac and ned-box. Read each relevant GHI and its linked Markdown file. Distinguish an unstarted design from implementation in progress and from code already operating.

Produce a small table: current task; owner; code or branch; remaining requirement; upstream candidate; recommendation to continue, pause, or replace. Preserve work already in progress. A pause recommendation does not authorize cancelling another agent-session or discarding a branch. If either machine is unavailable, identify the missing evidence and continue the comparison with the available repository.

The earlier [AI native software development notes](nedschorus-ai-native-software-development-notes.md) recommend building a unified runner early and completing recovery infrastructure. Reassess those recommendations against the components below. The user has explicitly rejected the old overview as a basis for present decisions; current code, current assignments, and current GHI plans take precedence.

## Prime Intellect and the component we actually need

[Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent) is Prime Intellect's coding and research agent. The [inspected MIT license](https://github.com/PrimeIntellect-ai/prime-agent/blob/561274fb2461d8d5b51c5125bc319e6bf17f3e3c/LICENSE) permits modification and redistribution with the required notices. The license also identifies the TypeScript product's Mario Zechner attribution. Forking the software does not make model inference or hosted services free.

Prime Agent supplies a Rust agent application and daemon, with a persistent Python environment for tools and agent coordination. The inspected workspace has nine Rust crates. Python remains part of the product, including the factory implementation. The relevant initial dependency is the agent application; training models and adopting Prime's wider compute or reinforcement-learning stack are separate decisions.

### Components to use or inspect

All Prime source links in this table refer to inspected commit 561274fb2461d8d5b51c5125bc319e6bf17f3e3c. Confirm behavior against the exact release chosen for the trial.

| Component and source | Immediate use | Boundary Claude must verify |
|---|---|---|
| [CLI arguments](https://github.com/PrimeIntellect-ai/prime-agent/blob/561274fb2461d8d5b51c5125bc319e6bf17f3e3c/crates/pa-cli/src/args.rs) | Start a coding agent in a separate worktree with selected model and instructions. | Provider access, instruction discovery, exit behavior, and cost. Using Claude models through Prime does not reproduce Claude Code behavior. |
| [Daemon implementation](https://github.com/PrimeIntellect-ai/prime-agent/tree/561274fb2461d8d5b51c5125bc319e6bf17f3e3c/crates/pa-daemon/src) | Try background work, discovery, messaging, reattachment, and schedules. | Separate terminal detachment from worker death, daemon death, and machine restart. Local discovery does not establish cross-machine delivery. |
| [Prompt assembly](https://github.com/PrimeIntellect-ai/prime-agent/blob/561274fb2461d8d5b51c5125bc319e6bf17f3e3c/crates/pa-core/src/prompts/system_prompt.rs) | Measure whether a worker receives only the context needed for the assigned task. | A custom system prompt replaces the static prefix; dynamic sections can still be appended. Inspect the assembled prompt, including discovered skills and project context. |
| [Child-agent request types](https://github.com/PrimeIntellect-ai/prime-agent/blob/561274fb2461d8d5b51c5125bc319e6bf17f3e3c/crates/pa-core/src/session_engine/rlm_host.rs) | Try separate implementer and reviewer conversations. | RlmSpawnRequest has no independent working-directory field; RlmCreateSessionRequest has cwd. Do not assume an ordinary child receives an isolated worktree. |
| [ACP daemon integration](https://github.com/PrimeIntellect-ai/prime-agent/blob/561274fb2461d8d5b51c5125bc319e6bf17f3e3c/crates/pa-daemon/src/acp/daemon.rs) | Candidate interface for a later small NedsChorus launcher. | Verify prompt completion, cancellation, agent identity, and subprocess lifetime before choosing the interface. |
| [Stdio RPC mode](https://github.com/PrimeIntellect-ai/prime-agent/blob/561274fb2461d8d5b51c5125bc319e6bf17f3e3c/crates/pa-daemon/src/rpc/mod.rs) | Candidate for a bounded headless worker. | This mode uses an in-process transport and returns errors for daemon-only operations. It is not equivalent to a daemon client with child-agent support. |
| [Python tools and factory](https://github.com/PrimeIntellect-ai/prime-agent/tree/561274fb2461d8d5b51c5125bc319e6bf17f3e3c/prime-agent-runtime/src/rlm) | Call existing Python programs; later test a small multi-step workflow. | Keep deterministic NedsChorus checks outside a model's claim of success. |

The [Prime README](https://github.com/PrimeIntellect-ai/prime-agent/blob/561274fb2461d8d5b51c5125bc319e6bf17f3e3c/README.md) documents starting prime-agent in a project, listing agents, attaching, resuming, checking service status, and provider login. Use those shipped operations first. Do not write another launcher merely to begin the trial.

### Conflicts that matter to NedsChorus

1. **Focus versus accumulated context.** Persistent conversations are useful for sustained work, but a fresh reviewer must not inherit the implementer's conclusions. Record the actual assembled inputs. More memory is not automatically better for NedsChorus.
2. **Instruction changes.** Prime can refine supplemental instructions and memories. For the comparison, disable automatic refinement and verify what can still change through manual operations. An immutable base prompt does not mean all effective instructions are immutable.
3. **Claude-specific hooks.** Existing NedsChorus hook scripts are not automatically installed or enforced by Prime. Enumerate the hooks the selected task relies on. Use existing external validation where available; identify any remaining requirement before giving Prime broader responsibility.
4. **Workflow durability.** The inspected [factory implementation](https://github.com/PrimeIntellect-ai/prime-agent/blob/561274fb2461d8d5b51c5125bc319e6bf17f3e3c/prime-agent-runtime/src/rlm/factory.py) keeps executions in the Python object's _runs dictionary. Restarting the Python environment does not provide a demonstrated durable workflow checkpoint. Wait states are explicitly rejected pending watch host handlers. Factory execution is opt-in. Do not equate background agent continuity with durable design-to-main execution.
5. **Identity and ownership.** Map a persistent NedsChorus agent-seat to the appropriate upstream identity, rather than assuming every upstream conversation is an agent-seat. Verify who owns pending work after restart, cancellation, or retirement.

## Alternatives worth Claude's time

This is a targeted comparison of reusable agent software. None of these projects has been demonstrated here to replace NedsChorus's review policy or complete development process.

| Candidate | Verified documentation or source | Why investigate | Priority |
|---|---|---|---|
| Prime Agent | Source inspection of the components above; Rust application plus Python tools. | Most direct first experiment with background coding and built-in agent coordination. | First real coding task. |
| Pi coding agent | [SDK](https://pi.dev/docs/latest/sdk), [extensions](https://pi.dev/docs/latest/extensions), [source](https://github.com/earendil-works/pi). TypeScript SDK exposes prompt, resource, tool, model, and conversation controls; extensions include context transformations and blocking tool calls. | Potentially a better fit if exact input control and adaptation of existing hooks dominate the decision. | Compare before writing a substantial Prime adapter. |
| Pi Durable | [Announcement](https://earendil.com/posts/pi-durable/) and [package README](https://github.com/earendil-works/pi/blob/main/packages/durable/README.md). A separate experimental package, not a property to assume of the ordinary Pi CLI. | Particularly relevant to recovery: documented persisted tasks, SQLite/JSONL storage, resumption, and request identifiers for deduplicating submissions. | First alternative to inspect before more recovery code. |
| OpenHands Software Agent SDK | [Repository](https://github.com/OpenHands/software-agent-sdk), [persistence guide](https://docs.openhands.dev/sdk/guides/convo-persistence), [state implementation](https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/conversation/state.py). Python SDK, TypeScript client, and REST API; local or remote workspaces and persisted conversations. | Strong candidate when an explicit service API and Python integration matter more than a terminal application. | Fallback if Prime integration requires extensive internal patching. |
| OpenCode | [Repository](https://github.com/anomalyco/opencode), [SDK](https://opencode.ai/docs/sdk/). A coding application with a JS/TS client for its server, conversation operations, cancellation, events, and structured output. | Another way to avoid building provider invocation and agent control from scratch. | Lower priority unless server integration proves simpler. |

Pi Durable was announced on 1 October 2026 and is explicitly experimental. The documentation describes per-conversation working directories and checkpointed operations; those mechanisms deserve a small recovery experiment. A deduplicated submission does not by itself prove exactly-once external file changes or Git operations. Test interruption during a tool operation, not only between messages. Inspect the package's Persist and Resume, Tools, Abort and Subagents, and Storage sections before adapting the design.

OpenHands persistence documents restoration using the same conversation identifier and persistence directory. That establishes a documented restoration interface, not proof that every interrupted external operation resumes correctly. OpenHands also has a separate [automation service](https://github.com/OpenHands/automation) for schedules and webhooks, explicitly marked beta. Do not add that service merely to schedule one local task.

Provisional selection: Prime for the first productive coding trial; Pi/Pi Durable for the closest competing context-control and recovery design; OpenHands if a service becomes the preferred integration boundary. A Rust preference should not eliminate a substantially simpler TypeScript or Python solution before the behavior is compared.

## Work to pause and the evidence needed to stop permanently

These recommendations concern new development, not shutdown of working services. Claude should reconcile the rows with actual current assignments first. Each GHI below has a linked Markdown plan that is part of the decision.

| NedsChorus work | Recommendation | Requirement before calling the work replaced |
|---|---|---|
| [Shared run-agent CLI](https://github.com/nedschorus/nedschorus/issues/41), [plan](../issues/41-run-agent-one-cli-to-invoke-a-claude.md) | Pause a general runner implementation. Upstream applications already provide model invocation and programmatic control. | The chosen interface supplies the task's inputs, outputs, cancellation, failure reporting, and evidence. Existing Claude Code and Codex callers may still require a small compatibility layer. |
| [Agent-seat registry](https://github.com/nedschorus/nedschorus/issues/972), [plan](../issues/972-a-small-service-on-ned-box-keeps-one.md) | Pause the new registry service pending comparison. | Discovery and identity across both machines, including disconnected operation, match the real requirement. A local Prime roster is only partial overlap. |
| [Mailboxes across machines](https://github.com/nedschorus/nedschorus/issues/749), [plan](../issues/749-seat-mailboxes-across-machines-and-runtimes.md) | Pause new transport work long enough to test upstream messaging. | Delivery to idle or stopped recipients, restart behavior, acknowledgment, and the Mac/ned-box path meet the plan. Do not claim cross-machine mailboxes are already solved. |
| [Due tasks](https://github.com/nedschorus/nedschorus/issues/940), [plan](../issues/940-tasks-raise-themselves-when-their-due-time-passes.md) | Stop designing another clock scheduler if only timed wake-up is required. Try Prime's schedule operation. | Timed wake-up survives the required interruptions. Prerequisite satisfaction is a separate requirement and may remain NedsChorus code. |
| [Handoff storage](https://github.com/nedschorus/nedschorus/issues/754), [plan](../issues/754-handoffs-become-one-pending-file-per-session-archived.md) | Defer an expanded handoff implementation for the trial agent. Keep existing agents' recovery operating. | The selected application preserves needed instructions, work identity, files, pending work, and recoverable progress under the relevant interruption. |
| [Moving agent-seats](https://github.com/nedschorus/nedschorus/issues/1129), [plan](../issues/1129-moving-an-agent-seat-to-the-other-machine.md), and [retirement](https://github.com/nedschorus/nedschorus/issues/1125), [plan](../issues/1125-agent-seat-retirement-as-a-program-the-agent.md) | Defer extensions until identity and ownership are mapped. | No claim of equivalent upstream behavior yet. Migration must stop the former owner; retirement must prevent unintended relaunch. |
| [Design-to-main build](https://github.com/nedschorus/nedschorus/issues/282), [plan](../issues/282-build-the-design-to-main-state-machine-the.md) | Keep the recorded build pause; preserve the existing state-machine code. | A real worker can complete the small supervised path first. Prime's factory is not yet evidence for replacing durable workflow state. |

Keep ColdRead, independent code review, affected-test selection, exact-commit test evidence, worktree isolation, and merge-lane-2. Continue repairs that prevent lost work or silent success. No evidence in this comparison establishes an equivalent upstream replacement for those project-specific behaviors.

The immediate stop is duplication of commodity mechanisms before testing available implementations. The permanent deletion decision comes after a successful replacement test. When current work is nearly complete, compare remaining effort with integration effort rather than discarding the implementation because an upstream feature has a similar name.

## First experiment and first possible addition

**First experiment: fix the review-plan subdirectory defect using Prime, then submit through the normal NedsChorus process.** The [GHI](https://github.com/nedschorus/nedschorus/issues/1011) remained open when checked for this report. The [Markdown reproduction](../issues/1011-the-pull-request-review-plan-silently-drops-agent.md) names the failure, cause, two acceptable corrections, and regression-test expectation. Reproduce against current main before changing code; an open GHI can outlive a correction.

The defect is in [pull-request-review-plan.py](../../scripts/pull-request-review-plan.py): invocation from a checkout subdirectory can silently omit agent-facing text and split test suites. This is a useful bounded task because correcting the defect strengthens the process that will review later NedsChorus changes.

1. Spend at most 30 minutes establishing current assignments and choosing an unclaimed task. If the defect is already assigned or fixed, choose another small reproduced defect with an observable result.
2. Start from a clean, isolated worktree and a pinned Prime release. Record the version, model, task, base commit, working directory, and effective instructions. Use the official release instructions; do not silently track changing main.
3. Read the repository's applicable instructions and identify required behavior supplied by Claude-specific hooks. Start with direct interactive Prime use. Avoid writing an adapter first.
4. Have Prime reproduce the failure and create one regression test that fails before the correction and passes afterward. Choose either normalizing to the repository root or explicitly refusing a subdirectory, as the GHI permits. Keep the correction atomic.
5. Invoke existing affected-suite selection and submit through existing independent review. The reviewer examines the actual changed commit. Prime's success message is not the acceptance test.
6. During the trial, detach and reattach. Record whether work continued and whether the user had to reconstruct context. Test process death separately on disposable work after useful coding is established.

Stop expanding setup after two hours without a usable worker. Record the blocking operation and compare the relevant Pi or OpenHands interface. Do not spend the rest of the day porting all NedsChorus features merely to make the experiment possible.

**First possible addition: one small invocation adapter, only after direct use proves useful.** Select one existing caller and one provider path. The adapter should accept an explicit working directory and task, return the actual completion or failure state, and expose cancellation and the evidence location. Do not add a new scheduler, database, registry, or workflow language. Prefer the supported CLI/ACP interface over importing internal Rust crates or the raw daemon protocol. Verify the chosen mode supports the operations the caller actually needs.

If no repeated manual invocation problem appears, add nothing. Keep using Prime directly while completing NedsChorus tasks.

## One week of useful work

| Time | Action | Evidence to retain |
|---|---|---|
| Day 1 | Complete the assignment inventory and first coding experiment. | Reproduction, correction, test result, independent review outcome, and manual interventions. |
| Days 2 and 3 | Complete two more bounded changes with the same setup. Compare one fresh reviewer in Prime with the existing review path. | Context actually supplied, findings that hold, corrective iterations, elapsed time, model usage when available. |
| Day 4 | Test cancellation and restart on disposable work. If recovery is the main obstacle, compare a minimal Pi Durable example before writing more NedsChorus recovery code. | What survived, what had to be replayed, whether pending work was lost or repeated, and required human intervention. |
| Day 5 | Automate one repeated step if justified. Decide each paused task's disposition with its owner. | A short keep/pause/replace table tied to observed behavior and exact upstream version. |

The preferred week-end result is three useful changes accepted through the existing process, fewer manual handoffs, and at least one avoided infrastructure build. Those are trial targets, not promises of performance. If Prime adds more work than the current agent-binaries, preserve the evidence and try the closest alternative rather than rationalizing the migration.

## Rust and upstream collaboration

Use Rust where new code benefits from process ownership, concurrency, or typed protocol handling. Do not rewrite working Python scripts merely to match Prime. The existing scripts can remain executable tools, and language choice should follow the smallest successful integration.

Begin with an unchanged upstream version. Fork only when an observed requirement cannot be supplied through supported configuration or extension. Keep each downstream patch narrow, tested, and associated with the reason the patch exists and the upstream change that would let NedsChorus remove the patch. Avoid moving all project-specific review policy into Prime internals.

Prime's [contribution policy](https://github.com/PrimeIntellect-ai/prime-agent/blob/561274fb2461d8d5b51c5125bc319e6bf17f3e3c/CONTRIBUTING.md) directs public feedback to Discussions first and requires invitation for contributed implementation; unsolicited PRs from unvouched contributors are closed. Prepare reproducible failures before seeking collaboration. Sending a message or publishing a contribution remains a separate action from reading this report.

## Evidence and limits

The NedsChorus audit inspected code at 3b300b6e0eb35c087d420f4a67d9ccac106a2781 and refreshed main to e7db1e9245951f65ccedd926caa8957f03e1b2b2 before adding this document. The inventory covered 161 GHIs, 69 comments, and 121 associated Markdown files; principal plans received deeper inspection. This was not a line-by-line verification of every plan or a view into every running Claude agent-session.

Prime source inspection used 561274fb2461d8d5b51c5125bc319e6bf17f3e3c. Ten selected factory tests passed with fake hosts; 96 selected NedsChorus state-machine tests passed with scripted agents. Those tests establish limited implementation behavior, not end-to-end agent performance. No real model task, Rust build, Mac/ned-box recovery trial, or alternative-product integration was performed for this comparison. Alternative links describe current documentation inspected on 9 October 2026 and should be pinned before implementation.

Claude's next response should identify current work worth pausing, select the first unclaimed trial task, and name any concrete blocker. Additional general architecture prose is not the next deliverable.
