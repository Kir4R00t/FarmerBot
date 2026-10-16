# FarmerBot

Python Discord bot for [xfarmerx's Discord server](https://discord.com/invite/bsjQV4tFMf). The Docker runtime uses Python 3.12.

## Commands and features

- `/poe2scout <currency_type> <reference_currency>` queries poe2scout directly for currency prices. The league is currently hardcoded in `bot/commands/poe2scout.py`.
- `/market-menu` browses Cloudflare R2 snapshot prices, top gainers, and top losers in paginated tables. Switch between currency items/uniques and exalted/chaos/divine references. Movers compare the latest two eligible snapshots and show signed percentage changes and recorded quantity (`Qty`); this is not verified traded volume. Data freshness depends on the upstream snapshots.
- `/gibcat` returns a random cat image from The Cat API.
- Price-check moderation deletes messages with attachments that lack the expected Path of Exile trade URL in the two configured price-check channels. Channel IDs are hardcoded in `bot/events/on_message_actions.py`; review them when using another server.
- The user configured by `DEV_ID` can send `ping` to receive `pong`.

## Local setup

Use Python 3.12 to match Docker. Run the following commands from the repository root.

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a `.env` file in the repository root with your own values:

```dotenv
DC=your_discord_bot_token
DEV_ID=your_numeric_discord_user_id
CAT_API=your_cat_api_key

# Required for /market-menu
R2_ENDPOINT=https://your_account_id.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_BUCKET=your_snapshot_bucket
# Optional: restrict snapshot discovery to a prefix
R2_SNAPSHOT_PREFIX=
R2_REGION=auto
```

`DC` and a numeric `DEV_ID` are needed at startup. `CAT_API` is used by `/gibcat`. R2 configuration is loaded when `/market-menu` is invoked; `R2_BUCKET_ID` is also accepted as a bucket-name alias. The bot reads existing consolidated snapshots; it does not collect or refresh them.

Enable the privileged intents requested by `Intents.all()` in the Discord Developer Portal, and invite the bot with the `bot` and `applications.commands` scopes. Give it permissions to view channels, send messages, embed links, and manage messages in the configured moderation channels.

Start the bot:

```bash
python -m bot.main
```

Startup connects to Discord, registers event handlers, and syncs slash commands globally. Use a dedicated test server when checking live behavior.

Emoji mappings are versioned in `bot/util/item_emojis.json`; restart the bot after editing them.

## Docker

With `.env` configured:

```bash
docker compose up -d --build
```

Compose passes `.env` into the container. The image copies the `bot/` package and installs runtime dependencies. The existing GitHub Actions workflow deploys on pushes to `main` using the configured VPS secrets; review `.github/workflows/deploy.yml` before pushing to that branch.

## Automated tests and coverage

In an activated virtual environment:

```bash
python -m pip install -r requirements-dev.txt
python tools/run_tests.py
```

The offline runner blocks live network connections and fakes external services. It prints results and coverage, and writes:

- `reports/coverage/index.html`: browsable coverage with missing lines and branches.
- `reports/coverage.xml`: coverage for CI/reporting tools.
- `reports/coverage.json`: machine-readable coverage.

Reports are ignored by Git and regenerated on each run. Test failures produce a nonzero exit code; coverage reports are still written. For one module, run `python -m unittest tests.test_snapshot_reader -v`.

See [TESTING.md](TESTING.md) for test scope and coverage limitations, [DOCS.md](DOCS.md) for command details, and [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md) for pipeline design. [PROJECT_STATUS.md](PROJECT_STATUS.md) records current implementation decisions and remaining work.

## Repository hygiene and contributing

Git ignores local environment files, credentials under `.aws/`, virtual environments, Python caches, coverage reports, downloaded `icons/`, root `output.json`, logs, editor settings, and local agent state. Shared instructions (`AGENTS.md`), tests, documentation, and emoji mappings remain versionable. Placeholder-only `.env.example` files are allowed.

Before committing, review `git status --short`, `git diff`, and `git diff --cached`. Ignore rules do not remove files already tracked by Git or erase earlier commits; keep credentials out of source and documentation.

Fork the repository, create a feature branch, make focused changes, run the offline checks, and open a pull request.

## Terms and privacy

- [Terms of Service](TERMS_OF_SERVICE.md)
- [Privacy Policy](PRIVACY_POLICY.md)

For Discord verification, publish these files in a public repository and enter their
full GitHub file URLs in the application’s **General Information → Terms of Service
URL / Privacy Policy URL** fields. Open both links while signed out to confirm they
are accessible. GitHub Pages is optional. Review the support contact and deployed
host’s logging practices before publishing; the policy describes the current code
and does not promise an automatic log-retention limit.

## License

[MIT](LICENSE).
