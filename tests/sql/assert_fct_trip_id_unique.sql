SELECT trip_id, count(*) AS n FROM {{ ref('fct_trips') }} GROUP BY trip_id HAVING count(*) > 1
