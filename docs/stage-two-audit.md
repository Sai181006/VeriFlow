# Stage 2 audit

## Implemented scope

Recursive-descent parser for one schema and one projection pipeline; immutable
source-positioned AST; schema symbol table and output-field resolution;
`ast` and `check` CLI commands. The parser consumes Stage 1 tokens directly.

## Review findings

- The grammar requires nonempty fields and statements, primitive field types,
  required delimiters, schema then pipeline, and complete consumption through EOF.
- Parser loops consume a declaration/statement or raise an error. Every proper
  prefix of a representative valid source was tested to catch truncated-input
  hangs and accidental index errors.
- require/let/keep produce explicit unsupported-statement errors. No expression
  execution or interpretation is claimed.
- AST spans retain exact declaration, reference, statement, and string-literal
  ranges. String values are decoded while their spans retain source spelling.
- Static checks reject duplicate schema fields, unresolved schemas, conflicting
  schema/pipeline names, unknown and repeated selected fields, missing or repeated
  select/emit, and reversed statement ordering.
- Schema symbols preserve primitive types and declaration order. Output symbols
  preserve selection order and refer to resolved declarations.
- Unknown-name diagnostics optionally suggest a similar schema/field name.
  Duplicate-name errors point to the second declaration/reference.
- `ast` performs syntax analysis only; `check` additionally performs semantic
  analysis. Neither accesses CSV input/output paths. Compiler errors produce no
  partial JSON and return exit status 1 with the stage and source location.
- Recursive descent replaces the report's proposed Lark infrastructure for the
  small prototype subset. This choice is recorded in the language and stage docs.
- The initial test run caught an incorrect expected column (58 instead of 51)
  in a CLI diagnostic test. The expectation was corrected; compiler behavior
  already identified the actual reference.

## Validation

`python -m unittest discover -s tests -v`: all 22 tests passed, including the
original lexer and CLI tests. Added coverage includes all primitive types,
exact AST spans, malformed syntax, unsupported statements, truncated source,
semantic failures, suggestions, ordered symbol resolution, and CLI diagnostics.

The module `ast` and `check` commands were run on the example. Both JSON results
parsed successfully; check resolved `name: text` and `marks: int` in that order.
Whitespace checks passed for the changes.

## Remaining scope and approval

CSV projection execution belongs to Stage 3. Expressions, typed IR,
optimization, bytecode, VM, and lineage remain subsequent compiler work.
No blocking issues were found for the parser-produced projection AST scope.
No commit or push has been made. Proposed Stage 2 commit message:
`Add parser and schema checks`. Push requires explicit user approval.
