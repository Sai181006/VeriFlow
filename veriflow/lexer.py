"""Token recognition with one-based, end-exclusive source positions.

The lexer is independent of the parser so tokens can be demonstrated directly.
Offsets count Unicode characters, not UTF-8 bytes. CRLF counts as one newline.
"""

from dataclasses import dataclass
import json
import re


@dataclass(frozen=True)
class Position:
    offset: int
    line: int
    column: int


@dataclass(frozen=True)
class Span:
    start: Position
    end: Position


@dataclass(frozen=True)
class Token:
    kind: str
    lexeme: str
    value: str
    span: Span


class LexError(ValueError):
    def __init__(self, message: str, span: Span):
        super().__init__(message)
        self.span = span


KEYWORDS = frozenset(
    "schema pipeline from as require else let keep where select emit "
    "int decimal text bool true false and or not".split()
)
SYMBOLS = {
    "{": "LBRACE", "}": "RBRACE", "(": "LPAREN", ")": "RPAREN",
    ":": "COLON", ";": "SEMICOLON", ",": "COMMA", "=": "ASSIGN",
    "+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH",
    "==": "EQ", "!=": "NE", "<": "LT", "<=": "LE",
    ">": "GT", ">=": "GE",
}
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def tokenize(source: str) -> list[Token]:
    """Scan a complete source file; fail at the first lexical error.

    Numeric values retain their spelling for exact decimal conversion later.
    Strings use JSON escapes and cannot contain unescaped control characters.
    """
    tokens: list[Token] = []
    offset, line, column = 0, 1, 1

    def position() -> Position:
        return Position(offset, line, column)

    def advance(text: str) -> None:
        nonlocal offset, line, column
        offset += len(text)
        breaks = re.split(r"\r\n|\r|\n", text)
        if len(breaks) > 1:
            line += len(breaks) - 1
            column = len(breaks[-1]) + 1
        else:
            column += len(text)

    def fail(message: str, start: Position, text: str) -> None:
        advance(text)
        raise LexError(message, Span(start, position()))

    while offset < len(source):
        start = position()
        char = source[offset]
        if char in " \t\r\n":
            text = "\r\n" if source.startswith("\r\n", offset) else char
            advance(text)
            continue
        if char == "#":
            end = offset
            while end < len(source) and source[end] not in "\r\n":
                end += 1
            advance(source[offset:end])
            continue
        if char == '"':
            end = offset + 1
            escaped = False
            while end < len(source):
                current = source[end]
                if ord(current) < 32:
                    fail("Unescaped control character in string", start, source[offset:end + 1])
                if current == '"' and not escaped:
                    break
                if current == "\\" and not escaped:
                    escaped = True
                else:
                    escaped = False
                end += 1
            if end == len(source):
                fail("Unterminated string", start, source[offset:end])
            text = source[offset:end + 1]
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                fail("Invalid string escape", start, text)
            # JSON permits lone surrogates, which cannot be written as UTF-8.
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                fail("String contains an invalid Unicode surrogate", start, text)
            kind = "STRING"
        elif match := IDENTIFIER.match(source, offset):
            text = match.group()
            value = text
            kind = text.upper() if text in KEYWORDS else "IDENT"
        elif match := NUMBER.match(source, offset):
            text = match.group()
            end = offset + len(text)
            if end < len(source) and (source[end] in "." or source[end].isalnum() or source[end] == "_"):
                fail("Invalid numeric literal", start, source[offset:end + 1])
            value = text
            kind = "DECIMAL_LITERAL" if "." in text else "INT_LITERAL"
        else:
            text = source[offset:offset + 2]
            if text not in SYMBOLS:
                text = char
            if text not in SYMBOLS:
                fail(f"Unexpected character {char!r}", start, char)
            value = text
            kind = SYMBOLS[text]
        advance(text)
        tokens.append(Token(kind, text, value, Span(start, position())))
    end = position()
    tokens.append(Token("EOF", "", "", Span(end, end)))
    return tokens
