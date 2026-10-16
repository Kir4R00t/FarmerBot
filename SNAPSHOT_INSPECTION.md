# Real R2 snapshot inspection

Inspected on 2026-10-16 using read-only listing/download operations through the
project's configured R2 reader. No cloud objects or application behavior changed.
Raw downloads remain in `/tmp/farmerbot-real-snapshots.json`, outside the repository.

## Scope and freshness

- Found 600 matching snapshot objects under the configured bucket/prefix.
- Downloaded the two newest eligible partitioned snapshots:
  - `470c6f52-ce4a-4af9-a933-8b344d512cbb`, captured `2026-08-31T17:20:22Z`.
  - `36853f29-7617-44aa-b7fc-8f84942a2369`, captured `2026-08-31T16:20:22Z`.
- Both are for PoE2, league `Runes of Aldur`, and contain 3,276 records.
- These are historical data relative to the inspection date. This does not
  establish whether collection stopped, configuration points at an archive,
  or newer data exists elsewhere. Do not describe these as today's prices.

## Actual schema

Each file is an array with these fields:

```text
schema_version (integer, 1)
snapshot_id, captured_at, realm, league
item_kind, category, api_id, name
reference_currency, current_price, current_quantity
price_observed_at (timestamp string or null)
source_page (integer)
```

All prices in these two samples are positive numbers and all quantities are
positive integers. No item/reference identities are duplicated. There are
1,092 distinct items: 643 currency-kind items and 449 uniques, each appearing
once per reference currency (`exalted`, `chaos`, `divine`). Currency-kind here
includes categories such as essences, runes, fragments, and gems.

A real example from the newest snapshot:

```json
{
  "item_kind": "currency",
  "category": "currency",
  "api_id": "mirror",
  "name": "Mirror of Kalandra",
  "reference_currency": "exalted",
  "current_price": 2578175.0,
  "current_quantity": 15,
  "price_observed_at": "2026-08-31T16:00:00.0000000Z"
}
```

## Price changes and freshness

All 1,092 item identities match between snapshots in each reference currency.
In exalted, 514 of 643 currency-kind prices changed. All 449 unique exalted
prices and quantities remained unchanged. Nevertheless, 209 unique chaos
prices and 427 unique divine prices changed. Those converted-price changes
must not automatically be interpreted as independent unique-item activity.

The newest snapshot has observation timestamps for 615 of 643 currency-kind
items, ranging from 11:00 to 16:00 UTC. The other 28 currency-kind items and
all 449 uniques lack them. Even a newly collected snapshot can therefore
contain older observations. For 83 currency-kind items, the non-null observation
timestamp did not advance between these two collections.

An unfiltered ranking in exalted produces these historical examples:

| Item | Previous | New | Change | Recorded quantity |
| --- | ---: | ---: | ---: | ---: |
| Perfect Essence of Flames | 0.5 | 27.75741 | +5,451.48% | 13 |
| Rune of Consistency | 3 | 123.28211 | +4,009.40% | 3 |
| Idol of the Martyr | 27.478018 | 0.14285715 | -99.48% | 7 |

These are computed movements in recorded prices, not verified profitable trades.
229 of 643 currency-kind items have recorded quantity at most five. Quantity,
minimum-price, observation-age, and outlier filters should be configurable.

## Arbitrage and volume limitations

For all 643 currency-kind items, converting chaos/divine prices back to exalted
uses effectively the same rates: approximately 33.3478 exalted per chaos and
360.8463 exalted per divine. Variation across items is below 0.00003%, consistent
with numeric rounding. This strongly suggests the reference prices are derived
conversions rather than independent pair quotes.

All 1,092 items repeat the same quantity across their three reference rows.
That quantity must not be summed three times. The snapshot contains no explicit
traded-volume window, trade count, bid/ask prices, order-book levels, or
directional execution depth. Its `current_quantity` semantics cannot be proven
from these records alone; retain the neutral label "quantity" until the
upstream definition is verified. Changes in quantity do not establish sales.

Different unique-item conversion factors also occur within a snapshot. Without
observation timestamps or executable quotes, these inconsistencies are data
quality/freshness questions, not evidence of executable arbitrage.

## Recommended feature scope

1. Implement gainers/losers with a fixed, selected reference currency, matching
   league/realm/item/category/reference identities, showing actual comparison
   times and quantity. Require a positive previous price and expose freshness
   and quantity filters. Separate currency-kind and unique rankings.
2. Add quantity rankings/change and historical price views with accurate labels.
3. Investigate the stale configured dataset before calling reports current.
4. For trade-volume or arbitrage rankings, extend collection with timestamped
   pair-level activity and verify its units and observation window. Executable
   arbitrage additionally needs directional prices and available depth/costs.
   PoE2Scout's [API reference](https://api.poe2scout.com/swagger/index.html)
   lists `SnapshotPairs` and currency-pair history endpoints worth investigating;
   their suitability and field semantics were not validated in this inspection.

This inspection supports building historical market movers now. It does not
support presenting executable trade returns or verified trading volume.
