"""Compare full old and guarded CSV runs on rows admitted by proved guards."""

import csv
from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path
import tempfile

from veriflow.evolution import compile_evolution
from veriflow.evolution_parser import parse_evolution
from veriflow.impact import analyze_impact
from veriflow.parser import parse
from veriflow.reporting import execute_with_report
from veriflow.semantics import analyze

from .negative_controls import CASES


ROOT = Path(__file__).resolve().parent
CONTROL_ROWS = (
    ("Ada", "-1", "x"),
    ("Ada", "-0.7", "x"),
    ("Ada", "0", "x"),
    ("Ada", "0.7", "x"),
    ("Ada", "39.9", "x"),
    ("Ada", "40", "x"),
    ("Ada", "40.7", "x"),
    ("Ada", "41", "x"),
    ("Ada", "41.7", "x"),
)


def run_once(source: str, rows: list[tuple[str, str, str]],
             evolution=None, impact=None) -> tuple[list[list[str]], list[list[str]], dict]:
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)
        source_path = directory / "pipeline.vfl"
        source_path.write_text(source, encoding="utf-8")
        with (directory / "input.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("name", "score", "legacy"))
            writer.writerows(rows)
        checked = analyze(parse(source))
        result = execute_with_report(checked, source_path,
                                     evolution=evolution, impact=impact)
        with (directory / "output.csv").open(encoding="utf-8", newline="") as stream:
            output = list(csv.reader(stream))
        with (directory / "output.rejects.csv").open(encoding="utf-8", newline="") as stream:
            rejects = list(csv.reader(stream))
        return output, rejects, asdict(result)


def main() -> None:
    results = []
    for case in CASES:
        if case["name"] not in {"require_strict", "derived_require", "executed_division"}:
            continue
        checked = analyze(parse(case["source"]))
        evolution = compile_evolution(parse_evolution(case["evolution"]))
        impact = analyze_impact(checked, evolution)
        if impact.status not in {"preserved", "conditional"}:
            raise AssertionError(f"{case['name']}: expected proved plan")
        admitted = [row for row in CONTROL_ROWS if all(
            guard.accepts({"score": Decimal(row[1])}) for guard in impact.guards)]
        old_output, old_rejects, old_summary = run_once(case["source"], admitted)
        new_output, new_rejects, new_summary = run_once(
            case["source"], admitted, evolution, impact)
        if old_output != new_output or old_rejects != new_rejects:
            raise AssertionError(f"{case['name']}: admitted CSV outcomes differ")
        if (old_summary["rows_written"], old_summary["rows_filtered"],
                old_summary["rows_rejected"]) != (
                new_summary["rows_written"], new_summary["rows_filtered"],
                new_summary["rows_rejected"]):
            raise AssertionError(f"{case['name']}: admitted row counts differ")
        results.append({"name": case["name"], "status": impact.status,
                        "total_candidates": len(CONTROL_ROWS),
                        "admitted": len(admitted),
                        "emitted": old_summary["rows_written"],
                        "filtered": old_summary["rows_filtered"],
                        "rejected": old_summary["rows_rejected"],
                        "output_equal": True, "rejects_equal": True})

    # The real-data preserved case processes every Iris row with no guard.
    source = (ROOT / "cases" / "iris.safe.vfl").read_text(encoding="utf-8")
    evolution_text = (ROOT / "cases" / "iris.evolution.vfl").read_text(encoding="utf-8")
    checked = analyze(parse(source))
    evolution = compile_evolution(parse_evolution(evolution_text))
    impact = analyze_impact(checked, evolution)
    if impact.status != "preserved":
        raise AssertionError("iris.safe: expected preserved")
    with (ROOT / "data" / "iris.csv").open(encoding="utf-8", newline="") as stream:
        source_rows = list(csv.DictReader(stream))
    # The helper expects the common three-column header used by controls, so
    # run this real-data case in its own temporary directories.
    def run_iris(evolved: bool) -> tuple[list[list[str]], list[list[str]], dict]:
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            source_path = directory / "pipeline.vfl"
            source_path.write_text(source, encoding="utf-8")
            with (directory / "input.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream,
                                        fieldnames=("sepal_length", "petal_width", "species"),
                                        lineterminator="\n")
                writer.writeheader()
                writer.writerows(source_rows)
            result = execute_with_report(checked, source_path,
                                         evolution=evolution if evolved else None,
                                         impact=impact if evolved else None)
            with (directory / "output.csv").open(encoding="utf-8", newline="") as stream:
                output = list(csv.reader(stream))
            with (directory / "output.rejects.csv").open(encoding="utf-8", newline="") as stream:
                rejects = list(csv.reader(stream))
            return output, rejects, asdict(result)
    old_output, old_rejects, old_summary = run_iris(False)
    new_output, new_rejects, new_summary = run_iris(True)
    if old_output != new_output or old_rejects != new_rejects:
        raise AssertionError("iris.safe: full CSV outcomes differ")
    results.append({"name": "iris.safe", "status": "preserved",
                    "total_candidates": len(source_rows), "admitted": len(source_rows),
                    "emitted": old_summary["rows_written"],
                    "filtered": old_summary["rows_filtered"],
                    "rejected": old_summary["rows_rejected"],
                    "output_equal": True, "rejects_equal": True})
    output = ROOT / "csv-parity.json"
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"{len(results)} CSV parity cases passed; wrote {output}")


if __name__ == "__main__":
    main()
