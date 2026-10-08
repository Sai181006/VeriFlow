"""Schema-evolution analysis, bidirectional adapters, and code generation."""

from dataclasses import asdict, dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from itertools import combinations
import json
from pathlib import Path
from typing import Any

from .evolution_ast import (AddRule, ConvertRule, DropRule, EvolutionProgram,
                            MergeRule, RenameRule, SplitRule)
from .semantics import SemanticError


@dataclass(frozen=True)
class EvolutionMapping:
    kind: str
    sources: tuple[str, ...]
    targets: tuple[str, ...]
    source_types: tuple[str, ...]
    target_types: tuple[str, ...]
    classification: str
    reason: str
    default: str | bool | None = None
    delimiter: str | None = None


@dataclass(frozen=True)
class EvolutionPlan:
    old_schema: str
    new_schema: str
    old_fields: tuple[tuple[str, str], ...]
    new_fields: tuple[tuple[str, str], ...]
    mappings: tuple[EvolutionMapping, ...]
    compatibility: str
    detections: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoundTripField:
    field: str
    original: Any
    reconstructed: Any
    preserved: bool


@dataclass(frozen=True)
class RoundTripReport:
    preserved: bool
    fields: tuple[RoundTripField, ...]
    forward_record: dict[str, Any]
    reconstructed_record: dict[str, Any]
    error: str | None = None


class MissingInformationError(ValueError):
    """A reverse adapter cannot construct a valid old-schema record."""


def _conversion_classification(source_type: str, target_type: str) -> tuple[str, str]:
    if source_type == target_type:
        return "lossless", "type is unchanged"
    if source_type == "int" and target_type == "decimal":
        return "lossless", "every integer is exactly representable as a decimal"
    if source_type == "decimal" and target_type == "int":
        return "lossy", "fractional information can be removed"
    if {source_type, target_type} <= {"int", "decimal", "text"}:
        return "conditional", "conversion depends on the actual field value"
    return "unsupported", f"automatic {source_type} to {target_type} conversion is unsafe"


def compile_evolution(program: EvolutionProgram) -> EvolutionPlan:
    schemas = {schema.name.value: schema for schema in program.schemas}
    if len(schemas) != 2:
        raise SemanticError("Evolution requires two schemas with distinct names", program.span)
    evolution = program.evolution
    if evolution.old_schema.value not in schemas:
        raise SemanticError(f"Unknown old schema {evolution.old_schema.value!r}", evolution.old_schema.span)
    if evolution.new_schema.value not in schemas:
        raise SemanticError(f"Unknown new schema {evolution.new_schema.value!r}", evolution.new_schema.span)
    old_schema = schemas[evolution.old_schema.value]
    new_schema = schemas[evolution.new_schema.value]

    def fields(schema):
        result = {}
        for field in schema.fields:
            if field.name.value in result:
                raise SemanticError(f"Duplicate schema field {field.name.value!r}", field.name.span)
            result[field.name.value] = field.type.value
        return result

    old = fields(old_schema)
    new = fields(new_schema)
    used_old: set[str] = set()
    used_new: set[str] = set()
    mappings: list[EvolutionMapping] = []

    def require_old(name, span):
        if name not in old:
            raise SemanticError(f"Unknown old field {name!r}", span)
        if name in used_old:
            raise SemanticError(f"Old field {name!r} is mapped more than once", span)

    def require_new(name, span):
        if name not in new:
            raise SemanticError(f"Unknown new field {name!r}", span)
        if name in used_new:
            raise SemanticError(f"New field {name!r} is mapped more than once", span)

    for rule in evolution.rules:
        if isinstance(rule, (RenameRule, ConvertRule)):
            source, target = rule.source.value, rule.target.value
            require_old(source, rule.source.span)
            require_new(target, rule.target.span)
            classification, reason = _conversion_classification(old[source], new[target])
            kind = "rename" if isinstance(rule, RenameRule) else "convert"
            mappings.append(EvolutionMapping(kind, (source,), (target,), (old[source],),
                                             (new[target],), classification, reason))
            used_old.add(source)
            used_new.add(target)
        elif isinstance(rule, AddRule):
            target = rule.target.value
            require_new(target, rule.target.span)
            compatible = (rule.default.type == new[target]
                          or rule.default.type == "int" and new[target] == "decimal")
            if not compatible:
                raise SemanticError(f"Default for {target!r} has type {rule.default.type}, "
                                    f"expected {new[target]}", rule.default.span)
            mappings.append(EvolutionMapping("add", (), (target,), (), (new[target],),
                                             "lossless", "new field has an explicit default",
                                             default=rule.default.value))
            used_new.add(target)
        elif isinstance(rule, DropRule):
            source = rule.source.value
            require_old(source, rule.source.span)
            mappings.append(EvolutionMapping("drop", (source,), (), (old[source],), (),
                                             "lossy", "old field is removed and cannot be reconstructed"))
            used_old.add(source)
        elif isinstance(rule, SplitRule):
            source = rule.source.value
            targets = tuple(item.value for item in rule.targets)
            require_old(source, rule.source.span)
            for item in rule.targets:
                require_new(item.value, item.span)
            if old[source] != "text" or any(new[item] != "text" for item in targets):
                raise SemanticError("split requires text source and target fields", rule.span)
            if not rule.delimiter:
                raise SemanticError("split delimiter must not be empty", rule.span)
            mappings.append(EvolutionMapping("split", (source,), targets, ("text",),
                                             ("text", "text"), "conditional",
                                             "round-trip is exact only when the delimiter is unambiguous",
                                             delimiter=rule.delimiter))
            used_old.add(source)
            used_new.update(targets)
        elif isinstance(rule, MergeRule):
            sources = tuple(item.value for item in rule.sources)
            target = rule.target.value
            for item in rule.sources:
                require_old(item.value, item.span)
            require_new(target, rule.target.span)
            if any(old[item] != "text" for item in sources) or new[target] != "text":
                raise SemanticError("merge requires text source and target fields", rule.span)
            if not rule.delimiter:
                raise SemanticError("merge delimiter must not be empty", rule.span)
            mappings.append(EvolutionMapping("merge", sources, (target,), ("text", "text"),
                                             ("text",), "conditional",
                                             "round-trip is exact only when the delimiter is unambiguous",
                                             delimiter=rule.delimiter))
            used_old.update(sources)
            used_new.add(target)

    for name in old:
        if name not in new:
            continue
        if name not in used_old and name not in used_new:
            classification, reason = _conversion_classification(old[name], new[name])
            mappings.append(EvolutionMapping("copy" if old[name] == new[name] else "convert",
                                             (name,), (name,), (old[name],), (new[name],),
                                             classification, reason))
            used_old.add(name)
            used_new.add(name)
    remaining_old = [name for name in old if name not in used_old]
    remaining_new = [name for name in new if name not in used_new]
    detections: list[str] = []
    for source in remaining_old:
        candidates = sorted(
            ((SequenceMatcher(None, source, target).ratio(), target)
             for target in remaining_new
             if _conversion_classification(old[source], new[target])[0] != "unsupported"),
            reverse=True,
        )
        if candidates and candidates[0][0] >= 0.45:
            score, target = candidates[0]
            detections.append(f"possible rename: {source} -> {target} ({score:.0%} name similarity)")
    old_text = [name for name in remaining_old if old[name] == "text"]
    new_text = [name for name in remaining_new if new[name] == "text"]
    for source in old_text:
        source_parts = set(source.split("_"))
        for first, second in combinations(new_text, 2):
            if source_parts & set(first.split("_")) and source_parts & set(second.split("_")):
                detections.append(f"possible split: {source} -> {first}, {second}")
                break
    for target in new_text:
        target_parts = set(target.split("_"))
        for first, second in combinations(old_text, 2):
            if target_parts & set(first.split("_")) and target_parts & set(second.split("_")):
                detections.append(f"possible merge: {first}, {second} -> {target}")
                break
    for name in old:
        if name in used_old:
            continue
        mappings.append(EvolutionMapping("drop", (name,), (), (old[name],), (), "lossy",
                                         "field was removed without a reverse value"))
    for name in new:
        if name in used_new:
            continue
        mappings.append(EvolutionMapping("add", (), (name,), (), (new[name],), "unsupported",
                                         "added field requires an explicit default"))

    severity = {"lossless": 0, "conditional": 1, "lossy": 2, "unsupported": 3}
    compatibility = max((mapping.classification for mapping in mappings),
                        key=severity.get, default="lossless")
    return EvolutionPlan(old_schema.name.value, new_schema.name.value,
                         tuple(old.items()), tuple(new.items()), tuple(mappings), compatibility,
                         tuple(dict.fromkeys(detections)))


def _convert(value: Any, target_type: str) -> Any:
    if value is None:
        return None
    if target_type == "text":
        return str(value)
    if target_type == "int":
        return int(Decimal(str(value)))
    if target_type == "decimal":
        return Decimal(str(value))
    if target_type == "bool":
        if isinstance(value, bool):
            return value
        if str(value).lower() in {"true", "false"}:
            return str(value).lower() == "true"
        raise ValueError(f"Cannot convert {value!r} to bool")
    raise ValueError(f"Unsupported target type {target_type!r}")


def migrate_forward(plan: EvolutionPlan, record: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for mapping in plan.mappings:
        if mapping.kind in {"copy", "rename", "convert"}:
            output[mapping.targets[0]] = _convert(record[mapping.sources[0]], mapping.target_types[0])
        elif mapping.kind == "add":
            output[mapping.targets[0]] = _convert(mapping.default, mapping.target_types[0])
        elif mapping.kind == "split":
            parts = str(record[mapping.sources[0]]).split(mapping.delimiter or "", 1)
            parts.append("")
            output[mapping.targets[0]], output[mapping.targets[1]] = parts[:2]
        elif mapping.kind == "merge":
            output[mapping.targets[0]] = (mapping.delimiter or "").join(
                str(record[name]) for name in mapping.sources)
    return {name: output.get(name) for name, _ in plan.new_fields}


def migrate_reverse(plan: EvolutionPlan, record: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for mapping in plan.mappings:
        if mapping.kind in {"copy", "rename", "convert"}:
            output[mapping.sources[0]] = _convert(record[mapping.targets[0]], mapping.source_types[0])
        elif mapping.kind == "drop":
            raise MissingInformationError(
                f"Cannot reconstruct dropped field {mapping.sources[0]!r} "
                "without retained source data")
        elif mapping.kind == "split":
            output[mapping.sources[0]] = (mapping.delimiter or "").join(
                str(record[name]) for name in mapping.targets)
        elif mapping.kind == "merge":
            parts = str(record[mapping.targets[0]]).split(mapping.delimiter or "", 1)
            parts.append("")
            output[mapping.sources[0]], output[mapping.sources[1]] = parts[:2]
    return {name: output.get(name) for name, _ in plan.old_fields}


def adapt(plan: EvolutionPlan, record: dict[str, Any], target_schema: str) -> dict[str, Any]:
    if target_schema == plan.new_schema:
        return migrate_forward(plan, record)
    if target_schema == plan.old_schema:
        return migrate_reverse(plan, record)
    raise ValueError(f"Unknown adapter target schema {target_schema!r}")


def verify_round_trip(plan: EvolutionPlan, record: dict[str, Any]) -> RoundTripReport:
    forward = migrate_forward(plan, record)
    try:
        reverse = migrate_reverse(plan, forward)
    except MissingInformationError as error:
        return RoundTripReport(False, (), forward, {}, str(error))
    fields = tuple(RoundTripField(name, record.get(name), reverse.get(name),
                                  record.get(name) == reverse.get(name))
                   for name, _ in plan.old_fields)
    return RoundTripReport(all(item.preserved for item in fields), fields, forward, reverse)


def verify_reverse_round_trip(plan: EvolutionPlan, record: dict[str, Any]) -> RoundTripReport:
    """Check new -> old -> new separately from the legacy-record direction."""
    try:
        reverse = migrate_reverse(plan, record)
    except MissingInformationError as error:
        return RoundTripReport(False, (), {}, {}, str(error))
    forward = migrate_forward(plan, reverse)
    fields = tuple(RoundTripField(name, record.get(name), forward.get(name),
                                  record.get(name) == forward.get(name))
                   for name, _ in plan.new_fields)
    return RoundTripReport(all(item.preserved for item in fields), fields, reverse, forward)


def directional_classification(mapping: EvolutionMapping) -> tuple[str, str]:
    """Classify each round trip over its whole typed input domain."""
    if mapping.classification == "unsupported":
        return "unsupported", "unsupported"
    if mapping.kind in {"copy", "rename", "convert"}:
        source_type, target_type = mapping.source_types[0], mapping.target_types[0]
        if source_type == target_type:
            return "lossless", "lossless"
        if (source_type, target_type) == ("int", "decimal"):
            return "lossless", "conditional"
        if (source_type, target_type) == ("decimal", "int"):
            return "conditional", "lossless"
        return "conditional", "conditional"
    if mapping.kind == "add":
        return "lossless", "conditional"
    if mapping.kind == "drop":
        return "lossy", "unsupported"
    if mapping.kind == "split":
        return "lossless", "conditional"
    if mapping.kind == "merge":
        return "conditional", "lossless"
    return "unsupported", "unsupported"


def plan_to_dict(plan: EvolutionPlan) -> dict[str, Any]:
    return asdict(plan)


def plan_from_dict(data: dict[str, Any]) -> EvolutionPlan:
    mappings = tuple(EvolutionMapping(
        item["kind"], tuple(item["sources"]), tuple(item["targets"]),
        tuple(item["source_types"]), tuple(item["target_types"]),
        item["classification"], item["reason"], item.get("default"), item.get("delimiter"))
        for item in data["mappings"])
    return EvolutionPlan(data["old_schema"], data["new_schema"],
                         tuple(tuple(item) for item in data["old_fields"]),
                         tuple(tuple(item) for item in data["new_fields"]),
                         mappings, data["compatibility"], tuple(data.get("detections", ())))


def format_compatibility(plan: EvolutionPlan) -> str:
    lines = [f"SCHEMA EVOLUTION: {plan.old_schema} -> {plan.new_schema}",
             f"LEGACY AGGREGATE LABEL: {plan.compatibility.upper()}",
             "Round-trip directions are classified separately below."]
    for mapping in plan.mappings:
        source = ", ".join(mapping.sources) or "<default>"
        target = ", ".join(mapping.targets) or "<removed>"
        lines.append(f"  {mapping.kind.upper():7} {source} -> {target}")
        lines.append(f"           {mapping.classification.upper()}: {mapping.reason}")
        old_trip, new_trip = directional_classification(mapping)
        lines.append(f"           round trips: old-new-old={old_trip}, "
                     f"new-old-new={new_trip}")
    if plan.detections:
        lines.append("DETECTED CANDIDATES (explicit confirmation required)")
        lines.extend(f"  - {detection}" for detection in plan.detections)
    return "\n".join(lines)


def generate_adapters(plan: EvolutionPlan, output_dir: Path) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = tuple(output_dir / name for name in (
        "forward_adapter.py", "reverse_adapter.py", "compatibility_adapter.py",
        "compatibility_report.json"))
    for path in paths:
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite {path}")
    encoded = repr(plan_to_dict(plan))
    common = ("from veriflow.evolution import plan_from_dict\n\n"
              f"PLAN = plan_from_dict({encoded})\n\n")
    paths[0].write_text(common +
                        "from veriflow.evolution import migrate_forward\n\n"
                        "def migrate(record):\n    return migrate_forward(PLAN, record)\n",
                        encoding="utf-8")
    paths[1].write_text(common +
                        "from veriflow.evolution import migrate_reverse\n\n"
                        "def migrate(record):\n    return migrate_reverse(PLAN, record)\n",
                        encoding="utf-8")
    paths[2].write_text(common +
                        "from veriflow.evolution import adapt\n\n"
                        "def translate(record, target_schema):\n"
                        "    return adapt(PLAN, record, target_schema)\n",
                        encoding="utf-8")
    report = plan_to_dict(plan)
    report["round_trips"] = [
        {"old_new_old": directional_classification(mapping)[0],
         "new_old_new": directional_classification(mapping)[1]}
        for mapping in plan.mappings
    ]
    paths[3].write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return paths
