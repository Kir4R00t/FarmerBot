# Project status

Updated: 2026-10-16

## Current focus
Expanded `/market-menu` with top gainers and top losers. Arbitrage is out of scope for now. Real snapshot findings remain in `SNAPSHOT_INSPECTION.md`.

## Established facts
- Added root `AGENTS.md` with project context, working rules, and verification guidance.
- Docker uses Python 3.12 and starts `python -m bot.main`.
- The market command currently calls poe2scout directly. The separate R2 snapshot reader is not wired into that command.
- Migrated all 271 emoji mappings from the Python module to `bot/util/item_emojis.json`, preserving the mapping exactly. The Python module was present when implementation began.
- Both market commands use `bot/util/emoji_loader.py`, which loads and validates JSON using a path relative to the module. Restart after emoji edits.
- Removed emoji filenames from `.gitignore` so the JSON mapping can be versioned and included in Docker builds.
- Empty or fully filtered market results now display “No prices available for this category.” instead of raising from `max()`.
- Added 76 offline tests across emoji loading, price calculations, market embeds/commands/views, gainers/losers, snapshot storage, cat replies, moderation, ready events, and startup. No lint configuration is currently provided.
- `requirements-dev.txt` adds coverage tooling. Run `python tools/run_tests.py` for terminal, HTML, XML, and JSON reports under `reports/` (ignored by Git); see `TESTING.md`.
- Regression tests prompted fixes for empty cat responses, network errors, missing market exchange rates, replying after deferral, ready handling with no guilds, and sync error logging.
- Fixed the legacy percentage formula to use `(new - old) / old * 100`; zero/invalid previous prices show unavailable change. Legacy HTTP calls now have timeouts and run outside the Discord event loop.
- Compared the original `main` branch command and the user's screenshot. Market-menu category pages now use padded name/price columns inside one inline-code span, with emojis outside. Widths remain stable across pages; long names are shortened to 40 characters and backticks/line breaks normalized. Missing history displays `---`. Navigation, conversions, and snapshot metadata are preserved.
- Read-only live R2 inspection found 600 matching objects. The two newest eligible snapshots are from 2026-08-31 at 17:20:22Z and 16:20:22Z, each with 3,276 rows (1,092 items across three reference currencies). Raw copies are temporary, outside the repo.
- Historical market movers are feasible. Currency reference prices appear derived from common exchange rates; snapshots lack explicit traded volume, bid/ask quotes, and directional depth. `current_quantity` meaning remains unverified. The configured dataset is stale relative to 2026-10-16; the cause has not been diagnosed.
- Added independent mover calculations in `bot/services/market_movers.py`. The menu has Top Gainers/Top Losers buttons and 15 categories per page. Ranking tables show Item, Price, signed Change, and Qty with pagination, direction/type/reference switching, and return navigation. Prices use one fixed selected reference; quantities are not described as traded volume. No arbitrary quantity threshold is applied.
- Rankings exclude unmatched/ambiguous identities, invalid prices, nonpositive historical prices, and changes that display as zero. They show comparison timestamps, collection interval, snapshot age, and observation staleness. Currency items and uniques have separate views.

## Repository hygiene
- Expanded `.gitignore` for environment variants, local AWS/agent state, virtual environments, Python/build/tool caches, reports, logs, and editor/OS files. Removed broad `test.*`; tests, shared instructions, documentation, and emoji JSON remain versionable. Placeholder `.env.example` files are allowed.
- Updated README against startup, commands, R2 configuration, moderation, Docker, deployment workflow, and offline test runner. Existing feature changes were preserved.
- Verified 27 ignore-rule cases, no tracked files matching ignore rules, all five local README links, and `git diff --check`. Documentation/ignore changes only; behavioral tests and live startup were not run for this task.

## Verification
- All 76 tests passed: `/tmp/farmerbot-verification/bin/python -B tools/run_tests.py`; coverage reports regenerated. Runner was also verified from outside the repository directory during initial setup.
- Coverage: 99.85% combined; the new market-mover service has 100% line/branch coverage. All executable bot functions are exercised. One defensive skip after numeric filtering remains unexecuted and visible. Default coverage exclusions apply to the type-only S3Client Protocol.
- Checked all 170 ranking pages from the two downloaded real snapshots across direction, item kind, and reference: aligned columns, correct pagination, and Discord description/total embed size limits. Representative payloads are in ignored `reports/market-movers-examples.json`.
- Syntax validation and `git diff --check` passed.
- Tests used a temporary Python 3.14 environment with Discord and requests dependencies. Docker's Python 3.12 runtime was not exercised.
- Bot not connected to Discord. A later read-only live R2 inspection successfully downloaded and validated two real snapshots through the existing reader; details are in `SNAPSHOT_INSPECTION.md`. Error-path test fixtures produce expected handled logs. Command unit tests fake thread dispatch; Python thread-pool behavior is outside their scope.

## Next task
- Review the gainers/losers views in a dedicated Discord test server when requested. Upstream quantity semantics and configured dataset freshness remain unresolved; no collection or arbitrage changes were made.
