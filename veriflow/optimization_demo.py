"""Isolated classroom demonstration of the optional optimizer."""

from pathlib import Path
import shutil
import tempfile

from .demo import DemoError
from .ir import build_plan, format_plan
from .optimizer import optimize_checked_program
from .parser import parse
from .runtime import execute
from .semantics import analyze
from .vm import compile_program, format_bytecode


def _section(title: str, body: str) -> str:
    rule = "=" * 72
    return f"{rule}\n{title}\n{rule}\n{body.rstrip()}"


def build_optimization_demo(source_path: Path) -> str:
    """Show code before and after rewriting, then execute it safely."""
    source_path = source_path.resolve()
    with source_path.open(encoding="utf-8-sig", newline="") as stream:
        source = stream.read()
    checked = analyze(parse(source))
    optimized, stats = optimize_checked_program(checked)
    before = compile_program(checked)
    after = compile_program(optimized)
    before_count = sum(len(operation.instructions) for operation in before.operations)
    after_count = sum(len(operation.instructions) for operation in after.operations)

    pipeline = checked.program.pipeline
    input_literal = Path(pipeline.input_path.value)
    output_literal = Path(pipeline.statements[-1].path.value)
    if input_literal.is_absolute() or output_literal.is_absolute():
        raise DemoError("The optimization demo requires relative input and output paths")
    real_input = (source_path.parent / input_literal).resolve()
    with tempfile.TemporaryDirectory(prefix="veriflow-optimization-demo-") as folder:
        root = Path(folder)
        resolved_root = root.resolve()
        demo_source = root / source_path.name
        demo_input = (root / input_literal).resolve()
        demo_output = (root / output_literal).resolve()
        if (not demo_input.is_relative_to(resolved_root)
                or not demo_output.is_relative_to(resolved_root)):
            raise DemoError("The optimization demo paths must stay inside its temporary folder")
        demo_input.parent.mkdir(parents=True, exist_ok=True)
        demo_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, demo_source)
        shutil.copyfile(real_input, demo_input)
        with demo_input.open(encoding="utf-8-sig", newline="") as stream:
            input_text = stream.read()
        result = execute(optimized, demo_source)
        with demo_output.open(encoding="utf-8", newline="") as stream:
            output_text = stream.read()

    summary = (f"Constant folds: {stats.folded}\n"
               f"Arithmetic identities removed: {stats.identities}\n"
               f"Boolean operations simplified: {stats.boolean}\n"
               f"Expression instructions before: {before_count}\n"
               f"Expression instructions after:  {after_count}")
    execution = (f"Rows written:  {result.rows_written}\n"
                 f"Rows filtered: {result.rows_filtered}\n"
                 "The run used a temporary folder. Your example files were not changed.")
    return "\n\n".join((
        _section("VERIFLOW - OPTIMIZATION DEMO", "The VM executes the optimized bytecode."),
        _section("1. SOURCE PROGRAM", source),
        _section("2. INPUT CSV", input_text),
        _section("3. BEFORE OPTIMIZATION - LOGICAL IR", format_plan(build_plan(checked))),
        _section("4. AFTER OPTIMIZATION - LOGICAL IR", format_plan(build_plan(optimized))),
        _section("5. BEFORE OPTIMIZATION - BYTECODE", format_bytecode(before)),
        _section("6. AFTER OPTIMIZATION - BYTECODE", format_bytecode(after)),
        _section("7. OPTIMIZATION SUMMARY", summary),
        _section("8. GENERATED OUTPUT CSV", output_text),
        _section("9. EXECUTION RESULT", execution),
    )) + "\n"
