# Second five-reader council: 8 October 2026

This is an adversarial review of the implemented prototype and pilot, not a
real external review. It is meant to focus the next month of work. The
[working draft](paper-draft.md), [method](impact-method.md), and
[pilot](../evaluation/README.md) are the reviewed artifacts.

## Council findings

| Reader | Immediate objection | Evidence in the current artifact | Proportionate response |
| --- | --- | --- | --- |
| Database researcher | “Is there novelty beyond query preservation and application equivalence?” | [PRISM](https://www.vldb.org/pvldb/vol1/1453939.pdf), [selected-information preservation](https://www.pure.ed.ac.uk/ws/portalfiles/portal/17752772/paper_viewd.pdf), and [Mediator](https://arxiv.org/abs/1710.07660) cover much of the conceptual space. [Conditional equivalence](https://www.microsoft.com/en-us/research/publication/conditional-equivalence/) also predates our guards. | Position the contribution as a restricted **migration-time, executable behavior contract** for validation/filter/projection pipelines. Add a comparison table naming what each prior system proves and what this prototype actually executes. Do not claim conditional equivalence or query rewriting as new. |
| Semantics researcher | “The adapted program is the old program behind a reverse adapter. Is the claim operationally useful, and when is the old row available for `G(s)`?” | `run-evolved-report` reads an old-schema CSV and checks guards before `migrate_forward`. It cannot evaluate those guards from only an arbitrary future new-schema row. | State migration-time scope in the title, abstract, theorem, and CLI docs. Give one execution diagram and an end-to-end replay example. Treat a standalone rewritten new-schema program and new-only guarantees as future work unless a chosen venue requires them. |
| Verification researcher | “Are `preserved` and `conditional` genuinely sound, including short-circuiting, errors, conversion failure, and dropped fields?” | The proof fragment is small and the tests sweep decimal boundaries; `Obs` uses the VM. Proof arguments are currently a table, and the dataset pilot mainly uses `keep` and `select`. | Write two explicit lemmas for threshold and gap guards, list theorem premises, and add a small adversarial matrix with `require`, derived `let`, division error, observed drop, failed conversion, and boolean combinations. Keep unsupported cases `unknown`. |
| Systems evaluator | “Were cases chosen to fit the rule, and are baselines and timing comparisons fair?” | The three public datasets use injected migrations; nine of ten cases share one numeric pattern. The dependency-only baseline is an internal ablation. Conditional executions reject rows early, so their runtimes cannot be interpreted as pure overhead. Abalone selected-value guard admits only 1 of 4,177 rows. | Report guard coverage prominently. Add negative controls and a preflight coverage summary for a supplied legacy CSV. Call coarse labels and lineage checks **ablations**, not competing systems. Use preserved cases for comparable overhead; report conditional timings separately as workload-dependent. |
| Artifact and paper reviewer | “Can I reproduce this exact manuscript, and is it ready for the selected venue?” | Data hashes and commands exist, but the repository has pre-existing uncommitted files and no venue has been chosen. The pilot has no real organizational schema history or independent expert review. | Freeze a reviewable revision or source archive and regenerate `results.json` before submission. Obtain supervisor/reader feedback and choose the venue. Describe all mappings as synthetic; a real history helps, but one more convenient public CSV does not by itself fix external validity. |

## Recommended feature addition

Add a **migration readiness report** to the existing `impact-check` path. For
a supplied legacy CSV it should combine: the proof status and rule, exact
guard, number and percentage of rows admitted/rejected by that guard, and a
replayed witness when one exists. The admission rate is a measured utility
estimate on that file, not part of the universal proof. This is a narrow
extension of code already present in `impact.py`, `reporting.py`, and the
evaluation script. It makes the paper's proposition concrete for a user
deciding whether to migrate a particular pipeline.

## Work to do now, without expanding the language

1. Add the migration readiness report and one CLI test showing a strict
   threshold that admits fractional rows beyond the risky interval.
2. Add a compact evaluation matrix with at least one `require`, derived `let`,
   expression error, observed drop/collision, and unsupported conversion.
   Record expected `preserved`, `conditional`, `breaking`, or `unknown` before
   running the checker.
3. Compare old and guarded CSV results on guard-admitted rows, including
   emitted values, filtered count, and reject reasons. Keep typed observation
   equivalence separate from byte-for-byte CSV formatting.
4. Put precise rule lemmas in the draft, including the exact safe set for one
   atomic strict threshold. Claim only sufficiency for composed expressions.
   Add the prior-work comparison and audit
   every use of “proof”, “equivalence”, and “overhead”.
5. Freeze the artifact and seek an independent read before submission.

## Deliberate research gaps

- A standalone source-to-source rewrite of the pipeline over the new schema.
  The current adapter execution answers a narrower migration-time question;
  rewriting is a separate system contribution and should be added only if the
  target venue demands it.
- Guards that can be checked from a new-schema row after the old row is gone,
  or provenance sidecars to recover lost values. This changes the storage and
  information model.
- General split/merge, text parsing, arbitrary arithmetic, joins, aggregates,
  UDFs, and SMT-based equivalence. The current checker should remain `unknown`
  for cases outside its proved fragment.
- Automatic mapping inference and multi-version migration chains. The paper
  assumes one explicit mapping and should continue saying so.
- Claims of generality to real organizational migrations. The current three
  public datasets support a reproducible pilot with synthetic changes. A
  documented real history is valuable if obtainable, but it is not something
  to fabricate or infer from these datasets.

## Decision

The viable one-month paper is a **scoped systems or workshop paper** about
migration-time contracts, guard utility, and replayed failure evidence. Its
research risk is novelty, not missing features. A broad equivalence or
automatic schema-evolution paper would require a different project.
