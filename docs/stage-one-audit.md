# Stage 1 audit

## Scope reviewed

Package metadata, lexer, source position models, CLI, tests, examples, language
specification, and stage plan. The remote repository was empty when cloned.

## Findings and decisions

- Reviewed scanner advancement and termination: every iteration consumes input
  or raises a source-positioned error; EOF has a zero-width span.
- Keywords match complete identifiers. Two-character operators take priority.
- Numbers preserve their text for later exact conversion. Malformed numeric
  suffixes are rejected instead of being silently split into valid tokens.
- Escaped quotes and backslashes are handled before JSON string decoding.
  Invalid escapes, unescaped controls, and lone surrogates are rejected.
- CRLF source offsets are preserved by the CLI. UTF-8 BOM handling is explicit.
- The CLI buffers tokens before printing, so lexical failure produces no partial
  JSON. Missing files and invalid UTF-8 yield a nonzero exit code.
- Package discovery includes compiler modules only. Generated Python files are
  ignored. There is no source evaluation or remote write in compiler behavior.
- The independent handwritten lexer differs from the report's proposed Lark
  infrastructure. This is documented; parser integration remains a Stage 2
  design decision.
- No blocking issues were found within the lexical-analysis scope. Error
  recovery, parsing, and CSV behavior are deliberately not yet implemented.

## Validation

`python -m unittest discover -s tests -v`: 10 tests passed.

Coverage includes every reserved word and operator, keyword prefixes, numeric
precision, comments, JSON escapes, Unicode surrogate pairs, Unicode source
positions, empty files, malformed input, CRLF, BOM, file failures, and the sample
source. The module CLI was also run on the example and its JSON parsed successfully.

## Review gate

Stage 1 is ready for user review. Proposed commit: `Add lexer and project setup`.
No commit or push has been made. Approval is required before pushing this stage.
