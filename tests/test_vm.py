from fractions import Fraction
import unittest

from veriflow.parser import parse
from veriflow.semantics import analyze
from veriflow.vm import compile_program, execute_expression, format_bytecode


def checked(body: str):
    return analyze(parse(
        'schema S { marks: int; divisor: int; } '
        f'pipeline P from "in.csv" as S {{ {body} select marks; emit "out.csv"; }}'))


class VmTests(unittest.TestCase):
    def test_pipeline_compiles_to_readable_bytecode(self):
        program = compile_program(checked('let doubled = marks * 2; keep where doubled >= 40;'))
        self.assertEqual([operation.kind for operation in program.operations], ["let", "keep"])
        rendered = format_bytecode(program)
        self.assertIn("VERIFLOW PIPELINE BYTECODE", rendered)
        self.assertIn("MULTIPLY", rendered)
        self.assertIn("COMPARE_GE", rendered)

    def test_vm_executes_arithmetic(self):
        program = compile_program(checked('keep where marks + 2 * 3 >= 40;'))
        value = execute_expression(program.operations[0].instructions,
                                   {"marks": Fraction(35), "divisor": Fraction(1)})
        self.assertTrue(value)

    def test_vm_preserves_boolean_short_circuit(self):
        left_false = compile_program(checked('keep where false and marks / divisor > 1;'))
        left_true = compile_program(checked('keep where true or marks / divisor > 1;'))
        row = {"marks": Fraction(10), "divisor": Fraction(0)}
        self.assertFalse(execute_expression(left_false.operations[0].instructions, row))
        self.assertTrue(execute_expression(left_true.operations[0].instructions, row))


if __name__ == "__main__":
    unittest.main()
