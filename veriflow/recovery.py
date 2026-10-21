"""Retain only observable old values needed to replay a migrated row.

The plan is for well-typed old rows and total forward mappings only. A sidecar
entry is keyed by the caller's row identity; keeping that association is the
caller's responsibility.
"""

from dataclasses import dataclass
from typing import Any

from .evolution import EvolutionPlan, _convert, migrate_forward
from .impact import Guard, adapt_record, analyze_impact
from .semantics import CheckedProgram


@dataclass(frozen=True)
class RecoveryRule:
    fields: tuple[str, ...]
    guards: tuple[Guard, ...] = ()


@dataclass(frozen=True)
class RecoveryPlan:
    required_old_fields: tuple[str, ...]
    rules: tuple[RecoveryRule, ...]


@dataclass(frozen=True)
class RecoveredRow:
    migrated: dict[str, Any]
    retained: dict[str, Any]
    reconstructed: dict[str, Any]


def plan_recovery(checked: CheckedProgram, evolution: EvolutionPlan) -> RecoveryPlan:
    """Find observable source cells to retain when an existing proof guard fails."""
    impact = analyze_impact(checked, evolution)
    required = set(impact.required_old_fields)
    rules: list[RecoveryRule] = []
    for mapping, finding in zip(evolution.mappings, impact.findings, strict=True):
        if mapping.classification == "unsupported":
            raise ValueError("Recovery requires a defined forward mapping")
        used = tuple(field for field in mapping.sources if field in required)
        if not used or finding.status == "preserved":
            continue
        if mapping.kind == "drop":
            rules.append(RecoveryRule(used))
        elif finding.status == "conditional":
            guards = tuple(guard for guard in impact.guards
                           if guard.field in mapping.sources)
            if not guards:
                raise ValueError("Conditional mapping has no recovery guard")
            rules.append(RecoveryRule(used, guards))
        else:
            raise ValueError(f"No recovery rule for {mapping.kind} mapping")
    return RecoveryPlan(impact.required_old_fields, tuple(rules))


def reconstruct_with_sidecar(evolution: EvolutionPlan, migrated: dict[str, Any],
                             recovery: RecoveryPlan,
                             retained: dict[str, Any]) -> dict[str, Any]:
    """Replay a migrated row using its saved observable source cells."""
    field_types = dict(evolution.old_fields)
    if not set(retained) <= set(recovery.required_old_fields):
        raise ValueError("Sidecar contains an unobserved old field")
    remaining = tuple(field for field in recovery.required_old_fields
                      if field not in retained)
    reconstructed = adapt_record(evolution, migrated, remaining)
    reconstructed.update({field: _convert(value, field_types[field])
                          for field, value in retained.items()})
    return reconstructed


def recover_row(evolution: EvolutionPlan, recovery: RecoveryPlan,
                old_record: dict[str, Any]) -> RecoveredRow:
    """Migrate one old row and produce its sparse observation sidecar."""
    retained: dict[str, Any] = {}
    for rule in recovery.rules:
        if not rule.guards or not all(guard.accepts(old_record) for guard in rule.guards):
            retained.update({field: old_record[field] for field in rule.fields})
    migrated = migrate_forward(evolution, old_record)
    reconstructed = reconstruct_with_sidecar(evolution, migrated, recovery, retained)
    return RecoveredRow(migrated, retained, reconstructed)
