"""Streaming CSV projection for the checked Phase One prototype."""

import csv
from dataclasses import dataclass
from fractions import Fraction
import os
from pathlib import Path
import re
import sys
import tempfile

from .ast import Emit
from .lexer import Span
from .semantics import CheckedProgram, TypedExpression


class ExecutionError(ValueError):
    def __init__(self, message: str, span: Span):
        super().__init__(message)
        self.span = span


@dataclass(frozen=True)
class ExecutionResult:
    input_path: str
    output_path: str
    rows_written: int
    rows_filtered: int
    columns: tuple[str, ...]


_INT = re.compile(r"[+-]?[0-9]+\Z")
_DECIMAL = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")


def _valid(value: str, type_name: str) -> bool:
    # Projection preserves values; syntax validation avoids lossy float conversion
    # and supports arbitrarily long integer/decimal spellings without evaluating.
    if type_name == "text":
        return True
    if type_name == "int":
        return _INT.fullmatch(value) is not None
    if type_name == "decimal":
        return _DECIMAL.fullmatch(value) is not None
    if type_name == "bool":
        return value in {"true", "false"}
    return False


def _convert(value: str, type_name: str):
    if type_name in {"int", "decimal"}:
        return Fraction(value)
    if type_name == "bool":
        return value == "true"
    return value


def _evaluate(expression: TypedExpression, row: dict[str, object]):
    if expression.kind == "literal":
        return _convert(str(expression.value), expression.type) if expression.type != "bool" else expression.value
    if expression.kind == "field":
        return row[str(expression.value)]
    if expression.kind == "unary":
        assert expression.left is not None
        value = _evaluate(expression.left, row)
        return not value if expression.operator == "not" else -value
    assert expression.left is not None and expression.right is not None
    left = _evaluate(expression.left, row)
    if expression.operator == "and" and not left:
        return False
    if expression.operator == "or" and left:
        return True
    right = _evaluate(expression.right, row)
    operations = {
        "+": lambda: left + right, "-": lambda: left - right,
        "*": lambda: left * right, "/": lambda: left / right,
        "==": lambda: left == right, "!=": lambda: left != right,
        "<": lambda: left < right, "<=": lambda: left <= right,
        ">": lambda: left > right, ">=": lambda: left >= right,
        "and": lambda: bool(right), "or": lambda: bool(right),
    }
    return operations[expression.operator]()


def execute(checked: CheckedProgram, source_path: Path) -> ExecutionResult:
    """Execute an analyze-produced projection without overwriting any file.

    CSV paths are relative to the source file. A temporary file in the output
    directory receives streamed rows. An exclusive hard link publishes it only
    after validation and closure, so failure never exposes a partial result.
    """
    pipeline = checked.program.pipeline
    emit = pipeline.statements[-1]
    assert isinstance(emit, Emit)
    temporary: Path | None = None
    active_span = pipeline.input_path.span
    active_path = source_path
    try:
        source_path = source_path.resolve()
        input_path = (source_path.parent / pipeline.input_path.value).resolve()
        active_span = emit.path.span
        output_path = (source_path.parent / emit.path.value).resolve()
        active_path = output_path
        if output_path in {input_path, source_path}:
            raise ExecutionError("Output path must differ from input and source paths", emit.path.span)
        if output_path.exists():
            raise ExecutionError(f"Output already exists: {output_path}", emit.path.span)
        columns = tuple(symbol.name for symbol in checked.selected)
        active_path, active_span = input_path, pipeline.input_path.span
        with input_path.open(encoding="utf-8-sig", newline="") as input_stream:
            reader = csv.reader(input_stream, strict=True)
            header = next(reader, None)
            if not header:
                raise ExecutionError(f"{input_path}: missing CSV header", active_span)
            if len(header) != len(set(header)) or any(not name for name in header):
                raise ExecutionError(f"{input_path}: duplicate or empty header name", active_span)
            indices = {name: index for index, name in enumerate(header)}
            for symbol in checked.symbols:
                if symbol.name not in indices:
                    raise ExecutionError(f"{input_path}: missing declared column {symbol.name!r}", symbol.declaration)
            active_path, active_span = output_path, emit.path.span
            # The parent directory must already exist. No implicit directories.
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                             dir=output_path.parent, prefix=".veriflow-",
                                             suffix=".tmp", delete=False) as output_stream:
                temporary = Path(output_stream.name)
                writer = csv.writer(output_stream, lineterminator="\n")
                writer.writerow(columns)
                count = 0
                filtered = 0
                while True:
                    active_path, active_span = input_path, pipeline.input_path.span
                    row = next(reader, None)
                    if row is None:
                        break
                    if len(row) != len(header):
                        raise ExecutionError(f"{input_path}: CSV line {reader.line_num}: "
                                             f"expected {len(header)} cells, found {len(row)}", active_span)
                    for symbol in checked.symbols:
                        if not _valid(row[indices[symbol.name]], symbol.type):
                            raise ExecutionError(f"{input_path}: CSV line {reader.line_num}: "
                                                 f"field {symbol.name!r} requires {symbol.type}", symbol.declaration)
                    typed_row = {symbol.name: _convert(row[indices[symbol.name]], symbol.type)
                                 for symbol in checked.symbols}
                    keep_row = True
                    for condition in checked.conditions:
                        try:
                            passed = bool(_evaluate(condition.expression, typed_row))
                        except (ZeroDivisionError, ArithmeticError) as error:
                            raise ExecutionError(f"{input_path}: CSV line {reader.line_num}: "
                                                 f"expression failed: {error}",
                                                 condition.expression.span) from error
                        if condition.kind == "require" and not passed:
                            raise ExecutionError(f"{input_path}: CSV line {reader.line_num}: "
                                                 f"requirement failed: {condition.message}",
                                                 condition.span)
                        if condition.kind == "keep" and not passed:
                            keep_row = False
                            filtered += 1
                            break
                    if not keep_row:
                        continue
                    active_path, active_span = output_path, emit.path.span
                    writer.writerow([row[indices[name]] for name in columns])
                    count += 1
                active_path, active_span = output_path, emit.path.span
        # Same-directory linking is atomic and refuses a concurrently created file.
        # If the filesystem cannot link, fail rather than overwrite or copy partially.
        os.link(temporary, output_path)
        return ExecutionResult(str(input_path), str(output_path), count, filtered, columns)
    except (OSError, UnicodeError, csv.Error) as error:
        raise ExecutionError(f"{active_path}: {error}", active_span) from error
    finally:
        if temporary is not None:
            pending_error = sys.exception()
            try:
                temporary.unlink(missing_ok=True)
            except OSError as error:
                message = f"Could not remove temporary file {temporary}: {error}"
                if pending_error is not None:
                    # Preserve the original execution failure if cleanup also fails.
                    pending_error.add_note(message)
                else:
                    raise ExecutionError("Output was published, but " + message, emit.path.span) from error
