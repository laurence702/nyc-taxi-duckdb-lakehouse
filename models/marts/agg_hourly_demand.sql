-- materialized: table
SELECT
    pickup_date,
    pickup_hour,
    count(*)                         AS trips,
    round(avg(fare_amount), 2)       AS avg_fare,
    round(avg(trip_distance_mi), 2)  AS avg_distance_mi,
    round(median(avg_speed_mph), 1)  AS median_speed_mph
FROM {{ ref('fct_trips') }}
GROUP BY pickup_date, pickup_hour
