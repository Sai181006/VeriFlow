import csv
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
