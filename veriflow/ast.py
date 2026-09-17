"""Immutable, source-positioned nodes for the projection prototype."""

from dataclasses import dataclass

from .lexer import Span


@dataclass(frozen=True)
class Name:
    value: str
    span: Span


@dataclass(frozen=True)
class StringLiteral:
    value: str
    span: Span


@dataclass(frozen=True)
class Literal:
    value: str | bool
    type: str
    span: Span


@dataclass(frozen=True)
class Variable:
    name: Name
    span: Span


@dataclass(frozen=True)
class Unary:
    operator: str
    operand: "Expression"
    span: Span


@dataclass(frozen=True)
class Binary:
    left: "Expression"
    operator: str
    right: "Expression"
    span: Span


Expression = Literal | Variable | Unary | Binary


@dataclass(frozen=True)
class Field:
    name: Name
    type: Name
    span: Span


@dataclass(frozen=True)
class Schema:
    name: Name
    fields: tuple[Field, ...]
    span: Span


@dataclass(frozen=True)
class Select:
    fields: tuple[Name, ...]
    span: Span


@dataclass(frozen=True)
class Require:
    condition: Expression
    message: StringLiteral
    span: Span


@dataclass(frozen=True)
class Keep:
    condition: Expression
    span: Span


@dataclass(frozen=True)
class Emit:
    path: StringLiteral
    span: Span


@dataclass(frozen=True)
class Pipeline:
    name: Name
    input_path: StringLiteral
    schema: Name
    statements: tuple[Require | Keep | Select | Emit, ...]
    span: Span


@dataclass(frozen=True)
class Program:
    schema: Schema
    pipeline: Pipeline
    span: Span
