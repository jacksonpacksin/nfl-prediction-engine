"""Availability evidence: explicit sourced starter attestations and as-of injury captures.

Injury status never implies a confirmed starter. Missing/stale evidence => UNKNOWN.
"""
import csv
import json
from pathlib import Path
from market_ev import load_jsonl,parse_utc

def availability(forecast,injuries,starters,max_age_hours=72):
    kickoff=parse_utc(forecast["kickoff_utc"])
    created=parse_utc(forecast["forecast_created_utc"])
    pid=forecast["player_id"]
    past=[r for r in injuries if r.get("player_id")==pid and r.get("captured_utc") and
          parse_utc(r["captured_utc"])<=created]
    recent=[r for r in past if (created-parse_utc(r["captured_utc"])).total_seconds()<=max_age_hours*3600]
    latest=max(recent,key=lambda r:r["captured_utc"]) if recent else None
    attest=[r for r in starters if r.get("player_id")==pid and r.get("game_id")==forecast["game_id"] and
            r.get("starter_confirmed","").lower()=="true" and r.get("source_url") and r.get("reviewer") and
            r.get("confirmed_utc") and parse_utc(r["confirmed_utc"])<=created]
    starter=max(attest,key=lambda r:r["confirmed_utc"]) if attest else None
    return {"player_id":pid,"game_id":forecast["game_id"],"forecast_created_utc":forecast["forecast_created_utc"],
        "starter_status":"CONFIRMED_AS_OF_FORECAST" if starter else "UNVERIFIED",
        "starter_source":starter.get("source_url") if starter else None,
        "injury_status":"SOURCE_CAPTURED_AS_OF_FORECAST" if latest else "UNKNOWN",
        "injury_report_status":latest.get("report_status") if latest else None,
        "injury_practice_status":latest.get("practice_status") if latest else None,
        "injury_source_capture_utc":latest.get("captured_utc") if latest else None,
        "injury_red_flag":bool(latest and str(latest.get("report_status") or "").strip().lower() in ("out","doubtful","injured reserve","ir")),
        "actionable":bool(starter and latest and str(latest.get("report_status") or "").strip().lower() not in ("out","doubtful","injured reserve","ir")),
        "warning":"Source report and starter attestation are not guarantees of participation."}

def run():
    root=Path("data");starters_file=Path("config/confirmed_starters.csv")
    starters=[]
    if starters_file.exists():
        with starters_file.open(newline="") as f:
            starters=list(csv.DictReader(f))
    forecasts=load_jsonl(root/"pregame_forecast_snapshots.jsonl")
    injuries=load_jsonl(root/"injury_snapshots.jsonl")
    # Only the latest capture for each unique pregame forecast model/player/game.
    latest={}
    for f in forecasts:
        k=(f["game_id"],f["player_id"],f["model_id"])
        if k not in latest or f["forecast_created_utc"]>latest[k]["forecast_created_utc"]:latest[k]=f
    results=[availability(f,injuries,starters) for f in latest.values()]
    summary={"status":"EVIDENCE_ONLY","checked":len(results),
             "starter_confirmed":sum(x["starter_status"]=="CONFIRMED_AS_OF_FORECAST" for x in results),
             "injury_captured":sum(x["injury_status"]=="SOURCE_CAPTURED_AS_OF_FORECAST" for x in results),
             "both_evidence_types":sum(x["actionable"] for x in results),
             "records":results[:500],
             "note":"No injury probability adjustment or verified starter inference. Source attestations required."}
    (root/"availability_status.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="records"}))
if __name__=="__main__":run()
