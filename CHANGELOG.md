# Changelog

All notable changes to this project will be documented in this file.

## [v0.1.0] - 2026-09-21
### Added
- NY Trend Continuation strategy with strict rule-based execution.
- ForexFactory NewsFilter to embargo trades around major USD events.
- Complete API key authentication for the FastAPI backend.
- `dotenv` for secrets management.

### Fixed
- Dead `max_trailing_dd_pct` config value not being respected by PropFirmGuard.
- Position sizing mixing up `point` and `tick_size`.
- `requirements.txt` mixed UTF-8/UTF-16 encoding.
- Missing crash isolation in the main loop of `main.py`.
- Unhandled `None` responses from `mt5.order_send()`.
- Emergency close loop lacking retries and verification.

### Changed
- Standardized documentation to a single root `README.md`.
- Restricted FastAPI CORS to localhost.
- Re-bound local dev startup scripts to `127.0.0.1`.
