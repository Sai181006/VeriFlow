import unittest

from veriflow.ir import build_plan, format_plan
from veriflow.parser import parse
from veriflow.semantics import analyze
from test_parser import source


class IrTests(unittest.TestCase):
    def test_plan_and_postfix_expression_lowering(self):
        checked = analyze(parse(source(
            'require marks >= 0 else "negative"; '
            'keep where marks + 2 * 3 >= 40 and not false; '
            'select name; emit "out.csv";')))
        plan = build_plan(checked)
        self.assertEqual([step.operation for step in plan.steps],
                         ["SCAN", "VALIDATE", "REQUIRE", "FILTER", "PROJECT", "EMIT"])
        self.assertEqual([instruction.opcode for instruction in plan.steps[3].instructions],
                         ["LOAD_FIELD", "PUSH_INT", "PUSH_INT", "MULTIPLY", "ADD",
                          "PUSH_INT", "COMPARE_GE", "PUSH_BOOL", "BOOLEAN_NOT", "BOOLEAN_AND"])
        text = format_plan(plan)
        self.assertIn("LOGICAL PLAN", text)
        self.assertIn("VALIDATE name:text, marks:int", text)
        self.assertIn("REQUIRE negative", text)
        self.assertIn("COMPARE_GE", text)
        self.assertIn("PROJECT name", text)
