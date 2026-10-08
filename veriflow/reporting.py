"""Execution mode that quarantines invalid rows and publishes lineage evidence."""

import csv
from dataclasses import asdict, dataclass
from decimal import Decimal
import json
import os
from pathlib import Path
import tempfile

from .ast import Emit
from .evolution import EvolutionPlan, migrate_forward
from .impact import ImpactReport, adapt_record
from .lineage import build_lineage
from .runtime import ExecutionError, _convert, _format_value, _valid
from .semantics import CheckedProgram
from .vm import compile_program, execute_expression


@dataclass(frozen=True)
class ReportResult:
    output_path: str
    rejects_path: str
    lineage_path: str
    rows_written: int
    rows_filtered: int
    rows_rejected: int
    rows_guard_rejected: int = 0


def execute_with_report(checked: CheckedProgram, source_path: Path,
                        *, evolution: EvolutionPlan | None = None,
                        impact: ImpactReport | None = None) -> ReportResult:
    pipeline = checked.program.pipeline
    emit = pipeline.statements[-1]
    assert isinstance(emit, Emit)
    if evolution is not None:
        if impact is None or impact.status not in {"preserved", "conditional"}:
            raise ExecutionError("Evolution execution requires a proved safe or guarded impact plan",
                                 pipeline.schema.span)
        if (pipeline.schema.value != evolution.old_schema
                or tuple((symbol.name, symbol.type) for symbol in checked.symbols) != evolution.old_fields):
            raise ExecutionError("Pipeline schema does not match evolution source schema",
                                 pipeline.schema.span)
    source_path = source_path.resolve()
    input_path = (source_path.parent / pipeline.input_path.value).resolve()
    output_path = (source_path.parent / emit.path.value).resolve()
    rejects_path = output_path.with_name(output_path.stem + ".rejects.csv")
    lineage_path = output_path.with_name(output_path.stem + ".lineage.json")
    targets = (output_path, rejects_path, lineage_path)
    if len(set(targets + (input_path, source_path))) != 5:
        raise ExecutionError("Output, rejects, lineage, input, and source paths must differ", emit.path.span)
    for target in targets:
        if target.exists():
            raise ExecutionError(f"Output already exists: {target}", emit.path.span)
        if not target.parent.is_dir():
            raise ExecutionError(f"Output directory does not exist: {target.parent}", emit.path.span)

    temporary: list[Path] = []
    published: list[Path] = []
    try:
        with input_path.open(encoding="utf-8-sig", newline="") as input_stream:
            reader = csv.reader(input_stream, strict=True)
            header = next(reader, None)
            if not header:
                raise ExecutionError(f"{input_path}: missing CSV header", pipeline.input_path.span)
            if len(header) != len(set(header)) or any(not name for name in header):
                raise ExecutionError(f"{input_path}: duplicate or empty header name", pipeline.input_path.span)
            indices = {name: index for index, name in enumerate(header)}
            for symbol in checked.symbols:
                if symbol.name not in indices:
                    raise ExecutionError(f"{input_path}: missing declared column {symbol.name!r}",
                                         symbol.declaration)

            streams = []
            for target in targets:
                mode = "w"
                stream = tempfile.NamedTemporaryFile(mode=mode, encoding="utf-8", newline="",
                                                     dir=target.parent, prefix=".veriflow-report-",
                                                     suffix=".tmp", delete=False)
                streams.append(stream)
                temporary.append(Path(stream.name))
            output_stream, reject_stream, lineage_stream = streams
            with output_stream, reject_stream, lineage_stream:
                output_writer = csv.writer(output_stream, lineterminator="\n")
                reject_writer = csv.writer(reject_stream, lineterminator="\n")
                columns = tuple(symbol.name for symbol in checked.selected)
                output_writer.writerow(columns)
                reject_writer.writerow([*header, "_veriflow_reason"])
                bytecode = compile_program(checked)
                written = filtered = rejected = guard_rejected = 0
                for row in reader:
                    reason = None
                    if len(row) != len(header):
                        reason = f"expected {len(header)} cells, found {len(row)}"
                    else:
                        for symbol in checked.symbols:
                            if not _valid(row[indices[symbol.name]], symbol.type):
                                reason = f"field {symbol.name!r} requires {symbol.type}"
                                break
                    if reason:
                        reject_writer.writerow([*row, f"CSV line {reader.line_num}: {reason}"])
                        rejected += 1
                        continue
                    if evolution is None:
                        values = {symbol.name: _convert(row[indices[symbol.name]], symbol.type)
                                  for symbol in checked.symbols}
                        rendered = {symbol.name: row[indices[symbol.name]]
                                    for symbol in checked.symbols}
                    else:
                        assert impact is not None
                        old_record = {}
                        for symbol in checked.symbols:
                            raw = row[indices[symbol.name]]
                            old_record[symbol.name] = (int(raw) if symbol.type == "int" else
                                                       Decimal(raw) if symbol.type == "decimal" else
                                                       raw == "true" if symbol.type == "bool" else raw)
                        rejected_guard = next((guard for guard in impact.guards
                                               if not guard.accepts(old_record)), None)
                        if rejected_guard is not None:
                            reject_writer.writerow([*row, f"CSV line {reader.line_num}: "
                                                     f"migration guard failed for {rejected_guard.field!r}"])
                            rejected += 1
                            guard_rejected += 1
                            continue
                        try:
                            migrated = migrate_forward(evolution, old_record)
                            adapted = adapt_record(evolution, migrated,
                                                   impact.required_old_fields)
                            values = {symbol.name: _convert(str(adapted[symbol.name]), symbol.type)
                                      if symbol.type in {"int", "decimal"} else adapted[symbol.name]
                                      for symbol in checked.symbols
                                      if symbol.name in adapted}
                        except (ValueError, KeyError, ArithmeticError) as error:
                            reject_writer.writerow([*row, f"CSV line {reader.line_num}: "
                                                     f"migration failed: {error}"])
                            rejected += 1
                            continue
                        rendered = {symbol.name: _format_value(values[symbol.name], symbol.type)
                                    for symbol in checked.symbols if symbol.name in values}
                    keep = True
                    for operation, compiled in zip(checked.operations, bytecode.operations, strict=True):
                        try:
                            value = execute_expression(compiled.instructions, values)
                        except (ArithmeticError, ZeroDivisionError) as error:
                            reason = f"expression failed: {error}"
                            break
                        if operation.kind == "let":
                            assert operation.symbol is not None
                            values[operation.symbol.name] = value
                            rendered[operation.symbol.name] = _format_value(value, operation.symbol.type)
                        elif operation.kind == "require" and not bool(value):
                            reason = f"requirement failed: {operation.message}"
                            break
                        elif operation.kind == "keep" and not bool(value):
                            keep = False
                            filtered += 1
                            break
                    if reason:
                        reject_writer.writerow([*row, f"CSV line {reader.line_num}: {reason}"])
                        rejected += 1
                    elif keep:
                        output_writer.writerow([rendered[name] for name in columns])
                        written += 1
                lineage = asdict(build_lineage(checked))
                if evolution is not None:
                    assert impact is not None
                    lineage["schema_evolution"] = {
                        "old_schema": evolution.old_schema,
                        "new_schema": evolution.new_schema,
                        "impact_status": impact.status,
                        "findings": [asdict(finding) for finding in impact.findings],
                        "guards": [asdict(guard) for guard in impact.guards],
                    }
                json.dump(lineage, lineage_stream, indent=2)
                lineage_stream.write("\n")

        for temporary_path, target in zip(temporary, targets, strict=True):
            os.link(temporary_path, target)
            published.append(target)
        return ReportResult(str(output_path), str(rejects_path), str(lineage_path),
                            written, filtered, rejected, guard_rejected)
    except (OSError, UnicodeError, csv.Error) as error:
        for target in published:
            target.unlink(missing_ok=True)
        raise ExecutionError(str(error), emit.path.span) from error
    finally:
        for temporary_path in temporary:
            temporary_path.unlink(missing_ok=True)
