from decimal import Decimal
import json
import unittest

from veriflow.evolution import compile_evolution
from veriflow.evolution_parser import parse_evolution
from veriflow.impact import observe
from veriflow.parser import parse
from veriflow.recovery import plan_recovery, recover_row, reconstruct_with_sidecar
from veriflow.semantics import analyze


def scenario(old_fields: str, new_fields: str, rule: str, body: str):
    source = (f'schema Old {{ {old_fields} }}\n'
              f'pipeline Pass from "input.csv" as Old {{ {body} emit "output.csv"; }}')
    evolution = (f'schema Old {{ {old_fields} }}\n'
                 f'schema New {{ {new_fields} }}\n'
                 f'evolve Old to New {{ {rule} }}')
    checked = analyze(parse(source))
    plan = compile_evolution(parse_evolution(evolution))
    return checked, plan, plan_recovery(checked, plan)


class RecoveryTests(unittest.TestCase):
    def test_dropped_observed_field_is_retained(self):
        checked, evolution, recovery = scenario(
            'name: text; legacy: text;', 'name: text;', 'drop legacy;',
            'select name, legacy;')
        old = {'name': 'Ada', 'legacy': 'secret'}
        result = recover_row(evolution, recovery, old)
        self.assertEqual(result.retained, {'legacy': 'secret'})
        self.assertEqual(observe(checked, old), observe(checked, result.reconstructed))

    def test_numeric_guard_retains_only_failed_rows(self):
        checked, evolution, recovery = scenario(
            'name: text; score: decimal;', 'name: text; score: int;',
            'convert score to score;', 'keep where score > 40; select name;')
        for score, expected in ((Decimal('40.7'), {'score': Decimal('40.7')}),
                                (Decimal('41.7'), {})):
            old = {'name': 'Ada', 'score': score}
            result = recover_row(evolution, recovery, old)
            self.assertEqual(result.retained, expected)
            self.assertEqual(observe(checked, old), observe(checked, result.reconstructed))
            serialized = json.loads(json.dumps(result.retained, default=str))
            replayed = reconstruct_with_sidecar(evolution, result.migrated,
                                                recovery, serialized)
            self.assertEqual(observe(checked, old), observe(checked, replayed))

    def test_structural_guards_retain_only_ambiguous_values(self):
        split_checked, split_plan, split_recovery = scenario(
            'full: text;', 'first: text; last: text;',
            'split full into first, last using "-";', 'select full;')
        for value, expected in (('Ada-B', {}), ('Ada', {'full': 'Ada'})):
            old = {'full': value}
            result = recover_row(split_plan, split_recovery, old)
            self.assertEqual(result.retained, expected)
            self.assertEqual(observe(split_checked, old),
                             observe(split_checked, result.reconstructed))

        merge_checked, merge_plan, merge_recovery = scenario(
            'first: text; last: text;', 'full: text;',
            'merge first, last into full using "aa";', 'select first, last;')
        for old, expected in (({'first': 'X', 'last': 'Y'}, {}),
                              ({'first': 'a', 'last': 'Y'},
                               {'first': 'a', 'last': 'Y'})):
            result = recover_row(merge_plan, merge_recovery, old)
            self.assertEqual(result.retained, expected)
            self.assertEqual(observe(merge_checked, old),
                             observe(merge_checked, result.reconstructed))

    def test_undefined_forward_mapping_is_refused(self):
        checked = analyze(parse('''
schema Old { value: bool; }
pipeline Pass from "input.csv" as Old { select value; emit "output.csv"; }
'''))
        evolution = compile_evolution(parse_evolution('''
schema Old { value: bool; }
schema New { value: int; }
evolve Old to New { convert value to value; }
'''))
        with self.assertRaisesRegex(ValueError, 'defined forward mapping'):
            plan_recovery(checked, evolution)


if __name__ == '__main__':
    unittest.main()
