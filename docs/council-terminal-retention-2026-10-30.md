# Council decision and execution — 30 October 2026

## Question

Does the research gap appear in executable code, and is there one useful,
bounded extension that improves the central claim before the presentation?

## Independent reviews

Three reviewers inspected compiler correctness, recent research, and the
evaluation independently. All found that the existing guard, compiled
new-schema binding, migration, and replay path is real implementation. Two
initially recommended terminal-aware retention. The compiler reviewer first
proposed certifying some future new-schema-only rows; after checking both
options, all three agreed that projection-only retention is the better first
extension because it has a direct correctness argument and measurable effect
on the documented ICU history.

| Candidate | Research value | Decision |
| --- | --- | --- |
| Terminal-aware retention for projection-only old fields | Refines pipeline-specific retention using the row's actual terminal outcome. The real ICU case has 3,290 rows filtered before selecting dropped `vent_sari`. | **Implement now** within the existing row-wise VM. |
| Certify future new-schema-only rows from integer values | Could extend the preservation domain, but requires a separate preimage guarantee and an explicit indeterminate outcome for ambiguous rows. | Defer to a separate, fully specified study. |
| Joins, UDFs, multi-step evolution, broad query rewriting | Increase language and proof burden without addressing this measurable gap. | Defer. |

The recent comparison remains narrow: [Awiti et al. (2025)](https://reference-global.com/article/10.2478/fcds-2025-0006)
repair ETL operators, [Kramer et al. (2025)](https://www.vldb.org/2025/Workshops/VLDB-Workshops-2025/QDB/QDB25_4.pdf)
describe robustness and self-adaptation, [Auge and Heuer (2022)](https://arxiv.org/abs/2211.13810)
establish provenance-assisted recovery, and [Ortín et al. (2026 preprint)](https://arxiv.org/abs/2604.22415)
evaluate broader query behavior after migration. VeriFlow does not claim that
retention or query preservation was invented here. Its executable distinction
is a typed row-pipeline observation contract combining guards, compiled
bindings, and retention chosen for the pipeline and terminal outcome.

## Implemented boundary

1. The evolved executor identifies old fields loaded by any VM operation and
   binds them conservatively before executing operations. It defers only old
   fields absent from all operations until final `select`.
2. Sparse migration computes the old typed observation before choosing
   retained cells. If the row filters, rejects, or has an expression error,
   it omits cells used only by `select`.
3. A terminal row that lacked a universal static proof remains `recovered`
   in the ledger, even when its sidecar has zero old cells. Guard-only and
   full-row remain unchanged comparison strategies.
4. Persisted replay re-executes the generated plan, and bundle publication
   still requires every accepted old and replayed observation to match.

This is terminal-aware **projection** retention, not a claim of globally
minimal dynamic lineage. Inputs to all operations remain conservative, even
when a particular row stops before a later operation.

## Execution evidence

The four new migration tests cover a filtered versus emitted dropped value,
validation rejection, expression error, a selected field also read by an
operation, a failing guard on an inactive projection, and source-free replay.
The complete suite passed **107 tests** on Python 3.12.14.

The integrated study ran each strategy three times per case. On the 7,315
paired Malaysian Ministry of Health ICU rows:

| Recovered pipeline strategy | Accepted rows | Old cells retained | Sidecar bytes | Bundle bytes | Typed mismatches |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sparse, terminal-aware | 7,315 | 4,025 | 1,088,711 | 4,228,322 | 0 |
| Guard-only | 0 | 0 | 0 | 861,957 | Not applicable |
| Full-row | 7,315 | 36,575 | 1,728,544 | 4,868,160 | 0 |

All 7,315 accepted migrated rows also match the official post-change
projection by `(date,state)`. The sparse plan retains `vent_sari` for the
4,025 emitted rows and omits its old cell for the 3,290 filtered rows. This
removes **45.0%** of cells retained by the earlier static sparse plan and
**89.0%** relative to full-row retention. Empty recovered sidecars still carry
row metadata, so sidecar bytes improve only **4.6%** relative to the earlier
sparse plan; the total bundle improves **13.1%** relative to full-row. The
guard-only strategy rejects all rows in this workload, so its size and
mismatch count cannot be compared as preservation coverage.

## Final council assessment

The extension broadens the idea from *which fields this pipeline may observe*
to *which projection fields this row actually reaches*. It improves data
minimization on a documented real schema history without expanding the DSL.
No further compiler feature is recommended before the supervisor presentation.
For a stronger full paper, the next work is an independent second lossy
history, a comparable baseline, and external scrutiny of the proof scope.
