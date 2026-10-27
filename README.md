# nyc-taxi-duckdb-lakehouse

A local, reproducible analytics pipeline over the real NYC yellow taxi trip
records for January 2016 (10.9 million rows, 1.6 GB of CSV). It turns the raw
file into a curated fact table and three marts, quarantines every bad row with
a named reason, and proves with tests that no row went missing.

It runs on a laptop with DuckDB. There is no cluster and no cloud account.

## Why this exists

Real data is dirty, and the interesting engineering is deciding what to do
about it. Profiling the raw file found, among other things, 171,704 pickups
outside New York City (170,212 of them at coordinates `0,0`), 64,065 trips of
zero distance and 31 trips that end before they start. This project makes
those decisions explicit and auditable instead of silently filtering rows.

## Architecture

```
CSV (1.6 GB) --ingest--> Parquet, ZSTD (237 MB) --view--> raw_trips
raw_trips --> stg_trips (typed, reject_reason on every row)
stg_trips --> fct_trips            (accepted rows, enriched)
          --> trips_rejected       (quarantine, with reason)
fct_trips --> agg_hourly_demand | agg_pickup_grid | agg_tip_by_payment
```

| Layer | Models | Purpose |
|---|---|---|
| Raw | `raw_trips` | Parquet over the untouched CSV, all columns as text |
| Staging | `stg_trips` | Type casting and one reject reason per row, nothing dropped |
| Curated | `fct_trips`, `trips_rejected` | Accepted rows and quarantined rows, split on the reason |
| Marts | `agg_*` | Hourly demand, ~500 m pickup hotspots, tip behaviour by payment method |

Design decisions worth being able to explain:

- **Raw stays text.** Casting happens in staging with `try_cast`, so a malformed
  value becomes a NULL that a rule can catch instead of crashing the load.
- **Quarantine, don't delete.** Rejected rows go to `trips_rejected` with a
  reason code. Reconciliation test: `raw = curated + rejected`.
- **One reason per row, ordered.** A row is reported under the first rule it
  breaks, so counts add up and the reason table is a clean partition.
- **Parquet between CSV and the warehouse.** Columnar and compressed: 1.6 GB
  became 237 MB, and later steps read only the columns they need.

## Quick start

```bash
# Run the unit tests (uses a 10-row fixture, no data needed)
make test

# Full pipeline: place yellow_tripdata_2016-01.csv in data/raw/ first
# (public NYC TLC trip record data), then:
make all
```

Requires Python 3 (standard library only; tested on 3.14) and the `duckdb` CLI on your PATH.

## Results (measured on a 16 GB laptop)

| Measure | Value |
|---|---|
| Raw rows | 10,906,858 |
| Curated (`fct_trips`) | 10,677,977 |
| Quarantined (`trips_rejected`) | 228,881 |
| Full model build, 6 models | 6 to 7 seconds (3 runs) |
| Busiest pickup hour | 18:00 (678,277 trips) |
| Credit card tips | 22.7% average, 96.6% of trips tipped |
| Cash tips | recorded as 0 in this dataset (cash tips are not captured) |

Reject reasons (each row counted once, under the first rule it breaks, so
these differ slightly from the raw profile above): `pickup_outside_nyc` 159,238, `nonpositive_distance` 64,065,
`nonpositive_fare` 5,304, `invalid_passenger_count` 158,
`distance_over_100_miles` 85, `dropoff_before_pickup` 31.

## Data tests

`tests/sql/*.sql` follow the dbt singular-test convention: a query that returns
failing rows, and the test passes when it returns none. They cover the
raw-to-curated reconciliation, a unique trip id, non-null required columns,
value ranges, accepted payment methods and mart totals. `tests/test_runner.py`
also checks that a corrupted table makes a test fail, so a green run is not
vacuous.

## The runner and dbt

`lakehouse/runner.py` is a zero-dependency stand-in for dbt that reads `{{ ref('model') }}` and `{{ source('raw', 'trips') }}`, resolves the dependency DAG, materialises models, and runs tests.

For full dbt workflows, the project includes `dbt_project.yml`, `profiles.yml`, and `schema.yml` configurations powered by `dbt-duckdb`:

```bash
# Build all models and execute singular and schema tests:
make dbt-build
# or directly:
.venv/bin/dbt build --profiles-dir .
```

The staging model runs as a view directly querying the underlying raw parquet file via `sources.yml`, while fact and aggregate marts materialise as DuckDB tables.


## Known limits

- One month of data. The grid cells are fixed-size, not true geohashes.
- The pickup bounding box is a rectangle around the city, so a few points in
  nearby water or New Jersey are still accepted.
- Zone-level analysis is not possible: this 2016 file has coordinates, not the
  location ids introduced later.
- The runner executes models sequentially and rebuilds them fully each run.
  Incremental models are the natural next step.
