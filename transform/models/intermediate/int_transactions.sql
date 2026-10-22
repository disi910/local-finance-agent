-- One row per leg from every source, with a NOK value where one can be
-- computed without prices: NOK as-is, fiat at the latest Norges Bank rate on
-- or before the booking date (at most a week old). Crypto stays NULL until
-- prices are added in M3.
with legs as (
    select * from {{ ref('stg_dnb__transactions') }}
    union all by name
    select * from {{ ref('stg_kraken__ledgers') }}
),

fx as (
    select * from {{ ref('stg_fx_rates') }}
)

select
    legs.*,
    case
        when legs.asset = 'NOK' then legs.amount
        when date_diff('day', fx.rate_date, legs.booked_on) <= 7 then round(legs.amount * fx.nok_per_unit, 2)
    end::decimal(18, 2) as amount_nok
from legs
asof left join fx
    on legs.asset = fx.currency
    and legs.booked_on >= fx.rate_date
