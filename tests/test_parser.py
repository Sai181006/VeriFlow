from pathlib import Path
import unittest

from veriflow.ast import Binary, Emit, Keep, Require, Select, Unary
from veriflow.lexer import LexError
from veriflow.parser import ParseError, parse


def source(body='select name, marks; emit "out.csv";', fields='name: text; marks: int;'):
    return f'schema Student {{ {fields} }} pipeline Project from "in.csv" as Student {{ {body} }}'


class ParserTests(unittest.TestCase):
    def test_example_tree_and_exact_spans(self):
        text = (Path(__file__).resolve().parents[1] / "examples/project_students.vfl").read_text()
        program = parse(text)
        self.assertEqual(program.schema.name.value, "Student")
        self.assertEqual([(f.name.value, f.type.value) for f in program.schema.fields],
                         [("name", "text"), ("marks", "int")])
        require, keep, select, emit = program.pipeline.statements
        self.assertIsInstance(require, Require)
        self.assertIsInstance(keep, Keep)
        self.assertIsInstance(select, Select)
        self.assertIsInstance(emit, Emit)
        self.assertEqual([f.value for f in select.fields], ["name", "marks"])
        self.assertEqual(program.pipeline.input_path.value, "students.csv")
        self.assertEqual(emit.path.value, "selected_students.csv")
        for node, spelling in ((program.schema.name, "Student"), (select, "select name, marks;"),
                               (emit.path, '"selected_students.csv"')):
            self.assertEqual(text[node.span.start.offset:node.span.end.offset], spelling)
        self.assertEqual(text[program.span.start.offset:program.span.end.offset], text.rstrip())

    def test_all_types_and_decoded_paths(self):
        program = parse(source('select flag; emit "out\\u002ecsv";',
                               'age: int; score: decimal; name: text; flag: bool;'))
        self.assertEqual([f.type.value for f in program.schema.fields], ["int", "decimal", "text", "bool"])
        self.assertEqual(program.pipeline.statements[1].path.value, "out.csv")

    def test_invalid_syntax(self):
        cases = ["", "schema Student {}", source(fields="name text;"),
                 source(fields="name: integer;"), source(fields="name: text"),
                 source(""), source('select; emit "x";'), source('select name,; emit "x";'),
                 source('select name emit "x";'), source('select name; emit x;'),
                 source('select name; emit "x"'), source()[:-1], source() + " name",
                 source().replace(" as Student", " Student"),
                 source().replace("schema Student", "schema select")]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(ParseError):
                parse(text)

    def test_let_remains_explicitly_unsupported(self):
        with self.assertRaisesRegex(ParseError, "not supported"):
            parse(source('let x = 1;'))

    def test_conditions_and_expression_precedence(self):
        program = parse(source('require marks >= 0 and not false else "bad"; '
                               'keep where marks + 2 * 3 >= 40 or false; '
                               'select name; emit "x";'))
        require, keep, _, _ = program.pipeline.statements
        self.assertIsInstance(require, Require)
        self.assertIsInstance(keep, Keep)
        self.assertEqual(require.condition.operator, "and")
        self.assertEqual(require.condition.left.operator, ">=")
        self.assertIsInstance(require.condition.right, Unary)
        self.assertEqual(keep.condition.operator, "or")
        self.assertIsInstance(keep.condition.left, Binary)
        self.assertEqual(keep.condition.left.left.operator, "+")
        self.assertEqual(keep.condition.left.left.right.operator, "*")

    def test_malformed_conditions(self):
        for statement in ('require marks >= else "bad";', 'require true "bad";',
                          'keep marks > 1;', 'keep where (marks > 1;',
                          'keep where marks > 1);'):
            with self.subTest(statement=statement), self.assertRaises(ParseError):
                parse(source(statement + ' select name; emit "x";'))

    def test_error_position_and_eof(self):
        with self.assertRaises(ParseError) as context:
            parse("schema Student {\r\nname: text\r\n}")
        self.assertEqual((context.exception.span.start.line, context.exception.span.start.column), (3, 1))
        with self.assertRaisesRegex(ParseError, "end of file"):
            parse(source()[:-1])

    def test_every_truncated_prefix_terminates_with_syntax_error(self):
        text = source()
        for end in range(len(text)):
            prefix = text[:end]
            # Prefixes inside a quoted path fail lexically instead of syntactically.
            with self.subTest(end=end), self.assertRaises((ParseError, LexError)):
                parse(prefix)
