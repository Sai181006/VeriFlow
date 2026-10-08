"""Small stack-style logical IR used by the explain command."""

from dataclasses import dataclass
from fractions import Fraction

from .semantics import CheckedProgram, TypedExpression


@dataclass(frozen=True)
class Instruction:
    opcode: str
    operand: str | bool | None = None


@dataclass(frozen=True)
class PlanStep:
    operation: str
    details: tuple[str, ...] = ()
    instructions: tuple[Instruction, ...] = ()


@dataclass(frozen=True)
class LogicalPlan:
    steps: tuple[PlanStep, ...]
    optimizations: tuple[str, ...] = ()


_OPCODES = {
    "+": "ADD", "-": "SUBTRACT", "*": "MULTIPLY", "/": "DIVIDE",
    "==": "COMPARE_EQ", "!=": "COMPARE_NE", "<": "COMPARE_LT",
    "<=": "COMPARE_LE", ">": "COMPARE_GT", ">=": "COMPARE_GE",
    "and": "BOOLEAN_AND", "or": "BOOLEAN_OR", "not": "BOOLEAN_NOT",
}


def lower_expression(expression: TypedExpression) -> tuple[Instruction, ...]:
    """Lower a typed expression to deterministic postfix instructions."""
    if expression.kind == "literal":
        return (Instruction(f"PUSH_{expression.type.upper()}", expression.value),)
    if expression.kind == "field":
        return (Instruction("LOAD_FIELD", f"{expression.value}:{expression.type}"),)
    if expression.kind == "unary":
        assert expression.left is not None and expression.operator is not None
        opcode = "NEGATE" if expression.operator == "-" else _OPCODES[expression.operator]
        return lower_expression(expression.left) + (Instruction(opcode),)
    assert expression.left is not None and expression.right is not None
    assert expression.operator is not None
    return (lower_expression(expression.left) + lower_expression(expression.right)
            + (Instruction(_OPCODES[expression.operator]),))


def _literal_value(expression: TypedExpression):
    if expression.kind != "literal":
        return None
    if expression.type in {"int", "decimal"}:
        return Fraction(str(expression.value))
    return expression.value


def optimize_expression(expression: TypedExpression) -> tuple[TypedExpression, int]:
    """Fold constant subexpressions while retaining source spans and types."""
    if expression.kind in {"literal", "field"}:
        return expression, 0
    left, left_count = optimize_expression(expression.left) if expression.left else (None, 0)
    right, right_count = optimize_expression(expression.right) if expression.right else (None, 0)
    rewritten = TypedExpression(expression.kind, expression.type, expression.span,
                                value=expression.value, operator=expression.operator,
                                left=left, right=right)
    if left is None or (expression.kind == "binary" and right is None):
        return rewritten, left_count + right_count
    left_value = _literal_value(left)
    right_value = _literal_value(right) if right is not None else None
    if left_value is None or (expression.kind == "binary" and right_value is None):
        return rewritten, left_count + right_count
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
        return rewritten, left_count + right_count
    if isinstance(value, Fraction):
        literal = (str(value.numerator) if value.denominator == 1
                   else f"{value.numerator}/{value.denominator}")
    else:
        literal = value
    return TypedExpression("literal", expression.type, expression.span, value=literal), left_count + right_count + 1


def build_plan(checked: CheckedProgram, optimized: bool = False) -> LogicalPlan:
    pipeline = checked.program.pipeline
    optimization_count = 0
    steps = [PlanStep("SCAN", (pipeline.input_path.value,)),
             PlanStep("VALIDATE", tuple(f"{symbol.name}:{symbol.type}"
                                        for symbol in checked.symbols))]
    for operation in checked.operations:
        expression = operation.expression
        folded = 0
        if optimized:
            expression, folded = optimize_expression(expression)
            if folded:
                optimization_count += folded
        if operation.kind == "let":
            assert operation.symbol is not None
            steps.append(PlanStep("DERIVE",
                                  (f"{operation.symbol.name}:{operation.symbol.type}",),
                                  lower_expression(expression)))
        else:
            details = (operation.message,) if operation.message is not None else ()
            steps.append(PlanStep("REQUIRE" if operation.kind == "require" else "FILTER",
                                  details, lower_expression(expression)))
    steps.extend((PlanStep("PROJECT", tuple(symbol.name for symbol in checked.selected)),
                  PlanStep("EMIT", (pipeline.statements[-1].path.value,))))
    optimizations = ((f"constant-folded {optimization_count} expression node(s)",)
                     if optimized and optimization_count else ())
    return LogicalPlan(tuple(steps), optimizations)


def format_plan(plan: LogicalPlan) -> str:
    lines = ["OPTIMIZED LOGICAL PLAN" if plan.optimizations else "LOGICAL PLAN"]
    for optimization in plan.optimizations:
        lines.append(f"  optimization: {optimization}")
    for number, step in enumerate(plan.steps, 1):
        details = " " + ", ".join(step.details) if step.details else ""
        lines.append(f"  {number}. {step.operation}{details}")
        for instruction in step.instructions:
            operand = f" {instruction.operand}" if instruction.operand is not None else ""
            lines.append(f"       {instruction.opcode}{operand}")
    return "\n".join(lines)
