-- Every matched pair takes money out of one account and puts it into another.
-- Automatic matches must also balance: exactly for the same asset, within the
-- FX tolerance across currencies. Manual matches are the user's call.
select m.pair_id
from {{ ref('transfer_matches') }} as m
inner join {{ ref('int_transactions') }} as o on o.transaction_id = m.out_id
inner join {{ ref('int_transactions') }} as i on i.transaction_id = m.in_id
where
    o.amount >= 0
    or i.amount <= 0
    or o.account = i.account
    or (
        m.match_method = 'unique'
        and (
            (o.asset = i.asset and o.amount + i.amount <> 0)
            or (
                o.asset <> i.asset
                and abs(o.amount_nok + i.amount_nok) > {{ var('fx_tolerance_pct') }} * abs(o.amount_nok)
            )
        )
    )
