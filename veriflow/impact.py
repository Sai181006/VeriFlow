"""Pipeline-aware analysis of explicitly mapped, one-step schema evolution.

The proof rules are intentionally small. A result of ``preserved`` or
``conditional`` is a sufficient guarantee over well-typed legacy records;
unsupported expressions and mappings remain ``unknown``.
"""

from dataclasses import dataclass, replace
from decimal import Decimal
from fractions import Fraction
from typing import Any

from .evolution import EvolutionPlan, MissingInformationError, migrate_forward
from .semantics import CheckedProgram, TypedExpression
from .vm import BytecodeProgram, compile_program, execute_expression


@dataclass(frozen=True)
class Observation:
    outcome: str
    message: str | None = None
    values: tuple[object, ...] = ()


@dataclass(frozen=True)
class Guard:
    field: str
    kind: str
    threshold: int | None = None

    def accepts(self, record: dict[str, Any]) -> bool:
        try:
            number = Decimal(str(record[self.field]))
        except (KeyError, ValueError, ArithmeticError):
            return False
        if not number.is_finite():
            return False
        if self.kind == "integral_decimal":
            return number == number.to_integral_value()
        if self.kind == "outside_positive_threshold_gap" and self.threshold is not None:
            return number <= self.threshold or number >= self.threshold + 1
        raise ValueError(f"Unknown guard kind {self.kind!r}")


@dataclass(frozen=True)
class ImpactFinding:
    status: str
    fields: tuple[str, ...]
    rule_id: str
    reason: str
    operations: tuple[str, ...] = ()


@dataclass(frozen=True)
class DivergenceWitness:
    old_record: dict[str, Any]
    new_record: dict[str, Any]
    old_observation: Observation
    adapted_observation: Observation


@dataclass(frozen=True)
class CollisionWitness:
    first_record: dict[str, Any]
    second_record: dict[str, Any]
    migrated_record: dict[str, Any]
    first_observation: Observation
    second_observation: Observation


@dataclass(frozen=True)
class ImpactReport:
    status: str
    findings: tuple[ImpactFinding, ...]
    guards: tuple[Guard, ...]
    required_old_fields: tuple[str, ...]
    divergence: DivergenceWitness | None = None
    collision: CollisionWitness | None = None


def _references(expression: TypedExpression, derived: dict[str, TypedExpression]) -> set[str]:
    if expression.kind == "field":
        name = str(expression.value)
        return _references(derived[name], derived) if name in derived else {name}
    result: set[str] = set()
    if expression.left is not None:
        result.update(_references(expression.left, derived))
    if expression.right is not None:
        result.update(_references(expression.right, derived))
    return result


def observed_source_fields(checked: CheckedProgram) -> tuple[str, ...]:
    """Resolve transitive dependencies of policies and projected values."""
    derived = {item.symbol.name: item.expression for item in checked.derivations}
    needed: set[str] = set()
    # Even an unselected derivation is executed and may fail (e.g. division by zero).
    for derivation in checked.derivations:
        needed.update(_references(derivation.expression, derived))
    for condition in checked.conditions:
        needed.update(_references(condition.expression, derived))
    for selected in checked.selected:
        if selected.name in derived:
            needed.update(_references(derived[selected.name], derived))
        else:
            needed.add(selected.name)
    return tuple(symbol.name for symbol in checked.symbols if symbol.name in needed)


def _typed(value: Any, kind: str) -> object:
    if kind in {"int", "decimal"}:
        return Fraction(str(value))
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if value in {"true", "false"}:
            return value == "true"
        raise ValueError(f"Invalid bool value {value!r}")
    if kind == "text":
        if not isinstance(value, str):
            raise ValueError(f"Invalid text value {value!r}")
        return value
    raise ValueError(f"Unknown field type {kind!r}")


def observe(checked: CheckedProgram, record: dict[str, Any],
            bytecode: BytecodeProgram | None = None) -> Observation:
    """Evaluate one well-typed row with the production VM operation order."""
    compiled = bytecode or compile_program(checked)
    values = {symbol.name: _typed(record[symbol.name], symbol.type)
              for symbol in checked.symbols if symbol.name in record}
    for operation, instructions in zip(checked.operations, compiled.operations, strict=True):
        try:
            result = execute_expression(instructions.instructions, values)
        except (ArithmeticError, ZeroDivisionError) as error:
            return Observation("expression-error", type(error).__name__)
        if operation.kind == "let":
            assert operation.symbol is not None
            values[operation.symbol.name] = result
        elif operation.kind == "require" and not bool(result):
            return Observation("rejected", operation.message)
        elif operation.kind == "keep" and not bool(result):
            return Observation("filtered")
    return Observation("emitted", values=tuple(values[item.name] for item in checked.selected))


def adapt_record(plan: EvolutionPlan, new_record: dict[str, Any],
                 required_old_fields: tuple[str, ...]) -> dict[str, Any]:
    """Reconstruct only fields observable by a legacy pipeline."""
    required = set(required_old_fields)
    result: dict[str, Any] = {}
    for mapping in plan.mappings:
        if not required.intersection(mapping.sources):
            continue
        if mapping.kind in {"copy", "rename", "convert"}:
            value = new_record[mapping.targets[0]]
            source_type = mapping.source_types[0]
            if source_type == "int":
                value = int(Decimal(str(value)))
            elif source_type == "decimal":
                value = Decimal(str(value))
            elif source_type == "text":
                value = str(value)
            elif source_type == "bool":
                value = _typed(value, "bool")
            result[mapping.sources[0]] = value
        elif mapping.kind == "drop":
            raise MissingInformationError(f"Required old field {mapping.sources[0]!r} was dropped")
        elif mapping.kind == "split":
            result[mapping.sources[0]] = (mapping.delimiter or "").join(
                str(new_record[name]) for name in mapping.targets)
        elif mapping.kind == "merge":
            parts = str(new_record[mapping.targets[0]]).split(mapping.delimiter or "", 1)
            parts.append("")
            result[mapping.sources[0]], result[mapping.sources[1]] = parts[:2]
    if required.difference(result):
        raise MissingInformationError(f"Cannot reconstruct {sorted(required.difference(result))}")
    return result


def observe_adapted(checked: CheckedProgram, plan: EvolutionPlan,
                    new_record: dict[str, Any], required: tuple[str, ...],
                    bytecode: BytecodeProgram | None = None) -> Observation:
    return observe(checked, adapt_record(plan, new_record, required), bytecode)


def _mentions(expression: TypedExpression, name: str,
              derived: dict[str, TypedExpression]) -> bool:
    return name in _references(expression, derived)


def _integer_literal(expression: TypedExpression) -> int | None:
    if expression.kind == "literal" and expression.type == "int":
        return int(str(expression.value))
    return None


def _truncation_invariant(expression: TypedExpression, name: str,
                          derived: dict[str, TypedExpression]) -> bool:
    """Sound rule for x >= k or x < k, where k is a positive integer.

    Python/Decimal integer conversion truncates toward zero. For k >= 1,
    both predicates are invariant under truncation for every finite decimal.
    """
    if not _mentions(expression, name, derived):
        return True
    if expression.kind == "field" and str(expression.value) in derived:
        return _truncation_invariant(derived[str(expression.value)], name, derived)
    if expression.kind == "unary" and expression.operator == "not":
        assert expression.left is not None
        return _truncation_invariant(expression.left, name, derived)
    if expression.kind == "binary" and expression.operator in {"and", "or"}:
        assert expression.left is not None and expression.right is not None
        return (_truncation_invariant(expression.left, name, derived)
                and _truncation_invariant(expression.right, name, derived))
    if expression.kind == "binary" and expression.left and expression.right:
        left, right = expression.left, expression.right
        if left.kind == "field" and left.value == name:
            threshold = _integer_literal(right)
            return threshold is not None and threshold >= 1 and expression.operator in {">=", "<"}
        if right.kind == "field" and right.value == name:
            threshold = _integer_literal(left)
            return threshold is not None and threshold >= 1 and expression.operator in {"<=", ">"}
    return False


def _threshold_guards(expression: TypedExpression, name: str,
                      derived: dict[str, TypedExpression]) -> tuple[Guard, ...] | None:
    """Return sufficient guards, or None when this expression is unsupported."""
    if _truncation_invariant(expression, name, derived):
        return ()
    if expression.kind == "field" and str(expression.value) in derived:
        return _threshold_guards(derived[str(expression.value)], name, derived)
    if expression.kind == "unary" and expression.operator == "not":
        assert expression.left is not None
        return _threshold_guards(expression.left, name, derived)
    if expression.kind == "binary" and expression.operator in {"and", "or"}:
        assert expression.left is not None and expression.right is not None
        left = _threshold_guards(expression.left, name, derived)
        right = _threshold_guards(expression.right, name, derived)
        return None if left is None or right is None else left + right
    if expression.kind == "binary" and expression.left and expression.right:
        left, right = expression.left, expression.right
        if left.kind == "field" and left.value == name and expression.operator in {">", "<="}:
            threshold = _integer_literal(right)
        elif right.kind == "field" and right.value == name and expression.operator in {"<", ">="}:
            threshold = _integer_literal(left)
        else:
            threshold = None
        if threshold is not None and threshold >= 1:
            return (Guard(name, "outside_positive_threshold_gap", threshold),)
    return None


def _contains_division(expression: TypedExpression,
                       derived: dict[str, TypedExpression]) -> bool:
    if expression.kind == "field" and str(expression.value) in derived:
        return _contains_division(derived[str(expression.value)], derived)
    return (expression.operator == "/"
            or expression.left is not None and _contains_division(expression.left, derived)
            or expression.right is not None and _contains_division(expression.right, derived))


def _default_record(plan: EvolutionPlan) -> dict[str, Any]:
    defaults: dict[str, Any] = {"int": 0, "decimal": Decimal("0"),
                                "text": "", "bool": False}
    return {name: defaults[kind] for name, kind in plan.old_fields}


def _numeric_literals(checked: CheckedProgram) -> set[Decimal]:
    values: set[Decimal] = set()

    def collect(expression: TypedExpression) -> None:
        if expression.kind == "literal" and expression.type in {"int", "decimal"}:
            values.add(Decimal(str(expression.value)))
        if expression.left:
            collect(expression.left)
        if expression.right:
            collect(expression.right)

    for operation in checked.operations:
        collect(operation.expression)
    return values


def _candidate_values(kind: str, anchors: set[Decimal]) -> tuple[Any, ...]:
    if kind == "text":
        return ("", "a", "b", "a b")
    if kind == "bool":
        return (False, True)
    numbers = {Decimal("-1"), Decimal("-0.7"), Decimal("0"),
               Decimal("0.7"), Decimal("1"), Decimal("40.7")}
    for anchor in anchors:
        numbers.update((anchor - 1, anchor, anchor + 1, anchor + Decimal("0.7")))
    if kind == "int":
        return tuple(sorted({int(number) for number in numbers if number == number.to_integral_value()}))
    return tuple(sorted(numbers))


def _replay_divergence(checked: CheckedProgram, plan: EvolutionPlan,
                       required: tuple[str, ...]) -> DivergenceWitness | None:
    compiled = compile_program(checked)
    anchors = _numeric_literals(checked)
    base = _default_record(plan)
    for name, kind in plan.old_fields:
        for value in _candidate_values(kind, anchors):
            old_record = {**base, name: value}
            try:
                new_record = migrate_forward(plan, old_record)
                old_result = observe(checked, old_record, compiled)
                new_result = observe_adapted(checked, plan, new_record, required, compiled)
            except (ValueError, KeyError, ArithmeticError, MissingInformationError):
                continue
            if old_result != new_result:
                return DivergenceWitness(old_record, new_record, old_result, new_result)
    return None


def _replay_collision(checked: CheckedProgram, plan: EvolutionPlan) -> CollisionWitness | None:
    compiled = compile_program(checked)
    anchors = _numeric_literals(checked)
    base = _default_record(plan)
    for name, kind in plan.old_fields:
        seen: dict[tuple[tuple[str, str], ...], tuple[dict[str, Any], Observation]] = {}
        for value in _candidate_values(kind, anchors):
            old_record = {**base, name: value}
            try:
                migrated = migrate_forward(plan, old_record)
                observation = observe(checked, old_record, compiled)
            except (ValueError, KeyError, ArithmeticError):
                continue
            key = tuple((field, repr(cell)) for field, cell in migrated.items())
            if key in seen:
                prior, prior_observation = seen[key]
                if observation != prior_observation:
                    return CollisionWitness(prior, old_record, migrated,
                                            prior_observation, observation)
            else:
                seen[key] = (old_record, observation)
    return None


def analyze_impact(checked: CheckedProgram, plan: EvolutionPlan) -> ImpactReport:
    """Derive conservative pipeline guarantees from explicit one-step mappings."""
    schema_fields = tuple((item.name, item.type) for item in checked.symbols)
    if checked.program.schema.name.value != plan.old_schema or schema_fields != plan.old_fields:
        raise ValueError("Pipeline schema must exactly match the evolution source schema")
    required = observed_source_fields(checked)
    derived = {item.symbol.name: item.expression for item in checked.derivations}
    selected_refs: set[str] = set()
    for symbol in checked.selected:
        if symbol.name in derived:
            selected_refs.update(_references(derived[symbol.name], derived))
        else:
            selected_refs.add(symbol.name)
    findings: list[ImpactFinding] = []
    guards: list[Guard] = []
    for mapping in plan.mappings:
        sites = tuple(f"{operation.kind}#{index}" for index, operation in
                      enumerate(checked.operations, 1)
                      if set(mapping.sources).intersection(
                          _references(operation.expression, derived)))
        if set(mapping.sources).intersection(selected_refs):
            sites += ("select",)
        used = tuple(name for name in mapping.sources if name in required)
        if mapping.classification == "unsupported":
            findings.append(ImpactFinding("unknown", mapping.sources + mapping.targets,
                                          "unsupported-mapping", "Forward migration is not defined"))
        elif not used:
            findings.append(ImpactFinding("preserved", mapping.sources + mapping.targets,
                                          "unused-source", "No observable operation depends on the changed source fields"))
        elif mapping.kind in {"copy", "rename", "convert"}:
            source_type, target_type = mapping.source_types[0], mapping.target_types[0]
            if source_type == target_type or (source_type, target_type) == ("int", "decimal"):
                findings.append(ImpactFinding("preserved", used, "exact-reconstruction",
                                              "Forward then reverse preserves the typed source value"))
            elif (source_type, target_type) == ("decimal", "int"):
                name = mapping.sources[0]
                risky_derivation = any(
                    name in _references(item.expression, derived)
                    and _contains_division(item.expression, derived)
                    for item in checked.derivations)
                policy_guards = [_threshold_guards(condition.expression, name, derived)
                                 for condition in checked.conditions]
                if name not in selected_refs and not risky_derivation and all(
                        item is not None for item in policy_guards):
                    sufficient = tuple(dict.fromkeys(
                        guard for item in policy_guards for guard in item))
                else:
                    sufficient = (Guard(name, "integral_decimal"),)
                if not sufficient:
                    findings.append(ImpactFinding("preserved", used, "positive-integer-threshold",
                                                  "Observed predicates are invariant under integer truncation"))
                else:
                    guards.extend(sufficient)
                    if all(guard.kind == "outside_positive_threshold_gap" for guard in sufficient):
                        findings.append(ImpactFinding("conditional", used, "threshold-gap",
                                                      "Guard excludes intervals where truncation can flip a predicate"))
                    else:
                        findings.append(ImpactFinding("conditional", used, "integral-decimal",
                                                      "An integral source value reconstructs exactly"))
            else:
                findings.append(ImpactFinding("unknown", used, "unproved-conversion",
                                              "No sound pipeline rule for this conversion"))
        elif mapping.kind == "drop":
            findings.append(ImpactFinding("unknown", used, "required-field-dropped",
                                          "An observable source field cannot be reconstructed; "
                                          "a behavioral collision is needed to prove a break"))
        else:
            findings.append(ImpactFinding("unknown", used, "unproved-structural-rule",
                                          "Pipeline effect of split or merge is not proved"))
        findings[-1] = replace(findings[-1], operations=sites)
    has_unknown = any(item.status == "unknown" for item in findings)
    status = "unknown" if has_unknown else "conditional" if guards else "preserved"
    collision = (_replay_collision(checked, plan)
                 if status in {"unknown", "conditional"} and plan.compatibility != "unsupported"
                 else None)
    if status == "unknown" and collision is not None:
        status = "breaking"
    divergence = _replay_divergence(checked, plan, required) if status == "conditional" else None
    return ImpactReport(status, tuple(findings), tuple(guards), required,
                        divergence, collision)


def format_impact(report: ImpactReport) -> str:
    lines = [f"PIPELINE IMPACT: {report.status.upper()}",
             "Observed source fields: " + (", ".join(report.required_old_fields) or "none")]
    for finding in report.findings:
        sites = f" via {', '.join(finding.operations)}" if finding.operations else ""
        lines.append(f"  {finding.status.upper():11} {', '.join(finding.fields) or '<none>'}: "
                     f"{finding.reason} [{finding.rule_id}]{sites}")
    for guard in report.guards:
        threshold = f" threshold={guard.threshold}" if guard.threshold is not None else ""
        lines.append(f"  GUARD {guard.field}: {guard.kind}{threshold}")
    if report.divergence:
        lines.append(f"  WITNESS old={report.divergence.old_record!r}")
        lines.append(f"          migrated={report.divergence.new_record!r}")
        lines.append(f"          before={report.divergence.old_observation!r}")
        lines.append(f"          after={report.divergence.adapted_observation!r}")
    if report.collision:
        lines.append(f"  COLLISION old1={report.collision.first_record!r}")
        lines.append(f"            old2={report.collision.second_record!r}")
        lines.append(f"            both migrate to={report.collision.migrated_record!r}")
    return "\n".join(lines)
