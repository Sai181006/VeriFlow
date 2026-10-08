# Working paper draft: pipeline behavior under schema migration

**Status:** technical draft for supervisor feedback, not a submission manuscript.
**Venue:** undecided. **Target:** within one month of 7 October 2026.

## Candidate title

Guarded Preservation of Row-Wise Pipeline Behavior During Schema Migration

## Abstract (draft)

Schema-level loss labels are too coarse to determine whether a particular data
pipeline changes behavior during migration. We study a restricted, deterministic
CSV pipeline language with typed fields, derived values, validation, filtering,
and projection. Given an explicit one-step schema mapping, our checker reasons
about observations of a legacy pipeline on well-typed old rows and on migrated
rows interpreted through a partial adapter while old rows remain available.
It returns a sufficient
preservation proof, executable guard, replayed breaking collision, or `unknown`.
The current proof rules cover exact field reconstruction and positive-integer
thresholds under decimal-to-integer truncation; narrow interval guards admit
additional rows for strict thresholds. On three public datasets with clearly
injected schema changes, the checker proves three record-lossy yet
pipeline-preserving cases. Across ten cases using 5,926 distinct source rows, one case remains
`unknown`; no row admitted by a proof guard changed its typed observation in
this pilot. Eight predeclared negative controls match their expected outcomes,
and four guarded CSV comparisons match old outputs and rejects on admitted
rows. The checker does not establish behavior on arbitrary new-schema
rows, malformed CSV, or unproved structural mappings.

## 1. Problem and motivating example

Suppose an old record has `score: decimal`, `name: text`, and an unused
`legacy_note`, while the new schema stores `score: int`, `name: text`, and no
note. Complete record reconstruction is impossible. Yet the pipeline
`keep where score >= 40; select name` makes the same decision after truncating
`score` toward zero for every finite decimal. The nearby predicate
`score > 40` changes its decision at `score = 40.7`. An aggregate migration
label of `lossy` cannot distinguish these pipelines.

The question is: when can an explicit schema migration preserve the decisions
and selected typed values of a specific pipeline over legacy records, and when
can the tool exhibit evidence of a change?

## 2. Contract and approach

Let `F` map an old row to a new row. Let `A` reconstruct only old fields that
the legacy pipeline can observe, and let `P` be the legacy pipeline. For each
well-typed old row `s` where the mappings are defined, a reported guard `G`
guarantees:

    G(s) => Obs(P, s) = Obs(P, A(F(s)))

An observation records emitted selected typed values, filtering, validation
failure with its message, or expression error. `let` fields are tracked
transitively; even an unselected `let` is treated as executed because it may
fail. The adapted execution uses the legacy program and a partial row adapter.
It is not currently a separately compiled program over the new schema. The
proof does not cover lexical spelling of CSV cells or arbitrary new-schema
rows. Guards require the original row, so the current tool supports decisions
at migration time; it does not certify new-only data after migration.
[The method note](impact-method.md) gives the exact domain, rule
arguments, and command behavior.

The checker first finds dependencies from executed operations and selected
outputs. Exact mappings preserve observed values. For decimal-to-integer
truncation, it proves `x >= k` and `x < k` invariant at integer `k >= 1`. For
`x > k` and `x <= k`, it guards out `k < x < k+1`, the only interval where the
atomic decision flips. This guard is exact for a single affected atomic
threshold; guards for composed expressions are only sufficient. Other uses of
the converted value fall back to an integral
source guard. Unsupported mappings are `unknown`. A bounded witness search
replays candidates through migration and the production VM; a collision of two
old rows with the same migrated row but different old observations proves that
no deterministic new-row-only pipeline can preserve both.

### Proof obligations for the supported fragment

Assume a finite, well-typed old row, a defined explicit forward mapping `F`,
and deterministic VM execution. For each field needed by an executed operation
or selected output, the checker either reconstructs its original typed value,
proves the relevant predicate invariant, or requires a guard that restores
exactness. These are sufficient conditions, not a decision procedure for all
pipelines.

**Exact-value lemma.** Copy and rename with unchanged types, and `int` to
`decimal`, reconstruct the same typed value. An integral old decimal also
survives `decimal` to `int` and back. If every changed field read by an
operation has this property, the operation receives the same VM operands.
Induction over the ordered `let`, `require`, and `keep` operations then gives
the same derived values, short-circuit choices, validation message, filter
decision, and selected typed output. An expression error occurs at the same
operation on both paths.

**Threshold lemma.** Let `T(x)` truncate a finite decimal `x` toward zero and
let `k` be an integer at least one. Both `x >= k` and `x < k` have the same
truth value when `x` is replaced by `T(x)`. For nonnegative `x`, truncation
stays in the same integer interval; for negative `x`, both values remain below
`k`. Pointwise preservation extends through `not`, `and`, and `or`, including
short-circuit order, when each affected atom is covered by a rule.

**Exact gap lemma.** For a single affected atomic `x > k` or `x <= k`, the
truth value differs after truncation if and only if `k < x < k+1`. The guard
`x <= k or x >= k+1` therefore admits every preserving value for that atom.
For compound conditions, the conjunction of per-atom guards is sufficient but
may reject rows whose changes cancel or are masked; no optimality is claimed.
An executed derivation containing division falls back to the integral guard,
because truncation may turn a nonzero denominator into zero.

**Collision lemma.** If two valid old rows migrate to the same new row but
have different old observations, any deterministic program that sees only the
new row must produce the same result for both. It cannot preserve both old
observations. The implementation reports `breaking` only after replaying such
a pair. Absence of a bounded-search witness leaves the case `unknown`.

## 3. Implementation

The prototype extends VeriFlow's typed pipeline, schema-evolution plan, VM,
lineage report, and rejected-row runner. `impact-check` prints per-mapping
status, affected operations, field names, rule IDs, guards, and witnesses.
`run-evolved-report` accepts only proved or guarded plans. It evaluates guards
before lossy conversion and records failures in the rejects CSV. Its lineage
JSON includes the evolution plan's schema names, findings, and guards. Output,
rejects, and lineage files are published through the existing temporary-file
path after execution.
With `impact-check --input`, a read-only migration readiness report scans a
legacy CSV and shows the number and percentage of well-typed rows admitted by
the proved guard. That measured coverage helps decide whether the guarantee
is useful for a particular file; it does not strengthen the proof.

## 4. Pilot evaluation

We projected real rows from UCI Abalone (4,177), Iris (150), and Wine Quality
red (1,599), then injected explicit synthetic decimal-to-integer and drop
mappings. These are not historical schema changes. Each source has a safe
non-strict threshold, a nearby strict threshold, and a selected-value case;
Iris also has an unproved split case. The case sources, licensed data,
preparation script, hashes, and raw results are in
[evaluation/](../evaluation/README.md).

| Dataset | Safe `>=` case | Strict `>` case | Selected changed value |
| --- | --- | --- | --- |
| Abalone | preserved, 0 changed / 4,177 | conditional, 1,395 changed; guard admits 2,782 | conditional; guard admits 1 |
| Iris | preserved, 0 changed / 150 | conditional, 51 changed; guard admits 99 | conditional; guard admits 17 |
| Wine red | preserved, 0 changed / 1,599 | conditional, 385 changed; guard admits 1,214 | conditional; guard admits 190 |

The schema-level baseline labels all nine numeric cases `lossy`. A dependency
only ablation cannot prove any of the three safe cases because each uses the
converted field. These internal ablations are not comparisons to a competing
research system. First-ten-row differential testing is also reported, but an
absence of differences in a sample is not a guarantee. The checker leaves the
Iris split case `unknown` although its 150 tested rows preserve the selected
value. No guard-admitted row violated the claim in this pilot. `results.json`
contains compilation, impact-check, and end-to-end CSV timings measured as
five-run medians on one Windows machine. Conditional runs reject rows that the
old execution processes, so their timing difference is not a clean overhead
measure. The preserved cases process the same rows and are the relevant pilot
comparison for overhead.

Eight predeclared negative controls test validation, derived values,
expression errors, observed drops, failed text parsing, unsupported conversion,
and Boolean combinations. All returned the expected status and rule. Four
full CSV checks compared old and guarded execution on admitted rows; output,
rejection reasons, and counts matched in all four. The separate
[raw control and parity files](../evaluation/README.md) record these checks.

## 5. Related work and novelty boundary

| Prior work | What it already covers | Boundary of this draft |
| --- | --- | --- |
| [PRISM](https://www.vldb.org/pvldb/vol1/1453939.pdf) | Migration operators, impact analysis, data migration, legacy query rewriting | Our prototype checks typed row-pipeline observations and migration-time guards; it does not offer PRISM's general query rewriting. |
| [Fan, Geerts, and Zheng](https://www.pure.ed.ac.uk/ws/portalfiles/portal/17752772/paper_viewd.pdf) | Selected-information preservation, query preservation, and view determinacy | Selected preservation itself is prior art. We implement a narrow value-dependent check for validation/filter/projection outcomes. |
| [Mediator](https://arxiv.org/abs/1710.07660) | Equivalence of database-driven applications across schemas | We analyze one-step row pipelines and return guards or replay evidence; we do not prove general application equivalence. |
| [Conditional equivalence](https://www.microsoft.com/en-us/research/publication/conditional-equivalence/) | Conditions under which program versions are equivalent | Conditional equivalence and condition synthesis are prior art. Our claim is specific to explicit lossy migrations and executable legacy-row guards. |
| [BiDEL/InVerDa](https://arxiv.org/abs/1608.05564) | Bidirectional support for co-existing schema versions | Our partial adapter is a mechanism used for the narrow observation check, not a new bidirectional evolution language. |

Our candidate contribution is the small executable contract for
validation/filter/projection pipelines that combines sufficient
value-dependent guards, measured guard coverage, and replayed collision
evidence at migration time. We do not claim query rewriting, selected
preservation, conditional equivalence, or bidirectional adapters as new. A
venue-specific search must check for closer work before the abstract claims
novelty.

## 6. Threats and next steps

The preservation theorem covers only explicit one-step mappings, well-typed
legacy rows, a deterministic row-wise language, and the documented rule
fragment. It does not compare original CSV spellings, guarantee behavior on
future new-schema records, or prove split/merge preservation. The adapted plan
is interpreted through an adapter, which a reviewer may consider less
compelling than a standalone rewritten new-schema pipeline. The cases use
injected changes on three public datasets; they are reproducible but do not
represent an observed organization's migration. Conditional selected-value
guards may be too restrictive to be useful, as Abalone shows. Witness search
is bounded and cannot prove the absence of a break.

Before submission: expand the independent bounded operator matrix, add one
documented real schema history if available, decide whether a standalone
adapted plan is necessary for the target venue, obtain an independent expert
read, and revise title, related work, and page length for the chosen venue.
