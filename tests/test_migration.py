import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from veriflow.evolution import compile_evolution
from veriflow.evolution_parser import parse_evolution
from veriflow.evolved import compile_evolved_pipeline, execute_evolved
from veriflow.impact import Observation, analyze_impact, observe
from veriflow.migration import replay_migration, run_migration
from veriflow.parser import parse
from veriflow.semantics import analyze


ROOT = Path(__file__).resolve().parents[1]


def scenario(body: str, evolution_rules: str, *, old: str = "score: decimal; name: text;",
             new: str = "score: int; name: text;"):
    source = (f'schema Old {{ {old} }}\n'
              f'pipeline P from "input.csv" as Old {{ {body} emit "output.csv"; }}')
    evolution = (f'schema Old {{ {old} }}\n'
                 f'schema New {{ {new} }}\n'
                 f'evolve Old to New {{ {evolution_rules} }}')
    checked = analyze(parse(source))
    plan = compile_evolution(parse_evolution(evolution))
    return checked, plan


class MigrationTests(unittest.TestCase):
    def test_terminal_projection_drop_retains_only_emitted_cells(self):
        checked, plan = scenario('keep where score > 0; select name;', 'drop name;',
                                 old='score: int; name: text;', new='score: int;')
        compiled = compile_evolved_pipeline(checked, plan, analyze_impact(checked, plan))
        self.assertEqual(execute_evolved(compiled, {'score': -1}), Observation('filtered'))
        with self.assertRaisesRegex(ValueError, 'Retained old field'):
            execute_evolved(compiled, {'score': 1})
        with TemporaryDirectory(dir=ROOT / 'evaluation') as directory:
            root = Path(directory)
            source = root / 'pipeline.vfl'
            source.write_text('source path supplied to run_migration', encoding='utf-8')
            data = root / 'input.csv'
            data.write_text('score,name\n-1,Ada\n1,Bob\n', encoding='utf-8')
            bundle = root / 'bundle'
            result = run_migration(checked, plan, source, bundle, input_path=data)
            self.assertEqual((result.admitted, result.recovered, result.rejected,
                              result.retained_cells, result.observation_mismatches),
                             (0, 2, 0, 1, 0))
            sidecars = [json.loads(line) for line in (bundle / 'sidecar.jsonl').read_text(
                encoding='utf-8').splitlines()]
            self.assertEqual([entry['fields'] for entry in sidecars], [{}, {'name': 'Bob'}])
            self.assertEqual(replay_migration(bundle),
                             [Observation('filtered'), Observation('emitted', values=('Bob',))])

    def test_projection_drop_after_rejection_or_expression_error(self):
        cases = (
            ('require score > 0 else "positive"; select name;', 'rejected', 'positive'),
            ('let ratio = 1 / score; select name;', 'expression-error', 'ZeroDivisionError'),
        )
        for body, outcome, message in cases:
            with self.subTest(outcome=outcome):
                checked, plan = scenario(body, 'drop name;',
                                         old='score: int; name: text;', new='score: int;')
                with TemporaryDirectory(dir=ROOT / 'evaluation') as directory:
                    root = Path(directory)
                    source = root / 'pipeline.vfl'
                    source.write_text('source path supplied to run_migration', encoding='utf-8')
                    data = root / 'input.csv'
                    data.write_text('score,name\n0,Ada\n1,Bob\n', encoding='utf-8')
                    bundle = root / 'bundle'
                    result = run_migration(checked, plan, source, bundle, input_path=data)
                    self.assertEqual((result.retained_cells, result.observation_mismatches),
                                     (1, 0))
                    self.assertEqual(replay_migration(bundle)[0], Observation(outcome, message))
                    sidecars = [json.loads(line) for line in (bundle / 'sidecar.jsonl').read_text(
                        encoding='utf-8').splitlines()]
                    self.assertEqual([entry['fields'] for entry in sidecars],
                                     [{}, {'name': 'Bob'}])

    def test_operation_loaded_field_remains_retained_on_filtered_row(self):
        checked, plan = scenario('keep where name == "Ada"; select name;', 'drop name;',
                                 old='score: int; name: text;', new='score: int;')
        with TemporaryDirectory(dir=ROOT / 'evaluation') as directory:
            root = Path(directory)
            source = root / 'pipeline.vfl'
            source.write_text('source path supplied to run_migration', encoding='utf-8')
            data = root / 'input.csv'
            data.write_text('score,name\n0,Bob\n1,Ada\n', encoding='utf-8')
            bundle = root / 'bundle'
            result = run_migration(checked, plan, source, bundle, input_path=data)
            self.assertEqual((result.retained_cells, result.observation_mismatches), (2, 0))
            self.assertEqual([item.outcome for item in replay_migration(bundle)],
                             ['filtered', 'emitted'])

    def test_terminal_projection_guard_needs_no_old_cell(self):
        checked, plan = scenario('keep where name == "Ada"; select score;',
                                 'convert score to score;')
        with TemporaryDirectory(dir=ROOT / 'evaluation') as directory:
            root = Path(directory)
            source = root / 'pipeline.vfl'
            source.write_text('source path supplied to run_migration', encoding='utf-8')
            data = root / 'input.csv'
            data.write_text('score,name\n40.7,Bob\n41.7,Ada\n', encoding='utf-8')
            bundle = root / 'bundle'
            result = run_migration(checked, plan, source, bundle, input_path=data)
            self.assertEqual((result.recovered, result.retained_cells,
                              result.observation_mismatches), (2, 1, 0))
            sidecars = [json.loads(line) for line in (bundle / 'sidecar.jsonl').read_text(
                encoding='utf-8').splitlines()]
            self.assertEqual([entry['fields'] for entry in sidecars],
                             [{}, {'score': '41.7'}])
            self.assertEqual([item.outcome for item in replay_migration(bundle)],
                             ['filtered', 'emitted'])

    def test_sparse_mixed_guards_certify_passed_binding(self):
        checked, plan = scenario(
            'keep where a > 40; keep where b > 40; select name;',
            'convert a to a; convert b to b;',
            old='a: decimal; b: decimal; name: text;',
            new='a: int; b: int; name: text;')
        with TemporaryDirectory(dir=ROOT / 'evaluation') as directory:
            root = Path(directory)
            source = root / 'pipeline.vfl'
            source.write_text('source path supplied to run_migration', encoding='utf-8')
            data = root / 'input.csv'
            data.write_text('a,b,name\n41.7,40.7,Ada\n', encoding='utf-8')
            bundle = root / 'bundle'
            result = run_migration(checked, plan, source, bundle, input_path=data)
            self.assertEqual((result.admitted, result.recovered, result.rejected,
                              result.retained_cells, result.observation_mismatches),
                             (0, 1, 0, 1, 0))
            ledger = json.loads((bundle / 'ledger.jsonl').read_text(encoding='utf-8'))
            sidecar = json.loads((bundle / 'sidecar.jsonl').read_text(encoding='utf-8'))
            self.assertEqual(ledger['certified_fields'], ['a'])
            self.assertEqual(sidecar['fields'], {'b': '40.7'})
            self.assertEqual(replay_migration(bundle),
                             [observe(checked, {'a': '41.7', 'b': '40.7', 'name': 'Ada'})])
            ledger['certified_fields'] = []
            (bundle / 'ledger.jsonl').write_text(json.dumps(ledger) + '\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, "Guard certificate or retained 'a'"):
                replay_migration(bundle)

    def test_sparse_drop_and_passing_guard(self):
        checked, plan = scenario(
            'keep where score > 40; select name;',
            'convert score to score; drop name;',
            old='score: decimal; name: text;', new='score: int;')
        with TemporaryDirectory(dir=ROOT / 'evaluation') as directory:
            root = Path(directory)
            source = root / 'pipeline.vfl'
            source.write_text('source path supplied to run_migration', encoding='utf-8')
            data = root / 'input.csv'
            data.write_text('score,name\n41.7,Ada\n', encoding='utf-8')
            bundle = root / 'bundle'
            result = run_migration(checked, plan, source, bundle, input_path=data)
            self.assertEqual((result.recovered, result.rejected, result.retained_cells,
                              result.observation_mismatches), (1, 0, 1, 0))
            self.assertEqual(len(replay_migration(bundle)), 1)

    def test_compiled_program_runs_new_schema_without_legacy_adapter(self):
        checked, plan = scenario('keep where score > 40; select name;',
                                 'convert score to score;')
        compiled = compile_evolved_pipeline(checked, plan, analyze_impact(checked, plan))
        self.assertEqual(compiled.new_schema, 'New')
        self.assertEqual(compiled.bindings[0].guards[0].kind,
                         'outside_positive_threshold_gap')
        with patch('veriflow.impact.adapt_record', side_effect=AssertionError('adapter used')):
            with self.assertRaisesRegex(ValueError, 'Guard certificate'):
                execute_evolved(compiled, {'score': 40, 'name': 'Ada'})
            self.assertEqual(execute_evolved(compiled, {'score': 40, 'name': 'Ada'},
                                             retained={'score': '40.7'}),
                             observe(checked, {'score': '40.7', 'name': 'Ada'}))

    def test_integrated_strategies_and_replay_pairing(self):
        checked, plan = scenario('keep where score > 40; select name;',
                                 'convert score to score;')
        with TemporaryDirectory(dir=ROOT / 'evaluation') as directory:
            root = Path(directory)
            source = root / 'pipeline.vfl'
            source.write_text('source path supplied to run_migration', encoding='utf-8')
            data = root / 'input.csv'
            data.write_text('score,name\n40.7,Ada\n41.7,Bob\ninvalid,Rejected\n', encoding='utf-8')
            expected = {
                'sparse': (1, 1, 1, 1),
                'guard-only': (1, 0, 2, 0),
                'full-row': (0, 2, 1, 4),
            }
            for strategy, counts in expected.items():
                bundle = root / strategy
                result = run_migration(checked, plan, source, bundle,
                                       input_path=data, strategy=strategy)
                self.assertEqual((result.admitted, result.recovered, result.rejected,
                                  result.retained_cells), counts)
                self.assertEqual(result.observation_mismatches, 0)
                compiled = compile_evolved_pipeline(checked, plan, analyze_impact(checked, plan))
                self.assertEqual(len(replay_migration(bundle, compiled)),
                                 result.admitted + result.recovered)
                self.assertEqual(len(replay_migration(bundle)),
                                 result.admitted + result.recovered)
                with (bundle / 'migrated.csv').open(newline='', encoding='utf-8') as stream:
                    rows = list(csv.reader(stream))
                self.assertEqual(rows[0], ['_veriflow_id', 'score', 'name'])
                self.assertEqual(len({row[0] for row in rows[1:]}), len(rows) - 1)
            tampered = root / 'sparse' / 'migrated.csv'
            tampered.write_text(tampered.read_text(encoding='utf-8').replace('Bob', 'Eve'),
                                encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'differs from ledger'):
                replay_migration(root / 'sparse', compiled)
            tampered.write_text(tampered.read_text(encoding='utf-8').replace('Eve', 'Bob'),
                                encoding='utf-8')
            sidecar = root / 'sparse' / 'sidecar.jsonl'
            sidecar.write_text(sidecar.read_text(encoding='utf-8').replace('40.7', '40.8'),
                               encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'sidecar differs from ledger'):
                replay_migration(root / 'sparse')
            other_checked, _ = scenario('keep where score >= 40; select name;',
                                        'convert score to score;')
            other_compiled = compile_evolved_pipeline(other_checked, plan,
                                                       analyze_impact(other_checked, plan))
            with self.assertRaisesRegex(ValueError, 'different evolved pipeline'):
                replay_migration(root / 'guard-only', other_compiled)

    def test_observed_drop_requires_recovery_and_merge_second_source(self):
        checked, plan = scenario('select name;', 'drop name;',
                                 old='name: text; score: decimal;',
                                 new='score: decimal;')
        compiled = compile_evolved_pipeline(checked, plan, analyze_impact(checked, plan))
        with self.assertRaisesRegex(ValueError, 'Retained old field'):
            execute_evolved(compiled, {'score': '1.5'}, admitted=True)
        with TemporaryDirectory(dir=ROOT / 'evaluation') as directory:
            root = Path(directory)
            source = root / 'pipeline.vfl'
            source.write_text('source path supplied to run_migration', encoding='utf-8')
            data = root / 'input.csv'
            data.write_text('name,score\nAda,1.5\nBob,1.5\n', encoding='utf-8')
            result = run_migration(checked, plan, source, root / 'bundle', input_path=data)
            self.assertEqual((result.recovered, result.retained_cells,
                              result.observation_mismatches), (2, 2, 0))
        merged, merge_plan = scenario('select last;',
                                      'merge first, last into full using "-";',
                                      old='first: text; last: text;',
                                      new='full: text;')
        merged_code = compile_evolved_pipeline(merged, merge_plan,
                                                analyze_impact(merged, merge_plan))
        self.assertEqual(execute_evolved(merged_code, {'full': 'A-B'}, admitted=True),
                         observe(merged, {'first': 'A', 'last': 'B'}))

    def test_mismatch_aborts_publication_and_rejects_have_fixed_width(self):
        checked, plan = scenario('select name;', 'convert score to score;')
        with TemporaryDirectory(dir=ROOT / 'evaluation') as directory:
            root = Path(directory)
            source = root / 'pipeline.vfl'
            source.write_text('source path supplied to run_migration', encoding='utf-8')
            data = root / 'input.csv'
            data.write_text('score,name\n41.0,Ada\nmissing-width\n', encoding='utf-8')
            with patch('veriflow.migration.execute_evolved', return_value=Observation('filtered')):
                with self.assertRaisesRegex(ValueError, 'changed 1 old observations'):
                    run_migration(checked, plan, source, root / 'failed', input_path=data)
            self.assertFalse((root / 'failed').exists())
            result = run_migration(checked, plan, source, root / 'valid', input_path=data)
            self.assertEqual(result.rejected, 1)
            with (root / 'valid' / 'rejects.csv').open(newline='', encoding='utf-8') as stream:
                rejected = list(csv.reader(stream))
            self.assertEqual(len(rejected[0]), 3)
            self.assertEqual(len(rejected[1]), 3)


if __name__ == '__main__':
    unittest.main()
