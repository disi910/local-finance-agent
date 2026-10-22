# Source formats

Column layouts of each export, as reported by `local-finance-agent inspect`. This file lists headers and types only, never real values.

## DNB (account transactions, Excel)

- File: `.xlsx` from the online bank's transaction list. One sheet, `Siste transaksjoner`, with the header on the first row.
- One account per file. The file has no account column, so the account is given on import: `--account dnb:brukskonto`. Importing the same file under a second account is refused.
- Parser settings are constants at the top of `src/local_finance_agent/ingest/dnb.py`.

| Column | Type | Used as |
|---|---|---|
| `Dato` | Excel date (text `dd.mm.yyyy` also accepted) | `booked_on` |
| `Forklaring` | text | `description` |
| `Rentedato` | Excel date | not used (value date) |
| `Ut fra konto` | Excel number or empty | outflow; sign ignored, always stored negative |
| `Inn på konto` | Excel number or empty | inflow |

Rows without a date (blank or summary rows) are skipped. DNB has no transaction IDs, so IDs are hashes plus an occurrence number (see `ingest/ids.py`).

## Kraken (Ledgers export, CSV)

- File: comma-separated, UTF-8 with BOM, one row per ledger entry.
- Required columns: `txid`, `refid`, `time`, `type`, `asset`, `amount`, `fee`. Rows without a `txid` are pending entries and are skipped.

| Column | Type | Used as |
|---|---|---|
| `txid` | text | `source_id`, and the transaction ID (`kraken:<txid>`) |
| `refid` | text | `group_id`; links the legs of one event, e.g. spend + receive |
| `time` | datetime `yyyy-mm-dd hh:mm:ss[.ffff]`, UTC | `occurred_at`, `booked_on` |
| `type`, `subtype` | text | `raw_type` as `type/subtype` |
| `aclass` | text (`currency`) | not used |
| `subclass` | text (`crypto`, `fiat`, `hold`, `stable_coin`) | not used |
| `asset` | text | `asset`, with legacy codes normalized (`XXBT` → `BTC`, `ZEUR` → `EUR`) |
| `wallet` | text (`spot / main`, `unknown`) | account, e.g. `kraken:spot-main` |
| `amount`, `fee` | number, dot decimal | `amount`, `fee` (read as text, never float) |
| `balance` | number, dot decimal | not used |
| `amountusd`, `feeusd`, `balanceusd` | number, dot decimal | not used |
| `feecurrency` | text or empty | `fee_asset` (falls back to `asset`) |

Older exports lack `subclass`, the `*usd` columns and `feecurrency`; the parser works with both.

`raw_type` values seen so far, and how the dbt staging model reads them:

| `raw_type` | `event_type` |
|---|---|
| `deposit`, `withdrawal` | `deposit`, `withdrawal` |
| `trade/tradespot`, `spend`, `receive` | `trade` ("Buy crypto" is a spend + receive pair sharing a `refid`) |
| `earn/reward`, `reward/welcomebonus` | `reward` |

Wallet `unknown` appears on some fiat funding legs and is treated as the spot wallet. `EUR.HOLD` is a card-funded balance on hold and is treated as `EUR`.

## Firi

Not available yet: no export has been inspected, and there is no parser.

## Norges Bank exchange rates (CSV)

- Endpoint: `https://data.norges-bank.no/api/data/EXR/B.<CUR>+<CUR>.NOK.SP?format=csv&startPeriod=…&endPeriod=…&locale=en`. The request contains only currency codes and dates.
- Semicolon-separated, one row per currency and business day. Columns used: `BASE_CUR`, `TIME_PERIOD` (`yyyy-mm-dd`), `OBS_VALUE` (dot decimal), `UNIT_MULT` (power of ten: `0` for EUR/USD, `2` for SEK/DKK, which are quoted per 100).
- Stored as NOK per single unit in `raw_fx_rates`.
