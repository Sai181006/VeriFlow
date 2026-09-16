from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from veriflow.cli import main


class CliTests(unittest.TestCase):
    def run_cli(self, path):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(["tokens", str(path)])
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
