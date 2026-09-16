"""Resolve the schema and ordered output fields before CSV execution."""

from dataclasses import dataclass
from difflib import get_close_matches

from .ast import Emit, Program, Select
from .lexer import Span


class SemanticError(ValueError):
    def __init__(self, message: str, span: Span):
        super().__init__(message)
        self.span = span


@dataclass(frozen=True)
class Symbol:
    name: str
    type: str
    declaration: Span


@dataclass(frozen=True)
class CheckedProgram:
    program: Program
    symbols: tuple[Symbol, ...]
    selected: tuple[Symbol, ...]


def _suggest(name: str, choices: list[str]) -> str:
    matches = get_close_matches(name, choices, n=1, cutoff=0.6)
    return f"; did you mean {matches[0]!r}?" if matches else ""


def analyze(program: Program) -> CheckedProgram:
    """Check a parser-produced AST; fail on the first semantic error.

    The returned symbols preserve declaration and selection order. This stage
    performs no file access or runtime conversion.
    """
    schema, pipeline = program.schema, program.pipeline
    symbols: dict[str, Symbol] = {}
    for field in schema.fields:
        name = field.name.value
        if name in symbols:
            raise SemanticError(f"Duplicate schema field {name!r}", field.name.span)
        symbols[name] = Symbol(name, field.type.value, field.name.span)
    if pipeline.name.value == schema.name.value:
        raise SemanticError("Schema and pipeline names must be distinct", pipeline.name.span)
    if pipeline.schema.value != schema.name.value:
        name = pipeline.schema.value
        raise SemanticError(f"Unknown schema {name!r}" + _suggest(name, [schema.name.value]), pipeline.schema.span)
    selects = [s for s in pipeline.statements if isinstance(s, Select)]
    emits = [s for s in pipeline.statements if isinstance(s, Emit)]
    for label, statements in (("select", selects), ("emit", emits)):
        if not statements:
            raise SemanticError(f"Pipeline requires exactly one {label} statement", pipeline.span)
        if len(statements) > 1:
            raise SemanticError(f"Duplicate {label} statement", statements[1].span)
    select, emit = selects[0], emits[0]
    if pipeline.statements != (select, emit):
        raise SemanticError("select must precede the terminal emit statement", pipeline.statements[0].span)
    for label, path in (("Input", pipeline.input_path), ("Output", emit.path)):
        if not path.value or "\x00" in path.value:
            raise SemanticError(f"{label} path must be nonempty and contain no NUL characters", path.span)
    selected: dict[str, Symbol] = {}
    for field in select.fields:
        name = field.value
        if name not in symbols:
            raise SemanticError(f"Unknown field {name!r}" + _suggest(name, list(symbols)), field.span)
        if name in selected:
            raise SemanticError(f"Duplicate selected field {name!r}", field.span)
        selected[name] = symbols[name]
    return CheckedProgram(program, tuple(symbols.values()), tuple(selected.values()))
