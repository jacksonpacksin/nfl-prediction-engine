"""Non-calibrated pregame QB evidence index. Never certifies a starter."""
import csv,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from market_ev import load_jsonl,parse_utc

def asof(r,at,hours):
    try:
        t=parse_utc(r["captured_utc"])
        return at-timedelta(hours=hours)<=t<=at
    except (KeyError,TypeError,ValueError):return False

def evaluate(f,injuries,depth,logs):
    at=parse_utc(f["forecast_created_utc"]);pid=f["player_id"];team=f.get("team")
    evidence={}
    recent=[r for r in injuries if r.get("player_id")==pid and asof(r,at,72)]
    if recent:
        r=max(recent,key=lambda x:x["captured_utc"])
        status=str(r.get("report_status") or "").strip().lower()
        practice=str(r.get("practice_status") or "").strip().lower()
        points=(0 if status in ("out","doubtful","ir","injured reserve") else
                8 if status=="questionable" else
                17 if status in ("probable","active") else
                12 if practice else None)
        evidence["injury"]={"points":points,"maximum":20,"status":status or None,
                             "captured_utc":r["captured_utc"]}
    else:evidence["injury"]={"points":None,"maximum":20,"reason":"No fresh as-of injury report"}
    charts=[r for r in depth if r.get("player_id")==pid and r.get("team")==team and asof(r,at,72)]
    if charts:
        r=max(charts,key=lambda x:x["captured_utc"])
        rank=str(r.get("depth_rank") or "").strip()
        points={"1":35,"1.0":35,"2":10,"2.0":10,"3":3,"3.0":3}.get(rank)
        evidence["depth_chart"]={"points":points,"maximum":35,"rank":rank or None,
                                  "captured_utc":r["captured_utc"]}
    else:evidence["depth_chart"]={"points":None,"maximum":35,"reason":"No fresh as-of projected depth chart"}
    played=[]
    for r in logs:
        if r.get("player_id")!=pid or r.get("team")!=team:continue
        try:
            date=datetime.strptime(r["game_date"][:10],"%Y-%m-%d").date()
            if date>=at.date() or (at.date()-date).days>42:continue
            played.append((date,float(r["pass_attempts"])))
        except (KeyError,ValueError,TypeError):continue
    played=sorted(played,reverse=True)[:4]
    if played:
        active=sum(attempts>=15 for _,attempts in played)
        evidence["recent_activity"]={"points":round(45*active/len(played)),
             "maximum":45,"games_considered":len(played),
             "games_with_15_plus_attempts":active,
             "note":"Pass attempts are a workload proxy, not official starts"}
    else:evidence["recent_activity"]={"points":None,"maximum":45,
                                      "reason":"No recent eligible game logs"}
    coverage=sum(v["maximum"] for v in evidence.values() if v["points"] is not None)
    score=sum(v["points"] for v in evidence.values() if v["points"] is not None) if coverage else None
    if coverage<60:label="INSUFFICIENT_EVIDENCE"
    elif evidence["injury"]["points"]==0:label="HIGH_RISK_INJURY_FLAG"
    elif score>=75:label="STRONG_INDICATORS"
    elif score>=45:label="MIXED_INDICATORS"
    else:label="WEAK_INDICATORS"
    return {"game_id":f["game_id"],"player_id":pid,"player":f.get("player"),
            "team":team,"forecast_created_utc":f["forecast_created_utc"],
            "kickoff_utc":f.get("kickoff_utc"),
            "score":score,"score_out_of":100,"evidence_coverage_weight":coverage,
            "label":label,"factors":evidence,"model_version":"heuristic_v1_uncalibrated",
            "starter_confirmation":"NOT_ASSESSED_BY_THIS_SCORE",
            "warning":"Heuristic evidence index, not probability of starting, participation, or prop success."}

def run():
    root=Path("data")
    forecasts=load_jsonl(root/"pregame_forecast_snapshots.jsonl")
    injuries=load_jsonl(root/"injury_snapshots.jsonl")
    try:depth=json.loads((root/"free_depth_chart_qbs.json").read_text())
    except (OSError,ValueError):depth=[]
    try:
        with (root/"qb_game_logs.csv").open(newline="") as file:logs=list(csv.DictReader(file))
    except OSError:logs=[]
    latest={}
    for f in forecasts:
        key=(f.get("game_id"),f.get("player_id"))
        if not all(key) or not f.get("forecast_created_utc"):continue
        if key not in latest or f["forecast_created_utc"]>latest[key]["forecast_created_utc"]:
            latest[key]=f
    records=[evaluate(f,injuries,depth,logs) for f in latest.values()]
    report={"generated_utc":datetime.now(timezone.utc).isoformat(),
            "status":"HEURISTIC_UNCALIBRATED_NOT_STARTER_CONFIRMATION",
            "scored_player_games":len(records),"records":records}
    root.mkdir(exist_ok=True)
    (root/"availability_confidence.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"status":report["status"],"scored_player_games":len(records)}))
if __name__=="__main__":run()
