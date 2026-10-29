# NYC 311 documented field-addition case

The [NYC311 announcement of 23 April 2018](https://www.nyc.gov/311/nyc311-enhances-service-request-open-dataset.page)
states that the Service Request Open Dataset added **Intake Channel** and
**Borough-Block-Lot (BBL)**. The two pre-change request records in this fixture
were transcribed from the [2016 NYC 311 CSV excerpt shown in a data-storage
tutorial](https://alfa.im.pwr.edu.pl/~szwabin/assets/unst/lec/6.pdf): keys
`32950265` and `32950917`, agencies `DHS` and `NYPD`, and complaint types
`Homeless Person Assistance` and `Illegal Parking`.

The mapping reproduces the documented *addition of fields*, but uses explicit
empty-text defaults because the historical values of the two newly published
fields are unavailable in this old-row excerpt. This is a two-row reenactment
on real pre-change records, **not** an official migrated NYC snapshot and not
evidence that NYC used these defaults. The tested pipeline does not read either
new field. The case cannot establish behavior for pipelines using those fields,
large-file performance, or real lossy type changes. NYC later changed two
**display labels** without changing backend API names, as its [current update
notice](https://www.nyc.gov/opendata/news/all-news/311-Service-Requests-Updates)
states; those label changes are not modeled here as schema renames.

## Malaysian Ministry of Health ICU schema history

The [official public COVID-19 repository](https://github.com/MoH-Malaysia/covid19-public)
versions `epidemic/icu.csv`. Its [22 July 2021 commit](https://github.com/MoH-Malaysia/covid19-public/commit/4e80229047d796f14c7aac82910a3377277b699f)
renamed four `beds_icu*` columns to `bed_icu*` and removed `vent_sari`.
We use the commit's [immediate parent](https://github.com/MoH-Malaysia/covid19-public/commit/3b56bc326306a013d1fb26eb4f33084f432b4b4c)
as the before version and the commit itself as the after version. The official
repository's [license note](https://github.com/MoH-Malaysia/covid19-public/blob/4e80229047d796f14c7aac82910a3377277b699f/LICENSE.md)
points to Malaysian open-data terms; this study attributes the publisher and
retains its provenance.

[`prepare_moh_icu.py`](prepare_moh_icu.py) pins both official Git blob hashes,
projects only the fields used by this experiment, and verifies the included
projections. Run it without arguments to verify the local artifacts, or with
`--fetch` to regenerate them from the pinned official commits when network
access is available. The before and after projections contain **7,315** rows
with unique `(date, state)` keys. Every paired row matches after renaming
`beds_icu` to `bed_icu` and removing `vent_sari`; the other projected values
are unchanged. The removed field is nonzero on **4,060** rows, so its loss is
material in these data. The projections are derived from official snapshots;
they are not described as complete official CSV files.

Two predeclared pipelines study the same actual schema event:

| Pipeline | Old observation | Expected result |
| --- | --- | --- |
| [`moh_icu_preserved.vfl`](moh_icu_preserved.vfl) | Filters on `vent_covid` and selects capacity, date, and state; it never reads `vent_sari`. | The record is lossy, but the pipeline is preserved with no sidecar. |
| [`moh_icu_recovered.vfl`](moh_icu_recovered.vfl) | Filters on `vent_covid` and selects the dropped `vent_sari` value with date and state. | Sparse mode retains `vent_sari` on 4,025 emitted rows and no old cell on 3,290 filtered rows; guard-only rejects all rows under the static proof. |

The [evolution rule](moh_icu_evolution.vfl) is explicit. The three-strategy
[`migration_study.py`](../migration_study.py) compares each emitted new row with
the actual post-change projection by `(date, state)`, as well as replaying the
old pipeline's typed observation. This is one documented organizational change,
not evidence that the Ministry used VeriFlow or that its operational pipelines
matched these two experimental pipelines. Rows are reused between the two
pipeline cases, and the schema history has a drop and renames but no observed
decimal-to-integer change.
