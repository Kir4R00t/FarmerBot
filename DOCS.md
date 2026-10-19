# Docs
## Bot commands
### # poe2scout 
To retrieve data about current currency market prices I use 
[poe2scout.com's website free API](https://api.poe2scout.com/swagger/index.html) <br>

Custom emoji references can point to application-owned or server-owned emojis.
The older setup used extra servers for emoji storage; the mapping strings alone
do not identify where an emoji is hosted. Discord documents a limit of
[2,000 application-owned emojis](https://docs.discord.com/developers/resources/emoji#application-owned-emoji),
managed through the Developer Portal or API. A regular unboosted server has
[50 static and 50 animated slots](https://discord.com/blog/beginners-guide-to-custom-emojis).
These are separate quotas; do not apply the server limit to the application.

### # gibcat
It's just a simple call to a [free cat pic API](https://thecatapi.com)

## Emoji maintenance

The versioned audit and downloader let each contributor check emoji coverage.
Run these commands from the repository root after installing the project
requirements:

```bash
python tools/audit_item_emojis.py --league 'Runes of Aldur'
python helpful_scripts/get_currency_icons.py emoji_audit/icons/missing-soul-cores --report emoji_audit/reports/missing-item-emojis.json --category ultimatum
```

The audit creates `emoji_audit/reports/missing-item-emojis.json`. This report,
local findings, saved catalogues, and downloaded icons stay in Git-ignored
`emoji_audit/`. Documentation contains instructions rather than a published
missing-item count or list. Contributors regenerate their own results locally.
The bot depends only on its runtime mapping and shared lookup code.

Only NPC currency-exchange categories in `bot/util/emoji_loader.py` are checked;
uniques, non-exchange categories, and separators are excluded. Review that
allowlist when upstream categories change. Use `--input path/to/items.json`
to audit a saved `/Items` response, or `--output path/to/report.json` to choose
a different destination; keep custom outputs in an ignored folder.

For an application upload plan, optionally supply `--application-emoji-count N`
with the current full Developer Portal inventory, including unused uploads.
The report deduplicates mapped IDs and estimates one new upload per missing key.
Without that inventory, capacity remains explicitly unverified. An over-limit
plan exits with code 2. Application and server quotas are separate; this tool
does not check server capacity or upload emojis.

The downloader also accepts a catalogue/category URL instead of `--report`.
It accepts PascalCase/camelCase fields, filters non-exchange entries even from
older reports, and uses full API IDs as filenames. Repeat `--category` to select
several categories or omit it for all eligible entries. Existing files are
preserved. Missing URLs, HTTP failures, and non-PNG responses produce a nonzero
exit status while other downloads continue. Requests use timeouts. Category
URLs process only the supplied page; use a complete `/Items` catalogue or its
audit for full coverage.

Run `python tools/run_tests.py` to check runtime and maintenance behavior with
external services faked and network connections blocked.

## Item emojis
`bot/util/item_emojis.json` maps item API IDs (and indicators such as `green-up`)
to Discord emoji strings. Edit this JSON object to add or replace an emoji:

```json
{
  "exalted": "<:exalt:1355493424207237210>",
  "default-item": "📦"
}
```

Both market commands load this file through `bot/util/emoji_loader.py`.
Restart the bot after editing it. The JSON file is versioned and included in
the Docker image by the existing `COPY bot ./bot` instruction.

An unmapped exchange item uses `default-item`, with 📦 as the built-in fallback. It reserves
an emoji position before the monospace cells instead of a narrow text bullet.
You can replace `default-item` with a custom Discord emoji reference. Actual
spacing still depends on the Discord client, and long rows may wrap on small
screens. The legacy command also keeps missing items, cutting large results at
whole rows with a note directing users to `/market-menu`.

Unique and non-exchange item rows show their names/prices without an item emoji
or placeholder. Their price-reference currency markers and change indicators
remain available; the item rows and ranking headers start at the text column.

Mapping keys must retain the full currency API ID. The emoji name
inside `<:name:id>` can be shorter; copying that short name into the JSON key
can prevent lookup even when the emoji is already uploaded.

## Market menu price layout
`/market-menu` category pages use the original `/poe2scout` table style:
item emoji, a single monospace span with the name on the left and price on the
right, currency emoji, and a change indicator. Column widths are measured across
the category so they stay consistent between pages. Names longer than 40
characters are shortened with an ellipsis; line breaks and backticks are
normalized to keep each item on one row. Missing comparisons show `---`.
Existing currency selection, divine conversion, snapshot metadata, and
pagination remain available.

### Top gainers and top losers
Open `/market-menu`, then choose **Top Gainers** or **Top Losers**. Category
pages now show 15 category buttons to leave space for these two entry points.
Ranking pages show aligned **Item**, **Price**, **Change**, and **Qty** columns,
with item emojis for exchange currencies and green/red change indicators. Names are shortened to 28
characters in rankings, and column widths stay consistent between pages.

- Gainers rank the largest positive percentage first; losers rank the largest
  negative percentage first. Changes that round to zero are omitted.
- Buttons switch direction, currency items/uniques, and reference currency.
  Direction/type/reference changes return to the first ranking page. **Categories**
  returns to the previous category page with the selected reference preserved.
- Price and percentage always use the selected reference in these rankings;
  expensive items are not automatically converted to divines. A change in the
  selected currency's value can also affect the reported percentage.
- Comparisons use the newest two snapshots, matching realm, league, item kind,
  category, identity, and reference. Unique names bridge older snapshots that
  lacked stable IDs. Missing matches, ambiguous duplicates, invalid prices, and
  nonpositive previous prices are excluded. A current price of zero can show a
  100% loss. Missing or invalid quantity displays `—`.
- **Qty** is `current_quantity` from the newer snapshot. Its upstream meaning
  has not been verified; it is not labeled as traded volume. No arbitrary
  minimum quantity is imposed, so small-quantity outliers remain visible.
- Comparison timestamps, collection interval, snapshot age, and observation
  staleness are shown. No fixed one-hour interval is assumed. Two chronologically
  ordered snapshots are needed; the menu disables entry buttons with only one.

Ranking calculations live in `bot/services/market_movers.py`, independent of
Discord. This feature does not implement arbitrage or change collection in R2.
