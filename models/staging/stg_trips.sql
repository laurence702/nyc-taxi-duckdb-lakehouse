-- materialized: view
-- Types the all-varchar raw layer and assigns at most one reject reason per
-- trip. Reasons are ordered from most to least fundamental so a row is
-- reported under the first rule it breaks.
WITH typed AS (
    SELECT
        file_row_number                              AS trip_id,
        try_cast(VendorID AS INTEGER)                AS vendor_id,
        try_cast(tpep_pickup_datetime AS TIMESTAMP)  AS pickup_at,
        try_cast(tpep_dropoff_datetime AS TIMESTAMP) AS dropoff_at,
        try_cast(passenger_count AS INTEGER)         AS passenger_count,
        try_cast(trip_distance AS DOUBLE)            AS trip_distance_mi,
        try_cast(pickup_longitude AS DOUBLE)         AS pickup_lon,
        try_cast(pickup_latitude AS DOUBLE)          AS pickup_lat,
        try_cast(dropoff_longitude AS DOUBLE)        AS dropoff_lon,
        try_cast(dropoff_latitude AS DOUBLE)         AS dropoff_lat,
        try_cast(payment_type AS INTEGER)            AS payment_type,
        try_cast(fare_amount AS DOUBLE)              AS fare_amount,
        try_cast(tip_amount AS DOUBLE)               AS tip_amount,
        try_cast(total_amount AS DOUBLE)             AS total_amount
    FROM {{ source('raw', 'trips') }}
)
SELECT
    *,
    date_diff('second', pickup_at, dropoff_at) / 60.0 AS duration_min,
    CASE
        WHEN pickup_at IS NULL OR dropoff_at IS NULL           THEN 'invalid_timestamp'
        WHEN dropoff_at < pickup_at                            THEN 'dropoff_before_pickup'
        WHEN trip_distance_mi IS NULL OR trip_distance_mi <= 0 THEN 'nonpositive_distance'
        WHEN trip_distance_mi > 100                            THEN 'distance_over_100_miles'
        WHEN fare_amount IS NULL OR fare_amount <= 0           THEN 'nonpositive_fare'
        WHEN total_amount IS NULL OR total_amount < 0          THEN 'negative_total'
        WHEN passenger_count IS NULL
             OR passenger_count NOT BETWEEN 1 AND 6            THEN 'invalid_passenger_count'
        WHEN pickup_lon IS NULL OR pickup_lat IS NULL
             OR pickup_lon NOT BETWEEN -74.3 AND -73.6
             OR pickup_lat NOT BETWEEN 40.45 AND 41.0          THEN 'pickup_outside_nyc'
    END AS reject_reason
FROM typed
