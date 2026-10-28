# Reproducible evaluation

The ten UCI pilot cases test explicit **synthetic** schema changes on real rows;
their publishers did not make those changes. A separate paired Malaysian ICU
history tests an actual documented rename and drop. The case files in
`cases/` are the complete pipeline and mapping definitions; `results.json` is
the raw output from `run_study.py` on Python 3.12.14 and Windows 11. The Git
base at the start of this work was `d725ff08f0a4d3f0f79ce433368e21f8dfb9c1d1`
with pre-existing uncommitted work, so the base hash alone does not identify
the prototype. Preserve these files and record a later revision before
submission.

## Data and preparation

- [UCI Abalone](https://archive.ics.uci.edu/dataset/1/abalone), DOI
  [10.24432/C55C7W](https://doi.org/10.24432/C55C7W), 4,177 rows. The study
  projects whole weight, rings, and sex from `abalone.data`.
- [UCI Iris](https://archive.ics.uci.edu/dataset/53/iris), DOI
  [10.24432/C56C76](https://doi.org/10.24432/C56C76), 150 rows. The study
  projects sepal length, petal width, and species from `iris.data`.
- [UCI Wine Quality](https://archive.ics.uci.edu/dataset/186/wine+quality), DOI
  [10.24432/C56S3T](https://doi.org/10.24432/C56S3T), 1,599 red-wine rows.
  The study projects alcohol, quality, and residual sugar from the semicolon
  CSV. It does not use the white-wine file.

All three UCI pages state the data license as CC BY 4.0. The raw downloads and
prepared projections are in `data/`. `run_study.py` pins each raw file's
SHA-256 and records prepared-file hashes in `results.json`.

From the repository root:

```sh
python -m unittest discover -s tests -q
python -m evaluation.run_study
python -m evaluation.negative_controls
python -m evaluation.csv_parity
python -m evaluation.recovery_study
python -m evaluation.structural_matrix
python -m evaluation.freeze_manifest
python -m evaluation.migration_study
```

## Integrated compiled migration study

`python -m evaluation.migration_study` writes
[`migration-results.json`](migration-results.json). It runs the ten synthetic
pilot cases under three strategies, with three end-to-end repetitions each:

- `sparse` admits guard-passing rows and retains only needed old cells on
  guard failures or observed drops.
- `guard-only` rejects rows that fail a guard or need an observed dropped field.
- `full-row` retains every declared old source cell for every well-typed row.

The study also runs an observed-drop collision control, two pipelines over an
[actual Malaysian Ministry of Health ICU rename-and-drop history](real_history/README.md),
and a [two-row NYC311 field-addition reenactment](real_history/README.md). The city
documented the 2018 addition and the source rows predate it, but the new-field
values are experimental empty defaults, not an observed official backfill.
The NYC311 case is limited real-history evidence, not a real before/after
snapshot. The Malaysian case has actual paired versions with 7,315 matched rows
and a removed field that is nonzero in 4,060 old rows. The study compares every
migrated Malaysian row to the actual post-change projection, and separately
replays the typed pipeline observation. The two Malaysian pipelines reuse the
same source rows.

Results include admitted, recovered, and rejected rows; retained cells;
sidecar, ledger, migrated, and total bundle bytes; three-run median elapsed
time; and typed observation mismatches on admitted or recovered rows. The
guard-only mismatch count excludes its rejected rows, so compare it with
admission coverage. End-to-end timings include analysis, migration, writing,
and disk replay, while the strategies process different numbers of rows.
They are not isolated overhead measurements. Total bundle bytes include the
compulsory migrated rows, ledger, compiled plan, replay, rejects, and summary;
sidecar bytes count only retained-cell entries. See the
[migration method](../docs/migration-method.md).
Recovered rows may carry per-field guard certificates for other observed fields
whose guards passed before migration; the [mixed-guard regression](../tests/test_migration.py)
tests this alongside one retained field.

Use `python -m evaluation.run_study --fetch` only to refetch the three UCI raw
files. The ordinary run uses the included files and needs no network access.
It rewrites the prepared projections and `results.json`.

The other two commands run eight **predeclared** negative controls and four
full CSV parity checks. They write `negative-controls.json` and
`csv-parity.json`, respectively; neither downloads data. The controls cover
`require`, a derived `let`, an expression error, an observed drop with a
collision, text parsing, an unsupported type conversion, and mixed Boolean
predicates. The CSV checks compare output and rejects files on guard-admitted
rows, including requirement messages and an expression error. The preserved
Iris case compares all 150 rows.
`recovery_study` replays each case with a sparse observation sidecar and writes
`recovery-results.json`. Across these ten repeated workloads, it retains 7,549
cells versus 35,706 cells for retaining every observed source field on every
row. All replayed typed observations match. These are cell counts, not byte
sizes; cases reuse the same source rows and are not independent datasets. See
the [recovery method](../docs/recovery-method.md) for its proof scope and a
JSONL export command.
The same script also replays an observed-drop collision: two old rows migrate
to the same new row, while one retained `name` cell per row restores their
distinct legacy outputs.
`structural_matrix` enumerates 3,280 short text rows over two delimiters,
including overlapping `aa`. It writes `structural-matrix.json`; every admitted
row and every recovered row matched the old typed observation. This bounded
experiment probes edge cases and is not a universal proof.
`freeze_manifest` hashes the current code, tests, docs, case definitions, data,
and raw result files into `artifact-manifest.json`. Rerun it after any edit to
those files. This identifies a reviewable snapshot even while the repository
contains uncommitted work; it does not create a Git commit.

To inspect measured guard utility before executing a migration:

```sh
python -m veriflow impact-check evaluation/cases/iris.strict.vfl --evolution evaluation/cases/iris.evolution.vfl --input evaluation/data/iris.csv
```

This read-only report includes the proof rule, guard, replayed witness, and
coverage among well-typed rows. On Iris it admits 99 of 150 rows (66.00%).
Coverage describes this file; it is not part of the universal proof.
For the guarded text split demo, replace the case paths with
`iris.split.vfl` and `iris.split_evolution.vfl`; the report shows a
delimiter-free witness and admits all 150 Iris rows.

## Cases and results

| Data | Pipeline | Impact | Changed observations without guards | Rows admitted by guard |
| --- | --- | --- | ---: | ---: |
| Abalone | `whole_weight >= 1`, select rings | preserved | 0 / 4,177 | 4,177 / 4,177 |
| Abalone | `whole_weight > 1`, select rings | conditional | 1,395 / 4,177 | 2,782 / 4,177 |
| Abalone | select rings and whole weight | conditional | 4,176 / 4,177 | 1 / 4,177 |
| Iris | `sepal_length >= 5`, select species | preserved | 0 / 150 | 150 / 150 |
| Iris | `sepal_length > 5`, select species | conditional | 51 / 150 | 99 / 150 |
| Iris | select species and sepal length | conditional | 133 / 150 | 17 / 150 |
| Iris | split species, select species | conditional | 0 / 150 | 150 / 150 |
| Wine red | `alcohol >= 10`, select quality | preserved | 0 / 1,599 | 1,599 / 1,599 |
| Wine red | `alcohol > 10`, select quality | conditional | 385 / 1,599 | 1,214 / 1,599 |
| Wine red | select quality and alcohol | conditional | 1,409 / 1,599 | 190 / 1,599 |

For the nine numeric-conversion cases, the schema-level label is `lossy`; the simple
lineage-only baseline is `unknown` because it sees a used converted field.
The checker proves all three safe lossy cases. Across the ten case definitions,
three are `preserved` and seven are `conditional`, including the split case.
No admitted row violated the stated guard in this dataset run. The eight
negative controls also matched their declared status
and rule; the division case now includes a replayed expression-error witness.
The split guard admits all 150 Iris rows because their `species` values contain
the delimiter; a delimiter-free old value would be rejected. The Abalone
selected-value case
admits only one row on this dataset, showing that a formally valid guard can
offer little operational benefit. A ten-row differential sample is
reported in `results.json` as a diagnostic baseline, never as proof.

`results.json` also records rule IDs, witness availability, guard counts,
five-run median compilation and impact-analysis times, and five-run median end-to-end CSV execution time
for the old and guarded paths. Timing includes parsing/validation of CSV rows,
the VM, and output/reject/lineage file generation. It excludes network download
and temporary input copying. These single-machine pilot timings are not
performance generalizations. Conditional runs reject some rows before normal
pipeline execution, so their timing difference from the old run is not a pure
overhead estimate. The `preserved` cases process the same rows and give the
more comparable pilot cost measurement.

## Limits for a submission

The three UCI datasets still use injected changes. The Malaysian case supplies
one real organizational schema event, but its two pipeline definitions are
experimental and do not represent the Ministry's operational pipelines. A
single change does not establish generality across organizations or migration
types. The sampled data cannot prove universal soundness; rule arguments and bounded
tests in [impact-method.md](../docs/impact-method.md) carry the scoped claim.
The method lacks a general proof for unguarded structural changes, arbitrary new-schema row guarantees,
malformed-row equivalence, and a standalone rewritten new-schema program. A
venue-specific novelty review and an independent technical read are still
needed before calling this submission ready.
