"""Measure observation-scoped recovery on the existing synthetic pilot cases."""

import argparse
from collections import Counter
import csv
from decimal import Decimal
import json
from pathlib import Path

from veriflow.evolution import compile_evolution
from veriflow.evolution_parser import parse_evolution
from veriflow.impact import analyze_impact, observe
from veriflow.parser import parse
from veriflow.recovery import plan_recovery, recover_row, reconstruct_with_sidecar
from veriflow.semantics import analyze

from .run_study import CASE_NAMES, CASES, DATA, ROOT, typed_rows
from .negative_controls import CASES as NEGATIVE_CASES


def evaluate_case(name: str, case: str, sidecar_path: Path | None = None,
                  migrated_path: Path | None = None) -> dict:
    source = (CASES / f"{name}.{case}.vfl").read_text(encoding="utf-8")
    evolution_name = 'split_evolution' if case == 'split' else 'evolution'
    evolution_source = (CASES / f"{name}.{evolution_name}.vfl").read_text(
        encoding="utf-8")
    checked = analyze(parse(source))
    evolution = compile_evolution(parse_evolution(evolution_source))
    recovery = plan_recovery(checked, evolution)
    rows = typed_rows(DATA / f"{name}.csv")
    entries: list[dict] = []
    migrated_rows: list[dict] = []
    counts: Counter[str] = Counter()
    for index, old in enumerate(rows, 1):
        recovered = recover_row(evolution, recovery, old)
        if migrated_path is not None:
            migrated_rows.append(recovered.migrated)
        encoded = json.loads(json.dumps(recovered.retained, default=str))
        replayed = reconstruct_with_sidecar(evolution, recovered.migrated,
                                            recovery, encoded)
        if observe(checked, old) != observe(checked, replayed):
            raise AssertionError(f"{name}/{case} row {index}: recovery changed observation")
        if encoded:
            entries.append({"row": index, "fields": encoded})
            counts.update(encoded.keys())
    if migrated_path is not None:
        with migrated_path.open('x', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream, lineterminator='\n')
            fields = [field for field, _ in evolution.new_fields]
            writer.writerow(fields)
            for row in migrated_rows:
                writer.writerow([str(row[field]).lower() if isinstance(row[field], bool)
                                 else row[field] for field in fields])
    if sidecar_path is not None:
        with sidecar_path.open('x', encoding='utf-8', newline='') as stream:
            for entry in entries:
                stream.write(json.dumps(entry, ensure_ascii=True) + '\n')
    baseline = len(rows) * len(recovery.required_old_fields)
    return {"dataset": name, "case": case, "rows": len(rows),
            "required_old_fields": list(recovery.required_old_fields),
            "retained_rows": len(entries), "retained_cells": sum(counts.values()),
            "retain_all_observed_cells": baseline,
            "retained_by_field": dict(sorted(counts.items())),
            "observation_mismatches": 0}


def evaluate_observed_drop() -> dict:
    """Show that a saved source cell repairs a previously breaking collision."""
    case = next(item for item in NEGATIVE_CASES if item['name'] == 'observed_drop')
    checked = analyze(parse(case['source']))
    evolution = compile_evolution(parse_evolution(case['evolution']))
    if analyze_impact(checked, evolution).status != 'breaking':
        raise AssertionError('observed_drop must be breaking without a sidecar')
    recovery = plan_recovery(checked, evolution)
    old_rows = ({'name': 'Ada', 'score': Decimal('1.5'), 'legacy': 'x'},
                {'name': 'Bob', 'score': Decimal('1.5'), 'legacy': 'x'})
    recovered = [recover_row(evolution, recovery, old) for old in old_rows]
    if recovered[0].migrated != recovered[1].migrated:
        raise AssertionError('observed_drop collision did not replay')
    for old, result in zip(old_rows, recovered, strict=True):
        if result.retained != {'name': old['name']} or observe(checked, old) != observe(
                checked, result.reconstructed):
            raise AssertionError('observed_drop recovery failed')
    return {'case': 'observed_drop', 'original_status': 'breaking',
            'collision_rows': len(old_rows), 'retained_cells': len(old_rows),
            'observation_mismatches': 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', help='One case, for example abalone.strict')
    parser.add_argument('--sidecar', type=Path,
                        help='Write sparse JSONL sidecar for --case; refuses overwrite')
    parser.add_argument('--migrated', type=Path,
                        help='Write matching migrated CSV for --case; refuses overwrite')
    args = parser.parse_args()
    if (args.sidecar is not None or args.migrated is not None) and args.case is None:
        parser.error('export paths require --case')
    if (args.sidecar is None) != (args.migrated is None):
        parser.error('--sidecar and --migrated must be supplied together')
    if args.sidecar is not None and args.sidecar.resolve() == args.migrated.resolve():
        parser.error('export paths must differ')
    for path in (args.sidecar, args.migrated):
        if path is not None and path.exists():
            parser.error(f'refusing to overwrite {path}')
    if args.case is not None and '.' not in args.case:
        parser.error('--case must have DATASET.CASE form')
    cases = ([(name, case) for name, group in CASE_NAMES.items() for case in group]
             if args.case is None else [tuple(args.case.split('.', 1))])
    for name, case in cases:
        if name not in CASE_NAMES or case not in CASE_NAMES[name]:
            parser.error(f'unknown case {name}.{case}')
    results = [evaluate_case(name, case, args.sidecar, args.migrated)
               for name, case in cases]
    if args.case is None:
        drop_control = evaluate_observed_drop()
        output = ROOT / 'recovery-results.json'
        output.write_text(json.dumps({"cases": results,
                                      "observed_drop_control": drop_control},
                                     indent=2) + '\n',
                          encoding='utf-8')
        print(f'Wrote {output}')
        print('observed_drop: breaking collision recovered with one retained cell per row')
    for result in results:
        print(f"{result['dataset']} {result['case']}: retained "
              f"{result['retained_cells']} / {result['retain_all_observed_cells']} "
              'observable cells')


if __name__ == '__main__':
    main()
