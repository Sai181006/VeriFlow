"""Run the repository's guided VeriFlow demonstration."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from veriflow.demo import build_demo, build_error_demo, build_mistake_demo


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the VeriFlow error, success, or complete classroom demo.")
    parser.add_argument(
        "mode", nargs="?", choices=("all", "errors", "success"), default="all",
        help="all shows errors followed by recovery; errors and success run one part",
    )
    args = parser.parse_args(argv)
    source = Path(__file__).parent / "examples" / "project_students.vfl"
    builders = {
        "all": build_mistake_demo,
        "errors": build_error_demo,
        "success": build_demo,
    }
    print(builders[args.mode](source), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
