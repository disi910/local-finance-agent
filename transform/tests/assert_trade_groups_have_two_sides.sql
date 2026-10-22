-- A trade (one Kraken refid) gives up one asset and receives another. A
-- one-sided trade means an export is missing rows; worth a look, but it should
-- not block the rest of the build.
{{ config(severity='warn') }}

select group_id
from {{ ref('fct_transactions') }}
where kind = 'trade'
group by group_id
having count(*) filter (where amount < 0) = 0
    or count(*) filter (where amount > 0) = 0
