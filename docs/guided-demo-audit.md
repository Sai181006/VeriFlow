# Guided demo audit

## Implemented scope

- `python demo.py` runs a single, human-readable walkthrough.
- `demo.cmd` provides a double-clickable Windows entry point and keeps the
  terminal open after completion.
- `python -m veriflow demo <program.vfl>` exposes the same walkthrough through
  the package CLI.
- The output contains the VeriFlow source, CSV input, compiler summary, logical
  plan and postfix IR, generated CSV, and execution totals.

## Isolation and behavior

The demo compiles the real source but copies its input and source into a new
temporary directory before execution. It reads the generated result from that
directory, then allows automatic cleanup. Existing example output is neither
required nor modified, so repeated demonstrations are deterministic.

Guided mode accepts relative input and output paths only. Resolved paths must
remain inside the temporary directory; absolute paths and `..` escapes are
rejected. This restriction applies only to the guided presentation command, not
to the normal `run` command.

Long input and output displays are capped at twelve physical lines to keep a
presentation readable. Compilation and execution errors continue to use the
normal CLI diagnostic path.

## Validation

`python -m unittest discover -s tests -v`: all 55 tests passed.

Tests confirm that all six sections appear, filtering totals and output are
correct, no real output is published, the CLI route works, and absolute/escaping
paths are refused. `python demo.py` was also run against the repository example
and produced the complete expected walkthrough. Python compilation and Git
whitespace checks passed.

No blocking issues remain. The changes are local and uncommitted. Proposed
commit message: `Add guided demo`. Push requires explicit user approval.
