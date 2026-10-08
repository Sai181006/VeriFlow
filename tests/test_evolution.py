import importlib.util
import json
from decimal import InvalidOperation
from pathlib import Path
import tempfile
import unittest

from veriflow.evolution import (adapt, compile_evolution, format_compatibility,
                                generate_adapters, migrate_forward,
                                migrate_reverse, verify_round_trip,
                                verify_reverse_round_trip, MissingInformationError,
                                directional_classification)
from veriflow.evolution_parser import parse_evolution
from veriflow.semantics import SemanticError


SOURCE = '''
schema ChatV1 {
    sender: text;
    message: text;
}

schema ChatV2 {
    user: text;
    content: text;
    timestamp: text;
}

evolve ChatV1 to ChatV2 {
    rename sender to user;
    rename message to content;
    add timestamp default "not-recorded";
}
'''


class EvolutionTests(unittest.TestCase):
    def test_forward_reverse_adapter_and_round_trip(self):
        plan = compile_evolution(parse_evolution(SOURCE))
        old = {"sender": "Sai", "message": "Hello"}
        new = migrate_forward(plan, old)
        self.assertEqual(new, {"user": "Sai", "content": "Hello",
                               "timestamp": "not-recorded"})
        self.assertEqual(migrate_reverse(plan, new), old)
        self.assertEqual(adapt(plan, old, "ChatV2"), new)
        self.assertTrue(verify_round_trip(plan, old).preserved)
        changed_new = {**new, "timestamp": "edited"}
        self.assertFalse(verify_reverse_round_trip(plan, changed_new).preserved)
        self.assertEqual(directional_classification(plan.mappings[-1]),
                         ("lossless", "conditional"))
        self.assertEqual(plan.compatibility, "lossless")

    def test_split_merge_and_loss_are_reported(self):
        source = '''
schema V1 { full_name: text; score: decimal; legacy: text; }
schema V2 { first: text; last: text; score: int; }
evolve V1 to V2 {
  split full_name into first, last using " ";
  drop legacy;
}
'''
        plan = compile_evolution(parse_evolution(source))
        self.assertEqual(plan.compatibility, "lossy")
        report = verify_round_trip(plan, {"full_name": "Sai Kumar", "score": 91.5,
                                          "legacy": "x"})
        self.assertFalse(report.preserved)
        self.assertIn("Cannot reconstruct dropped field", report.error)
        with self.assertRaises(MissingInformationError):
            migrate_reverse(plan, migrate_forward(plan, {"full_name": "Sai Kumar",
                                                      "score": 91.5, "legacy": "x"}))
        rendered = format_compatibility(plan)
        self.assertIn("CONDITIONAL", rendered)
        self.assertIn("LOSSY", rendered)
        self.assertIn("old-new-old=", rendered)

    def test_invalid_mapping_is_semantic_error(self):
        source = SOURCE.replace("rename sender to user;", "rename missing to user;")
        with self.assertRaisesRegex(SemanticError, "Unknown old field"):
            compile_evolution(parse_evolution(source))
        empty_delimiter = '''
schema V1 { first: text; last: text; }
schema V2 { full: text; }
evolve V1 to V2 { merge first, last into full using ""; }
'''
        with self.assertRaisesRegex(SemanticError, "delimiter must not be empty"):
            compile_evolution(parse_evolution(empty_delimiter))

    def test_conversion_and_delimiter_boundaries(self):
        numeric = compile_evolution(parse_evolution('''
schema V1 { value: text; }
schema V2 { value: int; }
evolve V1 to V2 { convert value to value; }
'''))
        self.assertEqual(migrate_forward(numeric, {"value": "12"}), {"value": 12})
        self.assertFalse(verify_round_trip(numeric, {"value": "012"}).preserved)
        with self.assertRaises(InvalidOperation):
            migrate_forward(numeric, {"value": "not-a-number"})

        split = compile_evolution(parse_evolution('''
schema V1 { full: text; }
schema V2 { first: text; last: text; }
evolve V1 to V2 { split full into first, last using "-"; }
'''))
        old = {"full": "a-b-c"}
        self.assertTrue(verify_round_trip(split, old).preserved)
        self.assertFalse(verify_reverse_round_trip(split,
                         {"first": "a-b", "last": "c"}).preserved)

    def test_unmapped_changes_produce_detection_candidates(self):
        source = '''
schema V1 { full_name: text; user_score: int; }
schema V2 { first_name: text; last_name: text; score: int; }
evolve V1 to V2 { }
'''
        plan = compile_evolution(parse_evolution(source))
        detections = "\n".join(plan.detections)
        self.assertIn("possible rename: user_score -> score", detections)
        self.assertIn("possible split: full_name -> first_name, last_name", detections)
        merge_source = '''
schema V1 { first_name: text; last_name: text; }
schema V2 { full_name: text; }
evolve V1 to V2 { }
'''
        merge_detections = "\n".join(
            compile_evolution(parse_evolution(merge_source)).detections)
        self.assertIn("possible merge: first_name, last_name -> full_name", merge_detections)

    def test_generated_programs_are_importable_and_execute(self):
        plan = compile_evolution(parse_evolution(SOURCE))
        with tempfile.TemporaryDirectory() as folder:
            paths = generate_adapters(plan, Path(folder))
            self.assertEqual(len(paths), 4)
            spec = importlib.util.spec_from_file_location("generated_forward", paths[0])
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
            self.assertEqual(module.migrate({"sender": "A", "message": "B"})["user"], "A")
            report = json.loads(paths[3].read_text(encoding="utf-8"))
            self.assertIn({"old_new_old": "lossless", "new_old_new": "conditional"},
                          report["round_trips"])


if __name__ == "__main__":
    unittest.main()
