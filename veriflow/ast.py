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
class Emit:
    path: StringLiteral
    span: Span


@dataclass(frozen=True)
class Pipeline:
    name: Name
    input_path: StringLiteral
    schema: Name
    statements: tuple[Select | Emit, ...]
    span: Span


@dataclass(frozen=True)
class Program:
    schema: Schema
    pipeline: Pipeline
    span: Span
