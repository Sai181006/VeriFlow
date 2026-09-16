"""Command-line access to completed compiler stages."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .lexer import LexError, tokenize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VeriFlow CSV pipeline compiler")
    commands = parser.add_subparsers(dest="command", required=True)
    tokens = commands.add_parser("tokens", help="Inspect source-positioned tokens")
    tokens.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    try:
        # Preserve original newline offsets, including CRLF.
        with args.source.open(encoding="utf-8-sig", newline="") as stream:
            source = stream.read()
        result = tokenize(source)
    except (OSError, UnicodeError) as error:
        print(f"{args.source}: {error}", file=sys.stderr)
        return 1
    except LexError as error:
        start = error.span.start
        print(f"{args.source}:{start.line}:{start.column}: lexical error: {error}", file=sys.stderr)
        return 1
    print(json.dumps([asdict(token) for token in result], ensure_ascii=True, indent=2))
    return 0
