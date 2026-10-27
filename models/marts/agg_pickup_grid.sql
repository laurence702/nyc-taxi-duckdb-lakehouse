-- materialized: table
-- Roughly 500 metre cells; cells with fewer than 100 trips are dropped so
-- the hotspot ranking is not dominated by noise.
SELECT
    pickup_grid_lat,
    pickup_grid_lon,
    count(*)                    AS trips,
    round(avg(fare_amount), 2)  AS avg_fare
FROM {{ ref('fct_trips') }}
GROUP BY pickup_grid_lat, pickup_grid_lon
HAVING count(*) >= 100
