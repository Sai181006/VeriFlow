# Phase One working prototype

## Demonstration

From the repository directory, with Python 3.12 or later:

```sh
python -m veriflow tokens examples/project_students.vfl
python -m veriflow ast examples/project_students.vfl
python -m veriflow check examples/project_students.vfl
python -m veriflow run examples/project_students.vfl
python -m unittest discover -s tests -v
```

The example selects name and marks for all three students. Expected output at
`examples/selected_students.csv`:

```csv
name,marks
Anika,82
Ravi,38
"Mira, S",91
```

The run command prints resolved input/output paths, `rows_written: 3`, and
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
  conversion. Selected cells preserve signs, leading zeros, and decimal scale.
- All schema fields are validated on every row. Extra undeclared columns are
  checked for record width but have no type constraints. Row order and selected
  column order are preserved. No filtering, derivation, or coercion is performed.

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

## Phase boundary

This prototype demonstrates source-to-AST-to-checked-projection-to-CSV execution.
It executes the checked AST directly. It does not yet generate typed IR or
bytecode, optimize code, execute a VM, produce lineage, recover from errors, or
support require/let/keep expressions. Those remain Phase Two/Three compiler work.
