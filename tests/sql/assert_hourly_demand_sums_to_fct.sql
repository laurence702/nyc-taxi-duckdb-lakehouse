SELECT a.total AS hourly_total, f.total AS fct_total
FROM (SELECT sum(trips) total FROM {{ ref('agg_hourly_demand') }}) a,
     (SELECT count(*) total FROM {{ ref('fct_trips') }}) f
WHERE a.total <> f.total
