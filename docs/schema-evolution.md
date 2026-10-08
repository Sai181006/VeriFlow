# Schema-evolution compiler

The schema-evolution language accepts two schema versions and explicit mapping
rules. Compilation produces a bidirectional plan and classifies information loss.

```veriflow
schema ChatV1 {
    sender: text;
    message: text;
}

schema ChatV2 {
    user: text;
    content: text;
    timestamp: text;
}

evolve ChatV1 to ChatV2 {
    rename sender to user;
    rename message to content;
    add timestamp default "not-recorded";
}
```

## Outputs

- `forward_adapter.py` migrates old records to the new schema.
- `reverse_adapter.py` migrates new records to the old schema.
- `compatibility_adapter.py` translates toward either named schema.
- `compatibility_report.json` records mappings and loss classifications.

The round-trip verifiers check `old -> new -> old` and `new -> old -> new`
separately. The evolution report lists both directions for every mapping.
An added default preserves an old row in the first direction, while an edited
new value can be lost in the second. A dropped required field makes reverse
record reconstruction fail explicitly. Conversion and split/merge results can
depend on values and delimiters; the aggregate legacy label is only a coarse
summary.

Automatic detection is deliberately conservative. Same-name fields and type
changes are mapped automatically. Name similarity and shared name components
produce rename, split, and merge candidates. These candidates appear in the
report but require explicit rules, so a heuristic guess never silently changes
user data.

## Demonstration

```sh
python evolution_demo.py
python -m veriflow evolution-check examples/chat_evolution.vfl
python -m veriflow generate-adapters examples/chat_evolution.vfl --output-dir generated
```

## Pipeline impact checker

Use `impact-check` to analyze a legacy pipeline against a separate explicit
evolution file. `run-evolved-report` executes `preserved` and `conditional`
plans, enforcing each guard on the original row before conversion and writing
guard failures to the rejects CSV.

```sh
python -m veriflow impact-check evaluation/cases/iris.safe.vfl --evolution evaluation/cases/iris.evolution.vfl
```

The supported rules, observation contract, proof sketches, and limits are in
[impact-method.md](impact-method.md). The [pilot evaluation](../evaluation/README.md)
uses public data with clearly synthetic schema changes. The
[research tasks](paper-research-tasks.md) track the work remaining for a paper.
