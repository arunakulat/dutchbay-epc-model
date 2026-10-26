`RECRUIT-01` module 3 §1 now states that a reviewer supplies findings, not subject bytes: where a
reviewer demonstrates a gap with code, that snippet is a description of the gap and the writer
reimplements it in its own terms rather than committing the reviewer's lines. The steward skill
carries the same instruction to the writer at the step where a review forces a change.

This closes a gap #1381 exposed, where a writer committed test lines copied verbatim from a
reviewer's record and nothing said who reviewed those lines. A writer that adopts them makes the
reviewer a co-author of the subject, so that lane's disposition on those bytes is a pass over its
own work rather than an independent review, and the two required dispositions stop being
independent. Reimplementing is what keeps the lane eligible to review the result, which is the
point: the reviewer who found the gap is usually best placed to judge whether the writer's own
version closes it. The finding stays credited to the reviewer.

The rule is a clarification of `RECRUIT-01`'s existing independence requirement rather than a new
canonical rule row, and `tests/lint/test_recruit_01_reviewer_supplied_code.py` pins the text,
its placement in the independence section, and its resistance to an exception added beside it.
