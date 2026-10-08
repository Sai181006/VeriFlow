"""Read-only migration-time guard coverage on an old-schema CSV."""

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .impact import ImpactReport
from .runtime import _valid
from .semantics import CheckedProgram


@dataclass(frozen=True)
class ReadinessReport:
    input_path: str
    rows_seen: int
    rows_well_typed: int
    rows_invalid: int
    rows_admitted: int | None
    rows_guard_rejected: int | None
    admitted_percent: float | None


def inspect_readiness(checked: CheckedProgram, impact: ImpactReport,
                      input_path: Path) -> ReadinessReport:
    """Count guard coverage without migrating rows or writing output files.

    The denominator is well-typed old-schema rows. Unknown/breaking plans have
    no admission claim, even when they contain an empty guard list.
    """
    if impact.status not in {"preserved", "conditional", "unknown", "breaking"}:
        raise ValueError(f"Unrecognized impact status {impact.status!r}")
    seen = valid = invalid = admitted = rejected = 0
    try:
        with input_path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            header = next(reader, None)
            if not header:
                raise ValueError("missing CSV header")
            if len(header) != len(set(header)) or any(not name for name in header):
                raise ValueError("duplicate or empty CSV header name")
            indices = {name: index for index, name in enumerate(header)}
            missing = [symbol.name for symbol in checked.symbols if symbol.name not in indices]
            if missing:
                raise ValueError(f"missing declared CSV columns: {', '.join(missing)}")
            for row in reader:
                seen += 1
                if (len(row) != len(header)
                        or any(not _valid(row[indices[symbol.name]], symbol.type)
                               for symbol in checked.symbols)):
                    invalid += 1
                    continue
                valid += 1
                if impact.status not in {"preserved", "conditional"}:
                    continue
                guard_record = {guard.field: Decimal(row[indices[guard.field]])
                                for guard in impact.guards}
                if all(guard.accepts(guard_record) for guard in impact.guards):
                    admitted += 1
                else:
                    rejected += 1
    except csv.Error as error:
        raise ValueError(f"invalid CSV: {error}") from error
    proved = impact.status in {"preserved", "conditional"}
    return ReadinessReport(
        str(input_path.resolve()), seen, valid, invalid,
        admitted if proved else None,
        rejected if proved else None,
        round(100 * admitted / valid, 2) if proved and valid else None,
    )


def format_readiness(report: ReadinessReport) -> str:
    lines = [f"READINESS INPUT: {report.input_path}",
             f"  rows seen={report.rows_seen}, well-typed={report.rows_well_typed}, "
             f"invalid={report.rows_invalid}"]
    if report.rows_admitted is None:
        lines.append("  guard coverage: unavailable (no proved admission rule)")
    else:
        percent = (f"{report.admitted_percent:.2f}%" if report.admitted_percent is not None
                   else "n/a (no well-typed rows)")
        lines.append(f"  guard admitted={report.rows_admitted}, "
                     f"guard rejected={report.rows_guard_rejected}, "
                     f"admitted among well-typed={percent}")
        lines.append("  measured coverage on this file; not a preservation proof")
    return "\n".join(lines)
