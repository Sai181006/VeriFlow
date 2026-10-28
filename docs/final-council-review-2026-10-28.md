# Final internal council review — 28 October 2026

**Reviewed artifacts:** the current VeriFlow implementation, migration tests and evaluation, [paper draft](paper-draft.md), and the eight-page detailed execution report in `output/docx/`.

**Review method:** three independent internal readers examined compiler correctness, evaluation, and recent related work. This is an internal technical review, not external peer review. The council did not change implementation or results.

## Decision

VeriFlow has a coherent, narrow contribution for a workshop or systems/demo paper: a compiled new-schema input plan for a deterministic row pipeline, migration-time value guards, selective recovery, and persisted replay of typed observations. The current artifact is **not submission ready**. One mixed-guard execution defect must be fixed; the main research gap is a substantial real lossy migration history. Adding broad compiler features now would not address either issue.

The eight-page Word document is a detailed supervisor report, not a venue-formatted research manuscript. It explains the implementation and pilot honestly, but a submission needs an updated paper draft, a sharper comparison to close prior work, and stronger external evidence.

## Council findings

| Reader | Finding | Evidence | Priority |
| --- | --- | --- | --- |
| Compiler | A row with mixed guard results can be rejected even when selective retention could preserve it. | `migration.py` computes a row-wide `guard_pass`, retains only fields for failed rules, then calls `execute_evolved(..., admitted=False)` for the recovered row. `evolved.py` requires retention for every guarded binding when `admitted=False`. | **Fix before submission** |
| Compiler | The split guard warrants closer inspection; its admission set should match the actual forward/reverse code. | `impact.py` and `evolution.py` implement the guard and split mapping. | Checked below; no change needed |
| Evaluation | The ten main migrations are injected changes on three reused public datasets; the only documented history case is a two-row, add-only NYC311 reenactment with experimental defaults. | `evaluation/README.md`, `evaluation/real_history/README.md`, `evaluation/migration_study.py`. | **Main research gap** |
| Evaluation | The reported 17,932 are repeated case-rows over 5,926 distinct source rows. Guard-only's zero mismatches exclude its 7,551 rejected rows. Three-run timing medians compare strategies processing different row counts. | `evaluation/migration-results.json` and its protocol. | Preserve these qualifications in every abstract, chart, and result table |
| Reproducibility | The migration study records Python 3.11.9, while package metadata requires Python 3.12 or later. | `evaluation/migration-results.json`, `pyproject.toml`. | Rerun on a supported runtime |
| Research | The working draft still says the adapted path uses the old adapter and is not separately compiled, although the current code has generated new-schema bindings. Its related-work table omits a close 2025 ETL repair paper. | `docs/paper-draft.md` §2 versus §3; `veriflow/evolved.py`; Awiti et al. (2025). | Rewrite before submission |

## Reproduced compiler defect

Use two observed decimal fields `a` and `b` converted to integers, with pipeline predicates `a > 40` and `b > 40`. For old values `a = 41.7` and `b = 40.7`, the first guard passes and the second fails. Sparse retention should save `b` and reconstruct the original observation using the certified `a` and retained `b`. Current migration retains `b`, marks the row recovered, and then rejects it with `Guard certificate or retained 'a' is required`. The defect also affects a row recovered for an observed drop while another guarded field passes.

The row-wide admission flag loses information about *which* bindings passed. A focused repair is to persist the passed binding certificates per row and let replay use a certificate for one binding while using a retained cell for another. Add a mixed-pass/fail regression test and an observed-drop-plus-guard test. If a smaller implementation instead retains every guarded field whenever a row is recovered, update the sparse-storage claim and regenerate all byte counts. This defect does not show an incorrect output among rows the current study processed; it shows that a valid recoverable row can be rejected outside the tested single-guard cases.

**Correction after code review:** the earlier council suggestion to remove the split guard was wrong. When the old value lacks the delimiter, the forward mapping stores the old value and an empty second part; reverse joining adds a trailing delimiter. The guard therefore correctly rejects that value. Existing tests cover delimiter-free text. Keep the split mapping conditional.

## What the evaluation establishes

The existing pilot supports a scoped feasibility claim. Across the evaluated workloads, sparse mode admitted 10,381 case-rows, recovered 7,551, and reported zero observation mismatches on processed rows. Full-row retention processed the same 17,932 case-rows. Guard-only admitted 10,381 and rejected 7,551; its zero mismatches apply only to admitted rows. The three public datasets supply 5,926 distinct source rows, reused across ten cases. The NYC311 fixture reflects a documented 2018 field addition, but it does not provide an observed before/after lossy conversion or an official migrated snapshot.

The next experiment should use **one documented, nontrivial lossy schema history** with real before/after versions or an independently specified expected outcome. State the mapping and expected pipeline behavior before measuring results. Run the existing sparse, guard-only, and full-row strategies; report admission, recovery, rejection, typed observation agreement, retained cells, bytes, and runtime on the same host. If no suitable paired history is available, present the work explicitly as a reproducible prototype and synthetic pilot rather than claiming real-world migration validation.

## Research positioning

- [Awiti, Wrembel, and Zimányi (2025)](https://reference-global.com/article/10.2478/fcds-2025-0006) repair affected ETL processes using schema-change/operator repair rules. VeriFlow must distinguish its value-dependent typed-observation contract, migration-time guard/recovery choice, and paired replay; it should not claim ETL repair itself as new.
- [Kramer et al. (2025)](https://www.vldb.org/2025/Workshops/VLDB-Workshops-2025/QDB/QDB25_4.pdf) motivate robustness and adaptation evaluation for data-cleaning pipelines. Compare problem scope and measured adaptation behavior directly.
- [Auge and Heuer (2022)](https://arxiv.org/abs/2211.13810) establish provenance-assisted inversion for schema evolution. Selective retained information alone is not a novel concept.
- [EvoSchema (2025)](https://www.vldb.org/pvldb/vol18/p3655-zhang.pdf) benchmarks text-to-SQL robustness under schema changes. It is context for evaluation diversity, not a direct pipeline-behavior baseline.

## Feature decision and completion criteria

**Do not add another broad compiler feature now.** Joins, aggregates, UDFs, automatic mapping inference, multi-version migration, and general guarantees for arbitrary future new-schema rows would expand the theorem and evaluation burden. The present contribution already contains several interacting mechanisms; more breadth would make its claim harder to defend without closing the evidence gap.

Do the following in order:

1. Fix the mixed-guard recovery defect and test it, including replay from the saved bundle. Keep the conditional split rule.
2. Rerun the full suite and migration study on Python 3.12 or later; refresh the artifact manifest and report numbers if they change.
3. Evaluate one documented real lossy history with the current three strategies and independently specified expected observations.
4. Rewrite `docs/paper-draft.md` as a venue-specific manuscript: correct the outdated adapter statement, add the close 2025 ETL comparison, state theorem premises and threats, and make repeated-row/guard-only limitations visible in results.

**Only if the chosen real migration is blocked by one unsupported, well-defined mapping:** add the smallest sound conversion or guard rule required for that case, with a proof argument, a breaking counterexample, and tests. That would be a justified feature extension rather than feature accumulation.

**Final vote:** promising focused paper after the correctness repair and stronger evaluation; no new general feature recommended at this stage.

## Execution after the council

The mixed-guard defect was repaired with per-binding certificates in the
persisted ledger and evolved executor. Two regression tests cover a row with
one passing and one failing guard, and a dropped observed field alongside a
passing guard. The suggested split-rule simplification was withdrawn after
checking delimiter-free inputs against the actual forward and reverse code.

The evaluation now includes the official Malaysian Ministry of Health ICU
change of 22 July 2021: 7,315 paired before/after rows, an actual removed
`vent_sari` field, and 4,060 nonzero removed values. Two experimental pipelines
show no-retention preservation and one-cell-per-row recovery on the same event.
The resulting [submission draft](paper-manuscript-2026-10-28.md) supersedes the
older working paper. Python 3.12.14 ran the integrated study and all 103 tests
passed in an environment permitting the repository's Windows hard-link tests.

**Post-execution assessment:** the council's correctness and external-evidence
conditions above have been met for a focused workshop or systems/demo
submission draft. No further feature is recommended before seeking external
feedback. The draft still needs a selected venue's template, author details,
and independent review; the single real schema event limits generality.
