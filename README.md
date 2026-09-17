# VeriFlow

VeriFlow is a small compiler project for schema-aware CSV pipelines. A VeriFlow
program declares the expected columns and types, selects output fields, and names
the input and output CSV files. The compiler checks the program before execution
and reports errors with source locations.

```veriflow
schema Student {
    name: text;
    marks: int;
}

pipeline PassingStudents from "students.csv" as Student {
    require marks >= 0 and marks <= 100
        else "marks must be between 0 and 100";
    keep where marks >= 40;
    select name, marks;
    emit "selected_students.csv";
}
```

## Phase 1

Phase 1 provides a working schema-aware pipeline prototype:

- lexical analysis with source-positioned tokens;
- recursive-descent parsing and an inspectable AST;
- schema symbols, name resolution, and static projection checks;
- typed arithmetic, comparison, and Boolean expressions;
- `require` data constraints and `keep where` row filtering;
- a logical plan and postfix expression IR through `explain`;
- streaming CSV validation and projection;
- source-line and caret diagnostics for compiler errors; and
- tests for valid programs, invalid programs, CSV edge cases, and safe output.

The prototype validates all declared fields and preserves the selected column
order and original CSV cell text. It refuses to overwrite existing output files.
Derived fields, optimization, bytecode, a virtual machine, and lineage generation
are planned for later phases.

## Run it

Python 3.12 or later is required. There are no third-party runtime dependencies.

```sh
python -m veriflow tokens examples/project_students.vfl
python -m veriflow ast examples/project_students.vfl
python -m veriflow check examples/project_students.vfl
python -m veriflow explain examples/project_students.vfl
python -m veriflow run examples/project_students.vfl
```

The `run` command creates `examples/selected_students.csv` and prints a JSON
summary. Remove that generated file or use a new `emit` path before running the
same program again.

Run the tests with:

```sh
python -m unittest discover -s tests -v
```

See the [language specification](docs/language.md), [prototype behavior](docs/prototype.md),
and [Phase 1 stages](docs/phase-one.md) for more detail.
