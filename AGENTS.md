# Working on FarmerBot

## Project map
- Python Discord bot. The Docker runtime uses Python 3.12.
- `bot/main.py`: loads `.env`, constructs the bot, and registers commands/events.
- `bot/commands/`: Discord commands, including market prices and cat images.
- `bot/events/`: Discord event handlers.
- `bot/services/r2_snapshot_reader.py`: synchronous Cloudflare R2 snapshot reader.
- `bot/services/market_movers.py`: Discord-independent gainers/losers ranking. `current_quantity` is not verified trading volume; keep the UI label `Qty` until its upstream meaning is established.
- `README.md` and `DOCS.md`: setup and usage; `DATA_FLOW_ARCHITECTURE.md`: data pipeline design. Check code before assuming documentation describes implemented behavior.

## Collaboration
- At the start of every session, check the current Git branch and work on `dev` by default. If needed, switch to the existing `dev` branch (or create it tracking `origin/dev`) before making project changes. Preserve any uncommitted work; do not discard it to switch branches.
- Never work directly on `main` unless the user explicitly instructs you to do so for the current task. General permission to implement, commit, or push changes does not authorize working on `main`.
- The user is learning agentic coding. Briefly explain consequential choices and how changes are verified.
- Read `PROJECT_STATUS.md` when starting a new session. Verify its claims against relevant code before relying on them.
- Keep changes focused on the requested task and follow nearby code conventions.
- Make routine, reversible implementation decisions independently. Ask when missing requirements materially change behavior or scope.

## Implementation and verification
- Keep Discord handlers responsive. Run synchronous network operations outside the event loop, for example with `asyncio.to_thread`.
- Keep storage/data logic separate from Discord presentation where practical.
- For behavior changes, use focused tests covering observable behavior and relevant failure cases. Fake external services in automated tests.
- Install test dependencies with `python -m pip install -r requirements-dev.txt`. Run `python tools/run_tests.py` for offline tests and terminal/HTML/XML/JSON coverage reports. For focused tests use `python -m unittest tests.test_snapshot_reader -v`. No lint configuration is currently provided. Do not describe syntax checks as behavioral tests.
- Keep all `bot` modules in coverage reporting. Inspect missing lines and branches instead of excluding functions to improve the percentage. Coverage records execution, not correctness; use assertions about observable behavior.
- For Python syntax validation without starting the bot or producing bytecode:
  `python3 -c "import ast, pathlib; files = list(pathlib.Path('bot').rglob('*.py')); [ast.parse(p.read_text(), filename=str(p)) for p in files]; print(f'Parsed {len(files)} Python files')"`
- Report what changed, checks run, and any remaining limitations.

## Credentials and external actions
- Never print or commit `.env` contents, tokens, or cloud credentials. Use variable names or placeholders in documentation.
- Local bot startup (`python -m bot.main`) connects to Discord and can trigger event handlers. Prefer offline verification unless a live run is requested.
- Do not deploy, push, or change live Discord/cloud resources unless the task authorizes it.

## Emoji maintenance and release scope
- Item emojis are only for NPC currency-exchange items. Exclude unique equipment and other non-exchange items from audits, downloads, and upload budgets; their market rows have no item emoji or fallback placeholder. Keep price-reference currency markers and change indicators. Use PoE2Scout's `CurrencyCategories` boundary, not merely a nonempty API ID; review the shared category allowlist when upstream categories change.
- Keep reusable emoji audit/download scripts, their dedicated tests, and neutral usage instructions versioned so contributors can run checks themselves. Keep generated reports, missing-item counts/lists, saved catalogues, downloaded icons, and session findings local-only under Git-ignored `emoji_audit/`; do not force-add them or publish current audit findings in shared documentation. Tools may be included in a future release to `main`; this does not authorize editing or publishing `main`.
- Runtime emoji mappings, the default emoji/fallback behavior, and relevant bot tests may be proposed for `main` so the deployed bot can use them. The runtime must not depend on the audit or downloader.
- Before recommending emoji uploads, check the current Discord quota for the actual target (application versus server), count distinct uploaded emoji IDs rather than JSON mapping keys, and include unused uploads in that target's inventory. Reused emoji references and the Unicode fallback consume no new slots. Label mapping-only capacity estimates as unverified; never treat them as a live inventory check.
- When preparing a release, include runtime changes and reusable maintenance tools/tests/instructions as appropriate, while keeping generated audit results local. Preserve test imports and documentation links when selecting changes. This preference does not authorize editing `main`, publishing, or deleting helper scripts already present there.

## Session handoff
- At the end of meaningful project work, update `PROJECT_STATUS.md` with decisions, verification results, and remaining tasks.
- Keep that file short and current. Do not copy chat transcripts or secrets into it.
