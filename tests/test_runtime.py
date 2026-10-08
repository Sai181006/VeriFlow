import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from veriflow.parser import parse
from veriflow.runtime import ExecutionError, execute
from veriflow.semantics import analyze


PROGRAM = ('schema S { name: text; age: int; score: decimal; flag: bool; } '
           'pipeline P from "input.csv" as S { select score, name; emit "output.csv"; }')
HEADER = "name,age,score,flag\n"


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = self.root / "program.vfl"
        self.source.write_text(PROGRAM, encoding="utf-8")
        self.checked = analyze(parse(PROGRAM))

    def write_input(self, text):
        (self.root / "input.csv").write_text(text, encoding="utf-8", newline="")

    def assert_failure(self, text, message):
        self.write_input(text)
        with self.assertRaisesRegex(ExecutionError, message):
            execute(self.checked, self.source)
        self.assertFalse((self.root / "output.csv").exists())
        self.assertEqual(list(self.root.glob(".veriflow-*.tmp")), [])

    def test_quotes_multiline_unicode_and_exact_numeric_spelling(self):
        self.write_input(HEADER + '"Mira, S",+42,0.700,true\n"தமிழ்\nname",-3,-12.50,false\n')
        result = execute(self.checked, self.source)
        self.assertEqual((result.rows_written, result.columns), (2, ("score", "name")))
        self.assertEqual(result.output_path, str(self.root / "output.csv"))
        with (self.root / "output.csv").open(encoding="utf-8", newline="") as stream:
            self.assertEqual(list(csv.reader(stream)),
                             [["score", "name"], ["0.700", "Mira, S"], ["-12.50", "தமிழ்\nname"]])
        self.assertEqual(list(self.root.glob(".veriflow-*.tmp")), [])

    def test_derived_fields_are_typed_evaluated_and_selected(self):
        program = ('schema S { name: text; marks: int; } '
                   'pipeline P from "input.csv" as S {'
                   ' let percentage = marks / 2; keep where percentage >= 20;'
                   ' select name, percentage; emit "derived.csv"; }')
        self.source.write_text(program, encoding="utf-8")
        self.write_input("name,marks\nA,81\nB,20\n")
        result = execute(analyze(parse(program)), self.source)
        self.assertEqual((result.rows_written, result.rows_filtered), (1, 1))
        self.assertEqual((self.root / "derived.csv").read_text(encoding="utf-8"),
                         "name,percentage\nA,40.5\n")

    def test_reordered_headers_and_extra_columns(self):
        self.write_input("extra,flag,score,age,name\nx,false,1,3,A\n")
        execute(self.checked, self.source)
        self.assertEqual((self.root / "output.csv").read_text(), "score,name\n1,A\n")

    def test_header_only_bom_crlf(self):
        (self.root / "input.csv").write_bytes(b"\xef\xbb\xbfname,age,score,flag\r\n")
        self.assertEqual(execute(self.checked, self.source).rows_written, 0)
        self.assertEqual((self.root / "output.csv").read_text(), "score,name\n")

    def test_invalid_headers(self):
        for text, message in [("", "missing CSV header"), ("\n", "missing CSV header"),
                              ("name,age,age,flag\n", "duplicate or empty"),
                              ("name,,score,flag\n", "duplicate or empty"),
                              ("name,age,flag\n", "missing declared column 'score'")]:
            with self.subTest(text=text):
                self.assert_failure(text, message)

    def test_bad_types_include_unselected_columns_and_no_partial_output(self):
        for row, message in [("A,bad,1,true", "field 'age' requires int"),
                             ("A,1,NaN,true", "field 'score' requires decimal"),
                             ("A,1,1e3,true", "field 'score' requires decimal"),
                             ("A,1,1,TRUE", "field 'flag' requires bool"),
                             ("A,,1,true", "field 'age' requires int"),
                             ("A, 1,1,true", "field 'age' requires int")]:
            with self.subTest(row=row):
                self.assert_failure(HEADER + "Valid,1,2,true\n" + row + "\n", message)

    def test_missing_extra_blank_and_malformed_rows(self):
        for row, message in [("A,1,2\n", "expected 4 cells"),
                             ("A,1,2,true,x\n", "expected 4 cells"),
                             ("\n", "expected 4 cells"),
                             ('"unterminated,1,2,true\n', "unexpected end of data")]:
            with self.subTest(row=row):
                self.assert_failure(HEADER + row, message)

    def test_existing_output_is_preserved(self):
        self.write_input(HEADER)
        output = self.root / "output.csv"
        output.write_text("keep me")
        with self.assertRaisesRegex(ExecutionError, "already exists"):
            execute(self.checked, self.source)
        self.assertEqual(output.read_text(), "keep me")

    def test_output_cannot_alias_input_or_source(self):
        self.write_input(HEADER)
        for path in ("input.csv", "program.vfl", "./input.csv"):
            with self.subTest(path=path), self.assertRaisesRegex(ExecutionError, "must differ"):
                execute(analyze(parse(PROGRAM.replace('emit "output.csv"', f'emit "{path}"'))), self.source)

    def test_missing_files_directories_and_bad_encoding(self):
        with self.assertRaises(ExecutionError):
            execute(self.checked, self.source)
        self.write_input(HEADER)
        with self.assertRaises(ExecutionError):
            execute(analyze(parse(PROGRAM.replace('emit "output.csv"', 'emit "missing/out.csv"'))), self.source)
        (self.root / "input.csv").write_bytes(b"\xff")
        with self.assertRaises(ExecutionError):
            execute(self.checked, self.source)
        self.assertFalse((self.root / "output.csv").exists())

    def test_publish_race_does_not_overwrite(self):
        self.write_input(HEADER + "A,1,2,true\n")
        original_link = os.link

        def concurrent_link(source, destination):
            Path(destination).write_text("other writer")
            original_link(source, destination)

        with patch("veriflow.runtime.os.link", side_effect=concurrent_link):
            with self.assertRaises(ExecutionError):
                execute(self.checked, self.source)
        self.assertEqual((self.root / "output.csv").read_text(), "other writer")
        self.assertEqual(list(self.root.glob(".veriflow-*.tmp")), [])

    def test_write_failure_cleans_temporary_output(self):
        self.write_input(HEADER + "A,1,2,true\n")
        with patch("veriflow.runtime.csv.writer", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(ExecutionError, "disk full"):
                execute(self.checked, self.source)
        self.assertFalse((self.root / "output.csv").exists())
        self.assertEqual(list(self.root.glob(".veriflow-*.tmp")), [])

    def test_unsupported_publication_is_reported_and_cleans_temp(self):
        self.write_input(HEADER)
        with patch("veriflow.runtime.os.link", side_effect=OSError("links unavailable")):
            with self.assertRaisesRegex(ExecutionError, "links unavailable"):
                execute(self.checked, self.source)
        self.assertFalse((self.root / "output.csv").exists())
        self.assertEqual(list(self.root.glob(".veriflow-*.tmp")), [])

    def test_cleanup_failure_reports_published_result(self):
        self.write_input(HEADER)
        with patch("veriflow.runtime.Path.unlink", side_effect=PermissionError("cleanup denied")):
            with self.assertRaisesRegex(ExecutionError, "Output was published"):
                execute(self.checked, self.source)
        self.assertEqual((self.root / "output.csv").read_text(), "score,name\n")

    def test_cleanup_failure_preserves_primary_error(self):
        self.write_input(HEADER + "A,bad,1,true\n")
        with patch("veriflow.runtime.Path.unlink", side_effect=PermissionError("cleanup denied")):
            with self.assertRaisesRegex(ExecutionError, "requires int") as context:
                execute(self.checked, self.source)
        self.assertIn("cleanup denied", context.exception.__notes__[0])
        self.assertFalse((self.root / "output.csv").exists())

    def test_require_and_keep_execute_in_source_order(self):
        program = PROGRAM.replace(
            'select score, name;',
            'require age >= 0 and age <= 120 else "age out of range"; '
            'keep where score >= 40; select score, name;')
        checked = analyze(parse(program))
        self.write_input(HEADER + "A,20,39,true\nB,21,40,true\nC,22,91,false\n")
        result = execute(checked, self.source)
        self.assertEqual((result.rows_written, result.rows_filtered), (2, 1))
        self.assertEqual((self.root / "output.csv").read_text(),
                         "score,name\n40,B\n91,C\n")

    def test_requirement_failure_uses_message_and_publishes_nothing(self):
        program = PROGRAM.replace('select score, name;',
                                  'require age >= 0 else "age cannot be negative"; select score, name;')
        self.write_input(HEADER + "A,-1,50,true\n")
        with self.assertRaisesRegex(ExecutionError, "CSV line 2: requirement failed: age cannot be negative"):
            execute(analyze(parse(program)), self.source)
        self.assertFalse((self.root / "output.csv").exists())

    def test_arithmetic_parentheses_boolean_and_short_circuit(self):
        program = PROGRAM.replace(
            'select score, name;',
            'keep where flag == true and (age == 0 or score / age >= 2); select score, name;')
        self.write_input(HEADER + "Zero,0,10,true\nPass,20,40,true\nNo,20,100,false\n")
        result = execute(analyze(parse(program)), self.source)
        self.assertEqual((result.rows_written, result.rows_filtered), (2, 1))
        self.assertEqual((self.root / "output.csv").read_text(),
                         "score,name\n10,Zero\n40,Pass\n")

    def test_data_dependent_division_by_zero_is_runtime_error(self):
        program = PROGRAM.replace('select score, name;',
                                  'keep where score / age > 1; select score, name;')
        self.write_input(HEADER + "A,0,50,true\n")
        with self.assertRaisesRegex(ExecutionError, "CSV line 2: expression failed"):
            execute(analyze(parse(program)), self.source)
        self.assertFalse((self.root / "output.csv").exists())

    def test_expression_arithmetic_is_exact(self):
        program = PROGRAM.replace('select score, name;',
                                  'keep where (score / 3) * 3 == score; select score, name;')
        self.write_input(HEADER + "Third,1,1,true\n")
        result = execute(analyze(parse(program)), self.source)
        self.assertEqual((result.rows_written, result.rows_filtered), (1, 0))
