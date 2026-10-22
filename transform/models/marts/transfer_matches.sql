-- Transfers between own accounts. Pairs accepted in review-transfers come
-- first. Of the remaining strict candidates, a pair is matched automatically
-- only when it is the only one for both of its legs; anything less certain
-- goes to transfer_review.
with candidates as (
    select * from {{ ref('int_transfer_candidates') }}
),

legs as (
    select transaction_id from {{ ref('int_transactions') }}
),

accepted as (
    select d.out_id, d.in_id
    from {{ source('ledger', 'transfer_decisions') }} as d
    where d.decision = 'accept'
        and d.out_id in (select transaction_id from legs)
        and d.in_id in (select transaction_id from legs)
),

open_candidates as (
    select
        *,
        count(*) over (partition by out_id) as out_candidates,
        count(*) over (partition by in_id) as in_candidates
    from candidates
    where is_strict
        and out_id not in (select out_id from accepted)
        and in_id not in (select in_id from accepted)
),

matches as (
    select out_id, in_id, 'manual' as match_method from accepted
    union all
    select out_id, in_id, 'unique' as match_method
    from open_candidates
    where out_candidates = 1 and in_candidates = 1
)

select
    'pair:' || left(md5(out_id || '|' || in_id), 16) as pair_id,
    out_id,
    in_id,
    match_method
from matches
