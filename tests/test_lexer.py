import unittest

from veriflow.lexer import KEYWORDS, LexError, SYMBOLS, tokenize


class LexerTests(unittest.TestCase):
    def test_keywords_do_not_capture_identifier_prefixes(self):
        for word in KEYWORDS:
            with self.subTest(word=word):
                self.assertEqual([t.kind for t in tokenize(f"{word} {word}_x")],
                                 [word.upper(), "IDENT", "EOF"])

    def test_every_operator_and_delimiter(self):
        for spelling, kind in SYMBOLS.items():
            with self.subTest(spelling=spelling):
                self.assertEqual(tokenize(spelling)[0].kind, kind)
        self.assertEqual([t.kind for t in tokenize("a<=2!=3>=1==1")],
                         ["IDENT", "LE", "INT_LITERAL", "NE", "INT_LITERAL", "GE",
                          "INT_LITERAL", "EQ", "INT_LITERAL", "EOF"])

    def test_literals_and_comments(self):
        tokens = tokenize('0 0.70 -42 "a#b\\n\\\"c" # ignored\ntrue')
        self.assertEqual([t.kind for t in tokens],
                         ["INT_LITERAL", "DECIMAL_LITERAL", "MINUS", "INT_LITERAL",
                          "STRING", "TRUE", "EOF"])
        self.assertEqual(tokens[1].value, "0.70")
        self.assertEqual(tokens[4].value, 'a#b\n"c')

    def test_source_positions_with_crlf_and_unicode(self):
        tokens = tokenize('# heading\r\n  "தமிழ்";\r\nx')
        string, semicolon, identifier, eof = tokens
        self.assertEqual((string.span.start.offset, string.span.start.line, string.span.start.column),
                         (13, 2, 3))
        self.assertEqual(string.span.end, semicolon.span.start)
        self.assertEqual((identifier.span.start.line, identifier.span.start.column), (3, 1))
        self.assertEqual(eof.span.start, identifier.span.end)
        self.assertEqual(eof.span.start, eof.span.end)

    def test_empty_and_comment_only_sources(self):
        for source in ("", "# comment", " \r\n\t"):
            self.assertEqual([t.kind for t in tokenize(source)], ["EOF"])

    def test_invalid_input_fails_at_start_of_bad_token(self):
        for source in ('@', '!', '1.2.3', '12abc', '1e3', '"unterminated',
                       '"bad\\q"', '"bad\nline"', '"\\ud800"', 'é'):
            with self.subTest(source=source), self.assertRaises(LexError) as context:
                tokenize("\n  " + source)
            self.assertEqual((context.exception.span.start.line,
                              context.exception.span.start.column), (2, 3))

    def test_escaped_backslash_and_unicode_pair(self):
        self.assertEqual(tokenize(r'"a\\"')[0].value, "a\\")
        self.assertEqual(tokenize(r'"\ud83d\ude00"')[0].value, "😀")


if __name__ == "__main__":
    unittest.main()
