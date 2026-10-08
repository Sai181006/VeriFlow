# VeriFlow research presentation

The current, editable eight-slide PowerPoint is
[veriflow-research-blue-bell-v2.pptx](output/veriflow-research-blue-bell-v2.pptx).
It follows the [presentation brief](../docs/presentation-brief.md). The
research question, concrete truncation example, related-work comparison,
two-path guarantee, checker flow, pilot evidence, and scope are explained on
the slides. Full paper links and methodological qualifications are in the
speaker notes.

The deck was created with the bundled presentation artifact tool. The
[v2 builder](src/build_research_redesign_v2.mjs) and
[cover artwork](assets/cover-blue-bell.png) are kept here for revision. The
cover was made with the built-in image generator from this visual brief:
“A restrained, flat academic data-migration graphic in deep violet and Blue
Bell tones; data rows and mapping lines on the right; dark open title space on
the left; no text or logos.” Technical diagrams, comparison table, and evidence
bars are editable PowerPoint objects. The earlier
[v1 redesign](output/veriflow-research-redesign-v1.pptx) and
[v3 deck](output/veriflow-research-brief-v3.pptx) remain available for reference.
The v3 deck's
[Material Symbols assets](assets/) are covered by the included
[Apache 2.0 license](assets/LICENSE).

The color system follows the opaque [Blue Bell palette](https://uicolors.app/generate/9999cc)
from [UI Colors](https://uicolors.app/generate/99c3). The supplied `99c3`
seed resolves to a translucent color, so the deck uses the corresponding
opaque `#9999CC` ramp. Background `#F3F4FA`, text `#2B293D`, and emphasis
`#6A649E` keep the body copy readable; green and rust retain their meaning for
preserved and conditional/breaking outcomes. [General Sans on
Fontshare](https://www.fontshare.com/fonts/general-sans) guided the weight and
size hierarchy. The PPTX uses Segoe UI for reliable rendering without a font
installation, with Consolas for code and equations.

The visual direction draws on academic database-systems talks and
[assertion-evidence guidance](https://www.writing.engr.psu.edu/research.html):
claim headlines, one technical argument per slide, and visible primary-work
citations. Examples reviewed include [CMU database-group research
slides](https://db.cs.cmu.edu/files/slides/2024/iap/Disaggregated-DB-World-IAP-2024.pdf)
and [Harvard Catalyst's scientific slide guidance](https://catalyst.harvard.edu/writing-communication-center/visualize-science/slides/).

The study numbers are from [evaluation/results.json](../evaluation/results.json),
with details in the [evaluation guide](../evaluation/README.md). The dataset
rows are public, and the schema changes in the pilot are synthetic. The
contribution is labelled *candidate* because an independent domain review of
novelty and proof is still pending.
