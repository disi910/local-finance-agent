-- DNB account rows. Every row is a bank movement; whether it is a transfer,
-- income or consumption is decided after transfer matching.
select
    transaction_id,
    source,
    account,
    booked_on,
    occurred_at,
    asset,
    amount,
    fee,
    fee_asset,
    'bank' as event_type,
    group_id,
    description,
    raw_type,
    source_file,
    source_row
from {{ source('ledger', 'raw_transactions') }}
where source = 'dnb'
