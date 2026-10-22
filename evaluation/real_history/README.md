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
