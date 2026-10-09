# Phase 2 - core compiler implementation

Phase 2 completes the core language-processing path required by the lab manual.

## Implemented tasks

1. `let name = expression;` creates typed derived fields.
2. Semantic analysis resolves derived fields in source order and rejects
   duplicates, unknown references, and invalid operand types.
3. Derived expressions lower to typed postfix IR.
4. The original `optimize` command constant-folds compile-time expression
   subtrees for its displayed plan. The optional optimizer in
   `veriflow/optimizer.py` also removes safe arithmetic identities (`+ 0`,
   `- 0`, and `* 1`) and simplifies Boolean operations while preserving
   evaluation order and short-circuit behavior.
5. Checked operations compile to stack-machine bytecode.
6. The VM supports short-circuit `and` and `or`. `optimized_run.py` passes a
   rewritten checked program to the existing bytecode compiler and runtime;
   the original `run` command remains available.

## Demonstration

```sh
python -m veriflow optimize examples/project_students.vfl
python -m veriflow bytecode examples/project_students.vfl
python optimization_demo.py
```

The optional optimizer reports folded nodes, removed arithmetic identities,
and simplified Boolean operations. The optimization demo compares bytecode before
and after rewriting and executes the optimized program in a temporary folder.
The example has 21 expression instructions before and 13 after optimization;
that count is not a runtime speed measurement. Rules such as `x * 0 -> 0` or
`x and false -> false` are deliberately excluded because they could hide an
error while evaluating `x`.
