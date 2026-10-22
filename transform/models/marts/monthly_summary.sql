-- Income, consumption and savings rate per month, in NOK.
-- * Transfers are neither income nor consumption.
-- * Legs awaiting transfer review are left out of both until answered;
--   open_review_legs shows how many, so a month with open items is provisional.
-- * Crypto rewards have no NOK value until M3 and are only counted.
with tx as (
    select * from {{ ref('fct_transactions') }}
),

monthly as (
    select
        date_trunc('month', booked_on)::date as month,
        coalesce(sum(amount_nok) filter (where kind = 'income'), 0) as income_nok,
        coalesce(-sum(amount_nok) filter (where kind = 'consumption'), 0) as consumption_nok,
        coalesce(-sum(amount_nok) filter (where transfer_status = 'matched' and amount < 0), 0) as transfers_out_nok,
        count(*) filter (where kind = 'reward' and amount_nok is null) as unvalued_reward_rows,
        count(*) filter (where transfer_status = 'review') as open_review_legs
    from tx
    group by 1
)

select
    month,
    income_nok,
    consumption_nok,
    transfers_out_nok,
    round((income_nok - consumption_nok) / nullif(income_nok, 0), 4) as savings_rate,
    unvalued_reward_rows,
    open_review_legs
from monthly
order by month
