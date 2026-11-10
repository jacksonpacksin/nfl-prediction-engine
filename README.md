# NFL Prediction Engine

Automated **research-only** NFL quarterback passing-yards data pipeline and chronological backtest.

## Automated workflow
GitHub Actions runs at 11:17, 17:17, and 23:17 UTC daily (schedule may be delayed), and can be triggered manually under **Actions → NFL data refresh → Run workflow**.

The workflow installs Python 3.11, nflreadpy and polars, retrieves nflverse player-week statistics and schedules for seasons 2022 through the current season, joins games, excludes the current UTC date, checks duplicate IDs and historical-record disappearance, calculates expanding-window quarterback passing-yard baseline forecasts, and commits output files under `data/`.

## Files
- `pipeline.py`: ingestion, data checks, probability baseline, chronological backtest, and CSV/JSON publication.
- `requirements.txt`: dependencies.
- `.github/workflows/nfl-refresh.yml`: scheduled GitHub Actions job.
- `data/qb_game_logs.csv`: downloaded historical QB data, generated on successful run.
- `data/backtest_predictions.csv`: chronological baseline predictions.
- `data/backtest_summary.json`: Brier score and log loss.
- `data/metadata.json`: source and retrieval timestamp.

## Manual execution
```bash
pip install -r requirements.txt
python pipeline.py
```

## Validation limitations
The cloud workflow has not yet been confirmed successful. An initial manual run is required to validate the current nflreadpy schema and GitHub Actions permissions. The probability baseline uses a prespecified normal distribution with six prior games minimum, 12 recent games maximum, a 220-yard shrinkage anchor, and a 55-yard standard deviation floor. These are modeling assumptions, not a calibrated trading model. Historical game outcomes alone do not prove market edge. Injuries, weather, live Kalshi prices, fees, and trading are not connected.

**No automatic trade execution.**

## v0.5 model benchmarking and honest holdout evaluation

Every scheduled run now executes `python -m unittest -v test_validation_v05.py`, downloads nflverse data, then runs `python validation_v05.py`. The original v0.4 files remain intact.

Four *prespecified* probability models compete on the **2025 validation season**: shrinkage normal, rolling normal, Laplace-smoothed empirical hit rate, and a league-wide historical frequency baseline. The winner is selected using 2025 Brier score. Separate isotonic probability calibration maps for each passing-yard threshold are fitted using **2025 observations only**. Both the selected raw model and calibrated model are evaluated on **2026 holdout games**. All player history and league history are updated only after a game's calendar date, preventing same-day outcome leakage.

New automatically published files:
- `data/v05_model_report.json`: validation leaderboard, untouched 2026 holdout scores, Brier/log loss/ECE, calibration bins, and threshold breakdowns.
- `data/v05_calibration.json`: fitted monotonic calibration maps (2025 data only).
- `data/v05_holdout_predictions.csv`: 2026 holdout probabilities and outcomes.

**Interpretation:** 2026 is a partial-season holdout; the report will change as more 2026 games are played. Calibration and model selection share the 2025 validation sample; 2026 remains held out. Threshold predictions from the same game are correlated, so the 5× prediction count is not 5× independent evidence. A Brier improvement is not proof of a profitable market edge. Market quotes, injuries, weather, and trades remain unconnected.

**Activation:** Visit Actions → NFL data refresh → Run workflow. A successful job must show both the unit tests and `Benchmark and validate v0.5 models` passing, with the new `data/v05_*` outputs committed. Do not treat the upgrade as empirically validated until that run succeeds.

## v0.6: timestamped injury and Kalshi market research (NO trading)

The existing workflow now also runs `market_capture.py` and `market_ev.py` after model validation. The capture job appends snapshots, retaining `captured_utc` rather than overwriting earlier observations.

**Injuries:** `data/injury_snapshots.jsonl` captures nflverse injury reports for the current season with both upstream `date_modified` and the time *our* job saw the report. These are NOT reconstructed historical pregame reports; only snapshots captured before kickoff can be used in later point-in-time analyses. Current forecasting probabilities are not yet injury-adjusted.

**Kalshi:** Set repository **Settings → Secrets and variables → Actions → Variables → New repository variable** named `KALSHI_TICKERS` to a comma-separated list of exact, independently verified player-prop market tickers. No API key is required for the public endpoints. Without this variable the market capture intentionally records zero quotes. `data/kalshi_orderbook_snapshots.jsonl` records both bid sides and derives asks by complementing the opposite bid. No ask is assumed if the opposite bid is missing. The quote is an observed top-of-book indication, not a guaranteed execution price. `data/market_capture_status.json` reports captured/error counts.

**Fee-aware research:** `market_ev.py` calculates conservative general taker fees per order, the after-fee break-even probability, and expected payout for YES and NO. Special series fees MUST be checked and specified; the general default is not universal. Actual performance against market-implied probabilities CANNOT be measured until a matching archive of point-in-time pregame forecasts, verified contract rules, and captured quotes exists.

**Strict gating:** Market comparisons require BOTH `config/verified_market_mappings.csv` and `data/pregame_forecasts.csv`. Mappings must include `ticker,player_id,game_id,threshold,kickoff_utc,rules_verified,yes_outcome,fee_multiplier,contracts`; `rules_verified` must be `true` and `yes_outcome` must be `OVER` or `UNDER`. Pregame forecasts must include `player_id,game_id,threshold,forecast_created_utc,p_yes,model_id`. All timestamps must include UTC offsets, forecasts must precede the quote, and the quote must precede kickoff. If any input is missing or stale, comparison is BLOCKED. **Do not fabricate timestamps or use v0.5 hindsight holdout outcomes as pregame forecasts.** Neither of these input files is generated by v0.6; mapping and forecast publishing are the next development stage.

**Caveats:** Capture cadence is 3 times per day, NOT live streaming. Large injuries JSONL files may make Git history grow. This system does not automatically place orders. Do not interpret a positive estimated EV as an established market edge or a guaranteed fill.

Sources: https://nflreadpy.nflverse.com/api/load_functions/ ; https://docs.kalshi.com/ ; https://kalshi.com/fee-schedule
