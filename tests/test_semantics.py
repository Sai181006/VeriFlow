import unittest

from veriflow.parser import parse
from veriflow.semantics import SemanticError, analyze
from test_parser import source


class SemanticTests(unittest.TestCase):
    def test_symbols_and_projection_preserve_order(self):
        checked = analyze(parse(source('select marks, name; emit "x";')))
        self.assertEqual([(s.name, s.type) for s in checked.symbols], [("name", "text"), ("marks", "int")])
        self.assertEqual([s.name for s in checked.selected], ["marks", "name"])
        self.assertIs(checked.selected[0], checked.symbols[1])

    def test_invalid_semantics(self):
        cases = [
            (source(fields="name: text; name: int;"), "Duplicate schema field"),
            (source().replace("as Student", "as Other"), "Unknown schema"),
            (source().replace("pipeline Project", "pipeline Student"), "must be distinct"),
            (source('select unknown; emit "x";'), "Unknown field"),
            (source('select name, name; emit "x";'), "Duplicate selected field"),
            (source('emit "x";'), "exactly one select"),
            (source('select name;'), "exactly one emit"),
            (source('select name; select marks; emit "x";'), "Duplicate select"),
            (source('select name; emit "x"; emit "y";'), "Duplicate emit"),
            (source('emit "x"; select name;'), "emit must be terminal"),
        ]
        for text, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(SemanticError, message):
                analyze(parse(text))

    def test_name_suggestions_and_reference_span(self):
        text = source('select makrs; emit "x";')
        with self.assertRaisesRegex(SemanticError, "did you mean 'marks'") as context:
            analyze(parse(text))
        span = context.exception.span
        self.assertEqual(text[span.start.offset:span.end.offset], "makrs")
        with self.assertRaisesRegex(SemanticError, "did you mean 'Student'"):
            analyze(parse(source().replace("as Student", "as Studen")))

    def test_duplicate_points_to_second_declaration(self):
        text = source(fields="name: text; name: int;")
        with self.assertRaises(SemanticError) as context:
            analyze(parse(text))
        self.assertEqual(context.exception.span.start.offset, text.index("name: int"))

    def test_empty_and_nul_paths_fail_before_execution(self):
        for text in (source().replace('"in.csv"', '""'),
                     source().replace('"out.csv"', '""'),
                     source().replace('"in.csv"', '"bad\\u0000.csv"'),
                     source().replace('"out.csv"', '"bad\\u0000.csv"')):
            with self.subTest(text=text), self.assertRaisesRegex(SemanticError, "path must be nonempty"):
                analyze(parse(text))

    def test_typed_conditions(self):
        checked = analyze(parse(source(
            'require marks >= 0 and marks <= 100 else "range"; '
            'keep where not (marks < 40); select name; emit "x";')))
        self.assertEqual([condition.kind for condition in checked.conditions], ["require", "keep"])
        self.assertTrue(all(condition.expression.type == "bool" for condition in checked.conditions))
        self.assertEqual(checked.conditions[0].message, "range")

    def test_expression_type_errors_and_unknown_fields(self):
        cases = [
            ('keep where name + 1; select name; emit "x";', "requires numeric operands"),
            ('keep where marks and true; select name; emit "x";', "requires bool operands"),
            ('keep where name > "A"; select name; emit "x";', "requires numeric operands"),
            ('keep where name == marks; select name; emit "x";', "compatible operands"),
            ('keep where marks + 1; select name; emit "x";', "condition must have type bool"),
            ('keep where makrs > 1; select name; emit "x";', "did you mean 'marks'"),
            ('keep where marks / 0 > 1; select name; emit "x";', "Literal division by zero"),
            ('keep where marks / -0 > 1; select name; emit "x";', "Literal division by zero"),
            ('select name; keep where true; emit "x";', "require/keep must precede"),
        ]
        for body, message in cases:
            with self.subTest(body=body), self.assertRaisesRegex(SemanticError, message):
                analyze(parse(source(body)))
