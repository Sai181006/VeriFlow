# Phase One working prototype

## Demonstration

From the repository directory, with Python 3.12 or later:

```sh
python demo.py
```

On Windows, `demo.cmd` can also be opened directly. The guided walkthrough
prints the program, input, compiler summary, logical plan, generated CSV, and
row totals. It copies relative-path inputs into a temporary directory and never
publishes the example output. Absolute paths and paths escaping that temporary
directory are refused in guided-demo mode.

The individual stage commands remain available:

```sh
python -m veriflow tokens examples/project_students.vfl
python -m veriflow ast examples/project_students.vfl
python -m veriflow check examples/project_students.vfl
python -m veriflow explain examples/project_students.vfl
python -m veriflow run examples/project_students.vfl
python -m unittest discover -s tests -v
```

The example checks that marks are in the range 0-100, keeps students with marks
of at least 40, and selects name and marks. Expected output at
`examples/selected_students.csv`:

```csv
name,marks
Anika,82
"Mira, S",91
```

The run command prints resolved paths, `rows_written: 2`, `rows_filtered: 1`, and
`columns: ["name", "marks"]` as JSON. Repeat runs refuse an existing output.
Change the emit path to a fresh destination when another result is needed.

## CSV and type rules

- Input is comma-delimited UTF-8, with an optional BOM. Standard CSV quoting,
  quoted commas, multiline text, and CRLF are supported using Python's strict
  CSV reader. Output is UTF-8 with LF record separators and standard quoting.
- A nonempty header is mandatory. Duplicate and empty names are rejected.
  All declared schema fields must exist, including fields not selected for output.
  Header order may differ from schema order; extra columns are allowed.
- Every data record must have exactly as many cells as the header. Blank
  records, missing cells, and extra cells are errors. A header-only file produces
  an output header with zero data rows; a completely empty input is an error.
- text accepts any decoded cell, including an empty string. int accepts an
  optional sign and ASCII digits. decimal accepts an optional sign, digits,
  and an optional fractional part with digits on both sides of its decimal point.
  bool accepts exactly lowercase true or false.
- Numeric whitespace, empty numeric/Boolean cells, exponents, NaN, and Infinity
  are rejected. Numeric spellings are validated without floating-point
  conversion. Expression arithmetic uses exact rational values, while selected
  cells preserve signs, leading zeros, and decimal scale.
- All schema fields are validated on every row. Extra undeclared columns are
  checked for record width but have no type constraints. Row order and selected
  column order are preserved. `require` aborts on a false condition with its
  message; `keep where` drops false rows. No derivation or coercion is performed.

## Expressions and explain output

Conditions support field references, int/decimal/text/bool literals, parentheses,
unary `-` and `not`, arithmetic, comparisons, equality, and short-circuiting
`and`/`or`. Standard precedence is encoded directly by the parser. Static
analysis rejects invalid operand types and non-Boolean conditions before CSV IO.

`explain` performs lexical, syntax, and semantic analysis without opening the
CSV. It displays SCAN, VALIDATE, REQUIRE, FILTER, PROJECT, and EMIT plan steps.
Each condition is lowered to typed postfix instructions such as LOAD_FIELD
(with a `name:type` operand),
PUSH_INT, COMPARE_GE, and BOOLEAN_AND. This is the prototype's first explicit IR.

## Paths and failure behavior

Relative CSV paths resolve against the `.vfl` source file's directory, independent
of the command's working directory. Absolute paths are allowed. Output must
differ from both input and source and its parent must already exist. Existing
output files/directories are refused; the prototype has no overwrite option.

The runtime streams validated rows to a temporary file in the output directory.
After reading and closing the files successfully, an exclusive hard link
publishes the completed result and the temporary name is removed. Concurrently
created output is not overwritten. The filesystem must support hard links;
otherwise execution fails instead of falling back to a partial copy. A process
termination or power loss may leave a temporary file; crash recovery and durable
filesystem synchronization are beyond this prototype.

If temporary-file cleanup fails, a runtime diagnostic identifies the leftover
file. A cleanup failure after publication reports that the completed output
already exists; it is not removed. If execution and cleanup both fail, the
original execution error is preserved and cleanup details are also printed.

Lexical, syntax, semantic, data, and file errors return exit status 1 without a
success summary. Runtime diagnostics include the source span and affected CSV
path; type and record-width failures include the CSV physical ending line.
CSV syntax follows the standard library reader, not a custom CSV grammar.
Compiler diagnostics also print the affected source line and a caret range.

## Phase boundary

This document records the Phase 1 prototype contract. Phase 2 and Phase 3 retain
these safety rules while adding `let`, optimization, full expression bytecode,
a stack VM, lineage, rejected-row quarantine, benchmarking, and schema evolution.
See `phase-two.md`, `phase-three.md`, and `schema-evolution.md` for the completed
later-phase behavior.
