-- materialized: table
-- One row per accepted trip, enriched with the fields analysts filter on.
SELECT
    trip_id,
    vendor_id,
    pickup_at,
    dropoff_at,
    CAST(pickup_at AS DATE)                      AS pickup_date,
    hour(pickup_at)                              AS pickup_hour,
    dayname(pickup_at)                           AS pickup_weekday,
    passenger_count,
    trip_distance_mi,
    duration_min,
    CASE WHEN duration_min > 0
         THEN trip_distance_mi / (duration_min / 60.0) END AS avg_speed_mph,
    round(floor(pickup_lat / 0.005) * 0.005, 3)  AS pickup_grid_lat,
    round(floor(pickup_lon / 0.005) * 0.005, 3)  AS pickup_grid_lon,
    CASE payment_type
        WHEN 1 THEN 'credit_card'
        WHEN 2 THEN 'cash'
        WHEN 3 THEN 'no_charge'
        WHEN 4 THEN 'dispute'
        ELSE 'other'
    END                                          AS payment_method,
    fare_amount,
    tip_amount,
    total_amount,
    CASE WHEN fare_amount > 0 THEN tip_amount / fare_amount END AS tip_ratio
FROM {{ ref('stg_trips') }}
WHERE reject_reason IS NULL
