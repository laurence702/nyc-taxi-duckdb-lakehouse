-- Reconciliation: no trip may vanish between raw and the curated/quarantine split.
SELECT r.n AS raw_rows, f.n AS fct_rows, q.n AS rejected_rows
FROM (SELECT count(*) n FROM {{ source('raw', 'trips') }}) r,
     (SELECT count(*) n FROM {{ ref('fct_trips') }}) f,
     (SELECT count(*) n FROM {{ ref('trips_rejected') }}) q
WHERE r.n <> f.n + q.n
