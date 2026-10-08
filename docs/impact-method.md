# Pipeline impact method and claim boundary

The prototype checks one explicit schema change against a legacy VeriFlow
pipeline. It evaluates the legacy pipeline on a migrated record by reconstructing
only the old fields that execution can observe. This is an executable adapted
plan, not a source-to-source rewrite into a new VeriFlow program.

The guard is evaluated on the original old-schema row **before** conversion.
This makes the implemented workflow a migration-time check and guarded runner
while legacy rows are available. It cannot certify an arbitrary new-schema row
after the old row has been discarded.

```text
old row s ────────────────> legacy pipeline P ──> old observation
     │
     ├──> guard G(s) ──> reject row if false
     └──> migration F ──> new row ──> partial adapter A
                                          │
                                          └──> legacy pipeline P ──> adapted observation
```

The two observations are compared in the analysis and evaluation. During CSV
execution, a failed guard is explicitly reported as a migration rejection.

For a well-typed old row `s`, let `F(s)` be the forward mapping, `P` the legacy
pipeline, and `A` the partial adapter for its observed old fields. The claim is:

    G(s) and F(s) is defined and A(F(s)) is defined
        implies Obs(P, s) = Obs(P, A(F(s)))

`Obs` is one of `emitted` with selected typed values in selection order,
`filtered`, `rejected` with the requirement message, or `expression-error` with
the error class. Output field names align by identity because the adapted plan
uses the same legacy selection. The domain is finite, well-typed old rows with
decimal values expressible by VeriFlow's CSV decimal syntax. Numeric comparison
uses exact rational values in the VM; text uses exact string equality. Original
CSV spelling, output decimal formatting, malformed rows, and arbitrary
new-schema rows are outside this preservation claim. The CSV runner separately
rejects malformed or guard-failing rows and records a reason.

## Sufficient rules

| Rule | Condition and argument |
| --- | --- |
| `exact-reconstruction` | Copy/rename of the same type and `int` to `decimal` reconstruct the same typed value. |
| `unused-source` | No executed `let`, policy, or selected output reads the old field, transitively. Its value cannot affect `Obs` on a well-typed row. |
| `positive-integer-threshold` | For finite decimal `x` and integer `k >= 1`, truncation toward zero preserves `x >= k` and `x < k`. Reversed comparisons, `not`, `and`, `or`, and derived booleans follow by composition. |
| `threshold-gap` | For `x > k` or `x <= k`, the result can change only when `k < x < k+1`. The guard admits values outside that interval. Multiple affected predicates contribute conjunctive guards. |
| `integral-decimal` | If a changed decimal value is integral, converting it to `int` and back leaves it equal. This fallback covers selected values, other expressions, and division-sensitive derivations. |

The positive-threshold rules do not apply to zero or negative thresholds.
For a pipeline whose only changed observation is one atomic `x > k` or
`x <= k` decision, with integer `k >= 1`, the gap is exact: every value inside
`k < x < k+1` flips that decision after truncation, and every value outside
preserves it. Thus the guard is maximally permissive for that atomic fragment.
For Boolean combinations and other operations, the checker only claims that
its combined guards are sufficient; one predicate's change may be masked by
another.
Division in an executed derivation prevents the threshold-only proof because
truncation may turn a nonzero denominator into zero. Unproved text conversions,
split/merge effects, and a dropped observed field return `unknown`; an observed
collision can upgrade `unknown` to `breaking`. Every `breaking` collision
contains two valid old records with the same migrated record and different old
observations, so no deterministic adapted pipeline using only that migrated
record can preserve both. A bounded witness search is diagnostic, not a proof
of preservation or a globally minimal counterexample.

`preserved` means `G` is true on the stated domain. `conditional` means the
listed executable guards suffice. `breaking` means a replayed collision proves
that the migration cannot preserve all old observations. `unknown` means no
supported rule or collision establishes a conclusion. The execution command
refuses `breaking` and `unknown` plans.

## Commands

```sh
python -m veriflow impact-check evaluation/cases/iris.safe.vfl --evolution evaluation/cases/iris.evolution.vfl
python -m veriflow impact-check evaluation/cases/iris.strict.vfl --evolution evaluation/cases/iris.evolution.vfl --input evaluation/data/iris.csv
python -m evaluation.run_study
```

`run-evolved-report` uses the same arguments as `impact-check`; its source file
must reference an existing input CSV and a new output path. It checks guards
against the original typed row before conversion, then writes output, rejects,
and lineage reports through the existing report publisher.

The optional `impact-check --input` path scans an old-schema CSV without
writing outputs. It reports well-typed and invalid row counts and the guard
admission rate on well-typed rows. For `breaking` or `unknown`, no row is
reported as safe, even if no guards were generated. Measured admission is a
utility statistic, not a proof.

See [evaluation/README.md](../evaluation/README.md) for the public-data pilot,
case definitions, raw results, and limitations.
