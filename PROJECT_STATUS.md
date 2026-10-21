# Project status

Updated: 2026-10-21

## Current decisions
- Changelog updates are required for every PR merged into `main`, including documentation-only changes and hotfixes. Keep the upcoming entry current on `dev` across sessions, with a new release version and matching final PR title; follow [the full changelog and versioning rules](AGENTS.md#changelog-and-versions).
- Work on `dev`. The pagination module is `bot/commands/pagination.py`, its class is `Pagination`, and startup/exports/tests use the new names. The rename preserves command behavior; the user confirmed `/market-menu` works in Discord.
- Local `origin/main` at `9ab32e2` contains PR #11 and release `0.1.0`. That changelog entry is preserved. Pending work is recorded under `0.1.1` with draft PR title `Rename pagination module and organize project tools`; local `main` was not modified.
- Runtime item emojis apply only to the shared NPC currency-exchange category allowlist plus legacy `idols`. Unique/non-exchange rows have no item emoji or placeholder; reference markers and change indicators remain. Exact full API IDs stay mapping keys; fallback is configurable `default-item` (📦).
- Supported commands are consolidated under `tools/`; tests/docs use the new paths. The user wants current documentation and active assets, without archived investigations, old audit runs, or session-review notes. The snapshot investigation, local archive, and superseded review/cleanup reports have been removed along with their references.
- Current DEV PNGs remain in ignored `icons/missing_exchange/`, with `icons/farmerbot_dev_emojis.zip`. Active manifests/catalogues and the inventory export remain under ignored `emoji_audit/`. Runtime mappings are unchanged; DEV uploads need their own IDs.
- Architecture docs describe implemented bot-side movers and planned warehouse/arbitrage work. `.dockerignore` limits the build context to runtime inputs.
- The user considers the table alignment sufficient with Unicode `heavy-equals-sign` (🟰) for neutral changes and has decided against adding percentage padding for now. The neutral branch emits fixed `+0.00%`, preventing `+-0.00%` for tiny negative changes. Keep the current row spacing; no padding work is pending.

## Verification
- All 104 offline Python tests pass via `/tmp/farmerbot-pagination/bin/python -B tools/run_tests.py` on Python 3.14.8, with 99.78% bot coverage. The new regression test reproduced the tiny-negative formatting bug before the fix, then passed for unchanged, tiny negative, and tiny positive prices. Existing zero-change expectations now reflect the intended `+0.00%` display. The neutral-formatting fix was not verified live in Discord.
- Verified active runtime/tools/tests, DEV icons/ZIP, inventory, and current reports against pre-removal SHA-256 hashes. Current file links and whitespace checks pass. No bot behavior changed in the removal.
- The helper relocation passed downloader smoke checks from `/tmp` and 42 exporter assertions in a JavaScript V8 isolate. Node.js and Docker Buildx are unavailable; no image build or Python 3.12 execution was verified locally. No live bot run, emoji upload, or deployment was performed.
- The user authorized focused commits and a push to `dev`. Changes are grouped into the pagination rename, neutral-formatting fix, helper relocation, Docker context filtering, documentation cleanup, and release handoff. Generated downloads/audit data stay ignored; `main` is unchanged.

## Remaining work
- Ensure the `0.1.1` heading matches the final PR title and let Python 3.12 CI verify the changes before release.
- Before further emoji upload planning, confirm the actual target application's current quota and complete inventory, including unused uploads; local mapping counts are not a live inventory check.
- `/market-menu` reads R2 snapshots; legacy `/poe2scout` calls PoE2Scout directly. Restart after a separately authorized runtime deployment. Movers retain **Qty**; upstream volume semantics and current collector freshness remain unresolved.
- Confirm operator contact and hosting practices before publishing privacy/terms documents.
