"""Reproduce bounded pipeline-impact cases on three public UCI datasets.

Run from the repository root with ``python -m evaluation.run_study --fetch`` once,
then ``python -m evaluation.run_study`` offline. Schema changes in this study are
injected examples, not historical changes to the UCI datasets.
"""

import argparse
import csv
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import platform
import shutil
import statistics
import tempfile
from time import perf_counter_ns
from urllib.request import urlopen

from veriflow.evolution import compile_evolution, migrate_forward
from veriflow.evolution_parser import parse_evolution
from veriflow.impact import analyze_impact, observe, observe_adapted
from veriflow.parser import parse
from veriflow.reporting import execute_with_report
from veriflow.semantics import analyze


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CASES = ROOT / "cases"
SOURCES = {
    "abalone": "https://archive.ics.uci.edu/ml/machine-learning-databases/abalone/abalone.data",
    "iris": "https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data",
    "wine_red": "https://archive.ics.uci.edu/ml/machine-learning-databases/wine-quality/winequality-red.csv",
}
RAW_SHA256 = {
    "abalone": "de37cdcdcaaa50c309d514f248f7c2302a5f1f88c168905eba23fe2fbc78449f",
    "iris": "6f608b71a7317216319b4d27b4d9bc84e6abd734eda7872b71a458569e2656c0",
    "wine_red": "4a402cf041b025d4566d954c3b9ba8635a3a8a01e039005d97d6a710278cf05e",
}
CASE_NAMES = {
    "abalone": ("safe", "strict", "selected"),
    "iris": ("safe", "strict", "selected", "split"),
    "wine_red": ("safe", "strict", "selected"),
}


def prepare(name: str, fetch: bool) -> tuple[Path, str]:
    DATA.mkdir(exist_ok=True)
    raw_path = DATA / (name + ".raw")
    prepared_path = DATA / (name + ".csv")
    if fetch:
        with urlopen(SOURCES[name], timeout=30) as response:
            raw_path.write_bytes(response.read())
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing {raw_path}; run with --fetch once")
    raw = raw_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != RAW_SHA256[name]:
        raise ValueError(f"Downloaded {name} SHA-256 changed: {digest}")
    lines = raw.decode("utf-8-sig").splitlines()
    if name == "abalone":
        records = [row for row in csv.reader(lines) if len(row) == 9]
        header = ("whole_weight", "rings", "sex")
        selected = [(row[4], row[8], row[0]) for row in records]
    elif name == "iris":
        records = [row for row in csv.reader(lines) if len(row) == 5]
        header = ("sepal_length", "petal_width", "species")
        selected = [(row[0], row[3], row[4]) for row in records]
    else:
        records = list(csv.DictReader(lines, delimiter=";"))
        header = ("alcohol", "quality", "residual_sugar")
        selected = [(row["alcohol"], row["quality"], row["residual sugar"])
                    for row in records]
    expected_first = {
        "abalone": ("0.514", "15", "M"),
        "iris": ("5.1", "0.2", "Iris-setosa"),
        "wine_red": ("9.4", "5", "1.9"),
    }
    if not selected or selected[0] != expected_first[name]:
        raise ValueError(f"{name}: projected columns do not match expected source order")
    with prepared_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(selected)
    return prepared_path, digest


def typed_rows(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if path.stem == "abalone":
        return [{"whole_weight": Decimal(row["whole_weight"]),
                 "rings": int(row["rings"]), "sex": row["sex"]} for row in rows]
    if path.stem == "iris":
        return [{"sepal_length": Decimal(row["sepal_length"]),
                 "petal_width": Decimal(row["petal_width"]),
                 "species": row["species"]} for row in rows]
    return [{"alcohol": Decimal(row["alcohol"]),
             "quality": int(row["quality"]),
             "residual_sugar": Decimal(row["residual_sugar"])} for row in rows]


def runtime_ms(source: str, data: Path, evolution=None, impact=None,
               repetitions: int = 5) -> tuple[float, dict[str, int]]:
    measurements = []
    counts = {}
    for _ in range(repetitions):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            shutil.copyfile(data, directory / "input.csv")
            source_path = directory / "pipeline.vfl"
            source_path.write_text(source, encoding="utf-8")
            checked = analyze(parse(source))
            start = perf_counter_ns()
            result = execute_with_report(checked, source_path,
                                         evolution=evolution, impact=impact)
            measurements.append((perf_counter_ns() - start) / 1_000_000)
            counts = {"written": result.rows_written,
                      "filtered": result.rows_filtered,
                      "rejected": result.rows_rejected,
                      "guard_rejected": result.rows_guard_rejected}
    return round(statistics.median(measurements), 3), counts


def evaluate(name: str, case: str, data: Path) -> dict[str, object]:
    source = (CASES / f"{name}.{case}.vfl").read_text(encoding="utf-8")
    evolution_text = (CASES / f"{name}.{'split_evolution' if case == 'split' else 'evolution'}.vfl")
    plan = compile_evolution(parse_evolution(evolution_text.read_text(encoding="utf-8")))
    compile_times = []
    impact_times = []
    for _ in range(5):
        start = perf_counter_ns()
        checked = analyze(parse(source))
        compile_times.append((perf_counter_ns() - start) / 1_000_000)
        start = perf_counter_ns()
        report = analyze_impact(checked, plan)
        impact_times.append((perf_counter_ns() - start) / 1_000_000)
    rows = typed_rows(data)
    different = 0
    guarded_violations = 0
    guard_pass = guard_reject = 0
    first_ten_different = 0
    for index, old in enumerate(rows):
        admitted = all(guard.accepts(old) for guard in report.guards)
        if admitted:
            guard_pass += 1
        else:
            guard_reject += 1
        migrated = migrate_forward(plan, old)
        before = observe(checked, old)
        try:
            after = observe_adapted(checked, plan, migrated,
                                    report.required_old_fields)
        except (ValueError, KeyError):
            # A structural mapping may be explicitly outside the proved fragment.
            continue
        if before != after:
            different += 1
            if admitted and report.status in {"preserved", "conditional"}:
                guarded_violations += 1
            if index < 10:
                first_ten_different += 1
    if guarded_violations:
        raise AssertionError(f"{name}/{case}: {guarded_violations} guarded preservation failures")
    changed_sources = {field for mapping in plan.mappings
                       if mapping.classification != "lossless"
                       for field in mapping.sources}
    lineage_only = ("preserved" if not changed_sources.intersection(
        report.required_old_fields) else "unknown")
    witness_validated = False
    if report.divergence is not None:
        witness = report.divergence
        witness_validated = (
            migrate_forward(plan, witness.old_record) == witness.new_record
            and observe(checked, witness.old_record) == witness.old_observation
            and observe_adapted(checked, plan, witness.new_record,
                                report.required_old_fields) == witness.adapted_observation
            and witness.old_observation != witness.adapted_observation)
    elif report.collision is not None:
        witness = report.collision
        witness_validated = (
            migrate_forward(plan, witness.first_record) == witness.migrated_record
            and migrate_forward(plan, witness.second_record) == witness.migrated_record
            and observe(checked, witness.first_record) == witness.first_observation
            and observe(checked, witness.second_record) == witness.second_observation
            and witness.first_observation != witness.second_observation)
    if (report.divergence is not None or report.collision is not None) and not witness_validated:
        raise AssertionError(f"{name}/{case}: invalid replayed witness")
    old_ms, old_counts = runtime_ms(source, data)
    evolved_ms = evolved_counts = None
    if report.status in {"preserved", "conditional"}:
        evolved_ms, evolved_counts = runtime_ms(source, data, plan, report)
    return {
        "dataset": name, "case": case, "rows": len(rows),
        "schema_label": plan.compatibility,
        "lineage_only": lineage_only,
        "sample_first_10": "divergence" if first_ten_different else "none_observed",
        "impact_status": report.status,
        "rules": [finding.rule_id for finding in report.findings],
        "guards": [asdict(guard) for guard in report.guards],
        "witness_validated": witness_validated,
        "observed_differences": different,
        "guard_pass": guard_pass if report.status != "unknown" else None,
        "guard_reject": guard_reject if report.status != "unknown" else None,
        "guarded_violations": guarded_violations if report.status != "unknown" else None,
        "compile_median_ms": round(statistics.median(compile_times), 3),
        "impact_median_ms": round(statistics.median(impact_times), 3),
        "old_runtime_median_ms": old_ms,
        "evolved_runtime_median_ms": evolved_ms,
        "old_counts": old_counts,
        "evolved_counts": evolved_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="Download public UCI files")
    args = parser.parse_args()
    datasets = {}
    results = []
    for name, cases in CASE_NAMES.items():
        data, digest = prepare(name, args.fetch)
        datasets[name] = {"source": SOURCES[name], "raw_sha256": digest,
                          "prepared_sha256": hashlib.sha256(data.read_bytes()).hexdigest()}
        for case in cases:
            results.append(evaluate(name, case, data))
    document = {"python": platform.python_version(), "platform": platform.platform(),
                "repetitions": 5, "datasets": datasets, "cases": results}
    output = ROOT / "results.json"
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    for item in results:
        print(item["dataset"], item["case"], item["impact_status"],
              f"differences={item['observed_differences']}")


if __name__ == "__main__":
    main()
