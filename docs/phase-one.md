# Phase One implementation stages

The lab manual defines Phase One as problem definition and design with an
initial working prototype. The earlier report supplies the design and a paper
prototype. This work adds executable evidence in small reviewed stages; the
full compiler belongs to subsequent phases.

| Stage | Deliverable | Validation | Plain commit message |
| --- | --- | --- | --- |
| 1 | Package setup, language contract, source-positioned lexer, token CLI | Token and CLI unit tests, sample CLI run, code audit | Add lexer and project setup |
| 2 | Parser, source-positioned AST, schema and projection semantics | Valid/invalid syntax, unknown/duplicate fields, statement ordering | Add parser and schema checks |
| 3 | CSV projection execution and prototype documentation | Quoted CSV, headers, conversions, error cases, output checks | Add CSV projection prototype |

Each stage ended with a code audit, tests, and a reviewable change summary. The
original Phase One prototype is committed and pushed on `main`. Later enhancements
remain local until they pass the same audit and receive explicit push approval.

## Architectural decisions

- Python 3.12+ with independent compiler components.
- A handwritten lexer makes lexical analysis visible and needs no dependency.
  The report proposed Lark for grammar/parser infrastructure. Stage 2 uses
  recursive descent over the existing tokens for this small deterministic
  subset, preserving a single lexical contract without third-party dependencies.
- Keep source spans from the front end through subsequent representations.
- No source evaluation through Python `eval` or `exec`.
- Reserve the full planned vocabulary now; recognize only completed stages
  as available features in the CLI.

Stage 2 is implemented locally: projection parsing, AST inspection, schema
symbols, reference resolution, and static projection checks. The `ast` command
accepts syntactically valid statements regardless of ordering; `check` applies
the ordering and name rules. These inspection commands do not execute CSV operations.

Stage 3: `run` performs static checks, validates CSV
headers and declared field types, and streams selected columns into a new output
file. Successful output is published after all input passes validation. See
[prototype behavior](prototype.md) and [Stage 3 audit](stage-three-audit.md).

## Later phases

Phase 2 and Phase 3 are now implemented in separate modules and documented in
`phase-two.md` and `phase-three.md`. They add derived fields, optimization,
pipeline bytecode, a VM, lineage, rejected-row reports, benchmarks, and schema
evolution. This file remains the record of the original Phase 1 boundary.
