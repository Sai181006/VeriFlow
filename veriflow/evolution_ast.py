"""AST nodes for the schema-evolution language."""

from dataclasses import dataclass

from .ast import Name, Schema
from .lexer import Span


@dataclass(frozen=True)
class DefaultValue:
    value: str | bool
    type: str
    span: Span


@dataclass(frozen=True)
class RenameRule:
    source: Name
    target: Name
    span: Span


@dataclass(frozen=True)
class AddRule:
    target: Name
    default: DefaultValue
    span: Span


@dataclass(frozen=True)
class DropRule:
    source: Name
    span: Span


@dataclass(frozen=True)
class ConvertRule:
    source: Name
    target: Name
    span: Span


@dataclass(frozen=True)
class SplitRule:
    source: Name
    targets: tuple[Name, Name]
    delimiter: str
    span: Span


@dataclass(frozen=True)
class MergeRule:
    sources: tuple[Name, Name]
    target: Name
    delimiter: str
    span: Span


EvolutionRule = RenameRule | AddRule | DropRule | ConvertRule | SplitRule | MergeRule


@dataclass(frozen=True)
class Evolution:
    old_schema: Name
    new_schema: Name
    rules: tuple[EvolutionRule, ...]
    span: Span


@dataclass(frozen=True)
class EvolutionProgram:
    schemas: tuple[Schema, Schema]
    evolution: Evolution
    span: Span
