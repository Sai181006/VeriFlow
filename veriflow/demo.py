"""Human-readable, isolated walkthrough for classroom demonstrations."""

from pathlib import Path
import shutil
import tempfile

from .ast import Keep, Require
from .ir import build_plan, format_plan
from .lexer import tokenize
from .parser import parse
from .runtime import ExecutionError, execute
from .semantics import analyze


class DemoError(ValueError):
    """The requested guided demo cannot be run in isolation."""


def _section(title: str, body: str) -> str:
    rule = "=" * 72
    return f"{rule}\n{title}\n{rule}\n{body.rstrip()}"


def _preview(text: str, limit: int = 12) -> str:
    lines = text.splitlines()
    if len(lines) <= limit:
        return text.rstrip()
    return "\n".join(lines[:limit]) + f"\n... ({len(lines) - limit} more lines)"


def build_demo(source_path: Path) -> str:
    """Compile and execute a program in a temporary directory for a safe demo."""
    source_path = source_path.resolve()
    with source_path.open(encoding="utf-8-sig", newline="") as stream:
        source = stream.read()
    tokens = tokenize(source)
    program = parse(source)
    checked = analyze(program)
    pipeline = program.pipeline
    input_literal = Path(pipeline.input_path.value)
    output_literal = Path(pipeline.statements[-1].path.value)
    if input_literal.is_absolute() or output_literal.is_absolute():
        raise DemoError("The guided demo requires relative input and output paths")
    real_input = (source_path.parent / input_literal).resolve()
    with real_input.open(encoding="utf-8-sig", newline="") as stream:
        input_text = stream.read()

    condition_lines = []
    for condition in checked.conditions:
        node = next(statement for statement in pipeline.statements
                    if ((condition.kind == "require" and isinstance(statement, Require)
                         and statement.span == condition.span)
                        or (condition.kind == "keep" and isinstance(statement, Keep)
                            and statement.span == condition.span)))
        if isinstance(node, Require):
            condition_lines.append(f"  - require rule: {node.message.value}")
        else:
            condition_lines.append("  - keep where filter")
    summary = [f"Tokens produced: {len(tokens)}",
               f"Schema: {program.schema.name.value}",
               "Fields: " + ", ".join(f"{s.name}:{s.type}" for s in checked.symbols),
               f"Pipeline: {pipeline.name.value}",
               "Selected output: " + ", ".join(s.name for s in checked.selected)]
    summary.extend(condition_lines)

    with tempfile.TemporaryDirectory(prefix="veriflow-demo-") as folder:
        demo_root = Path(folder)
        demo_source = demo_root / source_path.name
        resolved_root = demo_root.resolve()
        demo_input = (demo_root / input_literal).resolve()
        demo_output = (demo_root / output_literal).resolve()
        if (not demo_input.is_relative_to(resolved_root)
                or not demo_output.is_relative_to(resolved_root)):
            raise DemoError("The guided demo paths must remain inside its temporary folder")
        demo_input.parent.mkdir(parents=True, exist_ok=True)
        demo_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, demo_source)
        shutil.copyfile(real_input, demo_input)
        result = execute(checked, demo_source)
        with demo_output.open(encoding="utf-8", newline="") as stream:
            output_text = stream.read()

    execution = (f"Rows written:  {result.rows_written}\n"
                 f"Rows filtered: {result.rows_filtered}\n"
                 f"Columns:       {', '.join(result.columns)}\n\n"
                 "The run used a temporary folder. Your example files were not changed.")
    return "\n\n".join((
        _section("VERIFLOW - GUIDED COMPILER DEMO", "SQL-like validation and queries for CSV files"),
        _section("1. VERIFLOW PROGRAM", source),
        _section("2. INPUT CSV", _preview(input_text)),
        _section("3. COMPILER SUMMARY", "\n".join(summary)),
        _section("4. EXPLAIN PLAN AND EXPRESSION IR", format_plan(build_plan(checked))),
        _section("5. GENERATED OUTPUT CSV", _preview(output_text)),
        _section("6. EXECUTION RESULT", execution),
    )) + "\n"


def _mistake_case(source_path: Path, title: str, input_text: str) -> str:
    """Run one intentionally invalid CSV and explain the safe failure."""
    source_path = source_path.resolve()
    with source_path.open(encoding="utf-8-sig", newline="") as stream:
        source = stream.read()
    checked = analyze(parse(source))
    pipeline = checked.program.pipeline
    input_literal = Path(pipeline.input_path.value)
    output_literal = Path(pipeline.statements[-1].path.value)
    if input_literal.is_absolute() or output_literal.is_absolute():
        raise DemoError("The guided demo requires relative input and output paths")

    with tempfile.TemporaryDirectory(prefix="veriflow-mistake-demo-") as folder:
        demo_root = Path(folder)
        resolved_root = demo_root.resolve()
        demo_source = demo_root / source_path.name
        demo_input = (demo_root / input_literal).resolve()
        demo_output = (demo_root / output_literal).resolve()
        if (not demo_input.is_relative_to(resolved_root)
                or not demo_output.is_relative_to(resolved_root)):
            raise DemoError("The guided demo paths must remain inside its temporary folder")
        demo_input.parent.mkdir(parents=True, exist_ok=True)
        demo_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, demo_source)
        demo_input.write_text(input_text, encoding="utf-8", newline="")
        try:
            execute(checked, demo_source)
        except ExecutionError as error:
            message = str(error).replace(f"{demo_input}: ", "", 1)
            outcome = (f"VeriFlow stopped safely:\n  {message}\n\n"
                       f"Output created: {'YES' if demo_output.exists() else 'NO'}\n"
                       "The invalid input did not publish a partial result.")
        else:
            raise DemoError(f"The intentionally invalid case {title!r} unexpectedly succeeded")

    return "\n\n".join((
        _section(title, "INTENTIONALLY INCORRECT INPUT"),
        _section("BAD INPUT CSV", _preview(input_text)),
        _section("EXPECTED VALIDATION FAILURE", outcome),
    ))


def build_mistake_demo(source_path: Path) -> str:
    """Show two bad inputs followed by the existing successful walkthrough."""
    errors = build_error_demo(source_path)
    corrected = build_demo(source_path)
    return "\n\n".join((errors,
                         _section("CORRECTED INPUT - SUCCESSFUL RUN",
                                  "The original valid example now completes normally."),
                         corrected))


def build_error_demo(source_path: Path) -> str:
    """Show the invalid type and failed-rule cases without the successful run."""
    wrong_type = _mistake_case(
        source_path,
        "MISTAKE 1 - WRONG DATA TYPE",
        "name,marks\nAnika,82\nRavi,forty\nMira,91\n",
    )
    broken_rule = _mistake_case(
        source_path,
        "MISTAKE 2 - VALUE OUTSIDE THE ALLOWED RANGE",
        "name,marks\nAnika,82\nRavi,38\nMira,140\n",
    )
    introduction = _section(
        "VERIFLOW - EXPECTED ERROR DEMO",
        "Two incorrect CSV files are rejected safely and no partial output is published.",
    )
    return "\n\n".join((introduction, wrong_type, broken_rule))
