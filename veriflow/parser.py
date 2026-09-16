"""Recursive-descent syntax analysis for schema, select, and emit.

Statement ordering is checked by semantic analysis, not hidden in the grammar.
The public entry point always obtains a complete EOF-terminated lexer stream.
"""

from .ast import Emit, Field, Name, Pipeline, Program, Schema, Select, StringLiteral
from .lexer import Span, Token, tokenize


class ParseError(ValueError):
    def __init__(self, message: str, span: Span):
        super().__init__(message)
        self.span = span


class _Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def expect(self, *kinds: str) -> Token:
        token = self.current
        if token.kind not in kinds:
            found = "end of file" if token.kind == "EOF" else repr(token.lexeme)
            raise ParseError(f"Expected {' or '.join(kinds)}, found {found}", token.span)
        if token.kind != "EOF":
            self.index += 1
        return token

    def name(self) -> Name:
        token = self.expect("IDENT")
        return Name(token.value, token.span)

    def string(self) -> StringLiteral:
        token = self.expect("STRING")
        return StringLiteral(token.value, token.span)

    def schema(self) -> Schema:
        start = self.expect("SCHEMA")
        name = self.name()
        self.expect("LBRACE")
        fields = [self.field()]
        while self.current.kind != "RBRACE":
            fields.append(self.field())
        end = self.expect("RBRACE")
        return Schema(name, tuple(fields), Span(start.span.start, end.span.end))

    def field(self) -> Field:
        name = self.name()
        self.expect("COLON")
        token = self.expect("INT", "DECIMAL", "TEXT", "BOOL")
        type_name = Name(token.value, token.span)
        end = self.expect("SEMICOLON")
        return Field(name, type_name, Span(name.span.start, end.span.end))

    def statement(self) -> Select | Emit:
        start = self.current
        if start.kind in {"REQUIRE", "LET", "KEEP"}:
            raise ParseError(f"Statement {start.lexeme!r} is not supported in the projection prototype", start.span)
        if start.kind == "SELECT":
            self.expect("SELECT")
            fields = [self.name()]
            while self.current.kind == "COMMA":
                self.expect("COMMA")
                fields.append(self.name())
            end = self.expect("SEMICOLON")
            return Select(tuple(fields), Span(start.span.start, end.span.end))
        self.expect("EMIT")
        path = self.string()
        end = self.expect("SEMICOLON")
        return Emit(path, Span(start.span.start, end.span.end))

    def pipeline(self) -> Pipeline:
        start = self.expect("PIPELINE")
        name = self.name()
        self.expect("FROM")
        input_path = self.string()
        self.expect("AS")
        schema = self.name()
        self.expect("LBRACE")
        statements = [self.statement()]
        while self.current.kind != "RBRACE":
            statements.append(self.statement())
        end = self.expect("RBRACE")
        return Pipeline(name, input_path, schema, tuple(statements),
                        Span(start.span.start, end.span.end))

    def program(self) -> Program:
        schema = self.schema()
        pipeline = self.pipeline()
        self.expect("EOF")
        return Program(schema, pipeline, Span(schema.span.start, pipeline.span.end))


def parse(source: str) -> Program:
    """Parse one source file, failing at the first lexical or syntax error."""
    return _Parser(tokenize(source)).program()
