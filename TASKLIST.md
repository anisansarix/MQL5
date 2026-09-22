One important thing up front: **this repo already has a `ROADMAP.md` with a checklist, and most items are checked `[x]` — but I verified the actual code against every checked box, and several are false.** Files were "fixed" and then re-corrupted, or checked off without the corresponding code/tests actually existing. So this list is based on what the code _actually does right now_, not on the checkboxes. I'll flag which of my findings contradict an existing `[x]`.

Here are the tasks (later tasks depend on earlier ones not being broken).

---

## Tier 0 — The app cannot currently run at all. Fix these first.

**Task 1 — Recreate the missing `utils/notifier.py` module**
`risk_manager/prop_firm_guard.py` and `execution/mt5_executor.py` both do `from utils.notifier import send_alert`, but there is no `utils/` folder anywhere in the repo. Every import of `PropFirmGuard` or `MT5Executor` currently raises `ModuleNotFoundError` — meaning `main.py` cannot start at all. This is the single biggest blocker in the project.
Fix: create `PropFirm_System/utils/__init__.py` (empty) and `PropFirm_System/utils/notifier.py` exporting `send_alert(message: str, level: str = "INFO") -> None`. It should support Telegram webhooks read from environment variables (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`), no-op silently (just log) if none are configured, and never raise — a failed alert must never crash the trading loop. Add the new env vars to a `.env.example` (see Task 13).

**Task 2 — Fix the syntax error in `train_ibit.py`**
The file literally contains: ``from strategy.finrl_trainer import train_agent`ntrain_agent(symbol="IBIT", num_candles=20000)`` — a stray backtick-n has merged two lines into one invalid statement. This is a `SyntaxError` on any attempt to run it.
Fix: split into two real lines:

```python
from strategy.finrl_trainer import train_agent
train_agent(symbol="IBIT", num_candles=20000)
```

**Task 3 — Fix `requirements.txt` (still corrupted, and incomplete)**
`ROADMAP.md` checks off "fix mixed UTF-8/UTF-16 encoding" but it is still broken: `gymnasium`, `python-dotenv`, and `pytest` are UTF-16-encoded with embedded null bytes and have merged into one unparseable line (`gymnasiumpython-dotenv`). `pip install -r requirements.txt` will fail or silently skip these. It's also missing packages the code actually imports: `fastapi`, `uvicorn`, `pydantic`, `torch`.
Fix: delete the file and recreate it from scratch as plain UTF-8 (don't append to the old one), listing: `MetaTrader5`, `pandas`, `numpy`, `pytz`, `schedule`, `ta`, `finrl`, `stable-baselines3`, `gymnasium`, `python-dotenv`, `pytest`, `fastapi`, `uvicorn[standard]`, `pydantic`, `torch`. Verify with `file requirements.txt` (must say ASCII/UTF-8 text, not "data"), then `pip install -r requirements.txt` in a clean venv to confirm it resolves. Note in a comment that CUDA-enabled `torch` may need installing separately from PyTorch's own index if `pip install torch` gives a CPU-only build.

**Task 4 — Fix `.gitignore` (same corruption, still broken)**
`ROADMAP.md` checks off adding `*.log` and `strategy/models/*.zip` to `.gitignore`, but those two lines are UTF-16-encoded with embedded nulls, exactly like the requirements.txt bug — they will not function as ignore patterns.
Fix: rewrite `PropFirm_System/.gitignore` as plain UTF-8. Likely root cause: whenever content was appended to a file with a PowerShell redirect/here-string on Windows, it wrote UTF-16LE instead of UTF-8. Tell Antigravity to check every file it edits with `file <name>` afterward and never use `>>`/`Add-Content` for these edits — write the whole file with a proper UTF-8 writer instead.

**Task 5 — Fix the crash in `backtest/prop_firm_backtester.py`**
Line 76 reads `self.guard.max_total_loss_pct`. That attribute doesn't exist — `PropFirmGuard` was renamed to `max_trailing_dd_pct` (the exact rename `ROADMAP.md` already claims is done). This means the backtester raises `AttributeError` on the very first loop iteration and cannot have actually been run successfully, despite the roadmap checking off "Run PropFirmBacktester... walk-forward validate."
Fix: change to `self.guard.max_trailing_dd_pct`.

---

## Tier 1 — Money-safety and correctness bugs (fix before any demo/live run)

**Task 6 — Stop `calculate_position_size` from forcing a trade above the safe size**
In `risk_manager/prop_firm_guard.py`, the line `lot_size = max(symbol_info.volume_min, min(symbol_info.volume_max, target_lot_size))` means: if your risk-based or margin-capped size comes out _below_ the broker's minimum tradeable lot, the code silently bumps it back up to `volume_min` anyway — defeating the entire purpose of the risk/margin cap it just calculated. This can put on a larger position than your risk budget allows.
Fix: if `target_lot_size < symbol_info.volume_min`, return `0.0` (skip the trade) and log why, instead of forcing the minimum lot.

**Task 7 — Use broker server time, not local machine time, for the daily P&L reset**
`main.py`'s `save_state()` computes `today = datetime.now().replace(hour=0, ...)` — this uses the _host machine's_ local midnight to bound the "today's trades" query. Meanwhile `PropFirmGuard.get_daily_trades_count()` correctly derives "today" from the broker's tick timestamp. This inconsistency means the dashboard's displayed daily P&L can span the wrong window whenever your machine's timezone differs from the broker's server timezone — exactly the class of bug `ROADMAP.md` claims was tested for in Stage 2, but wasn't (see Task 10).
Fix: derive `today` in `save_state()` from `mt5.symbol_info_tick(...)` the same way `get_daily_trades_count()` does, not from `datetime.now()`.

**Task 8 — Don't ship `config.json` with `"bot_status": "running"`**
The committed `config.json` defaults to `"running"`. That means a fresh clone, a restarted machine, or a moment where you forgot to check `config.json` will start placing real trades the instant `main.py` launches and connects — with no explicit "go" from you.
Fix: default `bot_status` to `"stopped"` in the committed `config.json`, and only ever flip it to `"running"` deliberately from the dashboard.

**Task 9 — Fix the hardcoded symbol fallback in `get_daily_trades_count()`**
It hardcodes ticks from `"EURUSD"` then falls back to `"XAUUSD"` to get "current server time," regardless of what you're actually trading. If neither symbol happens to be in Market Watch, this silently falls back to local time.
Fix: pass in (or read from config) the actual traded symbol(s) and use the first configured symbol for the server-time lookup.

---

## Tier 2 — Testing & validation (the roadmap claims these exist — they don't)

**Task 10 — Actually write the pytest suite `ROADMAP.md` marks as done**
There is no `tests/` folder, no `test_*.py`, no `conftest.py` anywhere in the repo, despite Stage 2 of `ROADMAP.md` checking off three separate "write a test for..." items.
Fix: create `PropFirm_System/tests/` with:

- `conftest.py` that mocks the `MetaTrader5` module (so tests run without a live terminal) — mock `symbol_info`, `symbol_info_tick`, `account_info`, `history_deals_get`.
- `test_position_sizing.py`: assert `calculate_position_size` returns correct lot sizes when `point != tick_size` (e.g., mock gold-like symbol info), and returns `0.0` below `volume_min` (covers Task 6).
- `test_daily_reset.py`: assert `start_of_day_balance` resets on a broker-server-day rollover, not local midnight (covers Task 7).
- `test_risk_limits.py`: assert `check_risk_status()` returns `False` the instant equity crosses the configured `max_daily_loss_pct` / `max_trailing_dd_pct`, and that changing `config.json`'s value actually changes behavior (covers the original dead-config-value bug).

**Task 11 — Rebuild the backtester to test what you actually run**
`prop_firm_backtester.py` replicates an old EMA/RSI "golden cross" strategy that isn't used anywhere in production — it does not test `NYTrendContinuation` (your real, well-designed strategy per the roadmap) or `FinRLStrategy` (what `config.json` is currently set to run). Its PnL model is also fake: every stop-loss is hardcoded to exactly `-$500` and every take-profit to exactly `+$1000`, regardless of actual lot size, tick value, or price action.
Fix: rewrite it to (a) call `NYTrendContinuation.analyze_symbol()` bar-by-bar on historical data, (b) compute PnL from real lot size × tick value × exit price (using `PropFirmGuard.calculate_position_size`), and (c) add simple spread and slippage simulation on every simulated fill (since you execute `ORDER_FILLING_IOC` at market). Only after this rebuild does "walk-forward validate on 2023–2024 data" in Stage 2/4 mean anything.

**Task 12 — Add CI**
Add a GitHub Actions workflow that runs `pytest` (Task 10) and a lint pass (`ruff` or `flake8`) on every push, so a `requirements.txt`/`.gitignore`-style silent corruption (Tasks 3–4) is caught automatically instead of discovered live.

---

## Tier 3 — Security & config hardening

**Task 13 — Add a real `.env.example`**
No `.env` or `.env.example` exists anywhere, even though `api/server.py` reads `API_KEY` and `ALLOWED_ORIGIN` from the environment and falls back to the hardcoded default `dev_secret_key_change_me_in_production` if nothing is set. Add `PropFirm_System/.env.example` listing `API_KEY=`, `ALLOWED_ORIGIN=http://localhost:3000`, plus whatever webhook vars Task 1's notifier needs. Also make `api/server.py` log a loud `WARNING` on startup if it's still using the default dev key, so you notice if you forgot to set `.env`.

**Task 14 — Validate config on load**
`config_manager.py`'s `load_config()` does zero validation — a `config.json` with `max_daily_loss_pct: 0`, an empty `symbols_to_trade`, or a symbol not in Market Watch will only fail once the bot is already live. Add a validation pass that rejects/clamps obviously broken values and logs a clear error instead of letting the loop discover it mid-cycle.

**Task 15 — Surface config drift in the UI**
Since bugs like the original dead `max_trailing_dd_pct` value are exactly the kind of thing that's invisible until you go looking, have `save_state()` write both "config.json says X" and "guard is currently enforcing Y" into `state.json`, and have the frontend show a warning banner if they ever differ.

---

## Tier 4 — Frontend completeness

**Task 16 — Build the missing Configuration page**
The Next.js dashboard (`frontend/src/app/page.tsx`) only supports a Start/Stop toggle. The sidebar icons for a config/list/logs/settings view are decorative — no `onClick`, no routing, nothing behind them. Build an actual settings panel (new route or a modal) that lets you edit `symbols_to_trade`, `risk_per_trade_usd`, `strategy`, `model_path`, `timeframe`, `max_daily_loss_pct`, `max_trailing_dd_pct` and POSTs to the existing `/api/config` endpoint (which already supports this — it's just not wired up in the UI).

**Task 17 — Clean up `next.config.ts`**
`allowedDevOrigins` includes a leftover cloud-sandbox hostname (`0292a87d99d7930e-115-96-46-169.serveousercontent.com`) that has nothing to do with your setup. Remove it, and move any origin you do need into an env var instead of hardcoding it.

**Task 18 — Add `max_daily_trades` to the configurable surface**
It's fully implemented in the risk guard and `main.py` but not exposed in `api/server.py`'s `ConfigModel` or the frontend, so it can only ever be changed by hand-editing `config.json`.

---

## Tier 5 — Documentation truth & repo hygiene

**Task 19 — Rewrite the root `README.md` from scratch**
`ROADMAP.md` checks off "remove hardcoded personal path" and "consolidate to one README," but the current root `README.md` still contains ~8 hardcoded `d:/Omnity Era/Antigravity/MQL5/...` absolute file links, and describes an architecture that no longer exists: a Streamlit `dashboard.py` + `pages/` UI, with `TrendFollowingStrategy` framed as the main strategy. The real system is a FastAPI backend + Next.js frontend, and the real strategy is `NYTrendContinuation` with `FinRLStrategy` as an alternative. Rewrite it to describe what's actually in the repo, with relative paths only.

**Task 20 — Re-audit `ROADMAP.md` itself once the above lands**
Several `[x]` items in the existing roadmap are demonstrably false right now (Tasks 1, 3, 4, 5, 10, 11, 19 above all contradict a checked box). Once real fixes land, go back through Section 1–3 and Stage 1–3 of `ROADMAP.md` and only leave items checked that you've personally verified against the running code — this file is meant to be your source of truth for what session ran on what state, so it needs to be trustworthy.

**Task 21 — Automated backups**
Add a small scheduled task (or a step in `main.py`) that periodically copies `config.json`, `strategy/models/*.zip`, and `bot.log` to a dated backup folder, per the still-unchecked Stage 5 item.

---

## Tier 6 — Nice-to-have polish (only after everything above is solid)

**Task 22** — Per-symbol/per-strategy magic numbers instead of one hardcoded `234000`, so you can tell which strategy opened a position from the ticket alone.
**Task 23** — Replace `pytz` + manual UTC-offset math in `ny_trend_continuation.py` with stdlib `zoneinfo`.
**Task 24** — Normalize/scale the FinRL model's input features (`close`, `ema_fast`, `ema_slow`, `rsi`, `atr` are on wildly different numeric scales, fed raw into an `MlpPolicy`) — this is a model-quality improvement, not a bug, but likely helps training stability.
**Task 25** — Multi-strategy portfolio mode (run `NYTrendContinuation` and a second uncorrelated strategy) with a shared risk budget.

---
