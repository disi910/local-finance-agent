-- Kraken ledger rows.
-- * Kraken labels some fiat funding legs with wallet "unknown". They belong to
--   the spot wallet: trade groups span both.
-- * ".HOLD" assets (EUR.HOLD) are card-funded balances on hold, in the same
--   currency.
-- * "Buy crypto" appears as spend + receive legs sharing a refid, so both are
--   trades just like trade/tradespot.
with ledgers as (
    select *, split_part(raw_type, '/', 1) as kraken_type
    from {{ source('ledger', 'raw_transactions') }}
    where source = 'kraken'
)

select
    transaction_id,
    source,
    case when account = 'kraken:unknown' then 'kraken:spot-main' else account end as account,
    booked_on,
    occurred_at,
    regexp_replace(asset, '\.HOLD$', '') as asset,
    amount,
    fee,
    regexp_replace(fee_asset, '\.HOLD$', '') as fee_asset,
    case
        when kraken_type = 'deposit' then 'deposit'
        when kraken_type = 'withdrawal' then 'withdrawal'
        when kraken_type in ('trade', 'spend', 'receive') then 'trade'
        when raw_type = 'earn/reward' or kraken_type in ('staking', 'reward') then 'reward'
        when kraken_type in ('earn', 'transfer') then 'internal'  -- moves between Kraken wallets
        else 'other'
    end as event_type,
    group_id,
    description,
    raw_type,
    source_file,
    source_row
from ledgers
