# Benchmark evidence

Sample measured on 17 September 2026 using Python 3.12 and
`examples/derived_students.vfl`:

```text
Iterations:          100
Source characters:   327
Average compile time: 0.557 ms
Minimum compile time: 0.493 ms
Maximum compile time: 1.006 ms
```

Each iteration includes tokenization, parsing, semantic analysis, optimized IR
construction, and bytecode generation. The measurement excludes CSV execution
and filesystem output. Results depend on the computer and current system load;
the command below reproduces the measurement on another machine.

```sh
python -m veriflow benchmark examples/derived_students.vfl --iterations 100
```
