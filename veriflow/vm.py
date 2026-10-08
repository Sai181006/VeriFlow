"""Bytecode generation and stack-machine execution for checked VeriFlow programs."""

from dataclasses import dataclass
from fractions import Fraction

from .lexer import Span
from .semantics import CheckedProgram, TypedExpression


@dataclass(frozen=True)
class BytecodeInstruction:
    opcode: str
    operand: str | bool | int | None = None
    span: Span | None = None


@dataclass(frozen=True)
class BytecodeOperation:
    kind: str
    instructions: tuple[BytecodeInstruction, ...]
    target: str | None = None
    target_type: str | None = None
    message: str | None = None
    span: Span | None = None


@dataclass(frozen=True)
class BytecodeProgram:
    operations: tuple[BytecodeOperation, ...]
    selected: tuple[str, ...]


_BINARY_OPCODES = {
    "+": "ADD", "-": "SUBTRACT", "*": "MULTIPLY", "/": "DIVIDE",
    "==": "COMPARE_EQ", "!=": "COMPARE_NE", "<": "COMPARE_LT",
    "<=": "COMPARE_LE", ">": "COMPARE_GT", ">=": "COMPARE_GE",
}


def compile_expression(expression: TypedExpression) -> tuple[BytecodeInstruction, ...]:
    if expression.kind == "literal":
        return (BytecodeInstruction(f"PUSH_{expression.type.upper()}",
                                    expression.value, expression.span),)
    if expression.kind == "field":
        return (BytecodeInstruction("LOAD_FIELD", str(expression.value), expression.span),)
    if expression.kind == "unary":
        assert expression.left is not None
        opcode = "BOOLEAN_NOT" if expression.operator == "not" else "NEGATE"
        return compile_expression(expression.left) + (BytecodeInstruction(opcode, span=expression.span),)
    assert expression.left is not None and expression.right is not None
    if expression.operator in {"and", "or"}:
        left = compile_expression(expression.left)
        right = compile_expression(expression.right)
        jump = "JUMP_IF_FALSE" if expression.operator == "and" else "JUMP_IF_TRUE"
        return left + (BytecodeInstruction(jump, len(right), expression.left.span),) + right
    return (compile_expression(expression.left) + compile_expression(expression.right)
            + (BytecodeInstruction(_BINARY_OPCODES[expression.operator], span=expression.span),))


def compile_program(checked: CheckedProgram) -> BytecodeProgram:
    operations = []
    for operation in checked.operations:
        target = operation.symbol.name if operation.symbol else None
        target_type = operation.symbol.type if operation.symbol else None
        operations.append(BytecodeOperation(
            operation.kind,
            compile_expression(operation.expression),
            target,
            target_type,
            operation.message,
            operation.span,
        ))
    return BytecodeProgram(tuple(operations), tuple(symbol.name for symbol in checked.selected))


def execute_expression(instructions: tuple[BytecodeInstruction, ...],
                       values: dict[str, object]) -> object:
    stack: list[object] = []
    pointer = 0
    while pointer < len(instructions):
        instruction = instructions[pointer]
        opcode = instruction.opcode
        if opcode == "LOAD_FIELD":
            stack.append(values[str(instruction.operand)])
        elif opcode in {"PUSH_INT", "PUSH_DECIMAL"}:
            stack.append(Fraction(str(instruction.operand)))
        elif opcode == "PUSH_BOOL":
            stack.append(bool(instruction.operand))
        elif opcode == "PUSH_TEXT":
            stack.append(str(instruction.operand))
        elif opcode == "NEGATE":
            stack.append(-stack.pop())
        elif opcode == "BOOLEAN_NOT":
            stack.append(not stack.pop())
        elif opcode in {"JUMP_IF_FALSE", "JUMP_IF_TRUE"}:
            value = bool(stack[-1])
            should_jump = (opcode == "JUMP_IF_FALSE" and not value) or (opcode == "JUMP_IF_TRUE" and value)
            if should_jump:
                pointer += int(instruction.operand)
            else:
                stack.pop()
        else:
            right = stack.pop()
            left = stack.pop()
            operations = {
                "ADD": lambda: left + right,
                "SUBTRACT": lambda: left - right,
                "MULTIPLY": lambda: left * right,
                "DIVIDE": lambda: left / right,
                "COMPARE_EQ": lambda: left == right,
                "COMPARE_NE": lambda: left != right,
                "COMPARE_LT": lambda: left < right,
                "COMPARE_LE": lambda: left <= right,
                "COMPARE_GT": lambda: left > right,
                "COMPARE_GE": lambda: left >= right,
            }
            stack.append(operations[opcode]())
        pointer += 1
    if len(stack) != 1:
        raise RuntimeError(f"Invalid VeriFlow bytecode stack depth: {len(stack)}")
    return stack[0]


def format_bytecode(program: BytecodeProgram) -> str:
    lines = ["VERIFLOW PIPELINE BYTECODE"]
    for number, operation in enumerate(program.operations, 1):
        target = f" {operation.target}:{operation.target_type}" if operation.target else ""
        lines.append(f"  OPERATION {number}: {operation.kind.upper()}{target}")
        for offset, instruction in enumerate(operation.instructions):
            operand = f" {instruction.operand}" if instruction.operand is not None else ""
            lines.append(f"    {offset:04d}  {instruction.opcode}{operand}")
    lines.append("  PROJECT " + ", ".join(program.selected))
    return "\n".join(lines)
