---
name: pull-request-review-write
description: Use BEFORE writing or revising a review on a pull request — whether asked by the user, by another agent, or as a seat's standing merge duty. Covers how the review is delivered: one finding per comment, each naming the condition under which the wrong thing happens. Not for reading a review someone else wrote.
---

# pull-request-review-write

## Write your review this way

- **One finding per comment.** Do not put several findings in one comment: a
  comment holding one defect and three preferences cannot be sorted, so all
  four cost a round trip.
- **Name the failing condition.** Each finding states the input, state, or
  timing that makes the code do something it should not. If you cannot state
  a finding that way, it is not a finding — raise it as a question instead.
- **Cite the location** as `path:line`.
