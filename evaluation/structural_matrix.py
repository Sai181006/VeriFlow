"""Bounded adversarial checks for text split/merge guards and recovery."""

from itertools import product
import json

from veriflow.evolution import compile_evolution, migrate_forward
from veriflow.evolution_parser import parse_evolution
from veriflow.impact import analyze_impact, observe, observe_adapted
from veriflow.parser import parse
from veriflow.recovery import plan_recovery, recover_row
from veriflow.semantics import analyze
from veriflow.vm import compile_program

from .run_study import ROOT


def programs(kind: str, delimiter: str):
    if kind == 'split':
        old_fields = 'full: text;'
        new_fields = 'left: text; right: text;'
        rule = f'split full into left, right using "{delimiter}";'
        selection = 'full'
    else:
        old_fields = 'left: text; right: text;'
        new_fields = 'full: text;'
        rule = f'merge left, right into full using "{delimiter}";'
        selection = 'left, right'
    source = (f'schema Old {{ {old_fields} }}\n'
              'pipeline P from "input.csv" as Old { '
              f'select {selection}; emit "output.csv"; }}')
    evolution = (f'schema Old {{ {old_fields} }}\n'
                 f'schema New {{ {new_fields} }}\n'
                 f'evolve Old to New {{ {rule} }}')
    return analyze(parse(source)), compile_evolution(parse_evolution(evolution))


def main() -> None:
    values = [''.join(chars) for length in range(4)
              for chars in product('ab-', repeat=length)]
    results = []
    for kind in ('split', 'merge'):
        for delimiter in ('-', 'aa'):
            checked, evolution = programs(kind, delimiter)
            impact = analyze_impact(checked, evolution)
            recovery = plan_recovery(checked, evolution)
            bytecode = compile_program(checked)
            admitted = rejected = retained_cells = 0
            records = ({'full': value} for value in values) if kind == 'split' else (
                {'left': first, 'right': second} for first, second in product(values, repeat=2))
            for old in records:
                before = observe(checked, old, bytecode)
                migrated = migrate_forward(evolution, old)
                after = observe_adapted(checked, evolution, migrated,
                                        impact.required_old_fields, bytecode)
                passes = all(guard.accepts(old) for guard in impact.guards)
                if passes:
                    admitted += 1
                    if before != after:
                        raise AssertionError(f'{kind}/{delimiter}: admitted divergence {old}')
                else:
                    rejected += 1
                recovered = recover_row(evolution, recovery, old)
                retained_cells += len(recovered.retained)
                if before != observe(checked, recovered.reconstructed, bytecode):
                    raise AssertionError(f'{kind}/{delimiter}: recovery divergence {old}')
            results.append({'mapping': kind, 'delimiter': delimiter,
                            'enumerated_rows': admitted + rejected,
                            'guard_admitted': admitted, 'guard_rejected': rejected,
                            'retained_cells': retained_cells,
                            'admitted_mismatches': 0, 'recovery_mismatches': 0})
    output = ROOT / 'structural-matrix.json'
    output.write_text(json.dumps({'alphabet': 'ab-', 'max_length': 3,
                                  'cases': results}, indent=2) + '\n', encoding='utf-8')
    print(f'Checked {sum(case["enumerated_rows"] for case in results)} bounded rows; '
          f'wrote {output}')


if __name__ == '__main__':
    main()
