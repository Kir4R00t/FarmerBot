# Testing FarmerBot

Use Python 3.12 to match Docker. Install `requirements-dev.txt` in a virtual
environment and run `python tools/run_tests.py` from the project root. The
runner also accepts invocation by absolute path from another directory.

The suite uses Python's built-in `unittest` and `coverage.py` for reporting.
It needs no bot token, `.env` file, Discord server, or R2 account. Network
connections are blocked by the report runner: an accidentally unmocked network
call fails locally. Tests that construct the application replace `.env` loading
and supply fake environment values.

## What is tested

| Area | Behavior checked |
| --- | --- |
| Emoji JSON | Loading outside the project directory, mapping validation, shared command data |
| Legacy market command | Percentage direction and magnitude, zero/invalid history, league rates, item filters, empty/populated embeds, HTTP/network failures, deferred replies |
| Snapshot data and embeds | Categories, numeric validation, sorting, price formatting, divine conversion, comparisons using historical exchange rates, missing history, timestamps/staleness, pagination, table alignment across pages, safe/shortened names |
| Discord views | Owner checks, enabled/disabled controls, button callbacks, category/reference/item navigation, returning to categories |
| Snapshot command | Registration, lazy reader setup, reference fallback, empty categories, configuration/storage failures, sending a menu |
| Market movers | Signed ranking/order/ties, zero and invalid prices, matching scope, duplicate exclusion, missing/invalid quantity, fixed reference prices, aligned tables, all navigation controls, insufficient history, embed size limits |
| R2 reader | Configuration, paginated listings, TTL/refresh/clear, LRU eviction, body cleanup, JSON and metadata validation, latest-N selection, capture/partition consistency, storage failures |
| Cat command | Image replies, empty API results, HTTP and network failures |
| Events and startup | Bot-message exclusion, developer ping, moderation in both pricecheck channels, ready/sync behavior including errors and no guilds, module registration, token forwarding, entrypoint |

Tests use real Discord command registration, embeds, and views where practical.
Interaction response methods are `AsyncMock` objects, HTTP responses are fakes,
and R2 uses a fake S3 client and in-memory object bodies. Command tests replace
`asyncio.to_thread` with an awaitable that executes the fake dependency inline;
they assert dispatch and responses without testing Python's thread pool.

## Reading the report

Open `reports/coverage/index.html` in your browser. Select a module to see
unexecuted lines and branch outcomes. The function index shows coverage grouped
by function. Coverage includes every Python module under `bot`, including the
namespace directory `bot/services`. No executable bot functions are omitted and
there are no custom coverage exclusions. Coverage.py's defaults exclude the
type-only `S3Client` Protocol declaration; the real reader implementation is
fully measured. The local maintenance scripts and test tooling itself are outside the bot
coverage scope.

Line coverage asks whether a statement ran. Branch coverage asks whether each
control-flow outcome ran. The terminal's `Cover` column combines both; the XML
and JSON reports also expose separate totals. Neither metric proves correctness
or exhaustively covers all possible inputs. Assertions check expected results,
not just whether code executes.

The initial expanded suite leaves one defensive outcome unexecuted in
`create_category_embed`: skipping a nonnumeric price a second time after
`_records_for_category` has already removed it. That gap remains visible; no
test invents an impossible filter result just to reach 100%.

Live Discord permissions, network behavior, command synchronization against
Discord, and actual cloud credentials are not verified by these offline tests.
Those need a separate integration run with a dedicated test bot/server.

## Local emoji maintenance tests

The Git-ignored `emoji_audit/` folder holds the missing-emoji audit, downloader,
and their dedicated tests. When present, run `python emoji_audit/run_tests.py`
from the repository root to run both the versioned suite and local maintenance
tests with network access blocked and the same bot coverage reports. The normal
`python tools/run_tests.py` command does not depend on those local files, which
are absent from fresh clones.
