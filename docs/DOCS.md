# Docs
## Data Engineering Layer
The project now has a PostgreSQL-backed market data pipeline in `bot/data`.

The pipeline:
1. extracts poe2scout market categories,
2. stores raw JSON responses,
3. validates and transforms item prices and `PriceLogs`,
4. loads dimension, snapshot fact and price-history fact tables,
5. records ETL status and data quality issues.

Run it locally:

```bash
python -m bot.data.pipeline
```

Run it through Docker Compose:

```bash
docker compose --profile jobs run --rm market-ingestion
```

More details are documented in `docs/architecture.md`.

## Bot Commands
### poe2scout
To retrieve data about current currency market prices I use
[poe2scout.com's website free API](https://poe2scout.com/api/swagger#/).

When it comes to making good looking embeds to nicely display all desired
currency prices, I use Discord emojis uploaded to servers that the bot can
access.

### etlstatus
Shows recent ETL runs saved in PostgreSQL.

### topmovers
Shows items with the largest price changes based on stored historical snapshots.

### pricehistory
Shows saved poe2scout price log history for a selected item.

### gibcat
It's just a simple call to a [free cat pic API](https://thecatapi.com).

## Util Scripts
### get_currency_icons.py
Script that automatically downloads icons of all currencies from a given
category provided by a valid poe2scout API URL.

File names of icons are set as `apiId` of each currency so that it is easier to
match them later in the item emojis file.

To run the script:

```bash
python get_currency_icons.py <path_to_folder> <poe2scout_api_url>
```
