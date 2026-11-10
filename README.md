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

## v0.7: automated candidate discovery and prospective research

Scheduled workflow now also runs:
- `market_discovery.py`: scans up to 3,000 open Kalshi markets, screens NFL passing-yard candidates, saves timestamped titles/rules and up to 40 top-of-book snapshots. **Discovery does NOT mean settlement rules are verified.** Results are `data/kalshi_discovered_candidates.jsonl` and `data/discovery_status.json`. The page cap can omit contracts.
- `pregame.py`: generates timestamped, append-only champion and experimental workload/matchup QB passing-yard forecasts for future games. Uses prior completed games, rolling passing attempts and passing yards, and opponent prior allowed passing yards. Results: `data/pregame_forecast_snapshots.jsonl` and `data/pregame_status.json`. **Starter and injury availability are NOT verified**, and the experimental model has NOT won a prospective backtest. If no upcoming kickoff is resolvable, it records zero rather than inventing a date.
- `execution_validation.py`: depth-aware paper taker fills (against opposite-side bids), missing-liquidity NO_FILL, fee and slippage estimates, and player-game-clustered bootstrap comparison when 30+ independently verified settled player-games have been collected. Output `data/edge_validation_status.json`. **No settled, mapped historical market archive is currently generated**; a real comparison remains blocked.
- `test_research_v07.py`: five new safety and modeling tests, executed on every refresh.

**Critical outstanding work:** Automatically verifying Kalshi contract settlement rules and mapping a ticker to the correct GSIS player/game/threshold is not solved by keyword discovery. Captured injuries are not yet linked into the forecasting features; no assumption of player availability should be made. Forecasts are not yet linked to the Kalshi quote archive, and actual settled contract outcomes must be independently reconciled. Therefore no claim of market outperformance or profitability is warranted.

**Research-only.** No live orders, no inferred backfilled prices, no fabricated pregame evidence. Run Actions → NFL data refresh and check the new stages and status JSON files before treating this version as operational.

## v0.8 reviewed contract and evidence reconciliation

The scheduled workflow now runs `contract_reconciliation.py`, `availability_evidence.py`, and `settlement_reconciliation.py` plus five additional tests.

- `data/reconciliation_status.json`: fail-closed validation of manually reviewed contract/player/game/threshold mappings. Keyword discovery alone NEVER verifies a contract. Requires `config/reviewed_contracts.csv` with columns `ticker,player_id,game_id,threshold,kickoff_utc,yes_outcome,reviewer,reviewed_utc,rules_url,rules_sha256,rules_verified,threshold_rule_quote,settlement_source`. The rule text and settlement source must be independently inspected, with reviewer attestation. Missing or conflicting evidence blocks the contract. **No reviewed mappings are shipped by default.**
- `data/availability_status.json`: links injury snapshots captured before the forecast to a specific player/game. Independently confirmed starter evidence requires `config/confirmed_starters.csv` with `player_id,game_id,starter_confirmed,source_url,reviewer,confirmed_utc`. Missing/stale injury reports or starter evidence produce UNKNOWN/UNVERIFIED. These checks annotate evidence; they DO NOT yet adjust probabilities.
- `data/settlement_status.json`: fetches Kalshi's actual market result for reviewed contracts, checks the NFL game log and the contract's declared YES direction, and accepts only previously captured pregame forecasts and quotes. Verified records feed `data/settled_point_in_time_comparisons.jsonl`, which the existing clustered bootstrap report uses. Unmatched and conflicting settlements are excluded, never invented.

**Important:** The reviewer must confirm threshold semantics, void/DNP rules, event identity, and any unusual settlement definitions before marking `rules_verified=true`. Automatic rule verification, independent starting-QB verification, and fully automated player mapping are NOT implemented; these require trustworthy external identity/lineup feeds and human review. The settlement cross-check is restricted to plain OVER/UNDER passing yards. Never use these results to claim an executable edge: midpoint comparisons are not fills, and statistical intervals require 30+ independent player-games.

**Activation:** Run GitHub Actions → NFL data refresh. Inspect all three new status files and the test log. A successful workflow may still report zero verified mappings or settlements, correctly reflecting missing attestations.

## v0.9: identity candidates and near-kickoff capture

- `identity_matching.py` compares complete normalized player names in discovered Kalshi market descriptions against GSIS `player_id` from prospectively captured QB forecasts. Unique names yield **IDENTITY_CANDIDATE_ONLY**, not verified settlement, team, matchup, threshold or confirmed starter. Ambiguous multiple games are blocked. Output: `data/identity_matching_status.json`.
- `near_kickoff_capture.py` captures full-depth Kalshi orderbooks (both bid sides) for up to 80 discovered market candidates when an upcoming NFL kickoff is within six hours. Quotes include independent UTC capture timestamps and are explicitly marked unverified candidates. Output: `data/near_kickoff_status.json` and append-only `data/kalshi_orderbook_snapshots.jsonl`.
- `.github/workflows/near-kickoff.yml` requests polling every 15 minutes. **GitHub scheduled workflows are best-effort and can run late or be skipped.** The collector does not run continuously and is not guaranteed to catch the final pregame quote. This frequent workflow may increase Git repository size and GitHub Actions usage.
- Availability checks now flag captured OUT, DOUBTFUL and injured-reserve reports as blocking the `actionable` evidence flag, while preserving the original report status.

**Unresolved:** A trustworthy independently authenticated starting-quarterback feed is NOT connected. The existing `config/confirmed_starters.csv` source-attestation path is required for starter verification. Identity candidates do not automatically become approved contract mappings; reviewed rules and exact threshold semantics remain mandatory. The system still does not automatically trade.

To activate, manually run both GitHub Actions workflows once and inspect `data/identity_matching_status.json`, `data/availability_status.json`, and `data/near_kickoff_status.json`. No new live run has been verified as of this commit.
