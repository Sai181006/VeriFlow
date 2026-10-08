"""Command-line access to completed compiler stages."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .benchmark import benchmark
from .lexer import LexError, tokenize
from .ir import build_plan, format_plan
from .demo import DemoError, build_demo
from .evolution import compile_evolution, format_compatibility, generate_adapters
from .evolution_parser import parse_evolution
from .impact import analyze_impact, format_impact
from .readiness import format_readiness, inspect_readiness
from .parser import ParseError, parse
from .lineage import build_lineage, format_lineage
from .reporting import execute_with_report
from .semantics import SemanticError, analyze
from .runtime import ExecutionError, execute
from .vm import compile_program, format_bytecode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VeriFlow CSV pipeline compiler")
    commands = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("tokens", "Inspect source-positioned tokens"),
        ("ast", "Inspect the projection syntax tree without semantic checks"),
        ("check", "Validate the projection program and inspect resolved symbols"),
        ("run", "Validate and execute CSV projection without overwriting files"),
        ("explain", "Display the checked logical plan and expression IR"),
        ("optimize", "Display the optimized logical plan and folded expression IR"),
        ("bytecode", "Display executable stack-machine bytecode"),
        ("lineage", "Display field-level source and output lineage"),
        ("run-report", "Execute while quarantining invalid rows and writing lineage"),
        ("benchmark", "Measure the complete compiler pipeline"),
        ("evolution-check", "Analyze schema changes and information loss"),
        ("generate-adapters", "Generate forward, reverse, and compatibility adapters"),
        ("impact-check", "Check a legacy pipeline against an explicit schema evolution"),
        ("run-evolved-report", "Run a proved legacy pipeline through guarded migration"),
        ("demo", "Run a guided demo without changing the example files"),
    ):
        subcommand = commands.add_parser(command, help=help_text)
        subcommand.add_argument("source", type=Path)
        if command == "benchmark":
            subcommand.add_argument("--iterations", type=int, default=25)
        if command == "generate-adapters":
            subcommand.add_argument("--output-dir", type=Path, required=True)
        if command in {"impact-check", "run-evolved-report"}:
            subcommand.add_argument("--evolution", type=Path, required=True)
        if command == "impact-check":
            subcommand.add_argument("--input", type=Path,
                                    help="Measure guard coverage on a legacy CSV")
    args = parser.parse_args(argv)
    active_path = args.source
    active_source = ""
    try:
        # Preserve original newline offsets, including CRLF.
        with args.source.open(encoding="utf-8-sig", newline="") as stream:
            source = stream.read()
        active_source = source
        if args.command == "demo":
            result = build_demo(args.source)
        elif args.command in {"evolution-check", "generate-adapters"}:
            evolution = compile_evolution(parse_evolution(source))
            if args.command == "evolution-check":
                result = format_compatibility(evolution)
            else:
                result = [str(path) for path in generate_adapters(evolution, args.output_dir)]
        elif args.command in {"impact-check", "run-evolved-report"}:
            active_path = args.evolution
            with args.evolution.open(encoding="utf-8-sig", newline="") as stream:
                evolution_source = stream.read()
            active_source = evolution_source
            evolution = compile_evolution(parse_evolution(evolution_source))
            active_path = args.source
            active_source = source
            checked = analyze(parse(source))
            impact = analyze_impact(checked, evolution)
            if args.command == "impact-check":
                result = format_impact(impact)
                if args.input is not None:
                    active_path = args.input
                    readiness = inspect_readiness(checked, impact, args.input)
                    result += "\n" + format_readiness(readiness)
            else:
                result = asdict(execute_with_report(checked, args.source,
                                                    evolution=evolution, impact=impact))
        elif args.command == "tokens":
            result = [asdict(token) for token in tokenize(source)]
        else:
            program = parse(source)
            if args.command == "ast":
                result = asdict(program)
            else:
                checked = analyze(program)
                if args.command == "run":
                    result = asdict(execute(checked, args.source))
                elif args.command == "run-report":
                    result = asdict(execute_with_report(checked, args.source))
                elif args.command == "lineage":
                    result = format_lineage(build_lineage(checked))
                elif args.command == "benchmark":
                    result = asdict(benchmark(args.source, args.iterations))
                elif args.command == "bytecode":
                    result = format_bytecode(compile_program(checked))
                elif args.command in {"explain", "optimize"}:
                    result = format_plan(build_plan(checked, optimized=args.command == "optimize"))
                else:
                    result = asdict(checked)
    except (OSError, UnicodeError) as error:
        print(f"{active_path}: {error}", file=sys.stderr)
        return 1
    except (LexError, ParseError, SemanticError, ExecutionError) as error:
        start = error.span.start
        stage = {LexError: "lexical", ParseError: "syntax", SemanticError: "semantic",
                 ExecutionError: "runtime"}[type(error)]
        print(f"{active_path}:{start.line}:{start.column}: {stage} error: {error}", file=sys.stderr)
        lines = active_source.splitlines()
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
    except DemoError as error:
        print(f"{args.source}: demo error: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"{active_path}: impact error: {error}", file=sys.stderr)
        return 1
    if args.command in {"explain", "optimize", "bytecode", "lineage", "demo",
                        "evolution-check", "impact-check"}:
        print(result)
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0
