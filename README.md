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
