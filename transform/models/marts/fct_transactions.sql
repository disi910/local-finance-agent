-- Every leg with what it means for my finances:
-- * transfer: money between own accounts (matched, awaiting review, or an
--   exchange deposit/withdrawal whose other side is not imported).
-- * income / consumption: bank movements that are not transfers.
-- * trade, reward, internal, other: from the exchange's own labels. Buying
--   assets is a trade, never consumption.
with legs as (
    select * from {{ ref('int_transactions') }}
),

matches as (
    select * from {{ ref('transfer_matches') }}
),

matched as (
    select out_id as transaction_id, in_id as counterpart_id, pair_id from matches
    union all
    select in_id, out_id, pair_id from matches
),

review_legs as (
    select out_id as transaction_id from {{ ref('transfer_review') }} where reason = 'ambiguous'
    union
    select in_id from {{ ref('transfer_review') }} where reason = 'ambiguous'
),

classified as (
    select
        legs.*,
        m.counterpart_id,
        m.pair_id,
        case
            when m.transaction_id is not null then 'matched'
            when r.transaction_id is not null then 'review'
            when legs.event_type in ('deposit', 'withdrawal') then 'unmatched'
        end as transfer_status
    from legs
    left join matched as m on m.transaction_id = legs.transaction_id
    left join review_legs as r on r.transaction_id = legs.transaction_id
)

select
    *,
    case
        when transfer_status is not null then 'transfer'
        when event_type = 'bank' and amount > 0 then 'income'
        when event_type = 'bank' and amount < 0 then 'consumption'
        when event_type = 'bank' then 'other'
        else event_type
    end as kind
from classified
