from decimal import Decimal
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from veriflow.evolution import compile_evolution, migrate_forward
from veriflow.evolution_parser import parse_evolution
from veriflow.impact import (analyze_impact, observe, observe_adapted,
                             observed_source_fields)
from veriflow.parser import parse
from veriflow.semantics import analyze
from veriflow.cli import main
from veriflow.reporting import execute_with_report


SCHEMAS = '''
schema Old { name: text; score: decimal; legacy: text; }
schema New { name: text; score: int; }
evolve Old to New { drop legacy; }
'''


def checked(condition: str, selection: str = "name"):
    return analyze(parse(f'''
schema Old {{ name: text; score: decimal; legacy: text; }}
pipeline Pass from "input.csv" as Old {{
    {condition}
    select {selection};
    emit "output.csv";
}}
'''))


class ImpactTests(unittest.TestCase):
    def setUp(self):
        self.plan = compile_evolution(parse_evolution(SCHEMAS))

    def test_lossy_record_migration_preserves_threshold_pipeline(self):
        pipeline = checked("keep where score >= 40;")
        report = analyze_impact(pipeline, self.plan)
        self.assertEqual(report.status, "preserved")
        self.assertEqual(report.required_old_fields, ("name", "score"))
        self.assertIn("positive-integer-threshold",
                      {item.rule_id for item in report.findings})
        for score in (Decimal("-0.5"), Decimal("39.9"), Decimal("40.7")):
            old = {"name": "Ada", "score": score, "legacy": "lost"}
            new = migrate_forward(self.plan, old)
            self.assertEqual(observe(pipeline, old),
                             observe_adapted(pipeline, self.plan, new,
                                             report.required_old_fields))

    def test_bounded_threshold_and_guard_claims(self):
        # Includes negative values, zero, both sides of the threshold, and
        # fractional values that truncate toward zero.
        values = [Decimal(number) / 10 for number in range(-25, 56)]
        expressions = ("score >= 1", "score < 1", "score >= 4",
                       "score < 4", "score > 1", "score <= 1",
                       "score == 1", "score >= 0", "score > -1",
                       "score > 1 and score < 4",
                       "score > 1 or score >= 4",
                       "not (score > 1)",
                       "score > 1 and name == \"Ada\"")
        for condition in expressions:
            pipeline = checked(f"keep where {condition};")
            report = analyze_impact(pipeline, self.plan)
            self.assertIn(report.status, {"preserved", "conditional"})
            for score in values:
                old = {"name": "Ada", "score": score, "legacy": "x"}
                if report.status == "conditional" and not all(
                        guard.accepts(old) for guard in report.guards):
                    continue
                migrated = migrate_forward(self.plan, old)
                self.assertEqual(
                    observe(pipeline, old),
                    observe_adapted(pipeline, self.plan, migrated,
                                    report.required_old_fields),
                    (condition, score),
                )

        derived = checked("let above = score > 1; keep where not above;")
        report = analyze_impact(derived, self.plan)
        self.assertEqual(report.status, "conditional")
        for score in values:
            old = {"name": "Ada", "score": score, "legacy": "x"}
            if all(guard.accepts(old) for guard in report.guards):
                self.assertEqual(observe(derived, old),
                                 observe_adapted(derived, self.plan,
                                                 migrate_forward(self.plan, old),
                                                 report.required_old_fields))

    def test_strict_threshold_is_conditional_and_has_replayed_witness(self):
        pipeline = checked("keep where score > 40;")
        report = analyze_impact(pipeline, self.plan)
        self.assertEqual(report.status, "conditional")
        self.assertEqual([(item.field, item.kind, item.threshold) for item in report.guards],
                         [("score", "outside_positive_threshold_gap", 40)])
        self.assertTrue(report.guards[0].accepts({"score": Decimal("40")}))
        self.assertFalse(report.guards[0].accepts({"score": Decimal("40.7")}))
        self.assertTrue(report.guards[0].accepts({"score": Decimal("41.7")}))
        self.assertIsNotNone(report.divergence)
        self.assertNotEqual(report.divergence.old_observation,
                            report.divergence.adapted_observation)
        self.assertIsNotNone(report.collision)
        self.assertEqual(migrate_forward(self.plan, report.collision.first_record),
                         migrate_forward(self.plan, report.collision.second_record))
        self.assertNotEqual(report.collision.first_observation,
                            report.collision.second_observation)

    def test_selected_converted_value_needs_guard(self):
        pipeline = checked("keep where true;", "name, score")
        self.assertEqual(analyze_impact(pipeline, self.plan).status, "conditional")

    def test_derived_field_dependency_is_transitive(self):
        pipeline = checked("let eligible = score >= 40; keep where eligible;")
        self.assertEqual(observed_source_fields(pipeline), ("name", "score"))
        self.assertEqual(analyze_impact(pipeline, self.plan).status, "preserved")

    def test_unused_but_executed_division_requires_guard(self):
        pipeline = checked("let reciprocal = 1 / score; keep where true;")
        self.assertEqual(observed_source_fields(pipeline), ("name", "score"))
        report = analyze_impact(pipeline, self.plan)
        self.assertEqual(report.status, "conditional")
        self.assertIsNotNone(report.divergence)
        self.assertEqual(report.divergence.adapted_observation.outcome,
                         "expression-error")
        old = {"name": "Ada", "score": Decimal("0.5"), "legacy": "x"}
        new = migrate_forward(self.plan, old)
        self.assertNotEqual(observe(pipeline, old),
                            observe_adapted(pipeline, self.plan, new, ("name", "score")))

    def test_dropping_observed_field_has_collision_witness(self):
        source = '''
schema Old { name: text; score: decimal; legacy: text; }
schema New { score: decimal; legacy: text; }
evolve Old to New { drop name; }
'''
        plan = compile_evolution(parse_evolution(source))
        report = analyze_impact(checked("keep where true;"), plan)
        self.assertEqual(report.status, "breaking")
        self.assertIsNotNone(report.collision)

    def test_cli_reports_rule_and_witness(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "pipeline.vfl"
            evolution = Path(folder) / "evolution.vfl"
            source.write_text('''
schema Old { name: text; score: decimal; legacy: text; }
pipeline Pass from "input.csv" as Old {
    keep where score > 40;
    select name;
    emit "output.csv";
}
''', encoding="utf-8")
            evolution.write_text(SCHEMAS, encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["impact-check", str(source),
                                       "--evolution", str(evolution)]), 0)
            self.assertIn("PIPELINE IMPACT: CONDITIONAL", output.getvalue())
            self.assertIn("WITNESS", output.getvalue())

    def test_cli_locates_evolution_error_in_evolution_file(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "pipeline.vfl"
            evolution = Path(folder) / "evolution.vfl"
            source.write_text('''schema Old { name: text; score: decimal; legacy: text; }
pipeline Pass from "input.csv" as Old {
    select name;
    emit "output.csv";
}
''', encoding="utf-8")
            evolution.write_text('''schema Old { name: text; }
schema New { name: text; }
evolve Old to New { rename missing to name; }
''', encoding="utf-8")
            output = io.StringIO()
            with redirect_stderr(output):
                self.assertEqual(main(["impact-check", str(source),
                                       "--evolution", str(evolution)]), 1)
            self.assertIn(str(evolution) + ":3:", output.getvalue())
            self.assertIn("rename missing", output.getvalue())

    def test_run_evolved_report_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "pipeline.vfl"
            evolution = Path(folder) / "evolution.vfl"
            source.write_text('''
schema Old { name: text; score: decimal; legacy: text; }
pipeline Pass from "input.csv" as Old {
    keep where score > 40;
    select name;
    emit "output.csv";
}
''', encoding="utf-8")
            evolution.write_text(SCHEMAS, encoding="utf-8")
            (Path(folder) / "input.csv").write_text(
                "name,score,legacy\nAda,40.7,x\nDee,41.7,y\n", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["run-evolved-report", str(source),
                                       "--evolution", str(evolution)]), 0)
            summary = json.loads(output.getvalue())
            self.assertEqual((summary["rows_written"], summary["rows_guard_rejected"]),
                             (1, 1))
            self.assertEqual((Path(folder) / "output.csv").read_text(encoding="utf-8"),
                             "name\nDee\n")

    def test_readiness_reports_guard_coverage_without_writing_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "pipeline.vfl"
            evolution = Path(folder) / "evolution.vfl"
            data = Path(folder) / "legacy.csv"
            source.write_text('''
schema Old { name: text; score: decimal; legacy: text; }
pipeline Pass from "unused.csv" as Old {
    keep where score > 40;
    select name;
    emit "output.csv";
}
''', encoding="utf-8")
            evolution.write_text(SCHEMAS, encoding="utf-8")
            data.write_text("name,score,legacy\nAda,40.7,x\nDee,41.7,y\n"
                            "Cal,39.9,z\nBad,not-a-number,q\n", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["impact-check", str(source),
                                       "--evolution", str(evolution),
                                       "--input", str(data)]), 0)
            report = output.getvalue()
            self.assertIn("PIPELINE IMPACT: CONDITIONAL", report)
            self.assertIn("WITNESS", report)
            self.assertIn("well-typed=3, invalid=1", report)
            self.assertIn("guard admitted=2, guard rejected=1", report)
            self.assertIn("66.67%", report)
            self.assertFalse((Path(folder) / "output.csv").exists())

    def test_readiness_does_not_admit_unknown_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "pipeline.vfl"
            evolution = Path(folder) / "evolution.vfl"
            data = Path(folder) / "legacy.csv"
            source.write_text('''
schema Old { name: text; score: text; }
pipeline Pass from "unused.csv" as Old {
    keep where score == "ok";
    select name;
    emit "output.csv";
}
''', encoding="utf-8")
            evolution.write_text('''
schema Old { name: text; score: text; }
schema New { name: text; score: int; }
evolve Old to New { convert score to score; }
''', encoding="utf-8")
            data.write_text("name,score\nAda,ok\n", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["impact-check", str(source),
                                       "--evolution", str(evolution),
                                       "--input", str(data)]), 0)
            self.assertIn("PIPELINE IMPACT: UNKNOWN", output.getvalue())
            self.assertIn("guard coverage: unavailable", output.getvalue())

    def test_guarded_execution_checks_legacy_value_before_conversion(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "pipeline.vfl"
            source.write_text('''
schema Old { name: text; score: decimal; legacy: text; }
pipeline Pass from "input.csv" as Old {
    keep where score > 40;
    select name;
    emit "output.csv";
}
''', encoding="utf-8")
            (Path(folder) / "input.csv").write_text(
                "name,score,legacy\nAda,40.7,x\nBob,41,y\nCal,40,z\nDee,41.7,q\n",
                encoding="utf-8")
            pipeline = analyze(parse(source.read_text(encoding="utf-8")))
            impact = analyze_impact(pipeline, self.plan)
            result = execute_with_report(pipeline, source,
                                         evolution=self.plan, impact=impact)
            self.assertEqual((result.rows_written, result.rows_filtered,
                              result.rows_guard_rejected), (2, 1, 1))
            output = (Path(folder) / "output.csv").read_text(encoding="utf-8")
            self.assertIn("Bob", output)
            self.assertIn("Dee", output)
            rejects = (Path(folder) / "output.rejects.csv").read_text(encoding="utf-8")
            self.assertIn("Ada,40.7,x", rejects)
            self.assertIn("migration guard failed", rejects)

    def test_safe_lossy_execution_accepts_fractional_row(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "pipeline.vfl"
            source.write_text('''
schema Old { name: text; score: decimal; legacy: text; }
pipeline Pass from "input.csv" as Old {
    keep where score >= 40;
    select name;
    emit "output.csv";
}
''', encoding="utf-8")
            (Path(folder) / "input.csv").write_text(
                "name,score,legacy\nAda,40.7,x\n", encoding="utf-8")
            pipeline = analyze(parse(source.read_text(encoding="utf-8")))
            impact = analyze_impact(pipeline, self.plan)
            result = execute_with_report(pipeline, source,
                                         evolution=self.plan, impact=impact)
            self.assertEqual((result.rows_written, result.rows_guard_rejected), (1, 0))
            self.assertEqual((Path(folder) / "output.csv").read_text(encoding="utf-8"),
                             "name\nAda\n")
            lineage = json.loads((Path(folder) / "output.lineage.json").read_text(
                encoding="utf-8"))
            self.assertEqual(lineage["schema_evolution"]["impact_status"], "preserved")


if __name__ == "__main__":
    unittest.main()
