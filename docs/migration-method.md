# Compiled migration and replay method

VeriFlow now compiles an old row pipeline plus an explicit one-step evolution
plan into an `EvolvedProgram`. The artifact records the **new schema**, a binding
for each old field the pipeline can observe, any guard or retention requirement
on that binding, and executable VM operations. Its execution reads a new-schema
row and optional retained old cells. It does not call the generic legacy-row
adapter. The existing VM instructions retain old register names; the generated
bindings fill those registers from new columns or the sidecar. This is a compiled
new-schema input plan, **not** a source-to-source rewrite into a new `.vfl` file.

The preserved observation contract remains restricted to well-typed old rows
whose forward mapping is defined. Guard admission is certified during migration
while the old row is available. A later arbitrary new-schema row cannot assert
that it passed a guard. The `migrate-run` command refuses an unsupported forward
mapping, uses sparse recovery for observed drops and failed guards, and rejects
malformed rows or mapping failures. `guard-only` and `full-row` are comparison
strategies. Each successful migrated row has a UUID row ID, and the replayed
observation is compared with the original before publication. Any mismatch
aborts the bundle.

From the repository root, for an Iris strict-threshold example:

```sh
python -m veriflow compile-evolved evaluation/cases/iris.strict.vfl --evolution evaluation/cases/iris.evolution.vfl
python -m veriflow migrate-run evaluation/cases/iris.strict.vfl --evolution evaluation/cases/iris.evolution.vfl --input evaluation/data/iris.csv --bundle iris-strict-bundle
python -m veriflow replay-migration --bundle iris-strict-bundle
```

The bundle path must not exist. Replay uses the persisted `program.json`; it
does not need the original `.vfl` files. The bundle contains:

| File | Role |
| --- | --- |
| `program.json` | Compiled new-schema bindings and VM bytecode. |
| `manifest.json` | Format version, strategy, and compiled-program digest. |
| `migrated.csv` | New-schema columns and `_veriflow_id` for every accepted row. |
| `ledger.jsonl` | Row IDs, admitted/recovered mode, migrated-row digest, and sidecar digest. |
| `sidecar.jsonl` | Retained old cells for recovered rows, joined by row ID. |
| `rejects.csv` | Stable `id,raw_cells_json,reason` layout for malformed or refused rows. |
| `replay.jsonl` | Typed-observation outcomes produced from the persisted bundle. |
| `summary.json` | Counts, bytes, duration, and observation mismatch count. |

Replay checks the compiled-program digest, unique row IDs, ledger order, and
each migrated row and sidecar digest before running the VM. These unkeyed
digests detect accidental mismatches and corruption; a party able to rewrite
the files and digests can forge a bundle. The UUID persists within the bundle
but is not an identifier supplied by the source dataset. The prototype does
not provide authenticated storage or cross-bundle identity continuity.

The `sparse` strategy retains a required dropped field on every affected row.
For conditional conversion, split, or merge mappings, it retains the observed
old source cell only on rows that fail its guard. The `full-row` strategy saves
every declared old field for every well-typed row. The `guard-only` strategy
rejects every row that fails a guard or requires an observed dropped field.
Both sparse and full-row preserve the admitted/recovered rows in the evaluated
fragment; guard-only preservation applies only to its admitted rows. Recovery
is sufficient, not proven storage-minimal.

To reproduce the comparison with the pilot and documented NYC311 addition
case, run:

```sh
python -m evaluation.migration_study
```

See [`migration-results.json`](../evaluation/migration-results.json) and the
[evaluation protocol](../evaluation/README.md). End-to-end timings include
different row counts and strategy-specific work, so they are not isolated
compiler or guard overhead. The NYC311 case is a two-row reenactment of a real
published field addition; its new-field defaults are chosen for this experiment
and are not observed NYC backfill values.
