select
    currency,
    rate_date,
    nok_per_unit,
    source
from {{ source('ledger', 'raw_fx_rates') }}
