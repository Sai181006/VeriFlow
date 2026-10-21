# VeriFlow research presentation brief

**Status:** reusable source for an academic PPT, prepared 8 October 2026.  
**Length:** eight slides maximum, including the title and conclusion.  
**Audience:** teacher or research review panel.  
**Working title:** *Guarded Preservation of Pipeline Behavior During Schema Migration*.

This brief describes the **implemented migration-time checker**, not a proposed
standalone rewrite system. Use the short “On slide” text for the deck. The
notes explain what to say and where each claim comes from. Verify the current
[evaluation results](../evaluation/README.md) again before presenting.

The current deck uses the [UI Colors Blue Bell ramp](https://uicolors.app/generate/9999cc)
for its violet neutrals and uses [Fontshare General Sans](https://www.fontshare.com/fonts/general-sans)
as a reference for restrained type weights. It uses installed Segoe UI in the
PPTX so the slides render without an additional font installation. The full
visual choices and source files are documented in the
[presentation README](../presentations/README.md).

## Slide 1 — Title and current focus

**On slide**

- **VeriFlow:** preserving CSV pipeline behavior during schema migration
- Research question: *When can a lossy record migration still preserve a
  pipeline's decisions and selected values?*
- Current scope: one explicit schema change, well-typed legacy rows, and a
  deterministic row-wise pipeline

**Say:** VeriFlow already compiles and runs typed CSV pipelines. The paper
focuses on the added migration impact checker. It evaluates existing legacy
rows while the old row is available. It does not establish behavior for every
future row written only in the new schema. [Method](impact-method.md).

**Visual:** one line showing `old row + old pipeline + schema mapping` feeding
an impact result. Keep the result labels for slide 6.

## Slide 2 — Problem statement

**On slide**

- A schema change can lose record information without changing what a
  particular pipeline observes.
- A single schema-level “lossy” label cannot distinguish safe and unsafe uses
  of the changed field.
- Sampling may find a break, but agreement on sampled rows is not a proof.

**Say:** The existing VeriFlow evolution report describes the mapping at the
record level. We need a question about the *pipeline's behavior*: selected
typed values, filtered rows, validation failures, and expression errors. This
is a focused problem in the larger schema-evolution area. PRISM already
analyzes schema impact and rewrites legacy queries, so query impact itself is
prior art. [PRISM paper](https://www.vldb.org/pvldb/vol1/1453939.pdf);
[project context](paper-research-context.md).

**Visual:** two boxes, “record information” and “pipeline observation,” with a
lossy mapping affecting the first but sometimes preserving the second.

## Slide 3 — One mapping, two outcomes

**On slide**

| Old value | New value after truncation | Pipeline condition | Outcome |
| --- | ---: | --- | --- |
| `score = 40.7` | `40` | `score >= 40` | Same decision |
| `score = 40.7` | `40` | `score > 40` | Different decision |

- Both cases use the same decimal-to-integer migration.

**Say:** Assume a positive integer threshold and truncation toward zero. The
checker proves the non-strict predicate invariant for every finite, well-typed
old decimal in its rule domain. For the strict predicate, the interval
`40 < score < 41` is unsafe; a guard can exclude it. Thus the *example row*
changes decision, while the checker's overall result can be `conditional`
with that guard. A dropped field can also
be harmless when no executed operation or selected output depends on it.
This example is a proof-rule instance, not a claim that all lossy conversions
are safe. [Proof lemmas](paper-draft.md).

**Visual:** a number line marking 40, 40.7, and 41, with the unsafe open
interval highlighted.

## Slide 4 — What prior papers establish, and the question left here

**On slide**

| Prior work | Established focus | Our narrower question |
| --- | --- | --- |
| PRISM | Schema operators, impact analysis, migration, legacy query rewriting | Does this typed row pipeline retain its full observation after a lossy mapping? |
| Fan, Geerts, Zheng | Preservation of selected information under data transformations | Can an executable checker give a useful guard for this pipeline's validation, filtering, and output? |
| Kramer, Restat, Störl | Robustness of data pipeline operators under schema evolution and conceptual self-adaptation | Can a typed pipeline retain its full observation under an explicit lossy row mapping, with an executable sufficient guard and replayed failure? |

**Say:** These papers solve broader or different formal problems. The table is
a positioning statement about *this project's focus*, not a claim that the
papers overlooked an obvious feature. BiDEL/InVerDa also establishes
bidirectional coexisting schema support; adapter generation is not our
novelty. Mediator and conditional equivalence are further theoretical context
in the notes. Cite the sources in the reference block below. An independent
literature review may narrow the novelty claim further.

**Visual:** use the table with short phrases; do not fill the slide with paper
abstracts.

## Slide 5 — Exact research claim

**On slide**

`G(s) ∧ F(s) defined  ⇒  Obs(P, s) = Obs(P, A(F(s)))`

- `s`: a well-typed old row; `F`: explicit forward migration
- `A`: partial adapter used by the legacy pipeline `P`
- `Obs`: selected typed values, filter outcome, validation message, or
  expression error

**Say:** A `preserved` result uses `G = true`. A `conditional` result supplies
an executable sufficient guard `G`. The old row is available when checking
`G`; this is a **migration-time** guarantee. `A(F(s))` expresses the implemented
adapted execution. It is not a separately compiled pipeline over arbitrary
new-schema rows. The guarantee excludes malformed CSV and original cell
spelling. [Formal contract](impact-method.md).

**Visual:** a two-path diagram: `s → P → Obs` and `s → F → A → P → Obs`, joined
by an equality sign under `G(s)`.

## Slide 6 — What the added checker does

**On slide**

1. Trace fields used by executed `let`, `require`, `keep`, and `select` steps.
2. Apply sound rules for exact reconstruction and supported numeric predicates.
3. Return `preserved`, `conditional` with a guard, `breaking` with a replayed
   collision, or `unknown`.

**Say:** The checker proves positive-integer `>=` and `<` thresholds stable
under decimal-to-integer truncation. For atomic `>` and `<=` thresholds, it
guards the exact interval where the decision flips. Other uses may require an
integral-source guard. A `breaking` collision is replayed through both real
execution paths. An unsuccessful bounded witness search yields `unknown`, not
“safe.” The guarded CSV runner records excluded rows, and `impact-check
--input` reports how many rows in a supplied legacy CSV pass the guard.
[Method](impact-method.md); [readiness report](../evaluation/README.md).

**Visual:** compact flow: lineage → rule/guard → replay or `unknown` →
readiness count.

## Slide 7 — Candidate novelty and evidence

**On slide**

- **Candidate contribution:** an executable migration-time behavior contract
  that combines sufficient guards, replayed failures, and guard coverage for
  typed validation/filter/projection pipelines.
- Pilot: **3 public datasets, 5,926 distinct rows, 10 injected migration cases**.
- Result: **3 record-lossy cases proved preserved; 1 guarded split case; no observed
  guard-admitted violation** in this pilot.

**Say:** The three datasets are Abalone, Iris, and red Wine Quality. Their rows
are real, but all schema changes in the study were injected by us. The nine
numeric cases all receive a schema-level `lossy` label, while the checker
proves three safe pipelines. Eight predeclared negative controls and four CSV
parity checks passed. The dataset outcome checks support the implementation;
the universal claim for a supported rule rests on its stated proof premises.
The schema label and lineage checks are internal ablations, not competing
systems. [Pilot data and raw results](../evaluation/README.md);
[paper draft](paper-draft.md).

**Visual:** three horizontal bars showing guard admission on the three public
CSVs, alongside the pilot totals (`3` datasets, `5,926` distinct rows, `10`
injected cases). Show the Iris split guard admitting 150 of 150 rows.

## Slide 8 — Boundary and next research step

**On slide**

- Present guarantee: explicit one-step mapping on well-typed legacy rows at
  migration time.
- Open research: independent novelty/proof review and a documented real
  schema history.
- Deliberately deferred: standalone new-schema rewrite, new-only guards,
  general split/merge proofs, arbitrary expressions, and multi-version chains.

**Say:** This is a scoped research result and a reproducible pilot. It cannot
yet claim an observed organizational migration or correctness for arbitrary
new-schema rows. A knowledgeable reader should try to falsify the proof and
check the closest prior work before a submission claim is finalized. The
supervisor must select the venue and decide whether this evidence fits its
paper type. [Council review](council-review-2026-10-08.md);
[remaining tasks](paper-research-tasks.md).

**Visual:** a boundary box labeled “proved now” and a short adjacent list
labeled “future work.”

## Primary literature for slide 4

- Curino, Moon, and Zaniolo, [*Graceful Database Schema Evolution: The PRISM
  Workbench*](https://www.vldb.org/pvldb/vol1/1453939.pdf), VLDB 2008.
  Schema modification operators, impact analysis, migration, and legacy query
  translation.
- Fan, Geerts, and Zheng, [*View Determinacy for Preserving Selected
  Information in Data Transformations*](https://www.pure.ed.ac.uk/ws/portalfiles/portal/17752772/paper_viewd.pdf),
  *Information Systems* 37(1), 2012. Selected-information preservation is
  already a formal research subject.
- Kramer, Restat, and Störl,
  [*Robustness of Data Pipelines in the Context of Schema Evolution*](https://www.vldb.org/2025/Workshops/VLDB-Workshops-2025/QDB/QDB25_4.pdf),
  QDB at VLDB 2025. This closer pipeline-level work studies operator
  robustness under ADD, DELETE, and RENAME and conceptual self-adaptation.
- Wang, Dillig, Lahiri, and Cook, [*Verifying Equivalence of Database-Driven
  Applications*](https://arxiv.org/abs/1710.07660), 2017. Mediator checks
  application equivalence across database schemas.
- Kawaguchi, Lahiri, and Rebelo, [*Conditional
  Equivalence*](https://www.microsoft.com/en-us/research/publication/conditional-equivalence/),
  Microsoft Research technical report, 2010. Equivalence under a subset of
  program inputs predates this work.
- Herrmann et al., [*Living in Parallel Realities: Co-Existing Schema Versions
  with a Bidirectional Database Evolution
  Language*](https://arxiv.org/abs/1608.05564), 2017. BiDEL/InVerDa supports
  coexisting schema versions and bidirectional evolution.

## Claim discipline for anyone turning this into slides

- Say **candidate novelty** until an independent domain reader reviews the
  venue-specific literature. Never say “first,” “general equivalence,” or
  “automatic query rewriting.”
- Call the three dataset mappings **synthetic/injected**. The real rows do not
  make the migration histories real.
- Distinguish a rule's mathematical guarantee from zero violations observed
  in the finite pilot. A guard's coverage percentage is specific to the CSV
  measured.
- Preserve the expression `Obs(P, A(F(s)))` or an equivalent two-path diagram.
  Replacing it with an unspecified `P_new` would overstate the implementation.
