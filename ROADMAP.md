# PropFirm_System — Audit Checklist & Roadmap to Production-Grade

**Repo:** github.com/anisansarix/MQL5
**Commit reviewed:** `b43a157` ("Fix nested git repository and gitignore encoding, add PropFirm_System files")
**Reviewed:** Sept 21, 2026
**Scope:** `PropFirm_System/` (the Python quant engine) + repo-level hygiene

> This is a working checklist. Check items off (`- [x]`) as you fix them and commit this file alongside your code so progress is tracked in git history.

---

## 0. Current State — Honest Assessment

You have a real, non-trivial system: MT5 data pipeline, a genuinely well-designed NY-session opening-range strategy (H1 trend filter + swing structure + M5 rejection confirmation), a risk guard, an executor, a FastAPI backend, and a Next.js frontend. That's a legitimate architecture — most retail "prop firm bots" don't get this far.

But right now it's at **prototype stage**: it runs, but a handful of concrete bugs mean it can silently violate the exact rules it exists to enforce, and it has no safety net if anything goes wrong at 3am while you're asleep and it's holding a live position. The plan below closes that gap in stages.

---

## 1. Critical Bugs — Fix Before Running on Any Funded/Live Account

- [x] **Dead `max_trailing_dd_pct` config value.**
  `main.py` sets `guard.max_trailing_dd_pct = config.get(...)`, but `PropFirmGuard.check_risk_status()` reads `self.max_total_loss_pct` (set only in `__init__`), which never gets updated. Changing "Max Trailing DD %" in the dashboard does nothing — the real limit is frozen at the constructor default.
  **Fix:** rename the constructor field to `max_trailing_dd_pct` (or update the same attribute name main.py sets), and add a unit test that asserts changing `config.json`'s value actually changes `guard.check_risk_status()` behavior.

- [x] **Position sizing mixes `point` and `tick_size`.**
  `main.py`: `sl_points = abs(price - sl) / tick_info.point`
  `prop_firm_guard.py`: `loss_per_lot = (stop_loss_points / tick_size) * tick_value`
  `point` and `tick_size` are not guaranteed equal (gold, indices, some FX pricing conventions differ per broker). Double-normalizing through both can size lots incorrectly.
  **Fix:** compute `sl_distance_price = abs(entry_price - sl_price)` once (raw price units, no division by `.point`), then in the guard: `loss_per_lot = (sl_distance_price / tick_size) * tick_value`. Add a test with a mock `symbol_info` where `point != tick_size` to catch regressions.

- [x] **`requirements.txt` is mixed-encoding (broken file).**
  First 6 lines are UTF-8; `finrl`, `stable-baselines3`, `gymnasium` are UTF-16 with embedded null bytes. `pip install -r requirements.txt` will likely fail or silently skip those lines.
  **Fix:** re-save as plain UTF-8 (open in a plain-text editor / `iconv`, don't append lines via a tool that defaults to UTF-16). Verify with `file requirements.txt` → should say `ASCII text` or `UTF-8 Unicode text`. Then `pip install -r requirements.txt` in a clean venv to confirm it actually resolves.

- [x] **No crash isolation in the main loop.**
  `main()` wraps the entire lifetime of the bot in one `try/except` that calls `mt5.shutdown()` on any exception — including one bad tick or a transient `None` from `order_send()`. One hiccup kills the whole process, including risk monitoring, until someone manually restarts it.
  **Fix:** move the per-cycle logic into its own `try/except` *inside* the `while True:` loop, log the error, sleep, and continue. Reserve the outer handler for truly fatal startup errors only.

- [x] **`mt5.order_send()` result never null-checked.**
  In `mt5_executor.py`, both `_execute_order()` and `close_all_positions()` call `mt5.order_send(request)` and immediately access `.retcode` / assume success. `order_send()` can return `None` on IPC failure — this will raise `AttributeError` and (per the bug above) crash the bot.
  **Fix:** `result = mt5.order_send(request); if result is None: log + return False` before touching `.retcode`.

- [x] **Emergency close has no verification or retry.**
  `close_all_positions()` fires one order per position and logs "All positions closed" unconditionally, regardless of whether each `order_send()` actually succeeded. This is your circuit breaker — it should be the most bulletproof code in the system, not the least.
  **Fix:** check each result's `retcode`, retry once on failure (e.g., requote), and only log success per-position after confirming `TRADE_RETCODE_DONE`. Log a `CRITICAL` if any position fails to close — this should page you, not just sit in a log file.

---

## 2. Security — Fix Before Exposing the API to Any Network
 
- [x] `api/server.py` has **no authentication** on any endpoint, including `POST /api/config` (lets anyone rewrite your risk limits, strategy, or symbols).
  **Fix:** add a simple API key header check (`X-API-Key`) validated against an env var, minimum viable for personal use.
- [x] `CORSMiddleware(allow_origins=["*"], allow_credentials=True, ...)` — wide open.
  **Fix:** restrict to `http://localhost:3000` (or wherever your frontend actually runs).
- [x] `start_dev.bat` / `start_osiris.bat` launch uvicorn with `--host 0.0.0.0`, exposing it to your whole LAN (and to the internet if you ever port-forward or run this on a VPS/cloud box).
  **Fix:** bind to `127.0.0.1` unless you specifically need remote access; if you do need remote access, put it behind the API key **and** a reverse proxy with HTTPS.
- [x] No secrets management pattern established yet (fine today since nothing sensitive is hardcoded — keep it that way). Add a `.env` + `python-dotenv` convention now, before you add anything like a Telegram/Discord alert token or a cloud API key.

---

## 3. Repository Hygiene

- [x] `.gitignore` rules (`*.ex5`, `*.log`, `logs/`, `*.dat`) are correct now but don't apply retroactively — 133 `.ex5` files, `logs/20260916.log`, and `experts.dat` are still tracked.
  **Fix:**
  ```bash
  git rm -r --cached "**/*.ex5" logs/ experts.dat
  git commit -m "Untrack compiled binaries and runtime logs"
  ```
- [x] Delete the stray junk file `PropFirm_System/nul\`n\`necho` (debris from a broken shell command; duplicate of `start_dev.bat` content).
- [x] Remove hardcoded personal path (`d:/Omnity Era/Antigravity/MQL5/...`) from `DOCUMENTATION.md` — use relative paths so the docs aren't tied to your machine.
- [x] Reconcile the three overlapping docs: top-level `DOCUMENTATION.md` (says 5%/10% limits, FinRL default), `PropFirm_System/README.md`, and `PropFirm_System/PROJECT_DOCUMENTATION.md`. Pick **one** source of truth and have the others link to it, or delete the stale ones. Right now they contradict your actual `config.json` (1%/3%, `NYTrendContinuation`).
- [x] `PropFirm_System/.gitignore` covers `node_modules/`, `__pycache__/`, `.env`, `state.json`, `bot.log` — good. Add `*.log`, `strategy/models/*.zip` (trained models are binary artifacts; consider a separate `models/` storage or Git LFS if you want them versioned) once you're training more than a handful.
- [x] Add a top-level `LICENSE` file (even a personal "all rights reserved" is better than none) and consolidate to a single root `README.md` that GitHub will render on the repo landing page.

---

## 4. Roadmap: Prototype → Reliable Personal Trading System

This is framed as "commercial-grade" reliability — i.e., the level of rigor a real trading firm would demand internally — not as a plan to sell or distribute the system. Since it's for personal use, skip anything about licensing it to others; the point is simply: **would you trust this, unattended, with money you can't afford to lose?** Each stage has an exit gate — don't move to the next stage until you can honestly check every box.

### Stage 0 — Where you are now
Architecture exists, core loop runs, one strategy is genuinely well-designed, but correctness bugs exist in the risk layer itself and there's no test coverage.

### Stage 1 — Stabilize (get correctness bugs out of the risk path)
- [x] Fix all 6 items in Section 1.
- [x] Fix all items in Section 2 (security).
- [x] Fix all items in Section 3 (hygiene).
- [x] Add a `CHANGELOG.md` and start tagging versions (`v0.1.0`, etc.) so you can tell which commit a given trading session ran on.

**Exit gate:** every function in `prop_firm_guard.py` and `mt5_executor.py` has been manually traced line-by-line at least once by you, not just by an AI reviewer.

### Stage 2 — Validation (prove it works before live money)
- [x] Write `pytest` fixtures for the position sizing logic (mock the tick size and point values to ensure it calculates correct lot sizes on non-Forex instruments).
- [x] Write a test for the daily reset boundary (assert `start_of_day_balance` resets at the broker's day boundary, not the host machine's local midnight).
- [x] Write a test for risk limits (assert `check_risk_status()` flips to `False` the moment equity drops 5% below `start_of_day_balance`).
- [x] Run `PropFirmBacktester` against your actual `NYTrendContinuation` strategy — if you're executing `ORDER_FILLING_IOC` at market, simulate spread + a few points of slippage on every fill.
- [x] Walk-forward validate, don't just single-split: train/tune on year 1, test untouched on year 2, repeat rolling. If you're still using the FinRL/PPO strategy at all, this matters even more.
 
**Exit gate:** Tests pass, and the backtester shows a positive expectancy on 2023-2024 unseen data with simulated slippage.
 
### Stage 3 — Robustness & Observability (so you can sleep)
- [x] Per-cycle exception isolation (`try/except` around the main `while True:` loop body) so a transient broker API timeout doesn't crash the daemon.
- [x] Reconnect logic: if `mt5.initialize()` / terminal IPC drops mid-session, detect it and re-attach rather than crash.
- [x] Basic alerting — a Telegram or Discord webhook is enough for personal use. Alert on: limits breached, connection lost, position filled.
- [x] Structured logging: move from plain `logging.info(f"...")` strings toward consistent fields (e.g. `[EXECUTION] symbol=XAUUSD volume=1.5 action=BUY reason=TREND_CONTINUATION`)., lot, retcode) so you can grep/aggregate later.
- [x] Process supervision: run `main.py` under something that auto-restarts it on crash (NSSM/Task Scheduler on Windows, or a simple watchdog script) — but only *after* Stage 3's crash-isolation work, so auto-restart is a safety net, not a crutch masking the real bug.

**Exit gate:** you can kill the MT5 terminal mid-session and the bot detects it, alerts you, and recovers or fails safe (flat, no orphaned state) without you touching a keyboard.

### Stage 4 — Extended Validation (earn trust with real money on the line)
- [ ] Minimum 4–6 weeks continuous run on a **demo** account with the exact production config, zero manual intervention, before touching a funded/evaluation account.
- [ ] Track every discrepancy between backtest-predicted and demo-actual behavior (slippage, missed fills, timing drift) and reconcile the backtester until it stops surprising you.
- [ ] Dry-run the emergency circuit breaker deliberately (force a drawdown in a demo/sandbox) and confirm it flattens everything within your expected time window.
- [ ] Only then: smallest real evaluation account size, one symbol, conservative config (your current 1%/3% is a reasonable starting point).

**Exit gate:** demo performance and backtest performance agree within a margin you're comfortable defending to yourself.

### Stage 5 — Ongoing "Commercial-Grade" Polish
- [ ] CI (GitHub Actions is fine) running `pytest` + a lint pass on every push, even for a personal repo — catches the requirements.txt-style silent breakage before you run it live.
- [ ] Config validation on load (`config_manager.py`) — reject a `config.json` with, e.g., `max_daily_loss_pct: 0` or a symbol not in Market Watch, instead of discovering it live.
- [ ] Dashboard shows *config drift warnings* (e.g., "loaded max_trailing_dd_pct differs from what guard is enforcing") so a bug like the one in Section 1 is visible in the UI, not just in code.
- [ ] Periodic automated backups of `config.json`, trained models, and trade history/logs.
- [ ] A single authoritative `README.md`/`ARCHITECTURE.md` kept in sync with the actual `config.json` defaults (Section 3 item) — update it as part of the PR/commit whenever behavior changes, not as an afterthought.

---

## 5. Nice-to-Haves (once the above is solid)
- [ ] Per-symbol/per-strategy magic numbers instead of one hardcoded `234000`, so the dashboard can distinguish which strategy opened which position.
- [ ] Multi-strategy portfolio mode (run `NYTrendContinuation` and a second uncorrelated strategy simultaneously) with shared risk budget.
- [x] Replace the fixed "max daily trades: 999 (temporarily increased for testing)" with a real configurable cap once you've decided what limit you actually want live.
- [ ] Swap `pytz`/manual offset math for `zoneinfo` (stdlib, Python 3.9+) — one less dependency and DST edge cases are handled by the tz database instead of hand-rolled offset detection.
