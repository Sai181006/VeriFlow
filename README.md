# VeriFlow

A small compiler for schema-aware CSV pipelines. The planned compiler checks
types and field names before execution and exposes tokens, AST, intermediate
code, bytecode, diagnostics, and field lineage.

## Current stage

Stage 1 implements lexical analysis and a token inspection CLI. It does not
yet parse or execute pipelines. The example is input for the lexer and the
upcoming CSV projection prototype.

Python 3.12 or later is required. From this repository directory:

```sh
python -m veriflow tokens examples/project_students.vfl
python -m unittest discover -s tests -v
```

No third-party runtime dependencies are needed for Stage 1. Optionally install
with `python -m pip install -e .` to use the `veriflow` command directly.

See [language specification](docs/language.md) and
[implementation stages](docs/phase-one.md) for the agreed design and review gates.
