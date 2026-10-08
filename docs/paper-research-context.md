# Paper research context (working research direction)

This document records the research question and prior-work position for
VeriFlow. A restricted checker and pilot evaluation are now implemented; this
does not establish that the contribution is novel enough for a particular
venue. The actual contract and rule arguments are in
[impact-method.md](impact-method.md), with results in
[evaluation/README.md](../evaluation/README.md). The language and schema rules
remain documented in [language.md](language.md) and
[schema-evolution.md](schema-evolution.md). A second, implementation-aware
[five-reader review](council-review-2026-10-08.md) records objections,
short-term additions, and deliberately deferred gaps.

## Existing foundation and motivating defect

VeriFlow has a typed CSV pipeline compiler with `let`, `require`, `keep`, and
`select`; static field lineage; a VM; rejected-row reporting; and explicit
schema-evolution rules. This is the foundation, not the paper contribution.

The original evolution report gave each mapping one `lossless`, `conditional`,
`lossy`, or `unsupported` label, checked only old -> new -> old, and silently
reconstructed a dropped old field as `None`. Directional classifications and
reverse checks now expose the added-default asymmetry, and dropped required
fields raise a missing-information error. The legacy aggregate label remains
for compatibility and must not be quoted as a directional guarantee.

The current compile-time benchmark uses one 327-character program and excludes
CSV execution. It is useful as a smoke measurement, not as evidence for the
proposed research claim.

## Research question and implemented proposition

**Question:** Given an explicit schema change and an existing VeriFlow pipeline,
when does processing migrated legacy data preserve that pipeline's decisions
and selected values, even if the complete old record cannot be recovered?

**Proposition:** Add a pipeline-aware migration checker that derives sound
sufficient conditions for behavior preservation on a defined fragment of
VeriFlow. It should report one of:

- `preserved`: the condition is true for every record in the stated domain;
- `conditional`: a checkable guard is sufficient for preservation;
- `breaking`: a valid, replayable record demonstrates changed behavior; or
- `unknown`: the supported analysis cannot establish either conclusion.

The checker executes a partial adapted plan and enforces proven guards during
CSV execution. An `unknown` result is refused by the evolved runner. A replayed
counterexample establishes a failure; failure to find one is not a proof.

For an old well-typed row `s`, let `F(s)` be its forward migration, `P_old` the
old pipeline, and `P_new` the adapted pipeline over the new schema. The intended
claim for a guard `G` is:

    G(s) and F(s) is defined  =>  Obs(P_old, s) = Obs(P_new, F(s))

`Obs` records whether the row is emitted, filtered, rejected by a `require`, or
stopped by an expression error. It includes the associated requirement message
or error class and the selected typed values. Output names align by identity
because the adapted execution uses the legacy selection.
The first analysis concerns well-typed legacy rows. Exact CSV cell spelling,
malformed CSV/type-error behavior, and arbitrary new-schema rows need separate
claims and are not implied by this equation. The tool must say which guarantee
it is reporting. It must not call the present pair of adapters a lawful lens.

Example: an old `decimal score` becomes an `int score`, while `legacy_note` is
dropped. The pipeline `keep where score >= 40; select name;` can preserve its
observable behavior even though source records lose information. Replacing the
condition with `score > 40` breaks it for `score = 40.7`, because the current
integer conversion truncates that value to `40`. This illustrates why a
pipeline-specific result can be more useful than a record-level loss label.

## Position against prior work

| Work | Established result | Boundary for this proposal |
| --- | --- | --- |
| [PRISM](https://www.vldb.org/pvldb/vol1/1453939.pdf) | Schema migration, impact analysis, and legacy query rewriting | Rewriting alone is not a novelty claim; examine value-dependent preservation of VeriFlow validation, filtering, and projection. |
| [Fan, Geerts, and Zheng](https://www.pure.ed.ac.uk/ws/portalfiles/portal/17752772/paper_viewd.pdf) | Theory of preserving selected information under transformations | Selected preservation is prior art; the proposed contribution is an executable, restricted analysis with guards and witnesses for this pipeline language. |
| [Mediator](https://arxiv.org/abs/1710.07660) | Verification of equivalence between database applications under different schemas | The proposed scope is smaller and row-wise, with conditional guarantees and actionable failures. |
| [BiDEL/InVerDa](https://arxiv.org/abs/1608.05564) and [Cambria](https://dspace.mit.edu/entities/publication/06a1140a-343d-4b1b-ad8a-5d8c5848c8f4) | Bidirectional schema transformation mechanisms | Generating forward/reverse adapters is prior art; the target is pipeline behavior under migration. |
| [Auge and Heuer](https://arxiv.org/abs/2211.13810) | Inversion of schema evolution with additional provenance | Recovery of entire source data or a sub-database is not the initial goal. Minimal recovery sidecars are deferred. |
| [Kramer, Restat, and Störl](https://www.vldb.org/2025/Workshops/VLDB-Workshops-2025/QDB/QDB25_4.pdf) | Operator robustness categories and a decision tree for data cleaning under schema evolution | Their conceptual framework motivates testing an executable checker on a precisely defined operator fragment. |
| [Foster et al.](https://www.cs.cornell.edu/~jnfoster/papers/lenses.pdf) | Laws for well-behaved bidirectional transformations | Do not use the term `lens` for VeriFlow's adapters without satisfying those laws. |
| [Kawaguchi, Lahiri, and Rebelo](https://www.microsoft.com/en-us/research/publication/conditional-equivalence/) | Conditional equivalence of program versions under subsets of inputs | Conditional preservation is prior art; our candidate result is restricted to explicit migrations with executable row guards and replay evidence. |

This is a targeted literature position, not an exhaustive novelty search. The
paper should avoid a "first system" claim until a venue-specific review is done.

## Five likely reviewer objections and responses

1. **Novelty:** Query rewriting and selected-information preservation already
   exist. State the narrower contribution, compare with those results, and
   demonstrate added value beyond a field-dependency warning.
2. **Vacuous equivalence:** Defining `P_new` merely as `P_old` after a reverse
   adapter can hide the actual question. Compare `P_old(s)` with
   `P_new(F(s))` over valid old rows, including effects of information loss.
3. **Unsound safety:** A single sampled round trip or a missing counterexample
   cannot prove equivalence. Prove each supported rule, replay witnesses through
   the runtime, and return `unknown` for unsupported expressions or mappings.
4. **Low utility:** A checker that rejects every lossy mapping adds little.
   Measure how many genuinely safe cases it accepts over a lineage-only
   baseline and how selective the guards are on data.
5. **Weak evidence:** One toy program or synthetic cases alone are not enough.
   Add documented real CSV case studies, controlled mutations with known
   outcomes, fair baselines, and end-to-end overhead measurements.

## Deliberate initial boundaries

- Explicit, user-approved mapping rules; no claim of automatic rename/split/
  merge inference.
- One schema change at a time; no multi-version composition theorem.
- Row-wise deterministic VeriFlow expressions. Begin with copy, rename, add,
  drop, and numeric conversion. Give split/merge a sound mapping-level report,
  but return `unknown` for pipeline effects that are not proved.
- Well-typed legacy rows for the primary preservation theorem. Report the
  handling of malformed rows and future new-schema records separately.
- Sound sufficient guards, not necessarily the weakest possible guards.

Automatic mapping inference, arbitrary UDFs/joins/aggregates, optimal recovery
sidecars, full error-behavior equivalence, and multi-version histories remain
candidate future research. These exclusions must appear as limits in the paper,
not as capabilities of the implementation.

See [paper-research-tasks.md](paper-research-tasks.md) for the current work plan.
