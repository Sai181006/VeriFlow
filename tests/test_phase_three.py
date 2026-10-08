import csv
from pathlib import Path
import tempfile
import unittest

from veriflow.benchmark import benchmark
from veriflow.lineage import build_lineage, format_lineage
from veriflow.parser import parse
from veriflow.reporting import execute_with_report
from veriflow.semantics import analyze


PROGRAM = ('schema S { name: text; marks: int; } '
           'pipeline P from "input.csv" as S {'
           ' let doubled = marks * 2; require marks <= 100 else "too high";'
           ' keep where marks >= 40; select name, doubled; emit "output.csv"; }')


class PhaseThreeTests(unittest.TestCase):
    def test_lineage_tracks_source_derived_policy_and_output(self):
        graph = build_lineage(analyze(parse(PROGRAM)))
        rendered = format_lineage(graph)
        self.assertIn("marks -> doubled", rendered)
        self.assertIn("doubled -> output.doubled", rendered)
        self.assertIn("marks -> policy.require.1", rendered)

    def test_report_quarantines_bad_rows_and_publishes_lineage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "program.vfl"
            source.write_text(PROGRAM, encoding="utf-8")
            (root / "input.csv").write_text(
                "name,marks\nA,80\nB,bad\nC,140\nD,20\n", encoding="utf-8")
            result = execute_with_report(analyze(parse(PROGRAM)), source)
            self.assertEqual((result.rows_written, result.rows_filtered, result.rows_rejected),
                             (1, 1, 2))
            with (root / "output.rejects.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertIn("requires int", rows[1][-1])
            self.assertIn("requirement failed", rows[2][-1])
            self.assertIn('"derived"', (root / "output.lineage.json").read_text(encoding="utf-8"))

    def test_benchmark_reports_positive_measurements(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "program.vfl"
            source.write_text(PROGRAM, encoding="utf-8")
            result = benchmark(source, iterations=3)
            self.assertEqual(result.iterations, 3)
            self.assertGreater(result.average_compile_ms, 0)


if __name__ == "__main__":
    unittest.main()
