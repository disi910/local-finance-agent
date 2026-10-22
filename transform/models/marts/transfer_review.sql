-- Open questions for review-transfers:
-- * ambiguous: strict candidate pairs whose legs have more than one possible
--   match. Both legs are kept out of income and consumption until answered.
-- * near_miss: looser pairs (further apart in time or NOK value) for legs
--   with no strict candidate. Never matched automatically; the legs keep
--   their normal kind until a pair is accepted.
-- * unmatched_exchange_leg: exchange deposits/withdrawals with no candidate
--   at all, e.g. funded from an account not imported yet. Counted as
--   transfers, so they never become income or consumption.
-- Each row puts the leg leaving an account on the out_ side and the leg
-- entering one on the in_ side. anchor_side is the side whose leg has more
-- options, so review-transfers can ask one question per anchor leg.
with legs as (
    select * from {{ ref('int_transactions') }}
),

candidates as (
    select * from {{ ref('int_transfer_candidates') }}
),

matched_legs as (
    select out_id as transaction_id from {{ ref('transfer_matches') }}
    union
    select in_id from {{ ref('transfer_matches') }}
),

unmatched_candidates as (
    select *
    from candidates
    where out_id not in (select transaction_id from matched_legs)
        and in_id not in (select transaction_id from matched_legs)
),

ambiguous as (
    select * from unmatched_candidates where is_strict
),

ambiguous_legs as (
    select out_id as transaction_id from ambiguous
    union
    select in_id from ambiguous
),

near_misses as (
    select *
    from unmatched_candidates
    where not is_strict
        and out_id not in (select transaction_id from ambiguous_legs)
        and in_id not in (select transaction_id from ambiguous_legs)
),

candidate_legs as (
    select out_id as transaction_id from candidates
    union
    select in_id from candidates
),

unmatched_exchange_legs as (
    select
        case when amount < 0 then transaction_id end as out_id,
        case when amount > 0 then transaction_id end as in_id
    from legs
    where event_type in ('deposit', 'withdrawal')
        and transaction_id not in (select transaction_id from matched_legs)
        and transaction_id not in (select transaction_id from candidate_legs)
),

pairs as (
    select 'ambiguous' as reason, out_id, in_id, day_gap, amount_gap_pct from ambiguous
    union all
    select 'near_miss', out_id, in_id, day_gap, amount_gap_pct from near_misses
),

items as (
    select
        *,
        case
            when count(*) over (partition by reason, in_id) > count(*) over (partition by reason, out_id) then 'in'
            else 'out'
        end as anchor_side
    from pairs
    union all
    select
        'unmatched_exchange_leg', out_id, in_id, null, null,
        case when out_id is null then 'in' else 'out' end
    from unmatched_exchange_legs
)

select
    items.reason,
    items.anchor_side,
    items.out_id,
    o.booked_on as out_booked_on,
    o.account as out_account,
    o.asset as out_asset,
    o.amount as out_amount,
    o.amount_nok as out_amount_nok,
    o.description as out_description,
    items.in_id,
    i.booked_on as in_booked_on,
    i.account as in_account,
    i.asset as in_asset,
    i.amount as in_amount,
    i.amount_nok as in_amount_nok,
    i.description as in_description,
    items.day_gap,
    items.amount_gap_pct
from items
left join legs as o on o.transaction_id = items.out_id
left join legs as i on i.transaction_id = items.in_id
