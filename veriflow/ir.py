"""Small stack-style logical IR used by the explain command."""

from dataclasses import dataclass

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


def build_plan(checked: CheckedProgram) -> LogicalPlan:
    pipeline = checked.program.pipeline
    steps = [PlanStep("SCAN", (pipeline.input_path.value,)),
             PlanStep("VALIDATE", tuple(f"{symbol.name}:{symbol.type}"
                                        for symbol in checked.symbols))]
    for condition in checked.conditions:
        details = (condition.message,) if condition.message is not None else ()
        steps.append(PlanStep("REQUIRE" if condition.kind == "require" else "FILTER",
                              details, lower_expression(condition.expression)))
    steps.extend((PlanStep("PROJECT", tuple(symbol.name for symbol in checked.selected)),
                  PlanStep("EMIT", (pipeline.statements[-1].path.value,))))
    return LogicalPlan(tuple(steps))


def format_plan(plan: LogicalPlan) -> str:
    lines = ["LOGICAL PLAN"]
    for number, step in enumerate(plan.steps, 1):
        details = " " + ", ".join(step.details) if step.details else ""
        lines.append(f"  {number}. {step.operation}{details}")
        for instruction in step.instructions:
            operand = f" {instruction.operand}" if instruction.operand is not None else ""
            lines.append(f"       {instruction.opcode}{operand}")
    return "\n".join(lines)
