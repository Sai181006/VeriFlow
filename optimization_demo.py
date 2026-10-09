"""Run the optimizer demonstration without changing example files."""

from pathlib import Path

from veriflow.optimization_demo import build_optimization_demo


if __name__ == "__main__":
    source = Path(__file__).parent / "examples" / "optimization_students.vfl"
    print(build_optimization_demo(source), end="")
