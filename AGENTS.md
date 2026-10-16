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

## Session handoff
- At the end of meaningful project work, update `PROJECT_STATUS.md` with decisions, verification results, and remaining tasks.
- Keep that file short and current. Do not copy chat transcripts or secrets into it.
