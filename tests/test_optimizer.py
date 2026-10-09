from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from optimized_run import main as optimized_run_main
from veriflow.optimization_demo import build_optimization_demo
from veriflow.ir import build_plan
from veriflow.optimizer import optimize_checked_program
from veriflow.parser import parse
from veriflow.semantics import analyze
from veriflow.vm import compile_program, execute_expression


def checked(expression: str):
    return analyze(parse(
        'schema S { marks: int; divisor: int; } '
        'pipeline P from "in.csv" as S { '
        f'keep where {expression}; select marks; emit "out.csv"; }}'))


class OptimizerTests(unittest.TestCase):
    def test_folding_and_identities_reach_executable_bytecode(self):
        program = checked('(marks + 2 * 3) * 1 + 0 >= 50')
        optimized, stats = optimize_checked_program(program)
        before = compile_program(program).operations[0].instructions
        after = compile_program(optimized).operations[0].instructions
        self.assertEqual([item.opcode for item in after],
                         ['LOAD_FIELD', 'PUSH_INT', 'ADD', 'PUSH_INT', 'COMPARE_GE'])
        self.assertEqual(after[1].operand, '6')
        self.assertLess(len(after), len(before))
        self.assertEqual((stats.folded, stats.identities), (1, 2))
        self.assertEqual([item.opcode for item in build_plan(optimized).steps[2].instructions],
                         [item.opcode for item in after])
        for marks in (Fraction(38), Fraction(44), Fraction(82)):
            values = {'marks': marks, 'divisor': Fraction(1)}
            self.assertEqual(execute_expression(before, values),
                             execute_expression(after, values))

    def test_boolean_simplification_respects_short_circuit_and_errors(self):
        row = {'marks': Fraction(10), 'divisor': Fraction(0)}
        for expression, expected in (
            ('false and marks / divisor > 1', False),
            ('true or marks / divisor > 1', True),
        ):
            optimized, _ = optimize_checked_program(checked(expression))
            instructions = compile_program(optimized).operations[0].instructions
            self.assertEqual(len(instructions), 1)
            self.assertEqual(execute_expression(instructions, row), expected)
        for expression in ('marks / divisor > 1 and false',
                           'marks / divisor > 1 or true'):
            optimized, _ = optimize_checked_program(checked(expression))
            instructions = compile_program(optimized).operations[0].instructions
            with self.assertRaises(ZeroDivisionError):
                execute_expression(instructions, row)

    def test_identity_rules_keep_type_and_observable_failures(self):
        optimized, _ = optimize_checked_program(checked('marks / 1 >= 1'))
        instructions = compile_program(optimized).operations[0].instructions
        self.assertIn('DIVIDE', [item.opcode for item in instructions])
        optimized, _ = optimize_checked_program(checked('marks + 0.0 >= 1'))
        instructions = compile_program(optimized).operations[0].instructions
        self.assertIn('ADD', [item.opcode for item in instructions])
        optimized, _ = optimize_checked_program(checked('marks / (2 - 2) > 1'))
        instructions = compile_program(optimized).operations[0].instructions
        with self.assertRaises(ZeroDivisionError):
            execute_expression(instructions, {'marks': Fraction(10), 'divisor': Fraction(1)})
        optimized, _ = optimize_checked_program(checked('marks / divisor * 0 >= 0'))
        instructions = compile_program(optimized).operations[0].instructions
        with self.assertRaises(ZeroDivisionError):
            execute_expression(instructions, {'marks': Fraction(10), 'divisor': Fraction(0)})

    def test_optimized_runner_uses_existing_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'program.vfl'
            source.write_text('schema S { marks: int; } '
                              'pipeline P from "input.csv" as S { '
                              'let adjusted = (marks + 2 * 3) * 1 + 0; '
                              'keep where true and adjusted >= 50; '
                              'select adjusted; emit "output.csv"; }', encoding='utf-8')
            (root / 'input.csv').write_text('marks\n38\n82\n', encoding='utf-8')
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(optimized_run_main([str(source)]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report['optimizations'],
                             {'folded': 1, 'identities': 2, 'boolean': 1})
            self.assertEqual(report['result']['rows_written'], 1)
            self.assertEqual((root / 'output.csv').read_text(encoding='utf-8'),
                             'adjusted\n88\n')

    def test_optimization_demo_shows_before_after_and_safe_output(self):
        source = Path(__file__).parents[1] / 'examples' / 'optimization_students.vfl'
        result = build_optimization_demo(source)
        self.assertIn('BEFORE OPTIMIZATION - BYTECODE', result)
        self.assertIn('AFTER OPTIMIZATION - BYTECODE', result)
        self.assertIn('Expression instructions before: 21', result)
        self.assertIn('Expression instructions after:  13', result)
        self.assertIn('Anika,88', result)
        self.assertIn('Rows written:  2', result)
        self.assertFalse(source.with_name('optimized_students.csv').exists())


if __name__ == '__main__':
    unittest.main()
