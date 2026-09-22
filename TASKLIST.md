## 🔴 New/regressed issues from the latest commits

**1. `backtest/prop_firm_backtester.py` is broken again — different cause.**
The "clean up legacy models and scripts" commit deleted `strategy/ny_trend_continuation.py` and `strategy/base_strategy.py`. But the backtester (which was correctly rebuilt last round to actually test `NYTrendContinuation`) still does `from strategy.ny_trend_continuation import NYTrendContinuation`. I ran it — it's a `ModuleNotFoundError` on import. It cannot run at all right now.

**2. The `strategy` config field is dead again — same bug class as the original `max_trailing_dd_pct` bug.**
`main.py` now hardcodes `active_strategies = [FinRLStrategy(...)]` and never branches on `config.get("strategy")` — it only reads that value for a log line. Changing "Strategy" in the dashboard does nothing (the modal's dropdown even only offers one option, `DynamicRLStrategy`, confirming this was noticed but not fully cleaned up). The root `README.md` still says `strategy`: _"e.g. `NYTrendContinuation` or `FinRLStrategy`"_ — that's no longer true.

**3. `backtest/ml_backtester.py` will crash if run.**
Its local `prepare_data()` wasn't updated for the new normalized/continuous-action environment — it computes raw `ema_fast`/`rsi`/`atr` but `ForexTradingEnv` now expects `close_norm`, `ema_fast_norm`, etc. It'll throw a `KeyError` the moment the env resets. It also still hardcodes `ppo_{symbol}_m15.zip`, but the only model that exists now is `ppo_XAUUSD_m5.zip`, so it'd fail even earlier with "Model not found."

**4. Your pytest suite exists but half of it fails.** I actually ran it:

```
tests/test_daily_reset.py::test_get_daily_trades_count_uses_server_time PASSED
tests/test_position_sizing.py::test_calculate_position_size_tick_size_differs_from_point FAILED
tests/test_position_sizing.py::test_calculate_position_size_below_min FAILED
tests/test_risk_limits.py::test_risk_limits_dynamic_update PASSED
```

Both failures are the same cause: `MockSymbolInfo` in `tests/test_position_sizing.py` is missing a `trade_contract_size` attribute that `calculate_position_size()` now reads unconditionally, so both tests error out with `AttributeError` before their assertions ever run. Since CI (`.github/workflows/ci.yml`, correctly configured) runs this on every push, **CI is almost certainly red right now.**

**5. `config.json` still ships with `"bot_status": "running"`.** The code's fallback default was changed to `"stopped"`, but that only matters if the key is _missing_ — the committed file still has the key set to `"running"`, so a fresh clone still auto-trades the instant it connects.

## Next tasks for Antigravity (in order)

**Task A — Decide the fate of `NYTrendContinuation` and fix accordingly.** It looks like you've intentionally standardized on the continuous-action `FinRLStrategy`. If that's correct: delete the remaining references instead of leaving them half-cleaned — remove the `NYTrendContinuation` import from `prop_firm_backtester.py` and rewrite it to backtest `FinRLStrategy` instead (bar-by-bar, feeding it the same `_prepare_state` normalization); remove the `strategy` dropdown's implication of choice in the frontend modal (or clearly label it as fixed); update `README.md`'s Configuration section to drop the `NYTrendContinuation` mention. If NYTrendContinuation was _not_ meant to be retired, restore the two deleted files and re-wire `main.py`'s strategy selection to actually branch on `config.get("strategy")` again.

**Task B — Fix `tests/test_position_sizing.py`.** Add `self.trade_contract_size = 100.0` (or an appropriate value) to `MockSymbolInfo`, and `mock_mt5.account_info.return_value` / `mock_mt5.symbol_info_tick.return_value` with sane numeric attributes so the leverage-cap branch doesn't hit a bare `MagicMock` in arithmetic. Re-run `pytest tests/ -v` locally and confirm all 4 pass before pushing — don't rely on CI to discover it.

**Task C — Fix `ml_backtester.py`** — either delete it if `Task A`'s rebuilt `prop_firm_backtester.py` now covers RL model testing, or update its `prepare_data()` to match `finrl_strategy.py`'s normalized feature set and fix the hardcoded `_m15` model filename to match whatever models actually exist in `strategy/models/`.

**Task D — Set `config.json`'s `"bot_status"` to `"stopped"`** in the committed file itself, not just the code fallback.

**Task E — Add spread/slippage simulation to `prop_firm_backtester.py`** (still outstanding from before) now that Task A will have you touching it anyway.

Once these land, bring it back and I'll re-verify the same way — actually running the tests and imports, not just reading the diff.
