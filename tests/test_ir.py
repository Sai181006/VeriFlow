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

    def test_derived_field_has_typed_ir(self):
        checked = analyze(parse(source(
            'let adjusted = marks + 5; select name, adjusted; emit "out.csv";')))
        plan = build_plan(checked)
        self.assertEqual([step.operation for step in plan.steps],
                         ["SCAN", "VALIDATE", "DERIVE", "PROJECT", "EMIT"])
        self.assertEqual(plan.steps[2].details, ("adjusted:int",))
        self.assertEqual([item.opcode for item in plan.steps[2].instructions],
                         ["LOAD_FIELD", "PUSH_INT", "ADD"])

    def test_optimizer_constant_folds_expression_subtrees(self):
        checked = analyze(parse(source(
            'keep where marks + 2 * 3 >= 40; select name; emit "out.csv";')))
        plan = build_plan(checked, optimized=True)
        opcodes = [item.opcode for item in plan.steps[2].instructions]
        self.assertEqual(opcodes, ["LOAD_FIELD", "PUSH_INT", "ADD", "PUSH_INT", "COMPARE_GE"])
        self.assertIn("constant-folded", format_plan(plan))
