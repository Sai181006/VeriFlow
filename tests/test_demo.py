from pathlib import Path
import tempfile
import unittest

from veriflow.demo import DemoError, build_demo, build_error_demo, build_mistake_demo


class DemoTests(unittest.TestCase):
    def test_error_only_demo_stops_before_successful_run(self):
        source = Path(__file__).parents[1] / "examples" / "project_students.vfl"
        result = build_error_demo(source)
        self.assertIn("VERIFLOW - EXPECTED ERROR DEMO", result)
        self.assertEqual(result.count("Output created: NO"), 2)
        self.assertNotIn("CORRECTED INPUT - SUCCESSFUL RUN", result)
        self.assertNotIn("GENERATED OUTPUT CSV", result)

    def test_mistake_demo_rejects_bad_inputs_then_runs_corrected_input(self):
        source = Path(__file__).parents[1] / "examples" / "project_students.vfl"
        result = build_mistake_demo(source)
        self.assertIn("MISTAKE 1 - WRONG DATA TYPE", result)
        self.assertIn("field 'marks' requires int", result)
        self.assertIn("MISTAKE 2 - VALUE OUTSIDE THE ALLOWED RANGE", result)
        self.assertIn("requirement failed: marks must be between 0 and 100", result)
        self.assertEqual(result.count("Output created: NO"), 2)
        self.assertIn("CORRECTED INPUT - SUCCESSFUL RUN", result)
        self.assertIn("Rows written:  2", result)
        self.assertIn("Rows filtered: 1", result)

    def test_guided_demo_is_complete_and_does_not_publish_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "program.vfl"
            source.write_text(
                'schema S { name: text; marks: int; } '
                'pipeline P from "input.csv" as S {'
                ' require marks >= 0 else "negative"; keep where marks >= 40;'
                ' select name, marks; emit "output.csv"; }', encoding="utf-8")
            (root / "input.csv").write_text("name,marks\nA,80\nB,20\n", encoding="utf-8")
            result = build_demo(source)
            self.assertIn("VERIFLOW - GUIDED COMPILER DEMO", result)
            self.assertIn("1. VERIFLOW PROGRAM", result)
            self.assertIn("2. INPUT CSV", result)
            self.assertIn("3. COMPILER SUMMARY", result)
            self.assertIn("4. EXPLAIN PLAN AND EXPRESSION IR", result)
            self.assertIn("5. GENERATED OUTPUT CSV", result)
            self.assertIn("Rows written:  1", result)
            self.assertIn("Rows filtered: 1", result)
            self.assertIn("A,80", result)
            self.assertNotIn("B,20\n\n", result.split("5. GENERATED OUTPUT CSV", 1)[1])
            self.assertFalse((root / "output.csv").exists())

    def test_absolute_paths_are_rejected_for_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "program.vfl"
            absolute = (root / "input.csv").as_posix()
            source.write_text(
                f'schema S {{ value: int; }} pipeline P from "{absolute}" as S '
                '{ select value; emit "output.csv"; }', encoding="utf-8")
            with self.assertRaisesRegex(DemoError, "relative"):
                build_demo(source)

    def test_parent_paths_cannot_escape_temporary_demo(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "program.vfl"
            outside_name = f"outside-{root.name}.csv"
            source.write_text(
                f'schema S {{ value: int; }} pipeline P from "../{outside_name}" as S '
                '{ select value; emit "../output.csv"; }', encoding="utf-8")
            outside_input = root.parent / outside_name
            outside_input.write_text("value\n1\n", encoding="utf-8")
            try:
                with self.assertRaisesRegex(DemoError, "inside"):
                    build_demo(source)
                self.assertFalse((root.parent / "output.csv").exists())
            finally:
                outside_input.unlink(missing_ok=True)
