"""Hash the current review artifact without changing Git state."""

import hashlib
import json
from pathlib import Path
import platform
import subprocess


ROOT = Path(__file__).resolve().parents[1]
INCLUDE = (
    Path("README.md"),
    Path("pyproject.toml"),
    Path("evaluation/README.md"),
    *sorted(Path("veriflow").glob("*.py")),
    *sorted(Path("tests").glob("test_*.py")),
    *sorted(Path("evaluation").glob("*.py")),
    *sorted(Path("evaluation/cases").glob("*.vfl")),
    *sorted(Path("evaluation/data").glob("*.csv")),
    *sorted(Path("evaluation/data").glob("*.raw")),
    *sorted(Path("evaluation").glob("*.json")),
    *sorted(Path("docs").glob("*.md")),
)


def main() -> None:
    files = {}
    for relative in INCLUDE:
        if relative.name == "artifact-manifest.json":
            continue
        absolute = ROOT / relative
        files[relative.as_posix()] = hashlib.sha256(absolute.read_bytes()).hexdigest()
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              check=True, capture_output=True, text=True).stdout.strip()
    manifest = {"git_base_revision": revision,
                "python": platform.python_version(),
                "file_sha256": files}
    output = ROOT / "evaluation" / "artifact-manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Hashed {len(files)} files into {output}")


if __name__ == "__main__":
    main()
