# Docs
## Bot commands
### # poe2scout 
To retrieve data about current currency market prices I use 
[poe2scout.com's website free API](https://api.poe2scout.com/swagger/index.html) <br>

When it comes to making good looking embeds to nicely display all desired currency prices all I had to do was create empty discord servers just to add emojis (it's a workaround for emoji limit of 50 for free servers) because the bot can use all emojis that it has access to on any server it's on.

### # gibcat
It's just a simple call to a [free cat pic API](https://thecatapi.com)

## Util scripts
### # get_currency_icons.py
Script that automatically downloads icons of all currencies from a given category (provided by a valid url to poe2scout.com API). <br>
File names of icons are set as 'apiId' of each currency so that it's then easier to match them later in `bot/util/item_emojis.json`. <br>
To run the script you have to: <br> 
```python get_currency_icons.py <path_to_folder> <poe2scout_api_url>```

## Item emojis
`bot/util/item_emojis.json` maps item API IDs (and indicators such as `green-up`)
to Discord emoji strings. Edit this JSON object to add or replace an emoji:

```json
{
  "exalted": "<:exalt:1355493424207237210>"
}
```

Both market commands load this file through `bot/util/emoji_loader.py`.
Restart the bot after editing it. The JSON file is versioned and included in
the Docker image by the existing `COPY bot ./bot` instruction.

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
with item emojis and green/red change indicators. Names are shortened to 28
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
