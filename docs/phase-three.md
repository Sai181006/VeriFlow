# Phase 3 - integration, evidence, and testing

Phase 3 integrates execution evidence and final-project validation.

## Implemented tasks

- The VM is used by the normal CSV runtime.
- Static field lineage records source, derived, policy, and output relationships.
- `run-report` writes valid output, rejected rows with reasons, and lineage JSON.
- Invalid type, failed requirement, malformed width, and expression failures can
  be quarantined without publishing partial temporary files.
- `benchmark` measures the complete tokenize, parse, analyze, optimize, and
  bytecode compilation pipeline over repeatable iterations.
- The test suite covers valid, invalid, boundary, short-circuit, safe-output,
  lineage, quarantine, benchmark, and schema-evolution behavior.

## Commands

```sh
python -m veriflow lineage examples/project_students.vfl
python -m veriflow run-report examples/project_students.vfl
python -m veriflow benchmark examples/project_students.vfl --iterations 25
```

`run-report` refuses existing output or report files. The default sidecars are
named from the emitted CSV, such as `selected_students.rejects.csv` and
`selected_students.lineage.json`.

A reproducible sample is recorded in `benchmark-results.md`.
