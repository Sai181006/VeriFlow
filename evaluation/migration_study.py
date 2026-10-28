"""Compare sparse migration, guard-only admission, and full-row retention."""

from dataclasses import asdict
import csv
import hashlib
import json
from pathlib import Path
import platform
import statistics
from tempfile import TemporaryDirectory

from veriflow.evolution import compile_evolution
from veriflow.evolution_parser import parse_evolution
from veriflow.migration import run_migration
from veriflow.parser import parse
from veriflow.semantics import analyze

from .run_study import CASE_NAMES, CASES, DATA, ROOT
from .real_history.prepare_moh_icu import verify as verify_moh_history


HISTORY = ROOT / "real_history"
CONTROLS = ROOT / "controls"
STRATEGIES = ("sparse", "guard-only", "full-row")


def compare_actual_after(bundle: Path, actual_after_path: Path) -> dict[str, int]:
    with actual_after_path.open(encoding="utf-8", newline="") as stream:
        expected = {(row["date"], row["state"]): row for row in csv.DictReader(stream)}
    mismatches = checked = 0
    with (bundle / "migrated.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            row.pop("_veriflow_id")
            actual = expected.get((row["date"], row["state"]))
            checked += 1
            mismatches += actual != row
    return {"actual_after_rows_checked": checked,
            "actual_after_mismatches": mismatches}


def evaluate_case(label: str, source_path: Path, evolution_path: Path,
                  input_path: Path, repetitions: int = 3,
                  actual_after_path: Path | None = None) -> dict:
    checked = analyze(parse(source_path.read_text(encoding="utf-8")))
    evolution = compile_evolution(parse_evolution(
        evolution_path.read_text(encoding="utf-8")))
    outputs = {}
    for strategy in STRATEGIES:
        samples = []
        for _ in range(repetitions):
            with TemporaryDirectory(dir=ROOT) as directory:
                result = run_migration(checked, evolution, source_path,
                                       Path(directory) / "bundle", input_path=input_path,
                                       strategy=strategy)
                bundle = Path(result.bundle)
                entry = asdict(result)
                entry.pop("bundle")
                entry["bundle_bytes"] = sum(path.stat().st_size for path in bundle.iterdir())
                if actual_after_path is not None:
                    entry.update(compare_actual_after(bundle, actual_after_path))
                samples.append(entry)
        metrics = {key: value for key, value in samples[0].items()
                   if key not in {"elapsed_ms", "bundle_bytes"}}
        if any({key: value for key, value in sample.items()
                if key not in {"elapsed_ms", "bundle_bytes"}} != metrics
               for sample in samples):
            raise AssertionError(f"{label}/{strategy}: nondeterministic counts or byte lengths")
        if metrics["observation_mismatches"]:
            raise AssertionError(f"{label}/{strategy}: replay observation mismatch")
        if metrics.get("actual_after_mismatches"):
            raise AssertionError(f"{label}/{strategy}: actual post-change snapshot mismatch")
        outputs[strategy] = {**metrics,
                             "elapsed_median_ms": round(statistics.median(
                                 sample["elapsed_ms"] for sample in samples), 3),
                             "bundle_median_bytes": int(statistics.median(
                                 sample["bundle_bytes"] for sample in samples))}
    return {"case": label, "source_rows_sha256": hashlib.sha256(
        input_path.read_bytes()).hexdigest(), "strategies": outputs}


def main() -> None:
    history_counts = verify_moh_history()
    cases = []
    for dataset, names in CASE_NAMES.items():
        for case in names:
            source = CASES / f"{dataset}.{case}.vfl"
            evolution = CASES / f"{dataset}.{'split_evolution' if case == 'split' else 'evolution'}.vfl"
            cases.append(evaluate_case(f"{dataset}.{case}", source, evolution,
                                       DATA / f"{dataset}.csv"))
    cases.append(evaluate_case("nyc311.documented_addition",
                               HISTORY / "nyc311_pipeline.vfl",
                               HISTORY / "nyc311_evolution.vfl",
                               HISTORY / "nyc311_2016_sample.csv"))
    cases.append(evaluate_case("control.observed_drop",
                               CONTROLS / "observed_drop.vfl",
                               CONTROLS / "observed_drop.evolution.vfl",
                               CONTROLS / "observed_drop.csv"))
    for variant in ("preserved", "recovered"):
        cases.append(evaluate_case(f"moh_icu.real_{variant}",
                                   HISTORY / f"moh_icu_{variant}.vfl",
                                   HISTORY / "moh_icu_evolution.vfl",
                                   HISTORY / "moh_icu_2021_before.csv",
                                   actual_after_path=HISTORY / "moh_icu_2021_after.csv"))
    output = {"python": platform.python_version(), "platform": platform.platform(),
              "repetitions": 3,
              "moh_history": history_counts,
              "history_scope": "Documented 2018 NYC311 field additions on two transcribed 2016 records; added values are explicit empty defaults, not official backfill",
              "cases": cases}
    target = ROOT / "migration-results.json"
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {target}")
    for case in cases:
        sparse = case["strategies"]["sparse"]
        guard = case["strategies"]["guard-only"]
        full = case["strategies"]["full-row"]
        print(f"{case['case']}: admitted={sparse['admitted']} recovered={sparse['recovered']} "
              f"rejected={sparse['rejected']} sidecar={sparse['sidecar_bytes']} B "
              f"vs full-row={full['sidecar_bytes']} B; guard-only rejected={guard['rejected']}")


if __name__ == "__main__":
    main()
