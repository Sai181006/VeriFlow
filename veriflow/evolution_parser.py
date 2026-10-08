"""Parser for two-version schema evolution specifications."""

from .ast import Field, Name, Schema
from .evolution_ast import (AddRule, ConvertRule, DefaultValue, DropRule,
                            Evolution, EvolutionProgram, MergeRule, RenameRule,
                            SplitRule)
from .lexer import Span, Token, tokenize
from .parser import ParseError


class _EvolutionParser:
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

    def schema(self) -> Schema:
        start = self.expect("SCHEMA")
        name = self.name()
        self.expect("LBRACE")
        fields = []
        while self.current.kind != "RBRACE":
            field_name = self.name()
            self.expect("COLON")
            type_token = self.expect("INT", "DECIMAL", "TEXT", "BOOL")
            end = self.expect("SEMICOLON")
            fields.append(Field(field_name, Name(type_token.value, type_token.span),
                                Span(field_name.span.start, end.span.end)))
        end = self.expect("RBRACE")
        if not fields:
            raise ParseError("Schema requires at least one field", name.span)
        return Schema(name, tuple(fields), Span(start.span.start, end.span.end))

    def default_value(self) -> DefaultValue:
        token = self.current
        self.expect("STRING", "INT_LITERAL", "DECIMAL_LITERAL", "TRUE", "FALSE")
        type_name = {"STRING": "text", "INT_LITERAL": "int", "DECIMAL_LITERAL": "decimal",
                     "TRUE": "bool", "FALSE": "bool"}[token.kind]
        value = token.kind == "TRUE" if token.kind in {"TRUE", "FALSE"} else token.value
        return DefaultValue(value, type_name, token.span)

    def rule(self):
        start = self.current
        if start.kind == "RENAME":
            self.expect("RENAME")
            source = self.name()
            self.expect("TO")
            target = self.name()
            end = self.expect("SEMICOLON")
            return RenameRule(source, target, Span(start.span.start, end.span.end))
        if start.kind == "ADD":
            self.expect("ADD")
            target = self.name()
            self.expect("DEFAULT")
            default = self.default_value()
            end = self.expect("SEMICOLON")
            return AddRule(target, default, Span(start.span.start, end.span.end))
        if start.kind == "DROP":
            self.expect("DROP")
            source = self.name()
            end = self.expect("SEMICOLON")
            return DropRule(source, Span(start.span.start, end.span.end))
        if start.kind == "CONVERT":
            self.expect("CONVERT")
            source = self.name()
            self.expect("TO")
            target = self.name()
            end = self.expect("SEMICOLON")
            return ConvertRule(source, target, Span(start.span.start, end.span.end))
        if start.kind == "SPLIT":
            self.expect("SPLIT")
            source = self.name()
            self.expect("INTO")
            first = self.name()
            self.expect("COMMA")
            second = self.name()
            self.expect("USING")
            delimiter = self.expect("STRING")
            end = self.expect("SEMICOLON")
            return SplitRule(source, (first, second), delimiter.value,
                             Span(start.span.start, end.span.end))
        self.expect("MERGE")
        first = self.name()
        self.expect("COMMA")
        second = self.name()
        self.expect("INTO")
        target = self.name()
        self.expect("USING")
        delimiter = self.expect("STRING")
        end = self.expect("SEMICOLON")
        return MergeRule((first, second), target, delimiter.value,
                         Span(start.span.start, end.span.end))

    def program(self) -> EvolutionProgram:
        old = self.schema()
        new = self.schema()
        start = self.expect("EVOLVE")
        old_name = self.name()
        self.expect("TO")
        new_name = self.name()
        self.expect("LBRACE")
        rules = []
        while self.current.kind != "RBRACE":
            rules.append(self.rule())
        end = self.expect("RBRACE")
        self.expect("EOF")
        evolution = Evolution(old_name, new_name, tuple(rules),
                              Span(start.span.start, end.span.end))
        return EvolutionProgram((old, new), evolution, Span(old.span.start, end.span.end))


def parse_evolution(source: str) -> EvolutionProgram:
    return _EvolutionParser(tokenize(source)).program()
