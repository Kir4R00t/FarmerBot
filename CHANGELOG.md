# [0.1.1]/Rename pagination module and organize project tools

- Changed the market menu module and class names to `pagination.py` and `Pagination`.
- Changed the neutral price-change indicator to 🟰 and fixed tiny negative changes displaying `+-0.00%`.
- Changed emoji helper paths to `tools/`; update saved helper commands to the new paths.
- Updated pipeline architecture documentation and removed obsolete investigation notes.
- Added Docker build context filtering for runtime files.

# [0.1.0]/Fix market emoji rendering and add emoji maintenance tools

- Added `/market-menu` with snapshot prices, gainers, losers, and pagination.
- Added `/poe2scout`, `/gibcat`, and price-check moderation.
- Added emoji audit, icon download, and application emoji export tools.
- Added offline tests, coverage reports, and Python 3.12 CI.
- Expanded emoji mappings and limited item emojis to exchange categories.
- Fixed missing-emoji items disappearing and oversized legacy market results.
- Fixed price-change calculations and handling of empty results and request failures.
