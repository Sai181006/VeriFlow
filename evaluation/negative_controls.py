"""Predeclared outcomes for migration-impact cases outside the pilot template.

The expected statuses below are written as case definitions, before analysis
runs. Run ``python -m evaluation.negative_controls`` from the repository root.
"""

import json
from pathlib import Path

from veriflow.evolution import compile_evolution, migrate_forward
from veriflow.evolution_parser import parse_evolution
from veriflow.impact import analyze_impact, observe
from veriflow.parser import parse
from veriflow.semantics import analyze


ROOT = Path(__file__).resolve().parent
DECIMAL_EVOLUTION = '''
schema Old { name: text; score: decimal; legacy: text; }
schema New { name: text; score: int; }
evolve Old to New { drop legacy; }
'''
DROP_OBSERVED_EVOLUTION = '''
schema Old { name: text; score: decimal; legacy: text; }
schema New { score: decimal; legacy: text; }
evolve Old to New { drop name; }
'''
TEXT_PARSE_EVOLUTION = '''
schema TextOld { name: text; score: text; }
schema TextNew { name: text; score: int; }
evolve TextOld to TextNew { convert score to score; }
'''
UNSUPPORTED_EVOLUTION = '''
schema FlagOld { name: text; flag: bool; }
schema FlagNew { name: text; flag: int; }
evolve FlagOld to FlagNew { convert flag to flag; }
'''


def pipeline(schema: str, fields: str, body: str, selection: str = "name") -> str:
    return f'''schema {schema} {{ {fields} }}
pipeline Check from "input.csv" as {schema} {{
    {body}
    select {selection};
    emit "output.csv";
}}
'''


CASES = (
    {"name": "require_strict", "expected": "conditional", "rule": "threshold-gap",
     "evolution": DECIMAL_EVOLUTION,
     "source": pipeline("Old", "name: text; score: decimal; legacy: text;",
                        'require score > 40 else "too low";')},
    {"name": "derived_require", "expected": "preserved",
     "rule": "positive-integer-threshold", "evolution": DECIMAL_EVOLUTION,
     "source": pipeline("Old", "name: text; score: decimal; legacy: text;",
                        'let eligible = score >= 40; require eligible else "too low";')},
    {"name": "executed_division", "expected": "conditional",
     "rule": "integral-decimal", "evolution": DECIMAL_EVOLUTION,
     "source": pipeline("Old", "name: text; score: decimal; legacy: text;",
                        "let reciprocal = 1 / score;")},
    {"name": "observed_drop", "expected": "breaking",
     "rule": "required-field-dropped", "evolution": DROP_OBSERVED_EVOLUTION,
     "source": pipeline("Old", "name: text; score: decimal; legacy: text;",
                        "", "name")},
    {"name": "text_parse", "expected": "unknown",
     "rule": "unproved-conversion", "evolution": TEXT_PARSE_EVOLUTION,
     "source": pipeline("TextOld", "name: text; score: text;",
                        "keep where score == \"ok\";")},
    {"name": "unsupported_bool_to_int", "expected": "unknown",
     "rule": "unsupported-mapping", "evolution": UNSUPPORTED_EVOLUTION,
     "source": pipeline("FlagOld", "name: text; flag: bool;",
                        "keep where flag;")},
    {"name": "mixed_boolean_safe", "expected": "preserved",
     "rule": "positive-integer-threshold", "evolution": DECIMAL_EVOLUTION,
     "source": pipeline("Old", "name: text; score: decimal; legacy: text;",
                        'keep where score >= 40 or name == "Ada";')},
    {"name": "mixed_boolean_guarded", "expected": "conditional",
     "rule": "threshold-gap", "evolution": DECIMAL_EVOLUTION,
     "source": pipeline("Old", "name: text; score: decimal; legacy: text;",
                        'keep where score > 40 and name == "Ada";')},
)


def main() -> None:
    results = []
    for case in CASES:
        checked = analyze(parse(case["source"]))
        plan = compile_evolution(parse_evolution(case["evolution"]))
        report = analyze_impact(checked, plan)
        rules = {finding.rule_id for finding in report.findings}
        if report.status != case["expected"] or case["rule"] not in rules:
            raise AssertionError(f"{case['name']}: expected {case['expected']} / "
                                 f"{case['rule']}, got {report.status} / {sorted(rules)}")
        witness_kind = ("divergence" if report.divergence is not None else
                        "collision" if report.collision is not None else None)
        if case["name"] == "executed_division":
            witness = report.divergence
            if (witness is None or
                    {witness.old_observation.outcome,
                     witness.adapted_observation.outcome}
                    != {"emitted", "expression-error"}):
                raise AssertionError("executed_division: expected replayed expression error")
        conversion_failure_observed = False
        if case["name"] == "text_parse":
            try:
                migrate_forward(plan, {"name": "Ada", "score": "not-numeric"})
            except (ValueError, ArithmeticError):
                conversion_failure_observed = True
            if not conversion_failure_observed:
                raise AssertionError("text_parse: expected failed forward conversion")
        if report.status == "breaking":
            witness = report.collision
            if witness is None:
                raise AssertionError(f"{case['name']}: breaking requires collision")
            if (migrate_forward(plan, witness.first_record) != witness.migrated_record
                    or migrate_forward(plan, witness.second_record) != witness.migrated_record
                    or observe(checked, witness.first_record)
                    == observe(checked, witness.second_record)):
                raise AssertionError(f"{case['name']}: collision did not replay")
        results.append({"name": case["name"], "expected": case["expected"],
                        "observed": report.status, "rule": case["rule"],
                        "witness": witness_kind,
                        "conversion_failure_observed": conversion_failure_observed})
    output = ROOT / "negative-controls.json"
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"{len(results)} declared controls passed; wrote {output}")


if __name__ == "__main__":
    main()
