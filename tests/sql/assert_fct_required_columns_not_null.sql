SELECT trip_id FROM {{ ref('fct_trips') }}
WHERE pickup_at IS NULL OR dropoff_at IS NULL OR fare_amount IS NULL
   OR total_amount IS NULL OR payment_method IS NULL
