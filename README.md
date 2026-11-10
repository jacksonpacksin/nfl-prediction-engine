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

## v1.0 operational hardening

The main refresh now publishes `data/research_readiness.json`: upcoming game coverage, unique pregame forecasts, discovered Kalshi candidates, GSIS-name matches, recent quote availability, starter attestations, and verified settlements. **Market edge remains NOT_ESTABLISHED until independently verified settled point-in-time comparisons exist.**

The 15-minute near-kickoff workflow now restricts polling to discovered candidates captured within the previous 24 hours, with an unambiguous player-name/GSIS game candidate match whose kickoff is within six hours. It excludes candidates with known expired close times. A matched name remains **not a certified contract mapping**. No automatic orders.

**Operational limitation:** This stricter filter may produce zero quotes if discovery, pregame forecasts, or identity matching are stale or incomplete. That is intentional. The main workflow must run successfully before near-kickoff snapshots can be useful. No automated independent starter verification provider is connected; starter evidence still requires a sourced attestation.

Run the main refresh workflow first, then the near-kickoff workflow. Verify their status JSON outputs and tests. GitHub Actions success confirms execution, not model validity or profitable edge.

## v1.1 external starter-provider adapter and Kalshi rule fingerprints

The main workflow now calls `starter_feed.py` and `contract_fingerprint.py` and runs four new tests.

**Starter feed:** To activate, you must select and contract with a reputable independent NFL lineup/injury provider that offers an HTTPS JSON endpoint with verified *confirmed* starters and authoritative GSIS IDs. Set Actions repository variable `NFL_STARTER_FEED_URL` and Actions secret `NFL_STARTER_FEED_TOKEN`. Required JSON shape:
```json
{"updated_utc":"2026-11-15T16:00:00Z","starters":[{"game_id":"2026_11_KC_BUF","player_id":"00-0033873","team":"KC","status":"confirmed","source_url":"https://provider.example/record","confirmed_utc":"2026-11-15T16:00:00Z"}]}
```
The provider must map to the **exact nflverse game_id and GSIS player_id**. The adapter rejects projected/probable statuses, missing sources and stale confirmations, records when the system first observed a claim, and never treats later data as available to earlier forecasts. Its status is `data/starter_feed_status.json`. The feed is **not configured automatically**; no vendor credentials or subscriptions were created. An authenticated endpoint is a source claim, not independent proof that the provider is accurate.

**Kalshi rule fingerprints:** For each `config/reviewed_contracts.csv` entry, `contract_fingerprint.py` re-fetches current Kalshi market metadata and checks a SHA-256 digest of the canonical fields `ticker,event_ticker,title,rules_primary,rules_secondary,strike_type,floor_strike,cap_strike`. Review CSV additionally requires `event_ticker,strike_type,floor_strike,cap_strike,source_game_reference` for this audit. Generate `rules_sha256` using `contract_fingerprint.fingerprint(market)` **only after independently reviewing** the full market rules and official NFL game identity. Missing or changed terms are BLOCKED. Status: `data/contract_fingerprint_status.json`. This check prevents silent rule drift; it cannot independently interpret complex void/DNP conditions or certify a human mapping.

**Not yet fully connected:** No vetted external starter provider was supplied, and no manually reviewed Kalshi mappings were provided. The workflow must report zero verified records until those inputs exist. Rule fingerprint matches are an additional audit; they are not themselves trade authorization. No live orders are submitted.

## v1.2 free-only NFL availability evidence

No subscription or API key required. `free_depth_charts.py` attempts to collect nflverse QB depth charts using the installed `nflreadpy` interface and writes `data/free_depth_chart_qbs.json` and `data/free_depth_chart_status.json`. The main workflow captures these before checking availability. Three unit tests assert that a projected depth-chart quarterback is **never** labeled a confirmed starter and that post-forecast observations cannot leak into prior forecasts.

The existing free nflverse injury snapshots remain in use. `availability_evidence.py` now annotates forecast records with the depth-chart rank and capture time, if a same-team GSIS player ID matches. Depth charts are projected roster ordering, not a game-day starter confirmation. If the installed nflreadpy release does not support depth charts or upstream data are unavailable, the collector reports `UNAVAILABLE` rather than manufacturing evidence.

The external paid-provider integration remains optional and unconfigured. This free-only system does **not** establish a trustworthy confirmed-starter feed. Do not treat any player as confirmed without a separate source-backed attestation. Run GitHub Actions → NFL data refresh and inspect `data/free_depth_chart_status.json` and `data/availability_status.json` to verify collection.

## v1.3 pregame availability evidence confidence (free, uncalibrated)

`availability_confidence.py` generates `data/availability_confidence.json` from free injury snapshots (20 points), projected QB depth-chart position (35 points), and recent completed-game passing attempts (45 points). All injury and depth-chart observations must have been captured **before** the forecast and within 72 hours. Passing-game activity is limited to completed prior dates in the last 42 days and the four most recent qualifying appearances; 15+ attempts is a workload proxy, **not** proof of an official start.

Scores use a fixed denominator of 100 and do not impute missing evidence. A coverage weight under 60 returns `INSUFFICIENT_EVIDENCE`; known out/doubtful/IR statuses return `HIGH_RISK_INJURY_FLAG` regardless of score. Otherwise, >=75 is `STRONG_INDICATORS`, >=45 `MIXED_INDICATORS`, and lower is `WEAK_INDICATORS`. This is an **uncalibrated heuristic index**, not a starting probability, game-participation probability, or market EV adjustment. A score cannot set `starter_status`, and `availability_evidence.py` remains the separate confirmation gate.

Five unit tests cover missing data, positive projected indicators without confirmation, future-data rejection, injury risk overrides, and stale depth charts. Run the main NFL refresh workflow and inspect `data/availability_confidence.json`. Scores are research-only until validated prospectively against verified starter/participation outcomes.

## v1.4 prospective outcome collection and descriptive validation

`availability_outcomes.py` freezes the first available availability-confidence score for each player/game in `data/availability_confidence_frozen.jsonl`, only if the forecast and snapshot were captured **before kickoff** and the forecast is no older than 12 hours. The freeze file is append-only. Historical scores are never fabricated from later data. The main workflow runs this automatically and writes `data/availability_outcome_validation.json`.

After kickoff plus five hours, it reconciles against downloaded nflverse QB passing-attempt logs. A recorded passing attempt indicates **observed passing activity**, not an official start. Zero recorded attempts means zero passing attempts in the source row, not definitive inactivity. A missing player-game row is always `UNKNOWN_NO_PLAYER_GAME_STAT` and excluded from the denominator; this creates potential selection bias. The validation report includes LOW/MID/HIGH score-band observed passing-activity rates, known and unknown counts, and only tests whether observed rates are monotonic when all three bins contain at least 30 observations. This is a descriptive threshold, **not** proof of calibration or predictive validity. We still need authoritative game participation / official starting-QB outcomes and unbiased negative labels for proper calibration.

No confidence score is used to adjust market probabilities, mark a player as a confirmed starter, or place a trade. Five tests cover pre-kickoff freeze, missing rows, one-attempt activity, delayed outcomes, and sample-size guard.
