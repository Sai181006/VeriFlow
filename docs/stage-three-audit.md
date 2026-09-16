# Stage 3 audit

## Implemented scope

CSV projection runtime, `run` CLI command, input/output path checks, runtime
diagnostics, streaming validation, exclusive output publication, and prototype
documentation. The runtime executes a statically checked AST directly.

## Findings and resolutions

- Static checks run before any CSV access; empty and NUL-containing paths are
  rejected during semantic analysis. Relative paths use the source directory.
- Headers require unique nonempty names and every declared schema field.
  Reordered headers and extra columns work; missing fields and bad record widths
  fail before publication.
- All schema fields are validated, including unselected columns. Numeric syntax
  is validated without float conversion. Output preserves numeric spellings,
  text, row order, and selection order. bool accepts lowercase true/false only.
- Input is streamed using standard CSV quoting; UTF-8 BOM, CRLF, quoted commas,
  multiline text, and Unicode were exercised. Header-only input writes a header;
  completely empty input and blank data records are rejected.
- Output cannot equal input/source or replace an existing destination. Temporary
  output is closed before exclusive same-directory hard-link publication.
  The concurrent-writer test confirms no existing file is overwritten.
- Validation, writing, and publication failure tests confirm no partial result
  is published and ordinary temporary-file cleanup succeeds.
- Audit identified that cleanup failure could escape as an unhandled OSError.
  It now reports an ExecutionError or adds cleanup details to the primary error.
  A published result remains present if subsequent temporary-name cleanup fails.
- Filesystems without hard-link support fail with a diagnostic. Crash recovery,
  durable filesystem synchronization, and adversarial path changes are outside
  this prototype's guarantees. These limits are documented.
- The sample pipeline was renamed ProjectStudents because projection processes
  all rows and does not filter students by marks.
- No blocking issues remain within the checked projection prototype scope.

## Validation

`python -m unittest discover -s tests -v`: all 39 tests passed.

Coverage includes the existing front end plus CSV/type/path behavior, end-to-end
CLI execution from outside the source directory, failure before IO, late invalid
rows, malformed CSV, existing output preservation, simulated concurrent output,
write/publication failures, and cleanup failures.

`python -m veriflow run examples/project_students.vfl` wrote three rows with
columns name/marks. The resulting CSV was compared exactly with the documented
expected output and matched. Whitespace checks passed for code changes.

## Phase One result and approval

The three stages now provide an executable schema/select/emit prototype with
inspectable tokens, AST, symbol table, diagnostics, and CSV output. This does
not claim the full compiler or change the earlier submitted paper report.
Expressions, require/let/keep, typed IR, optimization, bytecode, VM, lineage,
and recovery remain subsequent phases.

No commit or push has been made. Proposed Stage 3 commit message:
`Add CSV projection prototype`. Push still requires explicit user approval.
