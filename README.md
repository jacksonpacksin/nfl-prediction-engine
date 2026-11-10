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
