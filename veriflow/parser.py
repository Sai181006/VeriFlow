"""Recursive-descent syntax analysis for schema, select, and emit.

Statement ordering is checked by semantic analysis, not hidden in the grammar.
The public entry point always obtains a complete EOF-terminated lexer stream.
"""

from .ast import (Binary, Emit, Field, Keep, Literal, Name, Pipeline, Program,
                  Require, Schema, Select, StringLiteral, Unary, Variable)
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

    def statement(self) -> Require | Keep | Select | Emit:
        start = self.current
        if start.kind == "LET":
            raise ParseError(f"Statement {start.lexeme!r} is not supported in the projection prototype", start.span)
        if start.kind == "REQUIRE":
            self.expect("REQUIRE")
            condition = self.expression()
            self.expect("ELSE")
            message = self.string()
            end = self.expect("SEMICOLON")
            return Require(condition, message, Span(start.span.start, end.span.end))
        if start.kind == "KEEP":
            self.expect("KEEP")
            self.expect("WHERE")
            condition = self.expression()
            end = self.expect("SEMICOLON")
            return Keep(condition, Span(start.span.start, end.span.end))
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

    def expression(self):
        return self.or_expression()

    def or_expression(self):
        expression = self.and_expression()
        while self.current.kind == "OR":
            operator = self.expect("OR")
            right = self.and_expression()
            expression = Binary(expression, operator.value, right,
                                Span(expression.span.start, right.span.end))
        return expression

    def and_expression(self):
        expression = self.equality()
        while self.current.kind == "AND":
            operator = self.expect("AND")
            right = self.equality()
            expression = Binary(expression, operator.value, right,
                                Span(expression.span.start, right.span.end))
        return expression

    def equality(self):
        expression = self.comparison()
        while self.current.kind in {"EQ", "NE"}:
            operator = self.expect("EQ", "NE")
            right = self.comparison()
            expression = Binary(expression, operator.value, right,
                                Span(expression.span.start, right.span.end))
        return expression

    def comparison(self):
        expression = self.term()
        while self.current.kind in {"LT", "LE", "GT", "GE"}:
            operator = self.expect("LT", "LE", "GT", "GE")
            right = self.term()
            expression = Binary(expression, operator.value, right,
                                Span(expression.span.start, right.span.end))
        return expression

    def term(self):
        expression = self.factor()
        while self.current.kind in {"PLUS", "MINUS"}:
            operator = self.expect("PLUS", "MINUS")
            right = self.factor()
            expression = Binary(expression, operator.value, right,
                                Span(expression.span.start, right.span.end))
        return expression

    def factor(self):
        expression = self.unary()
        while self.current.kind in {"STAR", "SLASH"}:
            operator = self.expect("STAR", "SLASH")
            right = self.unary()
            expression = Binary(expression, operator.value, right,
                                Span(expression.span.start, right.span.end))
        return expression

    def unary(self):
        if self.current.kind in {"NOT", "MINUS"}:
            operator = self.expect("NOT", "MINUS")
            operand = self.unary()
            return Unary(operator.value, operand, Span(operator.span.start, operand.span.end))
        return self.primary()

    def primary(self):
        token = self.current
        if token.kind in {"INT_LITERAL", "DECIMAL_LITERAL", "STRING", "TRUE", "FALSE"}:
            self.expect(token.kind)
            type_name = {"INT_LITERAL": "int", "DECIMAL_LITERAL": "decimal",
                         "STRING": "text", "TRUE": "bool", "FALSE": "bool"}[token.kind]
            value = token.kind == "TRUE" if token.kind in {"TRUE", "FALSE"} else token.value
            return Literal(value, type_name, token.span)
        if token.kind == "IDENT":
            name = self.name()
            return Variable(name, name.span)
        if token.kind == "LPAREN":
            start = self.expect("LPAREN")
            expression = self.expression()
            end = self.expect("RPAREN")
            # Parentheses affect precedence and the diagnostic span, not node kind.
            if isinstance(expression, Literal):
                return Literal(expression.value, expression.type, Span(start.span.start, end.span.end))
            if isinstance(expression, Variable):
                return Variable(expression.name, Span(start.span.start, end.span.end))
            if isinstance(expression, Unary):
                return Unary(expression.operator, expression.operand, Span(start.span.start, end.span.end))
            return Binary(expression.left, expression.operator, expression.right,
                          Span(start.span.start, end.span.end))
        self.expect("INT_LITERAL", "DECIMAL_LITERAL", "STRING", "TRUE", "FALSE", "IDENT", "LPAREN")

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
