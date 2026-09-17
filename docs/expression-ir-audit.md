# Typed conditions, IR, and diagnostics audit

## Implemented scope

- Expression AST nodes for literals, fields, unary operators, and binary operators.
- Recursive-descent precedence parsing for arithmetic, comparison, equality,
  Boolean operators, unary operations, and parentheses.
- `require <condition> else <message>;` and `keep where <condition>;`.
- Recursive static type inference and operand validation.
- Exact rational runtime arithmetic, short-circuit Boolean evaluation, require
  failures, row filtering, and filtered-row counts.
- Logical plan generation and typed postfix expression IR through `explain`.
- Source-line and caret rendering for lexical, syntax, and semantic diagnostics.

## Audit findings and decisions

- Precedence is encoded as separate parser levels from `or` down to primary.
  Parentheses change grouping while retaining an encompassing diagnostic span.
- int and decimal are compatible numeric types. Division and mixed arithmetic
  have decimal result type. Ordering is numeric; equality requires equal types
  or numeric compatibility. Conditions must be bool.
- Direct zero and unary negative zero divisors are rejected during semantic
  analysis. Data-dependent division by zero is a runtime error with CSV line and
  expression span.
- Runtime numbers use `fractions.Fraction`, avoiding intermediate rounding while
  output projection continues to preserve original CSV spellings.
- `and` and `or` short-circuit. Conditions execute in source order. A failed
  require aborts without output; a false keep filters the row and skips later
  conditions for that row.
- The IR is a real lowering of the checked typed expression tree. It uses postfix
  instructions and includes field types in LOAD_FIELD operands. The runtime still
  evaluates checked expressions directly; it does not claim VM execution.
- Explain performs all compiler front-end checks but never opens CSV paths.
- Diagnostic carets use existing one-based, end-exclusive spans and expand tabs
  for alignment. Multiline spans mark the remainder of the first affected line.
- The first regression run exposed an outdated parser test that assumed the
  example had only select/emit statements. The assertion was updated for the new
  require/keep nodes; compiler behavior was correct.

## Validation

`python -m unittest discover -s tests -v`: all 51 tests passed.

New coverage includes precedence, malformed conditions, type errors, unknown
fields, condition ordering, literal and runtime division by zero, exact
arithmetic, Boolean short-circuiting, require messages, row filtering, IR order,
explain output, and caret diagnostics. Python bytecode compilation and Git
whitespace checks also passed.

The enhanced example produced the expected logical plan and typed postfix IR.
Its real CSV run wrote two passing students, filtered one student, and matched
the documented output exactly. Existing atomic output and failure tests continue
to pass.

## Remaining boundaries

There is no `let`, derived-field lineage, optimizer, constant folding, full
pipeline bytecode, VM, aggregation, join, or multi-error recovery. These remain
later work. No blocking issue was found in the implemented scope.

The changes are local and uncommitted. Proposed commit message:
`Add typed conditions and explain plan`. Push requires explicit user approval.
