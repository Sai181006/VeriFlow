# Paper research tasks (implementation in progress)

**Historical task plan.** See the [current manuscript](paper-manuscript-2026-10-28.md)
and [current council execution](final-council-review-2026-10-28.md) for completed
work and remaining scope.

Checked items have code, tests, or reproducible artifacts linked below.
Unchecked items remain before a credible submission. The supervisor has not
selected a venue; the target is within one month. Use
[paper-research-context.md](paper-research-context.md) for the question and
prior work, [impact-method.md](impact-method.md) for the scoped guarantee, and
[evaluation/README.md](../evaluation/README.md) for the pilot. The
[second council review](council-review-2026-10-08.md) sets the narrowed scope.

## 0. Establish the baseline

- [x] Record the repository revision and account for existing uncommitted work
      before changing code; preserve the current prototype.
- [x] Run the existing suite and record current behavior for each evolution
      operator, including both round-trip directions and failing conversions.
- [ ] Choose the paper venue, deadline, page limit, and evidence expected by the
      supervisor; adjust evaluation scale without changing the core question.
      A [verified venue decision note](venue-scout-2026-10-08.md) is ready for
      that conversation.

## 1. State and test the semantic contract

- [x] Define the valid input domain, forward migration `F`, old pipeline
      `P_old`, adapted pipeline `P_new`, output-field alignment, and `Obs`.
- [x] Specify how `let`, `require`, `keep`, and `select` affect the observable
      result; distinguish filtered rows from requirement failures.
- [x] Specify numeric and text equality and the fate of original CSV spelling.
- [x] Separate source-to-target pipeline preservation from old -> new -> old and
      new -> old -> new record reconstruction claims.
- [x] Write a compact correctness argument for every supported analysis rule.
      A result is `unknown` whenever the argument does not apply.

## 2. Repair baseline evolution claims

- [x] Replace one aggregate loss label, or qualify it, with directional results
      and explicit reasons; an added default must not imply unrestricted
      new -> old -> new preservation.
- [x] Check both round-trip directions with representative and boundary records.
- [x] Prevent the reverse adapter from presenting `None` for a dropped required
      field as a valid old-schema value; report missing information explicitly.
- [x] Test decimal-to-integer truncation, failed parses, text formatting, and
      split/merge delimiter ambiguity.
- [x] Use `adapter` terminology unless lens laws have actually been proved.

## 3. Add pipeline-aware analysis

- [x] Follow lineage transitively through `let` fields into `require`, `keep`,
      and selected outputs. Distinguish fields unused by the observable result.
- [x] Define and execute the migration-time adapted plan through the typed
      legacy pipeline and partial row adapter. Document its old-row guard
      premise and distinguish it from a standalone new-schema rewrite.
- [x] Add sound rules for copy/rename, unused add/drop, and supported numeric
      conversions. Include at least one comparison-sensitive rule so the
      checker can prove a safe nonintegral case and find an unsafe one.
- [x] Produce `preserved`, `conditional`, `breaking`, or `unknown` with affected
      operation, flat field name, assumptions, and proof-rule identifier.
- [x] Derive executable guards for conditional cases. Never turn `unknown` into
      an implicit pass.

## 4. Generate trustworthy witnesses and execute guards

- [x] Generate a valid input record for a claimed break and replay it through
      both actual execution paths before reporting it.
- [x] Keep counterexamples small, but do not claim global minimality.
- [x] Connect proven guards to the existing rejected-row reporting mode and
      record why each guarded row was stopped.
- [x] Maintain output publication safety and avoid silent truncation when a
      guarded conversion fails.

## 5. Evaluate the proposition

- [x] Define ground truth for a bounded operator/expression matrix and check
      all cases exhaustively where feasible; add generated boundary tests.
      The suite checks 13 direct predicates and one derived predicate across
      81 decimal values, plus mapping-specific boundary cases.
- [x] Curate several public CSV datasets or documented schema histories. Three
      public datasets are in the pilot, with all injected changes labeled
      synthetic. A real organizational history would strengthen the paper.
- [x] Compare with current VeriFlow compatibility labels, a conservative
      lineage-only checker, and sample-based differential testing.
- [x] Report soundness violations (target: zero within proved scope), safe-case
      acceptance, `unknown` rate, guard pass/reject rate, witness validation,
      and compilation plus CSV execution overhead.
- [x] Publish the case definitions, data sources/licenses, commands, versions,
      and raw results needed to reproduce every table and figure.
- [x] Add a migration readiness report for a supplied legacy CSV: proof status,
      guard, coverage counts/percentage, and a replayed witness if found.
- [x] Add predeclared negative controls for `require`, derived `let`, expression
      errors, observed drops, unsupported conversion, and mixed booleans.
- [x] Compare old and guarded CSV outcomes on admitted rows, including reject
      reasons; use preserved cases for comparable runtime overhead.

## 6. Write and review the paper

- [x] State the narrow contribution and distinguish it from PRISM, selected
      information preservation, bidirectional adapters, and Mediator.
- [x] Include a motivating safe lossy migration and a nearby breaking variant.
- [x] Include the formal contract, supported-rule arguments, implementation,
      evaluation, threats to validity, and explicit future work in a working
      [paper draft](paper-draft.md); polish and venue formatting remain.
- [x] Expand the proof table into explicit threshold/gap lemmas, prove the
      gap guard exact for one atomic strict threshold, and add a
      prior-work comparison that includes conditional equivalence.
- [ ] Ask a knowledgeable reader to challenge novelty, the observation model,
      rule soundness, baseline fairness, and the generality of results. The
      [reader packet](supervisor-review-note.md) lists concrete falsification
      questions; an independent review has not yet happened.

## Stop/go criteria before submission

- [x] No `preserved` or `conditional` claim lacks a stated domain and sound rule.
- [x] Every reported `breaking` example replays through real execution.
- [x] At least one meaningful safe but record-lossy case is accepted, and a
      close breaking case is detected.
- [x] Results include realistic data and end-to-end cost, not only compiler
      microbenchmarks.
- [x] Claims in the current draft abstract match the implemented and measured
      results: three datasets, 5,926 distinct rows, ten pilot cases, three
      preserved cases, one guarded split case, eight declared controls, four CSV parity
      checks, and zero observed guard violations. Reaudit after venue editing.

## Deferred research gaps

The current one-month scope does not require standalone source-to-source
rewriting over the new schema, new-row-only guards, recovery sidecars,
general split/merge proofs, automatic mapping inference, arbitrary expressions,
or multi-version histories. Keep these as explicit limits unless the selected
venue changes the contribution requirements; see the
[council review](council-review-2026-10-08.md) for the rationale.

## One-month submission sequence

1. **Week 1:** Share the [working draft](paper-draft.md), method note, and
   [pilot results](../evaluation/README.md) with the supervisor; choose a
   venue, exact deadline, page limit, and expected artifact policy.
2. **Week 2:** Ask a domain reader to challenge the proof rules, observation
   model, adapter interpretation, and closest prior work. Resolve any
   counterexample before expanding claims.
3. **Week 3:** Add a documented real schema history if obtainable; otherwise
   state plainly that all mappings are injected. Decide with the supervisor
   whether the current interpreted adapted plan is enough for the venue.
4. **Week 4:** Freeze code and data hashes, rerun tests and evaluation, check
   every table against `results.json`, format to the venue, and submit only
   after the independent review and supervisor approval.
