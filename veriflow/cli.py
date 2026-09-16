"""Command-line access to completed compiler stages."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .lexer import LexError, tokenize
from .parser import ParseError, parse
from .semantics import SemanticError, analyze
from .runtime import ExecutionError, execute


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VeriFlow CSV pipeline compiler")
    commands = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("tokens", "Inspect source-positioned tokens"),
        ("ast", "Inspect the projection syntax tree without semantic checks"),
        ("check", "Validate the projection program and inspect resolved symbols"),
        ("run", "Validate and execute CSV projection without overwriting files"),
    ):
        subcommand = commands.add_parser(command, help=help_text)
        subcommand.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    try:
        # Preserve original newline offsets, including CRLF.
        with args.source.open(encoding="utf-8-sig", newline="") as stream:
            source = stream.read()
        if args.command == "tokens":
            result = [asdict(token) for token in tokenize(source)]
        else:
            program = parse(source)
            if args.command == "ast":
                result = asdict(program)
            else:
                checked = analyze(program)
                result = asdict(execute(checked, args.source) if args.command == "run" else checked)
    except (OSError, UnicodeError) as error:
        print(f"{args.source}: {error}", file=sys.stderr)
        return 1
    except (LexError, ParseError, SemanticError, ExecutionError) as error:
        start = error.span.start
        stage = {LexError: "lexical", ParseError: "syntax", SemanticError: "semantic",
                 ExecutionError: "runtime"}[type(error)]
        print(f"{args.source}:{start.line}:{start.column}: {stage} error: {error}", file=sys.stderr)
        for note in getattr(error, "__notes__", ()):
            print(note, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0
