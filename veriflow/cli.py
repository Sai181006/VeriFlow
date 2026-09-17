"""Command-line access to completed compiler stages."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .lexer import LexError, tokenize
from .ir import build_plan, format_plan
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
        ("explain", "Display the checked logical plan and expression IR"),
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
                if args.command == "run":
                    result = asdict(execute(checked, args.source))
                elif args.command == "explain":
                    result = format_plan(build_plan(checked))
                else:
                    result = asdict(checked)
    except (OSError, UnicodeError) as error:
        print(f"{args.source}: {error}", file=sys.stderr)
        return 1
    except (LexError, ParseError, SemanticError, ExecutionError) as error:
        start = error.span.start
        stage = {LexError: "lexical", ParseError: "syntax", SemanticError: "semantic",
                 ExecutionError: "runtime"}[type(error)]
        print(f"{args.source}:{start.line}:{start.column}: {stage} error: {error}", file=sys.stderr)
        lines = source.splitlines()
        if 1 <= start.line <= len(lines):
            line = lines[start.line - 1]
            expanded = line.expandtabs(4)
            prefix = line[:max(start.column - 1, 0)].expandtabs(4)
            if error.span.end.line == start.line:
                raw_width = max(error.span.end.column - start.column, 1)
                marked = line[max(start.column - 1, 0):max(start.column - 1, 0) + raw_width]
                width = max(len(marked.expandtabs(4)), 1)
            else:
                width = max(len(expanded) - len(prefix), 1)
            print(f"    {expanded}", file=sys.stderr)
            print(f"    {' ' * len(prefix)}{'^' * width}", file=sys.stderr)
        for note in getattr(error, "__notes__", ()):
            print(note, file=sys.stderr)
        return 1
    if args.command == "explain":
        print(result)
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0
