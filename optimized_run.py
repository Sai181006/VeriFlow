"""Run any VeriFlow pipeline through the optional optimizer."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from veriflow.optimizer import optimize_checked_program
from veriflow.parser import parse
from veriflow.runtime import execute
from veriflow.semantics import analyze


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Optimize and run a VeriFlow pipeline")
    parser.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    with args.source.open(encoding="utf-8-sig", newline="") as stream:
        checked = analyze(parse(stream.read()))
    optimized, stats = optimize_checked_program(checked)
    result = execute(optimized, args.source)
    print(json.dumps({"optimizations": asdict(stats), "result": asdict(result)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
