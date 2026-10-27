SELECT trip_id FROM {{ ref('trips_rejected') }} WHERE reject_reason IS NULL
