-- Every plausible (out-leg, in-leg) pair between two different own accounts.
-- * Same asset: amounts must cancel exactly. This also works for crypto,
--   which has no NOK value yet.
-- * Different fiat assets: NOK values close enough to allow for FX spread
--   and card fees.
-- is_strict pairs are within transfer_window_days / fx_tolerance_pct and may
-- be matched automatically. The rest, up to review_window_days /
-- review_fx_tolerance_pct, are only offered as near misses for review.
-- Pairs rejected in review-transfers are dropped.
with legs as (
    select * from {{ ref('int_transactions') }}
),

outs as (
    select * from legs where amount < 0 and event_type in ('bank', 'withdrawal')
),

ins as (
    select * from legs where amount > 0 and event_type in ('bank', 'deposit')
),

rejected as (
    select out_id, in_id
    from {{ source('ledger', 'transfer_decisions') }}
    where decision = 'reject'
),

pairs as (
    select
        o.transaction_id as out_id,
        i.transaction_id as in_id,
        date_diff('day', o.booked_on, i.booked_on) as day_gap,
        case
            when o.asset = i.asset then 0
            else round(abs(i.amount_nok + o.amount_nok) / abs(o.amount_nok), 4)
        end as amount_gap_pct
    from outs as o
    inner join ins as i
        on i.account <> o.account
        and abs(date_diff('day', o.booked_on, i.booked_on)) <= {{ var('review_window_days') }}
    where
        (o.asset = i.asset and i.amount = -o.amount)
        or (
            o.asset <> i.asset
            and abs(i.amount_nok + o.amount_nok) <= {{ var('review_fx_tolerance_pct') }} * abs(o.amount_nok)
        )
)

select
    pairs.*,
    abs(day_gap) <= {{ var('transfer_window_days') }}
        and amount_gap_pct <= {{ var('fx_tolerance_pct') }} as is_strict
from pairs
anti join rejected using (out_id, in_id)
