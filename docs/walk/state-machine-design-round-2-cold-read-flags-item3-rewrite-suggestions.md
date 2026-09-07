<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=84 tokens=42296 target=docs/walk/state-machine-design-round-2-cold-read-flags-item3-rewrite.md -->

# 1. What it says

## Opening

Item 3 separates two previously incorrect counting rules into two sub-steps, each demonstrated with a run, before asking for one decision. Builds count successful implementation writes and have a limit of three for each design version, while corrections count rejected-contract rewrites and have a limit of two before the user is involved.

## Item 3.1 of 2: When the third build is rejected, the machine opens an investigation — it does not consult the arbitrator

Three rejected implementation builds exhaust the build limit; sending the third one to the arbitrator would permit further builds and leave the limit ineffective. Reaching that limit instead opens `investigate-workflow`, with the arbitrator reporting the three builds and rejections so the user can choose redesign, contract correction, or stopping; the arbitrator is otherwise routed only by a red suite.

If a third build passes review but its red suite causes an arbitrator ruling that would send work back to the already capped implementor, the build limit takes priority. The investigation includes that ruling so the user sees both the exhausted budget and the arbitrator's conclusion.

## Item 3.2 of 2: A correction is free; the rebuild it forces is not

The document distinguishes a contract rewrite from the implementation work caused by it: a contract-only exchange does not consume a build, but rebuilding code after a corrected contract does. The example says the existing topology can turn two contract corrections into three counted builds, despite the aim of keeping prose-only exchanges free.

An implementor that cannot build from a contract stops without a build, a replacement contract is one correction, and the subsequent implementation write is the first build. A rebuild after a correction remains counted because it changes code, while the second contract correction opens an investigation, limiting a defective contract to two builds before the user sees it.

## Recommendation

The document recommends adopting both sub-steps and requests Y, N, or D.

# 2. Where you stumbled

1. [question] "the third unclosed build" — What makes a build “unclosed”?

2. [question] "opens `investigate-workflow`" — What is `investigate-workflow`, and how does it relate to the user-facing investigation described here?

3. [two-readings] "Two corrections have consumed the epoch's build budget while writing one line of code twice." The preceding run describes builds 1, 2, and 3, so it is unclear whether this means two code writes, three builds, or something else.

# 3. What it does not cover

1. [rule-conflict] "The ceiling beats the arbitrator." What happens when a contract reaches its second-correction ceiling while the implementation build counter is already at its ceiling, since both ceilings call for an investigation with different stated contexts?
