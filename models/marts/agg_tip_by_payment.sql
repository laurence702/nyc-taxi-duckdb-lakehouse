-- materialized: table
-- Cash tips are not recorded in this dataset, so tip statistics are only
-- meaningful for card payments. The table keeps all methods to make that
-- visible instead of hiding it.
SELECT
    payment_method,
    count(*)                                   AS trips,
    round(avg(tip_ratio) * 100, 1)             AS avg_tip_pct,
    round(100.0 * count(*) FILTER (WHERE tip_amount > 0) / count(*), 1) AS pct_with_tip
FROM {{ ref('fct_trips') }}
GROUP BY payment_method
