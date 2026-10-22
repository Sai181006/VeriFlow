# Observation-scoped recovery sidecars

VeriFlow can retain a sparse set of old cells when a migration would otherwise
lose a legacy pipeline observation. This is a migration-time option for
well-typed old rows and explicit one-step mappings with a defined forward
operation. It complements the older guard-only runner. The integrated
[`migrate-run`](migration-method.md) command now combines admission, sparse
retention, rejection, UUID row identity, and replay from a compiled plan.

`plan_recovery` in `veriflow/recovery.py` uses the impact findings and
transitively observed fields. An observed dropped field is always retained.
For a conditional conversion, split, or merge, its observed source fields are
retained only on rows that fail the existing proof guard. Unused source fields
are never retained. Unsupported forward mappings are refused.

For an old row `s`, the migration `F(s)` and sparse sidecar `S(s)` are produced
together. Replay reconstructs the fields required by the old pipeline using
the ordinary adapter, then overlays the typed retained cells. Where a guard
passes, the existing impact rule proves the observation is preserved. Where it
fails, the corresponding observed old values are restored exactly. Thus the
supported claim is `Obs(P, s) = Obs(P, replay(F(s), S(s)))`, under the same
well-typed old-row and VM assumptions as the [impact method](impact-method.md).
The sidecar is sufficient, not guaranteed to use the fewest possible cells.
The evaluation includes an observed-drop collision that the guard-only checker
labels `breaking`; retaining the dropped observed field restores both distinct
legacy outputs.

The evaluation command writes [recovery-results.json](../evaluation/recovery-results.json)
and checks replayed observations on every row of the ten injected pilot cases:

```sh
python -m evaluation.recovery_study
```

The earlier standalone study can still export matching migrated CSV and JSONL
sidecar files for one case:

```sh
python -m evaluation.recovery_study --case abalone.strict --migrated abalone-strict.new.csv --sidecar abalone-strict.sidecar.jsonl
```

In this *older export format*, each entry has a one-based data-row number and
a `fields` object. Rows needing no retained value have no entry. It remains
paired by row order. The integrated bundle instead uses UUID row IDs and
checks row and sidecar digests; the digests are unkeyed and do not authenticate
deliberate rewrites. `reconstruct_with_sidecar` replays the saved values,
using old-schema field types to restore decimal values serialized as strings.

This implementation explores a narrower cost question than whole-record
inversion: how many source cells are sufficient for **this pipeline's**
observations? [Auge and Heuer (2022)](https://arxiv.org/abs/2211.13810)
already establish provenance-assisted recovery under schema evolution, so
retaining provenance alone is not a novelty claim. [Kramer, Restat, and Störl
(2025)](https://www.vldb.org/2025/Workshops/VLDB-Workshops-2025/QDB/QDB25_4.pdf)
call for broader structural operators and benchmarking adaptation mechanisms.
The current study supplies a small executable comparison, not a general
adaptation benchmark or evidence from a real organizational migration.
The [bounded structural matrix](../evaluation/structural-matrix.json)
additionally enumerates 3,280 short split/merge rows. It found zero admitted
or recovered observation mismatches; enumeration is diagnostic evidence rather
than a proof over arbitrary text.
