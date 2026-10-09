"""Semantics-preserving rewrites for typed VeriFlow expressions."""

from dataclasses import dataclass, replace
from fractions import Fraction

from .semantics import CheckedProgram, TypedExpression


@dataclass(frozen=True)
class OptimizationStats:
    folded: int = 0
    identities: int = 0
    boolean: int = 0

    def __add__(self, other: "OptimizationStats") -> "OptimizationStats":
        return OptimizationStats(self.folded + other.folded,
                                 self.identities + other.identities,
                                 self.boolean + other.boolean)

    @property
    def total(self) -> int:
        return self.folded + self.identities + self.boolean


def _literal_value(expression: TypedExpression | None):
    if expression is None or expression.kind != "literal":
        return None
    if expression.type in {"int", "decimal"}:
        return Fraction(str(expression.value))
    return expression.value


def _numeric_literal(expression: TypedExpression | None, value: int) -> bool:
    return (expression is not None and expression.type in {"int", "decimal"}
            and _literal_value(expression) == value)


def optimize_expression(expression: TypedExpression) -> tuple[TypedExpression, OptimizationStats]:
    """Fold constants and remove safe identities without hiding runtime errors.

    A right operand may be skipped only when the left operand already makes a
    Boolean result certain. For example, ``x and false`` must still evaluate x.
    Arithmetic identities retain the original type of the expression.
    """
    if expression.kind in {"literal", "field"}:
        return expression, OptimizationStats()

    left, left_stats = (optimize_expression(expression.left) if expression.left
                        else (None, OptimizationStats()))
    right, right_stats = (optimize_expression(expression.right) if expression.right
                          else (None, OptimizationStats()))
    stats = left_stats + right_stats
    rewritten = replace(expression, left=left, right=right)
    if left is None or (expression.kind == "binary" and right is None):
        return rewritten, stats

    left_value = _literal_value(left)
    right_value = _literal_value(right)
    if left_value is not None and (right is None or right_value is not None):
        try:
            if expression.kind == "unary":
                value = not left_value if expression.operator == "not" else -left_value
            else:
                operations = {
                    "+": lambda: left_value + right_value,
                    "-": lambda: left_value - right_value,
                    "*": lambda: left_value * right_value,
                    "/": lambda: left_value / right_value,
                    "==": lambda: left_value == right_value,
                    "!=": lambda: left_value != right_value,
                    "<": lambda: left_value < right_value,
                    "<=": lambda: left_value <= right_value,
                    ">": lambda: left_value > right_value,
                    ">=": lambda: left_value >= right_value,
                    "and": lambda: bool(left_value and right_value),
                    "or": lambda: bool(left_value or right_value),
                }
                value = operations[expression.operator]()
        except (ArithmeticError, KeyError):
            pass  # Preserve failures such as division by zero for execution.
        else:
            if isinstance(value, Fraction):
                value = (str(value.numerator) if value.denominator == 1
                         else f"{value.numerator}/{value.denominator}")
            literal = TypedExpression("literal", expression.type, expression.span, value=value)
            return literal, stats + OptimizationStats(folded=1)

    if expression.kind != "binary" or right is None:
        return rewritten, stats

    operator = expression.operator
    if operator in {"and", "or"}:
        # Left-hand constants can suppress the right side because the VM already
        # short-circuits. A right-hand constant cannot suppress the left side.
        if operator == "and":
            replacement = (left if left_value is False else right if left_value is True
                           else left if right_value is True else None)
        else:
            replacement = (left if left_value is True else right if left_value is False
                           else left if right_value is False else None)
        if replacement is not None:
            return replacement, stats + OptimizationStats(boolean=1)

    replacement = None
    if operator == "+":
        if _numeric_literal(right, 0) and left.type == expression.type:
            replacement = left
        elif _numeric_literal(left, 0) and right.type == expression.type:
            replacement = right
    elif operator == "-" and _numeric_literal(right, 0) and left.type == expression.type:
        replacement = left
    elif operator == "*":
        if _numeric_literal(right, 1) and left.type == expression.type:
            replacement = left
        elif _numeric_literal(left, 1) and right.type == expression.type:
            replacement = right
    elif operator == "/" and _numeric_literal(right, 1) and left.type == expression.type:
        replacement = left
    if replacement is not None:
        return replacement, stats + OptimizationStats(identities=1)
    return rewritten, stats


def optimize_checked_program(checked: CheckedProgram) -> tuple[CheckedProgram, OptimizationStats]:
    """Return a consistent checked program for the existing VM and runtime.

    The original compiler modules remain unchanged. Their normal bytecode
    generator compiles the rewritten operations supplied by this wrapper.
    """
    operations = []
    conditions = []
    derivations = []
    condition_index = 0
    derivation_index = 0
    total = OptimizationStats()
    for operation in checked.operations:
        expression, stats = optimize_expression(operation.expression)
        total += stats
        operations.append(replace(operation, expression=expression))
        if operation.kind == "let":
            derivations.append(replace(checked.derivations[derivation_index],
                                       expression=expression))
            derivation_index += 1
        else:
            conditions.append(replace(checked.conditions[condition_index],
                                      expression=expression))
            condition_index += 1
    optimized = replace(checked, operations=tuple(operations),
                        conditions=tuple(conditions), derivations=tuple(derivations))
    return optimized, total
