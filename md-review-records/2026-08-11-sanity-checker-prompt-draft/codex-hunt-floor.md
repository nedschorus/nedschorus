<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/agents/choirmaster/docs/drafts/sanity-checker-prompt-draft.md -->

1. “Status: DRAFT, walked and settled with the user 2026-08-11 (18 items; dispositions in git history at this file).” conflicts with the linked lessons file, which says “item 2” is “open” and “Items 3–10 below were never walked.” It also provides no way to locate the claimed 18 dispositions. This makes the draft’s status contradictory and unverifiable. Confidence: sure.

2. “It becomes a review cell only after the calibration protocol ... passes” is not executable from the named context. The protocol requires “commit 0890848’s `git-gatekeeper-design.md`,” S1–S9 rulings, scoring, and a second document, but no complete path, scoring rule, or pass condition is supplied. Confidence: sure.

3. “after the user walks the addition like any skill change” refers to an unexplained procedure. The file does not say what that walk consists of or when it is complete. Confidence: sure.

4. “The name ‘sanity-checker’” / “You are the sanity-checker.” The name is searchable but does not identify whether this is a reliability review, simplification review, consistency check, or smoke test. A future agent could infer the wrong scope. Confidence: unsure — the surrounding prompt narrows the meaning, but the name itself does not.

5. “Everything below the rule is the prompt itself.” No rule is identified; the visible `---` is a Markdown separator, not a named rule. The boundary between metadata and executable instructions is therefore ambiguous. Confidence: unsure — the separator may be what “rule” means.

6. “You receive MD files. They could be a design, plan, skill, or instruction document. It in turn may contain links ... Read the documents you are given and the documents they link.” This leaves the review subject unclear when multiple MD files are supplied, uses a singular “It” for a plural input, and gives no stopping point for recursive links, cycles, external links, inaccessible links, or linked code. The reviewer cannot determine what must be read or when reading is complete. Confidence: sure.

7. “changes ... that would make this a simpler, saner, safer plan” leaves “saner” and “safer” undefined. The later priority list operationalizes some meanings of “simpler,” but supplies no test for deciding whether a change is saner or safer. Confidence: sure.

8. “attempts to solve NP complete problems, like detecting every way a computer can edit a file.” Exhaustively detecting every way a computer can edit a file is not established as an NP-complete problem; it may involve unbounded programs or undecidable behavior rather than a finite decision problem in NP. This can send the reviewer toward the wrong analysis. Confidence: sure.

9. “In the case of guarding a file from edits, simply backing up that file, then checking if it has been altered.” A backup-and-check procedure detects some changes after the fact; it does not by itself prevent edits or specify when the check occurs, what copy is trusted, or how a race is handled. It is therefore not a literal solution to “guarding” the file. Confidence: sure.

10. “every change you propose must leave the system better — simpler or more autonomous, safer or more testable, and saner or more reliable.” The `or`/`and` structure supports incompatible readings: one reading requires an improvement from every pair, while another requires only one improvement overall. A proposal can improve readability without improving autonomy, safety, testability, sanity, or reliability. Confidence: sure.

11. “zero remembered human steps.” The same document requires user calibration and a user walk, and says the requesting agent triages findings with the user. If those are in scope, the absolute claim is contradicted; if they are out of scope, the scope is unstated. Confidence: sure.

12. “In the project owner’s words:” does not identify the project owner or establish whether this quote is a binding rule, a user preference, or merely background commentary. That matters because the quoted claims are used to guide decisions. Confidence: unsure — the surrounding references may make the intended person obvious to the author.

13. “the steps, states, or algorithm is both hundreds of times faster, deterministic, followed exactly, and can be tested and tuned exactly.” Code is not inherently hundreds of times faster, deterministic under all environments, followed exactly, or exactly testable and tunable. An inefficient script, a network-dependent program, or buggy code is an ordinary counterexample. Confidence: sure.

14. “Ten, a hundred, or even a thousand lines of Python is in actuality simpler to debug than invoking an agent with a short prompt.” This is not generally true. A large Python program can be harder to debug than a short prompt for a simple task, depending on the code, tests, and failure mode. Confidence: sure.

15. “Good code works or doesn’t.” Code can be partially correct, intermittently correct, environment-dependent, or correct for only a subset of inputs. The binary claim gives no usable account of those reachable cases. Confidence: sure.

16. “Trading long and complex for shorter and simpler is a win ... but so is trading simple and short prompts for 100% predictable, but far longer code.” Neither trade is always a win, and code cannot generally be 100% predictable in the presence of time, I/O, failures, concurrency, or external services. Confidence: sure.

17. “the real work did not disappear or even shrink, it moved somewhere invisible and difficult to test.” A prompt can genuinely remove manual work, and model behavior can be logged, evaluated, and tested. The sentence treats one possible failure mode as universal. Confidence: sure.

18. “The model handles what truly needs interpretation ... ranking alternatives no known libraries or algorithms cover.” “Truly needs interpretation,” “semantically complex,” and “no known libraries or algorithms cover” have no decision test. The reviewer cannot establish the negative claim that no applicable library or algorithm is known. Confidence: sure.

19. “Code handles everything where variability adds nothing.” “Everything” is broader than the stated examples can support. A code path can still depend on variable environments, and some tasks with stable goals require semantic interpretation of malformed or ambiguous input. Confidence: sure.

20. “For every component, step, state, or dependency ... ask these questions in this order and report the earliest one that applies.” There is no procedure for enumerating hidden, dynamic, or undocumented components and dependencies, and no outcome is specified when none of the questions applies. It also conflicts potentially with the later instruction to list every prompt-to-code opportunity, even when a preceding “Delete” question applies. Confidence: sure.

21. “stable, easily understood code,” “a bounded set,” “a simpler or saner result,” and “a more reliable, more maintainable, easier-to-test result.” These are the decision predicates for the ladder, but no baseline, threshold, or comparison method is supplied. Two reviewers can reach opposite earliest-rung decisions while both following the text literally. Confidence: sure.

22. “the mechanism you propose ... must pay for itself by preventing a real failure or removing a recurring cost.” This excludes findings whose benefit is improved comprehension, testability, or safety without preventing a named failure or recurring cost. It also does not fit a deletion, which proposes no new mechanism. Confidence: sure.

23. “A step that works reliably today, costs little, and fails loudly is not a finding.” This conflicts with the later required hunts for “outputs with no consumer,” “duplicated normative homes,” and “dead code”: such an item can work reliably, cost little, and fail loudly while still belonging to one of those cut classes. Confidence: sure.

24. “list every place the design relies on an LLM following English instructions where a script could do the job.” Given only MD files and whatever links are accessible, the reviewer cannot establish every such place in unprovided code or hidden workflow. “Could do the job” also has no boundary between a reliable script and a brittle approximation. Confidence: sure.

25. “A better way” is too generic to be self-documenting or reliably searchable. It does not identify whether the section concerns alternate architecture, requirements reframing, missing dependencies, or unknown risks. Confidence: sure.

26. “are we missing something important, an unknown unknown?” An unknown unknown cannot be identified literally while it remains unknown, and the prompt supplies no stopping point for this open-ended search. Confidence: sure.

27. “nothing and no one reads it.” A machine can consume an emitted value through a trigger, threshold, permission check, or event without a person “reading” it. The definition can therefore classify a live consumer as absent and justify a false deletion. Confidence: sure.

28. “the same rule stated authoritatively in two places, guaranteed to drift apart.” Duplication does not guarantee drift: two immutable copies can remain identical indefinitely. The claim overstates the risk and does not distinguish harmful duplication from intentional separate copies. Confidence: sure.

29. “Guards that guard nothing — checks whose failure condition cannot occur, or whose failure changes nothing downstream.” A useful guard can deliberately make failure produce no downstream state change; an authorization check that blocks an operation is an ordinary example. The definition would misclassify a guard whose purpose is to stop downstream effects. Confidence: sure.

30. “dead code and dead distinctions — code no path reaches, and distinction-carrying names no machine consumes.” This conflicts with “Forcing functions count as consumers,” where a human being forced to decide is explicitly a consumer even if no machine consumes the value. It also lacks the roadmap exception given later for currently unreachable machinery. Confidence: sure.

31. “You may be given the project’s forward plan.” The roadmap rule is necessary to decide whether a mechanism is cuttable, but the input contract does not require the forward plan or specify what happens when it is absent. “Needed at scale” is also undefined. Confidence: sure.

32. “Before declaring something unconsumed, ask who is forced to decide something because it exists.” The file gives no way to discover indirect, external, or human consumers, and “elsewhere” has no boundary. A reviewer cannot reliably conclude that the forced-decision set is empty. Confidence: unsure — this may intentionally delegate the judgment to the reviewer, but the result is not reproducible.

33. “it moves cost from build-time to forever.” A recurring human step may exist only during migration, release support, or a finite operating period; “forever” is literally false. A recurring step can also buy a safety property, so “not a simplification” requires the project-specific priority to be scoped more narrowly than this sentence. Confidence: sure.

34. “Solve the known, easily identified parts, and note the unsolvable remainder explicitly.” The prompt supplies no test for deciding that a remainder is unsolvable and no stopping point for solving all “known” parts. A reviewer can continue indefinitely or label an unknown limitation unsolvable without evidence. Confidence: sure.

35. “look for ‘ruled’/‘RULED’ annotations and walk-order blocks.” “Walk-order blocks” is undefined, and the rule assumes that every relevant ruling is marked with one of those strings. An unmarked ruling or differently formatted decision can therefore be missed. Confidence: sure.

36. “argue from the document’s own invariants.” “Invariant” is not defined, and a design or proposal may contain no explicit invariants. The reviewer is not told what grounds are acceptable in that case. Confidence: sure.

37. “which priority from the order above pays for it; ‘nothing’ is rarely true.” A deletion of genuinely dead code, or removal of a duplicate with no behavioral effect, can give up no stated priority. This instruction pressures the reviewer to invent a loss rather than report that none exists. Confidence: sure.

38. “COST — migration effort against what is already built.” The assignment does not guarantee access to the existing implementation, tests, deployment procedure, or migration state. A reviewer limited to the supplied MD documents cannot calculate this cost. Confidence: sure.

39. “every sentence elsewhere in the document, and every test, that becomes false or stale if this change lands.” “Every test” has no defined scope, and tests may be absent, external, hidden, or inaccessible. The requirement is therefore impossible to satisfy literally from the stated inputs. Confidence: sure.

40. “Order findings by depth of simplification, deepest first.” “Depth of simplification” is undefined and is not mapped to the six-question order or the three priorities. Findings with different kinds of benefit cannot be ordered consistently from this instruction. Confidence: sure.

41. “A wording-level trim is not worth reporting.” The assignment explicitly includes “making the MD file easier to read and understand.” A wording change can materially improve comprehension without being merely cosmetic, so the two instructions support incompatible readings of which clarity changes qualify. Confidence: unsure — “trim” may be intended to exclude only cosmetic edits.

42. “the rest is already lean is a finding” conflicts with the earlier statement that “your findings are design changes.” A statement that no further change is needed is not itself a design change, and the file gives no format for reporting areas that are already minimal. Confidence: sure.

43. “a 40-character commit id.” Git repositories can use 64-character SHA-256 object IDs, abbreviated IDs, refs, or other accepted identifiers. The example presents a project-specific representation as if it were general. Confidence: sure.

clean sections: none
