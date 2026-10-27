-- materialized: table
-- Quarantine: every trip the pipeline refused, with the reason, so data
-- loss is visible and auditable rather than silent.
SELECT trip_id, pickup_at, trip_distance_mi, fare_amount, total_amount,
       passenger_count, pickup_lon, pickup_lat, reject_reason
FROM {{ ref('stg_trips') }}
WHERE reject_reason IS NOT NULL
