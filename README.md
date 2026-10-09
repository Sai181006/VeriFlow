# VeriFlow

VeriFlow is a small compiler for safe CSV pipelines and bidirectional schema
evolution. It parses a SQL-like language, builds an AST, performs type and symbol
checks, optimizes a typed IR, emits stack-machine bytecode, and executes it in a
VM. It can also compile two schema versions into forward, reverse, and
compatibility adapters with an explicit information-loss report.

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

## Implemented phases

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

Phase 2 adds derived fields through `let`, typed derivation IR, constant folding,
full pipeline bytecode, and a stack virtual machine. An optional optimizer adds
arithmetic identity and short-circuit Boolean simplification in a separate
module. `optimized_run.py` passes its rewritten checked program to the existing
bytecode compiler and runtime. Phase 3 adds field-level
lineage, rejected-row quarantine, benchmark results, and integrated valid,
invalid, boundary, and recovery tests.

The schema-evolution compiler supports unchanged fields, rename, add with a
default, drop, type conversion, split, and merge. It generates three Python
programs and a compatibility report, and verifies old -> new -> old round trips.

The prototype validates all declared fields and preserves the selected column
order and original CSV cell text. It refuses to overwrite existing output files.
The implementation stays dependency-free at runtime and refuses to overwrite
generated data or adapter programs.

## Run it

Python 3.12 or later is required. There are no third-party runtime dependencies.

For a presentation, double-click `demo.cmd` on Windows or run one command:

```sh
python demo.py
```

The default `all` mode first shows two incorrect inputs: a text value inside the
integer `marks` column and a mark outside the allowed range. VeriFlow explains
each failure and proves that no partial output was published. It then runs the
corrected input and shows the source, compiler summary, explain plan, output CSV,
and execution totals. Everything runs in temporary folders, so the example
files are never changed.

Run the error and successful cases separately, then compare optimized code:

```sh
python demo.py errors
python demo.py success
python optimization_demo.py
```

`errors` shows two expected failures and confirms no partial output was
published. `success` shows the valid program, input, explain plan, output CSV,
and row counts. `optimization_demo.py` shows logical IR and executable bytecode
before and after optimization, then runs `examples/optimization_students.vfl` in a
temporary folder. In that example, expression bytecode decreases from 21 to
13 instructions while the output contains two selected rows. `all` runs the
error cases followed by the successful case. On Windows, `demo.cmd errors` and
`demo.cmd success` provide the same two modes; double-click
`optimization_demo.cmd` for the optimization walkthrough.

To apply the optional optimizer to your own pipeline and write its output:

```sh
python optimized_run.py examples/optimization_students.vfl
```

As with `run`, this writes the path named by `emit` and refuses to overwrite
an existing output file. The optimization demo uses a temporary directory and
does not leave an output file in `examples`.

Individual compiler stages can also be inspected:

```sh
python -m veriflow tokens examples/project_students.vfl
python -m veriflow ast examples/project_students.vfl
python -m veriflow check examples/project_students.vfl
python -m veriflow explain examples/project_students.vfl
python -m veriflow optimize examples/project_students.vfl
python -m veriflow bytecode examples/project_students.vfl
python -m veriflow lineage examples/project_students.vfl
python -m veriflow benchmark examples/project_students.vfl --iterations 25
python -m veriflow run examples/project_students.vfl
```

`examples/derived_students.vfl` is a compact Phase 2 example containing two
derived fields. Use it with `ast`, `check`, `optimize`, `bytecode`, or `run`.
Use `python optimization_demo.py` to see constant folding, arithmetic
identities, and Boolean simplification directly. The existing `optimize` command
still demonstrates its original constant-folding pass only.

Run the schema-evolution chat demonstration with:

```sh
python evolution_demo.py
```

Inspect and generate adapters with:

```sh
python -m veriflow evolution-check examples/chat_evolution.vfl
python -m veriflow generate-adapters examples/chat_evolution.vfl --output-dir generated
```

The generated directory contains `forward_adapter.py`, `reverse_adapter.py`,
`compatibility_adapter.py`, and `compatibility_report.json`.

The `run` command creates `examples/selected_students.csv` and prints a JSON
summary. Remove that generated file or use a new `emit` path before running the
same program again.

Run the tests with:

```sh
python -m unittest discover -s tests -v
```

See the [language specification](docs/language.md), [Phase 2](docs/phase-two.md),
[Phase 3](docs/phase-three.md), and [schema evolution](docs/schema-evolution.md).

The paper direction, implemented checker, evaluation pilot, and remaining work
are documented in [paper research context](docs/paper-research-context.md),
[impact method](docs/impact-method.md), [evaluation](evaluation/README.md), and
[research tasks](docs/paper-research-tasks.md). The
[second council review](docs/council-review-2026-10-08.md) explains the
near-term additions and deferred research gaps.
The reusable [eight-slide research presentation brief](docs/presentation-brief.md)
summarizes the problem, related work, precise contribution, evidence, and limits.
The [editable PowerPoint](presentations/output/veriflow-research-blue-bell-v2.pptx)
is documented in [presentations/README.md](presentations/README.md).
