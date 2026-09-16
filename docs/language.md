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
statement     = require_stmt | let_stmt | keep_stmt | select_stmt | emit_stmt ;
require_stmt  = "require" expression "else" STRING ";" ;
let_stmt      = "let" IDENT "=" expression ";" ;
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
  recovery and parser integration remain later work.

## Planned semantic rules

Schema fields and derived fields must have unique names. References resolve to
schema fields or earlier derived fields. Arithmetic requires numeric operands;
Boolean operations and conditions require bool. Selected fields must exist and
may not repeat. Exactly one select is followed by exactly one terminal emit.
The pipeline's schema reference must resolve. Literal division by zero is a
compile-time error; data-dependent zero is checked during execution.

The initial projection prototype will require select followed by emit and reject
all other statements explicitly until they are implemented. Later stages will
define CSV conversion, path resolution, row rejection, and execution semantics
before introducing the runtime.
