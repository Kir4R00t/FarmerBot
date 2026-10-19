# Project status

Updated: 2026-10-19

## Current decisions
- Work on `dev`, tracking `origin/dev`; working directly on `main` requires an explicit instruction for the task.
- Runtime emojis apply only to NPC currency-exchange categories, using the shared allowlist in `bot/util/emoji_loader.py` plus legacy `idols`. Unique/non-exchange rows have no item emoji or placeholder; price-reference markers and change indicators remain. Review the allowlist when upstream categories change.
- Missing exchange mappings use configurable `default-item` (📦). Legacy results retain unmapped items and truncate oversized descriptions at whole rows with a `/market-menu` hint.
- Repaired nine truncated mapping keys, reused 24 exact-image emoji references, and removed 19 out-of-scope keys. Existing shared-key values are preserved. No Discord emojis were uploaded or deleted.
- Emoji audit/download tools, dedicated tests, and neutral instructions are versioned for contributors. Generated missing-item reports/counts/lists, saved catalogues, icons, and session findings remain local-only under Git-ignored `emoji_audit/`. The audit creates that folder when needed; the bot never reads it. Do not publish dated audit findings in shared docs.
- The user clarified that reusable tools should be available in a future `main` release, while generated findings stay local. Changes remain on `dev`; `main` has not received the runtime emoji fixes or new audit workflow.

## Verification
- Reviewed every changed/new file from the previous session. Saved catalogue checks confirm the 17 exchange categories plus legacy alias, nine key repairs, all 24 exact-image aliases, and 19 out-of-scope removals.
- Python 3.14.8 temporary environment, dependencies installed from `requirements-dev.txt`: all 96 versioned offline tests pass via `python -B tools/run_tests.py`, including audit/downloader tests and a regression for creating the default report in the ignored workspace. The runner blocks network access and fakes external services; no local findings/assets are required.
- Bot coverage is 99.78%, with all bot modules included. Inspected gaps: defensive numeric skip after prior filtering (`pagination_test.py:433`) and oversized-description loop exhaustion (`poe2scout.py:137->143`). No exclusions added. Reports are under ignored `reports/`.
- Audit paths resolve from the repository root independently of the working directory. Generated reports default to the ignored workspace. Public documentation links target versioned instructions, with no current missing-item count/list. Ignore rules, syntax parsing, and `git diff --check` checked.
- Python 3.12/Docker and live Discord rendering remain untested. No bot startup, live-resource changes, or deployment performed.

## Remaining work
- Verify the actual target application's complete emoji inventory before planning uploads; mapping counts alone are unverified. Findings and capacity details remain in the local audit folder.
- `/market-menu` reads R2 snapshots; legacy `/poe2scout` calls PoE2Scout directly. Legacy API URLs are unchanged. Restart the bot after a separately authorized runtime deployment.
- Movers retain **Qty**; upstream trading-volume semantics and current collector freshness remain unresolved. Prior findings are in `SNAPSHOT_INSPECTION.md`.
- Confirm operator contact and hosting practices before publishing privacy/terms documents.
