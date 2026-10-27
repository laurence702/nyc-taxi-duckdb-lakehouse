SELECT DISTINCT payment_method FROM {{ ref('fct_trips') }}
WHERE payment_method NOT IN ('credit_card', 'cash', 'no_charge', 'dispute', 'other')
