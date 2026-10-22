"""Compile a legacy row pipeline into new-schema VM bindings and operations.

The compiled plan reads only new-schema cells and explicitly supplied retained
old cells. It never calls the generic legacy-row adapter at execution time.
Guard admission remains a migration-time certificate because guards need old
cells that may no longer exist in the new schema.
"""

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
import json
from pathlib import Path
from typing import Any

from .evolution import EvolutionPlan
from .impact import Guard, ImpactReport, Observation
from .lexer import Position, Span
from .semantics import CheckedProgram
from .vm import (BytecodeInstruction, BytecodeOperation, BytecodeProgram,
                 compile_program, execute_expression)


@dataclass(frozen=True)
class FieldBinding:
    old_field: str
    old_type: str
    operation: str
    source_index: int
    new_fields: tuple[str, ...]
    delimiter: str | None
    guards: tuple[Guard, ...]
    recovery_required: bool


@dataclass(frozen=True)
class EvolvedProgram:
    new_schema: str
    new_fields: tuple[tuple[str, str], ...]
    old_fields: tuple[tuple[str, str], ...]
    bindings: tuple[FieldBinding, ...]
    bytecode: BytecodeProgram
    impact_status: str


def compile_evolved_pipeline(checked: CheckedProgram, evolution: EvolutionPlan,
                             impact: ImpactReport) -> EvolvedProgram:
    """Generate explicit new-column bindings for the existing row-wise VM."""
    if checked.program.schema.name.value != evolution.old_schema or (
            tuple((symbol.name, symbol.type) for symbol in checked.symbols)
            != evolution.old_fields):
        raise ValueError("Pipeline schema does not match evolution source schema")
    if impact.required_old_fields != tuple(field for field, _ in evolution.old_fields
                                            if field in impact.required_old_fields):
        raise ValueError("Impact report does not match evolution source fields")
    required = set(impact.required_old_fields)
    bindings: list[FieldBinding] = []
    for mapping, finding in zip(evolution.mappings, impact.findings, strict=True):
        used = [field for field in mapping.sources if field in required]
        if not used:
            continue
        if mapping.classification == "unsupported" or finding.status == "unknown" and mapping.kind != "drop":
            raise ValueError(f"Cannot compile unsupported observed mapping: {mapping.kind}")
        guards = tuple(guard for guard in impact.guards if guard.field in mapping.sources)
        for index, old_field in enumerate(mapping.sources):
            if old_field not in required:
                continue
            bindings.append(FieldBinding(
                old_field, mapping.source_types[index], mapping.kind, index,
                mapping.targets, mapping.delimiter, guards,
                mapping.kind == "drop"))
    if {item.old_field for item in bindings} != required:
        raise ValueError("No new-schema binding for every observed old field")
    ordered = tuple(next(item for item in bindings if item.old_field == field)
                    for field in impact.required_old_fields)
    return EvolvedProgram(evolution.new_schema, evolution.new_fields, evolution.old_fields, ordered,
                          compile_program(checked), impact.status)


def load_evolved_pipeline(path: Path) -> EvolvedProgram:
    """Load a persisted compiled plan without legacy source or evolution files."""
    data = json.loads(path.read_text(encoding="utf-8"))

    def span(value: dict | None) -> Span | None:
        return (None if value is None else Span(Position(**value["start"]),
                                                Position(**value["end"])))

    bindings = tuple(FieldBinding(item["old_field"], item["old_type"],
                                  item["operation"], item["source_index"],
                                  tuple(item["new_fields"]), item["delimiter"],
                                  tuple(Guard(**guard) for guard in item["guards"]),
                                  item["recovery_required"])
                     for item in data["bindings"])
    operations = tuple(BytecodeOperation(
        item["kind"],
        tuple(BytecodeInstruction(instruction["opcode"], instruction["operand"],
                                  span(instruction["span"]))
              for instruction in item["instructions"]),
        item["target"], item["target_type"], item["message"], span(item["span"]))
        for item in data["bytecode"]["operations"])
    return EvolvedProgram(data["new_schema"], tuple(map(tuple, data["new_fields"])),
                          tuple(map(tuple, data["old_fields"])), bindings,
                          BytecodeProgram(operations, tuple(data["bytecode"]["selected"])),
                          data["impact_status"])


def _typed(value: Any, kind: str) -> object:
    if kind in {"int", "decimal"}:
        number = Decimal(str(value))
        if not number.is_finite() or kind == "int" and number != number.to_integral_value():
            raise ValueError(f"Invalid {kind} value {value!r}")
        return Fraction(number)
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if value in {"true", "false"}:
            return value == "true"
        raise ValueError(f"Invalid bool value {value!r}")
    if kind == "text" and isinstance(value, str):
        return value
    raise ValueError(f"Invalid {kind} value {value!r}")


def execute_evolved(program: EvolvedProgram, new_record: dict[str, Any],
                    *, retained: dict[str, Any] | None = None,
                    admitted: bool = False) -> Observation:
    """Run compiled operations from new cells and certified retained cells.

    ``admitted`` asserts that migration checked all guards on the old row.
    Without that assertion, every conditional binding must have a retained
    source cell. A dropped observed field always needs retention.
    """
    retained = retained or {}
    expected_new = dict(program.new_fields)
    if set(new_record) != set(expected_new):
        raise ValueError("New row does not match compiled new schema")
    if set(retained) - set(dict(program.old_fields)):
        raise ValueError("Sidecar contains an undeclared old field")
    for name, kind in program.new_fields:
        _typed(new_record[name], kind)
    values: dict[str, object] = {}
    for binding in program.bindings:
        if binding.old_field in retained:
            value = retained[binding.old_field]
        else:
            if binding.recovery_required:
                raise ValueError(f"Retained old field {binding.old_field!r} is required")
            if binding.guards and not admitted:
                raise ValueError(f"Guard certificate or retained {binding.old_field!r} is required")
            if binding.operation in {"copy", "rename", "convert"}:
                value = new_record[binding.new_fields[0]]
            elif binding.operation == "split":
                value = (binding.delimiter or "").join(
                    str(new_record[field]) for field in binding.new_fields)
            elif binding.operation == "merge":
                parts = str(new_record[binding.new_fields[0]]).split(binding.delimiter or "", 1)
                parts.append("")
                value = parts[binding.source_index]
            else:
                raise ValueError(f"Unsupported binding {binding.operation!r}")
        values[binding.old_field] = _typed(value, binding.old_type)
    for operation in program.bytecode.operations:
        try:
            result = execute_expression(operation.instructions, values)
        except (ArithmeticError, ZeroDivisionError) as error:
            return Observation("expression-error", type(error).__name__)
        if operation.kind == "let":
            assert operation.target is not None
            values[operation.target] = result
        elif operation.kind == "require" and not bool(result):
            return Observation("rejected", operation.message)
        elif operation.kind == "keep" and not bool(result):
            return Observation("filtered")
    return Observation("emitted", values=tuple(values[name] for name in program.bytecode.selected))
