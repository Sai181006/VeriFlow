# Final compiled migration execution report — 22 October 2026

## Implemented scope

VeriFlow now compiles a legacy row pipeline and an explicit one-step schema
evolution into an executable [`EvolvedProgram`](../veriflow/evolved.py). The
compiled program declares the new input schema, generated bindings for each
observed old field, guard and recovery requirements, and VM operations. It
runs from new-schema cells plus certified retained cells without invoking the
generic legacy-row adapter. The generated bindings still fill legacy VM
register names; this is a compiled new-schema input plan, not a textual `.vfl`
rewrite or a proof about arbitrary future new-schema rows.

[`migrate-run`](../veriflow/migration.py) now creates one bundle per run. It
chooses guard admission, sparse old-cell retention, or row rejection. It writes
UUID row IDs, migrated CSV, sidecars, a ledger, the persisted compiled plan,
rejects, replayed observations, and a summary. Replay reads the persisted plan
from disk without the original source or evolution files. `guard-only` and
`full-row` options provide explicit baselines. A changed typed observation
aborts publication of the bundle.

The documented [NYC311 2018 field addition](https://www.nyc.gov/311/nyc311-enhances-service-request-open-dataset.page)
was reenacted on two pre-change request records transcribed from a
[2016 CSV excerpt](https://alfa.im.pwr.edu.pl/~szwabin/assets/unst/lec/6.pdf).
The added fields use experimental empty defaults; this is not an observed
official before/after snapshot. The [case note](../evaluation/real_history/README.md)
states that boundary explicitly.

## Final execution

The reproducible comparison is [`migration_study.py`](../evaluation/migration_study.py)
with raw measurements in [`migration-results.json`](../evaluation/migration-results.json).
It runs the ten existing pilot cases, the two-row NYC311 addition case, and a
two-row observed-drop collision control. Each case runs under three strategies
with three end-to-end repetitions. The ten pilot workloads process **17,928
case-rows** but reuse **5,926 distinct source rows**. The total below includes
the four additional control/history rows and therefore counts repeated
workloads, not independent records.

| Strategy | Admitted | Recovered | Rejected | Old cells retained | Sidecar bytes | Total bundle bytes | Observation mismatches on processed rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Sparse | 10,381 | 7,551 | 0 | 7,551 | 1,221,480 | 7,312,456 | 0 |
| Guard-only | 10,381 | 0 | 7,551 | 0 | 0 | 3,911,068 | 0 |
| Full-row | 0 | 17,932 | 0 | 53,796 | 3,453,350 | 10,198,405 | 0 |

Sidecar bytes count retained-cell JSONL entries; total bundle bytes include
migrated rows, ledger, persisted plan, replay results, rejects, and summary.
Guard-only's zero mismatch count applies to its **10,381 admitted rows**; its
7,551 rejected rows were not processed or checked for preservation. Sparse and
full-row processed all valid rows in these cases. Runtime medians are in the
raw JSON. They include analysis, migration, file writing, and replay, with
different row counts by strategy; they are not isolated guard overheads.

The observed-drop control is the distinguishing recovery check: two old rows
produce the same new row but different selected `name` values. Sparse retains
one old cell per row and replays both observations; guard-only rejects both.
The NYC311 addition case admits both sampled rows without retention and
preserves their observations. Its tiny, add-only scope provides little evidence
about real lossy migrations.

The CLI smoke run used Iris `sepal_length > 5`: `migrate-run` admitted **99**,
recovered **51**, rejected **0**, and reported **0** observation mismatches.
Independent `replay-migration --bundle ...` loaded the saved compiled plan and
replayed **150** rows: 118 emitted and 32 filtered.

## Council review and resolutions

Three internal reviewers examined compiler correctness, research methodology,
and bundle integrity after the first implementation. Their findings and the
changes made are recorded here; this is an internal technical review, not
external peer review.

| Finding | Resolution |
| --- | --- |
| A replay mismatch could still publish a bundle. | `run_migration` now raises before publication; a test checks the destination never appears. |
| A changed sidecar value could pass the migrated-row digest check. | The ledger stores a canonical sidecar-content digest; replay verifies it. |
| A same-schema but different compiled program could replay a bundle. | `program.json` is persisted; its fingerprint is bound in `manifest.json` and checked on replay. |
| `_veriflow_id` could collide with a declared field. | The reserved name is rejected in both schemas. |
| An old-cell conversion exception could abort the whole input. | Conversion errors are quarantined per row. |
| Malformed rejected rows could make `rejects.csv` variable-width. | Rejects use fixed `id,raw_cells_json,reason` columns. |
| The evaluation lacked an integrated observed-drop baseline. | A two-row collision runs under all three strategies. |
| The NYC311 example could be overstated as a real before/after evaluation. | The report, dataset note, and paper draft label it a limited reenactment with experimental defaults. |

The second council pass found no remaining blocking correctness issue within
the stated fragment. It noted that unkeyed digests detect accidental
corruption, not deliberate forgery, and guard admission remains an assertion
made while the old row is available. The replay CLI also now catches malformed
CSV parser errors and reports them normally.

## Validation and reproducibility

The new focused migration tests cover direct new-schema execution without the
legacy adapter, all three strategies, row IDs, source-free replay, persisted
plan mismatch, migrated-row and sidecar corruption, observed-drop recovery,
merge binding, fixed-width rejects, and abort-on-mismatch publication. The
complete suite passed **101 tests** when run outside the filesystem sandbox.
The sandbox itself denies Windows hard-link creation used by pre-existing
output-publication tests; that restriction caused failures in a sandboxed
suite run and did not occur in the approved unsandboxed run. The migration
study and CLI smoke run also completed successfully. The study host reported
Python **3.11.9** on Windows; the package metadata currently declares Python
3.12 or later, so a 3.12 rerun remains appropriate before paper submission.

From the repository root:

```sh
python -m unittest discover -s tests -q
python -m evaluation.migration_study
python -m veriflow compile-evolved evaluation/cases/iris.strict.vfl --evolution evaluation/cases/iris.evolution.vfl
python -m veriflow migrate-run evaluation/cases/iris.strict.vfl --evolution evaluation/cases/iris.evolution.vfl --input evaluation/data/iris.csv --bundle iris-strict-bundle
python -m veriflow replay-migration --bundle iris-strict-bundle
```

The bundle path must be new. The [method](migration-method.md) describes its
files and trust boundary. The [artifact manifest](../evaluation/artifact-manifest.json)
records hashes of source, cases, data, and result files for review.

## Claim boundary and next research step

The guarantee remains about well-typed **old** rows with defined explicit
mappings, deterministic row-wise operations, and migration-time guard checks.
The compiled plan consumes new-schema cells but uses generated bindings to
execute the legacy VM program. It does not produce a new `.vfl` source file or
certify arbitrary new-only data. Sparse retention is sufficient, not globally
minimal. The bundle's UUID survives replay within that bundle but is not a
source-provided durable ID across separate migrations; its unkeyed hashes do
not authenticate an adversarially modified bundle.

The most valuable next evidence is an actual versioned before/after schema
snapshot with enough rows to test a nontrivial real migration. The NYC311 case
documents a real addition event, but cannot close the external-validity gap
for lossy conversions or structural changes. The paper should describe the
current work as a scoped executable migration system and keep that gap visible.
