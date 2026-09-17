from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from veriflow.cli import main


class CliTests(unittest.TestCase):
    def run_cli(self, path, command="tokens"):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main([command, str(path)])
        return status, stdout.getvalue(), stderr.getvalue()

    def test_example_is_tokenized(self):
        path = Path(__file__).resolve().parents[1] / "examples/project_students.vfl"
        status, stdout, stderr = self.run_cli(path)
        self.assertEqual((status, stderr), (0, ""))
        result = json.loads(stdout)
        self.assertEqual(result[0]["kind"], "SCHEMA")
        self.assertEqual(result[-1]["kind"], "EOF")

    def test_error_and_file_failure_have_no_partial_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.vfl"
            status, stdout, stderr = self.run_cli(path)
            self.assertEqual((status, stdout), (1, ""))
            self.assertIn("bad.vfl", stderr)
            path.write_text("schema\n@", encoding="utf-8")
            status, stdout, stderr = self.run_cli(path)
            self.assertEqual((status, stdout), (1, ""))
            self.assertIn(":2:1: lexical error:", stderr)
            path.write_bytes(b"\xff")
            self.assertEqual(self.run_cli(path)[0], 1)

    def test_bom_and_crlf(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bom.vfl"
            path.write_bytes(b"\xef\xbb\xbfselect\r\nname;")
            status, stdout, _ = self.run_cli(path)
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(stdout)[1]["span"]["start"],
                             {"offset": 8, "line": 2, "column": 1})

    def test_ast_and_check_example(self):
        path = Path(__file__).resolve().parents[1] / "examples/project_students.vfl"
        status, stdout, stderr = self.run_cli(path, "ast")
        self.assertEqual((status, stderr), (0, ""))
        self.assertEqual(json.loads(stdout)["schema"]["name"]["value"], "Student")
        status, stdout, stderr = self.run_cli(path, "check")
        self.assertEqual((status, stderr), (0, ""))
        self.assertEqual([s["name"] for s in json.loads(stdout)["selected"]], ["name", "marks"])

    def test_syntax_and_semantic_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.vfl"
            path.write_text("schema Student {\nname text;\n}", encoding="utf-8")
            status, stdout, stderr = self.run_cli(path, "ast")
            self.assertEqual((status, stdout), (1, ""))
            self.assertIn(":2:6: syntax error:", stderr)
            path.write_text('schema Student { name: text; }\n'
                            'pipeline P from "missing.csv" as Student { select nope; emit "x"; }',
                            encoding="utf-8")
            self.assertEqual(self.run_cli(path, "ast")[0], 0)
            status, stdout, stderr = self.run_cli(path, "check")
            self.assertEqual((status, stdout), (1, ""))
            self.assertIn(":2:51: semantic error: Unknown field", stderr)

    def test_run_end_to_end_from_another_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "project.vfl"
            path.write_text('schema S { name: text; marks: int; } '
                            'pipeline P from "students.csv" as S { select marks, name; emit "out.csv"; }')
            (root / "students.csv").write_text('name,marks\n"Mira, S",91\n')
            status, stdout, stderr = self.run_cli(path, "run")
            self.assertEqual((status, stderr), (0, ""))
            self.assertEqual(json.loads(stdout)["rows_written"], 1)
            self.assertEqual(json.loads(stdout)["columns"], ["marks", "name"])
            self.assertEqual((root / "out.csv").read_text(), 'marks,name\n91,"Mira, S"\n')
            status, stdout, stderr = self.run_cli(path, "run")
            self.assertEqual((status, stdout), (1, ""))
            self.assertIn("runtime error: Output already exists", stderr)

    def test_run_checks_before_io_and_reports_invalid_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "project.vfl"
            valid = ('schema S { marks: int; } '
                     'pipeline P from "missing.csv" as S { select marks; emit "out.csv"; }')
            path.write_text(valid.replace("select marks", "select typo"))
            status, stdout, stderr = self.run_cli(path, "run")
            self.assertEqual((status, stdout), (1, ""))
            self.assertIn("semantic error: Unknown field", stderr)
            self.assertFalse((root / "out.csv").exists())
            path.write_text(valid)
            (root / "missing.csv").write_text("marks\ninvalid\n")
            status, stdout, stderr = self.run_cli(path, "run")
            self.assertEqual((status, stdout), (1, ""))
            self.assertIn("runtime error:", stderr)
            self.assertIn("CSV line 2: field 'marks' requires int", stderr)
            self.assertFalse((root / "out.csv").exists())

    def test_explain_shows_logical_plan_and_ir(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "plan.vfl"
            path.write_text('schema S { marks: int; } pipeline P from "in.csv" as S {'
                            ' require marks >= 0 else "negative"; keep where marks >= 40;'
                            ' select marks; emit "out.csv"; }')
            status, stdout, stderr = self.run_cli(path, "explain")
            self.assertEqual((status, stderr), (0, ""))
            self.assertIn("LOGICAL PLAN", stdout)
            self.assertIn("REQUIRE negative", stdout)
            self.assertIn("LOAD_FIELD marks", stdout)
            self.assertIn("COMPARE_GE", stdout)
            self.assertFalse((Path(folder) / "out.csv").exists())

    def test_diagnostics_include_source_line_and_caret(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.vfl"
            path.write_text('schema S { marks: int; }\n'
                            'pipeline P from "in.csv" as S {\n'
                            '    keep where makrs >= 40;\n'
                            '    select marks; emit "out.csv";\n}', encoding="utf-8")
            status, stdout, stderr = self.run_cli(path, "check")
            self.assertEqual((status, stdout), (1, ""))
            self.assertIn("3:16: semantic error: Unknown field 'makrs'", stderr)
            self.assertIn("    keep where makrs >= 40;", stderr)
            self.assertIn("               ^^^^^", stderr)
