# Supervisor and independent-reader packet

**Working title:** Guarded Preservation of Row-Wise Pipeline Behavior During
Schema Migration.

**Claim for review:** For a restricted typed CSV pipeline and an explicit
one-step mapping, the checker supplies sufficient proof rules or guards for
preserving the old pipeline's typed observation on well-typed legacy rows at
migration time. A replayed collision demonstrates a break when found. It does
not certify standalone execution on arbitrary new-schema rows.

## Read these first

1. [Working paper draft](paper-draft.md): contribution, formal contract,
   supported rules, evaluation, limitations, and closest work.
2. [Method note](impact-method.md): executable semantics and rule scope.
3. [Evaluation guide](../evaluation/README.md): datasets, injected cases,
   negative controls, CSV parity, commands, and artifact manifest.
4. [Council critique](council-review-2026-10-08.md): likely reviewer objections
   and the deliberately deferred research gaps.
5. [Venue decision note](venue-scout-2026-10-08.md): verified calls and fit.

## Decisions requested from the supervisor

- Select the intended paper type and venue, or give a specific alternative;
  confirm deadline, page limit, and artifact policy.
- Decide whether a full research-paper submission in the near-term window is
  sensible with synthetic schema changes over public datasets, or whether to
  target a later cycle after adding a documented real migration history.
- Identify a database or program-analysis reader who can independently test
  the proof and novelty claim before submission.

## Independent-reader challenge

Please try to falsify the claim rather than only edit prose:

1. Find a well-typed old row admitted by a `preserved` or `conditional` proof
   whose two executions have different typed observations.
2. Check whether expression errors, `require` messages, filtering, `let`
   dependencies, and selected outputs are represented consistently.
3. Check whether the `x >= k`, `x < k`, and strict-threshold gap rules hold over
   the implementation's actual decimal and truncation semantics.
4. Identify the closest earlier paper or tool that already provides the same
   pipeline-specific migration-time guarantee; say exactly how this work
   differs or fails to differ.
5. Assess whether the baseline comparisons and three public datasets with
   injected mappings support the abstract's claims.

Record any counterexample with the source schema, mapping, pipeline, old row,
expected observation, and actual observation. The research task remains open
until a reader outside this implementation effort has supplied feedback.
