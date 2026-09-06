# nedschorus glossary

A list of the approved phrases and terms of this project, in alphabetical order. Generic SDLC vocabulary is deliberately absent. [do not include links as this will force the agents to read them].  Include key-terms that all or most agents might need. Do not include terms that will be rarely needed. Skills that fresh agents need to know to understand docs and workflows should be listed here too, since they will not have loaded them, they will not understand those phrases.

- **/cold read** — a skill used to improve the readability of prose.
- **/walk-me-through** — a skill that presents complex material to the user one item at a time and records his decision on each, sometimes known as walk.
- **adjudicator** - a fresh, and therefore neutral agent, used to resolve conflicts between agents. The adjudicator is told to read all the documents relevant to a conflict, and to work with the user to resolve these conflicts. Adjudicators can be used to solve hard merge issues, to resolve if the code or the test is the problem. and other problems best solved with user input.
- **agent-instructions** — prompts or MD files that instruct agents. Initial agent instructions are the agent-instructions given to an agent at its session start via the prompt that starts the agent or subagent. In addition, instructions can live in CLAUDE.md, CLAUDE.local.md, the project's appended system-prompt file, the project's memory index, a session-start hook, or the equivalent for non-Claude agents such as AGENTS.md.
- **agent-seat** — a named, long-lived agent identity with its own home directory, git branch and initial agent instructions; context compressed and renewed by a series of reincarnated agents connected by session handoffs from old agent to fresh agent.
- **Code Prompt Code (aka CPC)** — a combination of code and prompts that leverages the best of LLMs: vast knowledge, power, and flexibility, including the ability to recover from errors, with the best of code: speed, reliability, the ability to encapsulate very complex procedures, external systems and rules, to work with huge and complex (but rigid) data structures, and to use mature testing methodology.
- **fresh reader or fresh agent** — A minimal context agent, an agent that has read only CLAUDE.md, its initial agent instructions, and the documents selected for it to read, and (recursively) the documents referenced inside the selected documents. This project's durable documents are not targeted at the user. They are targeted at minimal context fresh agents, to enable parallelism and increase reliability.
- **GHI** — GitHub issue
- **GHI-MD** — the markdown document paired with a GitHub issue: the issue carries the state, the MD carries the substance. Replaces "pair document".
- **handoff-supervisor** — the per-seat program that launches a session and reincarnates it when it hands off.
- **hard-block** — a hook refusal with no override; only a change to the hook lifts it, often accompanied by additional context given to teach the agent the preferred behavior. There are three types of blocks, hard blocks, soft blocks and user blocks
- **merge-lane** — the seat on the user's Mac that reviews and merges every PR until the main-gatekeeper is live.
- **NedsChorus (aka NC)** — this project. Its goal is to increase the reliability of AI frameworks.
- **main-gatekeeper** — the program that is the only way a change reaches main: it takes declared files, commits them with a record in the commit, and pushes to main itself. Until it is live, changes reach main by PR through merge-lane.
- **reincarnate** — to replace a running session with a fresh one that continues from the session handoff.
- **review objection overruled by user** — a review objection overruled by the user. It states: the objection; why it was overruled; and if necessary, why a case specified here needs an exception to the user's overrule, with evidence listed or linked.
- **sanity-check** — a skill used to improve designs
- **session handoff** — the file or process used to transfer the key context and state of one LLM session to another.
- **soft-block** — a hook refusal the agent can override by including a reason why the override is needed.  Usually accompanied by additional context given to teach the agent the desired behavior.  
- **user ruling** — a decision by the user, recorded where it applies with its date: (user-ruled <date>)
- **user-block** - a hook refusal that can only be cleared by the user.
- **walk minutes** — the document the walk skill uses to record the decisions or results made in the walk. It includes: a link to the documents reviewed by the walk, a list of the results of the walk, and which steps were completed, so that the walk can resume later. File: `docs/walk/<name>-minutes.md`.
