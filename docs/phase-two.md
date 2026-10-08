# Phase 2 - core compiler implementation

Phase 2 completes the core language-processing path required by the lab manual.

## Implemented tasks

1. `let name = expression;` creates typed derived fields.
2. Semantic analysis resolves derived fields in source order and rejects
   duplicates, unknown references, and invalid operand types.
3. Derived expressions lower to typed postfix IR.
4. Constant folding replaces compile-time expression subtrees with literals.
5. Checked operations compile to stack-machine bytecode.
6. The runtime evaluates bytecode in a VM, including short-circuit `and` and `or`.

## Demonstration

```sh
python -m veriflow optimize examples/project_students.vfl
python -m veriflow bytecode examples/project_students.vfl
```

The optimizer reports the number of folded nodes. Bytecode output includes
loads, constants, arithmetic, comparison, jumps, and projection metadata.
