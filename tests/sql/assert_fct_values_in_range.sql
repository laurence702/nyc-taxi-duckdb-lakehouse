SELECT trip_id FROM {{ ref('fct_trips') }}
WHERE passenger_count NOT BETWEEN 1 AND 6
   OR trip_distance_mi <= 0 OR trip_distance_mi > 100
   OR fare_amount <= 0 OR dropoff_at < pickup_at
