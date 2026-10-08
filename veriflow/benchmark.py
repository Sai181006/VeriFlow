"""Repeatable compile-stage benchmark for project evidence."""

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

from .ir import build_plan
from .lexer import tokenize
from .parser import parse
from .semantics import analyze
from .vm import compile_program


@dataclass(frozen=True)
class BenchmarkResult:
    iterations: int
    source_characters: int
    average_compile_ms: float
    minimum_compile_ms: float
    maximum_compile_ms: float


def benchmark(source_path: Path, iterations: int = 25) -> BenchmarkResult:
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    source = source_path.read_text(encoding="utf-8-sig")
    timings = []
    for _ in range(iterations):
        start = perf_counter()
        tokenize(source)
        checked = analyze(parse(source))
        build_plan(checked, optimized=True)
        compile_program(checked)
        timings.append((perf_counter() - start) * 1000)
    return BenchmarkResult(iterations, len(source), sum(timings) / len(timings),
                           min(timings), max(timings))
