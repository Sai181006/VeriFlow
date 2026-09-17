# Language specification

This specification follows the Phase One report. The initial executable slice
will support one schema, one pipeline, projection, and CSV emission. Other
statements are reserved now and will be implemented in later slices.

```ebnf
program       = schema_decl pipeline_decl ;
schema_decl   = "schema" IDENT "{" field_decl+ "}" ;
field_decl    = IDENT ":" type ";" ;
type          = "int" | "decimal" | "text" | "bool" ;
pipeline_decl = "pipeline" IDENT "from" STRING "as" IDENT "{" statement+ "}" ;
statement     = require_stmt | keep_stmt | select_stmt | emit_stmt ;
require_stmt  = "require" expression "else" STRING ";" ;
keep_stmt     = "keep" "where" expression ";" ;
select_stmt   = "select" IDENT ("," IDENT)* ";" ;
emit_stmt     = "emit" STRING ";" ;
expression    = or_expr ;
or_expr       = and_expr ("or" and_expr)* ;
and_expr      = equality ("and" equality)* ;
equality      = comparison (("==" | "!=") comparison)* ;
comparison    = term (("<" | "<=" | ">" | ">=") term)* ;
term          = factor (("+" | "-") factor)* ;
factor        = unary (("*" | "/") unary)* ;
unary         = ("not" | "-") unary | primary ;
primary       = NUMBER | STRING | "true" | "false" | IDENT | "(" expression ")" ;
```

## Lexical rules

- Identifiers use `[A-Za-z_][A-Za-z_0-9]*`; keywords are case sensitive.
- Reserved words: `schema pipeline from as require else let keep where select
  emit int decimal text bool true false and or not`.
- Numbers use `[0-9]+(\.[0-9]+)?`. Signs are separate operators. Exponents and
  leading/trailing decimal points are unsupported. Spellings retain precision.
- Strings are double quoted UTF-8 text using JSON escapes. Unescaped control
  characters and invalid Unicode surrogates are rejected.
- `#` starts a comment outside strings, ending at the next newline.
- Operators use longest-match recognition; punctuation is `{ } ( ) : ; ,`.
- Spaces, tabs, LF, CRLF, and CR are ignored between tokens.
- Tokens include their exact lexeme, decoded string value (or original spelling
  for other kinds), and one-based start/end positions. End positions are exclusive;
  offsets count Unicode characters. CRLF is one line break. The CLI accepts an
  optional UTF-8 BOM, removed before source offsets are measured.
- Lexical errors stop scanning and report the start of the invalid token. Error
  recovery remains later work. The Stage 2 parser consumes these tokens directly.

## Semantic rules

Schema fields must have unique names. References resolve to schema fields.
Arithmetic requires numeric operands;
Boolean operations and conditions require bool. Selected fields must exist and
may not repeat. Exactly one select is followed by exactly one terminal emit.
The pipeline's schema reference must resolve. Literal division by zero is a
compile-time error; data-dependent zero is checked during execution.

The implemented pipeline syntax permits zero or more require/keep statements,
followed by exactly one select and one terminal emit. A schema must have at least
one field. A source must contain exactly
one schema followed by exactly one pipeline, with no trailing tokens. Schema
and pipeline names must be distinct.

The prototype implements require and keep expressions and continues to reject
`let` explicitly. Static checks resolve the schema reference and selected
fields, reject duplicate declarations and selections, and preserve field order
and primitive types in the symbol table. Unknown names include a likely-name
suggestion when available. Syntax and semantic errors fail at the first error
and retain source spans. The parser uses recursive descent rather than the
report's proposed Lark infrastructure.

Expression types are inferred recursively. Arithmetic accepts int/decimal and
produces int except division or mixed-decimal operations, which produce decimal.
Ordering comparisons accept numeric operands. Equality accepts identical types
or mixed numeric types. Boolean operators require bool, and require/keep
conditions must produce bool. Literal division by zero is a semantic error;
data-dependent division by zero is a runtime error. `and` and `or` short-circuit.

## Implemented CSV projection semantics

The runtime implements the execution contract in [prototype behavior](prototype.md).
Input and output path strings must be nonempty and contain no NUL characters;
these checks also run during `check`. CSV cells retain their exact text while
every declared field is validated against its schema type. Projection processes
all rows, preserving row order and selecting columns in source selection order.
Invalid schema data or a failed require aborts execution. A false keep condition
filters that row. Conditions execute in source order before projection.
