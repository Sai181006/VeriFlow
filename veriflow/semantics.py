"""Resolve the schema and ordered output fields before CSV execution."""

from dataclasses import dataclass
from decimal import Decimal
from difflib import get_close_matches

from .ast import Binary, Emit, Keep, Let, Literal, Program, Require, Select, Unary, Variable
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
    conditions: tuple["CheckedCondition", ...]
    derivations: tuple["CheckedDerivation", ...]
    operations: tuple["CheckedOperation", ...]


@dataclass(frozen=True)
class TypedExpression:
    kind: str
    type: str
    span: Span
    value: str | bool | None = None
    operator: str | None = None
    left: "TypedExpression | None" = None
    right: "TypedExpression | None" = None


@dataclass(frozen=True)
class CheckedCondition:
    kind: str
    expression: TypedExpression
    message: str | None
    span: Span


@dataclass(frozen=True)
class CheckedDerivation:
    symbol: Symbol
    expression: TypedExpression
    span: Span


@dataclass(frozen=True)
class CheckedOperation:
    kind: str
    expression: TypedExpression
    span: Span
    symbol: Symbol | None = None
    message: str | None = None


def _suggest(name: str, choices: list[str]) -> str:
    matches = get_close_matches(name, choices, n=1, cutoff=0.6)
    return f"; did you mean {matches[0]!r}?" if matches else ""


def _numeric_constant(expression: TypedExpression) -> Decimal | None:
    if expression.kind == "literal" and expression.type in {"int", "decimal"}:
        return Decimal(str(expression.value))
    if (expression.kind == "unary" and expression.operator == "-"
            and expression.left is not None):
        value = _numeric_constant(expression.left)
        return -value if value is not None else None
    return None


def _type_expression(expression, symbols: dict[str, Symbol]) -> TypedExpression:
    numeric = {"int", "decimal"}
    if isinstance(expression, Literal):
        return TypedExpression("literal", expression.type, expression.span, value=expression.value)
    if isinstance(expression, Variable):
        name = expression.name.value
        if name not in symbols:
            raise SemanticError(f"Unknown field {name!r}" + _suggest(name, list(symbols)),
                                expression.name.span)
        return TypedExpression("field", symbols[name].type, expression.span, value=name)
    if isinstance(expression, Unary):
        operand = _type_expression(expression.operand, symbols)
        if expression.operator == "not":
            if operand.type != "bool":
                raise SemanticError("Operator 'not' requires a bool operand", expression.span)
            result_type = "bool"
        else:
            if operand.type not in numeric:
                raise SemanticError("Unary '-' requires a numeric operand", expression.span)
            result_type = operand.type
        return TypedExpression("unary", result_type, expression.span,
                               operator=expression.operator, left=operand)
    if isinstance(expression, Binary):
        left = _type_expression(expression.left, symbols)
        right = _type_expression(expression.right, symbols)
        operator = expression.operator
        if operator in {"and", "or"}:
            if left.type != "bool" or right.type != "bool":
                raise SemanticError(f"Operator {operator!r} requires bool operands", expression.span)
            result_type = "bool"
        elif operator in {"+", "-", "*", "/"}:
            if left.type not in numeric or right.type not in numeric:
                raise SemanticError(f"Operator {operator!r} requires numeric operands", expression.span)
            result_type = "decimal" if operator == "/" or "decimal" in {left.type, right.type} else "int"
            if operator == "/" and _numeric_constant(right) == 0:
                raise SemanticError("Literal division by zero", right.span)
        elif operator in {"<", "<=", ">", ">="}:
            if not (left.type in numeric and right.type in numeric):
                raise SemanticError(f"Operator {operator!r} requires numeric operands", expression.span)
            result_type = "bool"
        else:
            compatible = left.type == right.type or {left.type, right.type} <= numeric
            if not compatible:
                raise SemanticError(f"Operator {operator!r} requires compatible operands", expression.span)
            result_type = "bool"
        return TypedExpression("binary", result_type, expression.span, operator=operator,
                               left=left, right=right)
    raise TypeError(f"Unsupported expression node: {type(expression).__name__}")


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
    if (len(pipeline.statements) < 2 or pipeline.statements[-2] is not select
            or pipeline.statements[-1] is not emit):
        select_index = pipeline.statements.index(select)
        offender = next((statement for index, statement in enumerate(pipeline.statements)
                         if ((isinstance(statement, (Let, Require, Keep)) and index > select_index)
                             or (statement is select and index != len(pipeline.statements) - 2)
                             or (statement is emit and index != len(pipeline.statements) - 1))),
                        pipeline.statements[0])
        raise SemanticError("let/require/keep must precede select, and emit must be terminal", offender.span)
    for label, path in (("Input", pipeline.input_path), ("Output", emit.path)):
        if not path.value or "\x00" in path.value:
            raise SemanticError(f"{label} path must be nonempty and contain no NUL characters", path.span)
    visible = dict(symbols)
    conditions: list[CheckedCondition] = []
    derivations: list[CheckedDerivation] = []
    operations: list[CheckedOperation] = []
    for statement in pipeline.statements[:-2]:
        if isinstance(statement, Let):
            name = statement.name.value
            if name in visible:
                raise SemanticError(f"Duplicate field or derived value {name!r}", statement.name.span)
            typed = _type_expression(statement.expression, visible)
            symbol = Symbol(name, typed.type, statement.name.span)
            visible[name] = symbol
            derivation = CheckedDerivation(symbol, typed, statement.span)
            derivations.append(derivation)
            operations.append(CheckedOperation("let", typed, statement.span, symbol=symbol))
            continue
        if not isinstance(statement, (Require, Keep)):
            raise SemanticError("Only let, require, or keep may appear before select", statement.span)
        typed = _type_expression(statement.condition, visible)
        if typed.type != "bool":
            raise SemanticError(f"{type(statement).__name__.lower()} condition must have type bool",
                                statement.condition.span)
        condition = CheckedCondition(
            "require" if isinstance(statement, Require) else "keep", typed,
            statement.message.value if isinstance(statement, Require) else None,
            statement.span,
        )
        conditions.append(condition)
        operations.append(CheckedOperation(condition.kind, typed, statement.span,
                                           message=condition.message))
    selected: dict[str, Symbol] = {}
    for field in select.fields:
        name = field.value
        if name not in visible:
            raise SemanticError(f"Unknown field {name!r}" + _suggest(name, list(visible)), field.span)
        if name in selected:
            raise SemanticError(f"Duplicate selected field {name!r}", field.span)
        selected[name] = visible[name]
    return CheckedProgram(program, tuple(symbols.values()), tuple(selected.values()),
                          tuple(conditions), tuple(derivations), tuple(operations))
