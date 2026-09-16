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

Each stage ends with a code audit, tests, and a reviewable change summary.
Pushes require explicit user approval after that evidence is available.
No remote writes have been made for Stage 1.

## Architectural decisions

- Python 3.12+ with independent compiler components.
- A handwritten lexer makes lexical analysis visible and needs no dependency.
  The report proposed Lark for grammar/parser infrastructure. Stage 2 will
  reconcile Lark integration with the independent token interface before coding.
- Keep source spans from the front end through subsequent representations.
- No source evaluation through Python `eval` or `exec`.
- Reserve the full planned vocabulary now; recognize only completed stages
  as available features in the CLI.

## Deferred work

Expressions, require/let/keep, typed IR, optimization, stack bytecode, VM,
lineage, and recovery are later compiler slices. Stage 3 is a narrow prototype
and must not be described as the completed compiler.
