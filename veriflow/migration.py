"""Integrated old-row migration, sparse retention, and disk-based replay."""

import csv
from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from time import perf_counter
from uuid import uuid4

from .evolution import EvolutionPlan, migrate_forward
from .evolved import (EvolvedProgram, compile_evolved_pipeline, execute_evolved,
                      load_evolved_pipeline)
from .impact import Observation, analyze_impact, observe
from .recovery import plan_recovery
from .runtime import _valid
from .semantics import CheckedProgram


@dataclass(frozen=True)
class MigrationResult:
    bundle: str
    strategy: str
    input_rows: int
    admitted: int
    recovered: int
    rejected: int
    retained_cells: int
    observation_mismatches: int
    migrated_bytes: int
    sidecar_bytes: int
    ledger_bytes: int
    elapsed_ms: float


def _cell(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _old_value(raw: str, kind: str) -> object:
    if kind == "int":
        return int(raw)
    if kind == "decimal":
        return Decimal(raw)
    if kind == "bool":
        return raw == "true"
    return raw


def _digest(row_id: str, cells: list[str]) -> str:
    payload = json.dumps([row_id, *cells], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _program_digest(program: EvolvedProgram) -> str:
    return _json_digest(asdict(program))


def _observation_json(observation: Observation) -> dict[str, object]:
    return {"outcome": observation.outcome, "message": observation.message,
            "values": [_cell(value) for value in observation.values]}


def replay_migration(bundle: Path, program: EvolvedProgram | None = None) -> list[Observation]:
    """Verify ID/row associations and execute the compiled new-schema plan."""
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    persisted = load_evolved_pipeline(bundle / "program.json")
    if manifest.get("program_sha256") != _program_digest(persisted):
        raise ValueError("Persisted evolved program differs from manifest")
    if program is None:
        program = persisted
    if manifest.get("program_sha256") != _program_digest(program):
        raise ValueError("Bundle was compiled for a different evolved pipeline")
    fields = [name for name, _ in program.new_fields]
    ledger = [json.loads(line) for line in (bundle / "ledger.jsonl").read_text(
        encoding="utf-8").splitlines()]
    sidecar = {}
    for line in (bundle / "sidecar.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["id"] in sidecar:
            raise ValueError("Duplicate sidecar row ID")
        sidecar[entry["id"]] = entry
    results: list[Observation] = []
    seen: set[str] = set()
    recovered_ids: set[str] = set()
    with (bundle / "migrated.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        if next(reader, None) != ["_veriflow_id", *fields]:
            raise ValueError("Migrated CSV does not match compiled new schema")
        for row, entry in zip(reader, ledger, strict=True):
            if len(row) != len(fields) + 1:
                raise ValueError("Migrated row has wrong column count")
            row_id, *cells = row
            if not row_id or row_id in seen or entry["id"] != row_id:
                raise ValueError("Missing, duplicate, or mismatched row ID")
            seen.add(row_id)
            digest = _digest(row_id, cells)
            if entry["row_sha256"] != digest:
                raise ValueError("Migrated row differs from ledger")
            mode = entry["mode"]
            if mode not in {"admitted", "recovered"}:
                raise ValueError("Invalid migration mode")
            saved = sidecar.get(row_id)
            if mode == "recovered" and (saved is None or saved["row_sha256"] != digest):
                raise ValueError("Recovered row lacks its paired sidecar")
            if mode == "recovered":
                if entry.get("sidecar_sha256") != _json_digest(saved["fields"]):
                    raise ValueError("Recovered sidecar differs from ledger")
                recovered_ids.add(row_id)
            if mode == "admitted" and saved is not None:
                raise ValueError("Admitted row unexpectedly has a sidecar")
            if mode == "admitted" and entry.get("sidecar_sha256") is not None:
                raise ValueError("Admitted row has an unexpected sidecar digest")
            values = {name: _old_value(cell, kind)
                      for (name, kind), cell in zip(program.new_fields, cells, strict=True)}
            result = execute_evolved(program, values,
                                     retained=saved["fields"] if saved else {},
                                     admitted=mode == "admitted")
            results.append(result)
    if recovered_ids != set(sidecar):
        raise ValueError("Orphan sidecar row ID")
    return results


def run_migration(checked: CheckedProgram, evolution: EvolutionPlan,
                  source_path: Path, bundle: Path, *,
                  input_path: Path | None = None,
                  strategy: str = "sparse") -> MigrationResult:
    """Create a bundle, replay it from disk, and publish only on success."""
    if strategy not in {"sparse", "guard-only", "full-row"}:
        raise ValueError("Unknown retention strategy")
    if any(mapping.classification == "unsupported" for mapping in evolution.mappings):
        raise ValueError("Migration requires defined forward mappings")
    if "_veriflow_id" in dict(evolution.old_fields) or "_veriflow_id" in dict(evolution.new_fields):
        raise ValueError("_veriflow_id is reserved for migration row identity")
    impact = analyze_impact(checked, evolution)
    compiled = compile_evolved_pipeline(checked, evolution, impact)
    recovery = plan_recovery(checked, evolution) if strategy == "sparse" else None
    source_path = source_path.resolve()
    input_path = ((source_path.parent / checked.program.pipeline.input_path.value)
                  if input_path is None else input_path).resolve()
    bundle = bundle.resolve()
    if bundle.exists() or not bundle.parent.is_dir():
        raise ValueError("Bundle must be a new directory in an existing parent")
    if input_path == source_path or bundle == input_path or bundle == source_path:
        raise ValueError("Source, input, and bundle paths must differ")
    start = perf_counter()
    temporary = Path(tempfile.mkdtemp(prefix=".veriflow-migration-", dir=bundle.parent))
    old_observations: list[Observation] = []
    admitted = recovered = rejected = retained_cells = total = 0
    try:
        (temporary / "program.json").write_text(json.dumps(asdict(compiled), indent=2) + "\n",
                                                  encoding="utf-8")
        (temporary / "manifest.json").write_text(json.dumps({
            "format_version": 1, "program_sha256": _program_digest(compiled),
            "strategy": strategy,
        }, indent=2) + "\n", encoding="utf-8")
        with input_path.open(encoding="utf-8-sig", newline="") as input_stream, (
                temporary / "migrated.csv").open("w", encoding="utf-8", newline="") as migrated_stream, (
                temporary / "sidecar.jsonl").open("w", encoding="utf-8") as sidecar_stream, (
                temporary / "ledger.jsonl").open("w", encoding="utf-8") as ledger_stream, (
                temporary / "rejects.csv").open("w", encoding="utf-8", newline="") as reject_stream:
            reader = csv.reader(input_stream, strict=True)
            header = next(reader, None)
            if not header or len(header) != len(set(header)) or any(not name for name in header):
                raise ValueError("Old CSV has a missing, empty, or duplicate header")
            indices = {name: index for index, name in enumerate(header)}
            if set(dict(evolution.old_fields)) - set(indices):
                raise ValueError("Old CSV is missing declared schema columns")
            migrated_writer = csv.writer(migrated_stream, lineterminator="\n")
            reject_writer = csv.writer(reject_stream, lineterminator="\n")
            fields = [name for name, _ in evolution.new_fields]
            migrated_writer.writerow(["_veriflow_id", *fields])
            reject_writer.writerow(["_veriflow_id", "raw_cells_json", "_veriflow_reason"])
            for cells in reader:
                total += 1
                row_id = uuid4().hex
                reason = None
                if len(cells) != len(header):
                    reason = f"expected {len(header)} cells, found {len(cells)}"
                else:
                    for name, kind in evolution.old_fields:
                        if not _valid(cells[indices[name]], kind):
                            reason = f"field {name!r} requires {kind}"
                            break
                if reason is not None:
                    reject_writer.writerow([row_id, json.dumps(cells, ensure_ascii=False), reason])
                    rejected += 1
                    continue
                try:
                    old = {name: _old_value(cells[indices[name]], kind)
                           for name, kind in evolution.old_fields}
                except (ValueError, ArithmeticError) as error:
                    reject_writer.writerow([row_id, json.dumps(cells, ensure_ascii=False),
                                            f"field conversion failed: {error}"])
                    rejected += 1
                    continue
                guard_pass = all(guard.accepts(old) for guard in impact.guards)
                observed_drop = any(binding.recovery_required for binding in compiled.bindings)
                if strategy == "guard-only" and (not guard_pass or observed_drop
                                                  or impact.status not in {"preserved", "conditional"}):
                    reject_writer.writerow([row_id, json.dumps(cells, ensure_ascii=False),
                                            "migration proof guard failed"])
                    rejected += 1
                    continue
                retained: dict[str, object] = {}
                if strategy == "full-row":
                    retained = dict(old)
                elif strategy == "sparse" and (not guard_pass or observed_drop):
                    assert recovery is not None
                    for rule in recovery.rules:
                        if not rule.guards or not all(guard.accepts(old) for guard in rule.guards):
                            retained.update({name: old[name] for name in rule.fields})
                mode = "recovered" if retained or strategy == "full-row" else "admitted"
                try:
                    migrated = migrate_forward(evolution, old)
                    new_cells = [_cell(migrated[name]) for name in fields]
                    # Check the generated program before publishing the row.
                    execute_evolved(compiled, migrated, retained=retained,
                                    admitted=mode == "admitted")
                except (ValueError, KeyError, ArithmeticError) as error:
                    reject_writer.writerow([row_id, json.dumps(cells, ensure_ascii=False),
                                            f"migration failed: {error}"])
                    rejected += 1
                    continue
                digest = _digest(row_id, new_cells)
                migrated_writer.writerow([row_id, *new_cells])
                serialized_retained = {name: _cell(value) for name, value in retained.items()}
                ledger_stream.write(json.dumps({"id": row_id, "mode": mode,
                                                "row_sha256": digest,
                                                "sidecar_sha256": _json_digest(serialized_retained)
                                                if mode == "recovered" else None}) + "\n")
                if mode == "recovered":
                    sidecar_stream.write(json.dumps({"id": row_id, "row_sha256": digest,
                                                     "fields": serialized_retained},
                                                    ensure_ascii=False) + "\n")
                    recovered += 1
                    retained_cells += len(retained)
                else:
                    admitted += 1
                old_observations.append(observe(checked, old))
        replayed = replay_migration(temporary)
        mismatches = sum(left != right for left, right in zip(old_observations, replayed, strict=True))
        if mismatches:
            raise ValueError(f"Migration replay changed {mismatches} old observations")
        with (temporary / "replay.jsonl").open("w", encoding="utf-8") as stream:
            with (temporary / "migrated.csv").open(encoding="utf-8", newline="") as migrated_stream:
                reader = csv.reader(migrated_stream)
                next(reader)
                for row, observation in zip(reader, replayed, strict=True):
                    stream.write(json.dumps({"id": row[0], **_observation_json(observation)}) + "\n")
        result = MigrationResult(str(bundle), strategy, total, admitted, recovered, rejected,
                                 retained_cells, mismatches,
                                 (temporary / "migrated.csv").stat().st_size,
                                 (temporary / "sidecar.jsonl").stat().st_size,
                                 (temporary / "ledger.jsonl").stat().st_size,
                                 round((perf_counter() - start) * 1000, 3))
        (temporary / "summary.json").write_text(json.dumps(asdict(result), indent=2) + "\n",
                                                  encoding="utf-8")
        os.rename(temporary, bundle)
        return result
    finally:
        if temporary.exists():
            if temporary.resolve().parent != bundle.parent.resolve() or not temporary.name.startswith(
                    ".veriflow-migration-"):
                raise RuntimeError("Refusing to remove an unexpected temporary directory")
            shutil.rmtree(temporary)
