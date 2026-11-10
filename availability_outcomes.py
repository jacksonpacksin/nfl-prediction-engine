"""Prospective QB passing-activity outcomes and evidence-index validation.

Observed QB passing attempts >0 proves passing participation, NOT an official
start or full game participation. Missing QB stats remain UNKNOWN, never zero.
Only frozen pre-kickoff scores are eligible for prospective validation.
"""
import csv,json,math
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
from market_ev import load_jsonl,parse_utc
from market_capture import append_jsonl

def freeze(records,previous,now):
    seen={(r.get("game_id"),r.get("player_id")) for r in previous}
    added=[]
    for r in records:
        key=(r.get("game_id"),r.get("player_id"))
        try:
            at=parse_utc(r["forecast_created_utc"])
            kickoff=parse_utc(r["kickoff_utc"])
        except (KeyError,ValueError,TypeError):continue
        if not all(key) or key in seen or at>now or now>=kickoff or at>=kickoff:continue
        # Existing forecasts are not eligible for retrospective reconstruction.
        if now-at>timedelta(hours=12):continue
        added.append({**r,"first_frozen_utc":now.isoformat(),
                      "snapshot_status":"FROZEN_PROSPECTIVE"})
        seen.add(key)
    return added

def reconcile(frozen,logs,now):
    observed={(r["game_id"],r["player_id"]):r for r in logs
              if r.get("game_id") and r.get("player_id")}
    results=[]
    for r in frozen:
        key=(r["game_id"],r["player_id"])
        try:
            kickoff=parse_utc(r["kickoff_utc"])
            if now<kickoff+timedelta(hours=5):continue
        except (ValueError,TypeError,KeyError):continue
        log=observed.get(key)
        if not log:status="UNKNOWN_NO_PLAYER_GAME_STAT";outcome=None
        else:
            try:
                attempts=float(log["pass_attempts"])
                outcome=int(attempts>0)
                status="OBSERVED_PASS_ATTEMPT" if outcome else "ZERO_PASS_ATTEMPTS_RECORDED"
            except (KeyError,ValueError,TypeError):
                outcome=None;status="UNKNOWN_INVALID_STATS"
        results.append({"game_id":key[0],"player_id":key[1],
                        "forecast_created_utc":r["forecast_created_utc"],
                        "score":r.get("score"),"label":r.get("label"),
                        "evidence_coverage_weight":r.get("evidence_coverage_weight"),
                        "outcome":outcome,"outcome_status":status,
                        "outcome_definition":"At least one recorded NFL passing attempt; NOT official start"})
    return results

def report(rows):
    known=[r for r in rows if r["outcome"] is not None and r["score"] is not None
           and r.get("evidence_coverage_weight",0)>=60]
    bins=[]
    for name,low,high in (("LOW",0,45),("MID",45,75),("HIGH",75,101)):
        group=[r for r in known if low<=r["score"]<high]
        bins.append({"band":name,"n":len(group),
                     "passing_activity_rate":round(sum(r["outcome"] for r in group)/len(group),4) if group else None})
    # No claim of calibration with tiny or biased samples.
    sufficiently_populated=all(b["n"]>=30 for b in bins)
    ordered=all(bins[i]["passing_activity_rate"]<=bins[i+1]["passing_activity_rate"] for i in (0,1)) if sufficiently_populated else False
    return {"status":"DESCRIPTIVE_ONLY" if sufficiently_populated else "INSUFFICIENT_PROSPECTIVE_DATA",
            "known_outcomes":len(known),"unknown_outcomes":sum(r["outcome"] is None for r in rows),
            "bins":bins,"monotonic_observed_rates":ordered if sufficiently_populated else None,
            "warning":"Passing activity is not confirmed starting status. Missing player rows are UNKNOWN. Selection bias and score calibration remain untested."}

def run():
    root=Path("data");root.mkdir(exist_ok=True)
    now=datetime.now(timezone.utc)
    try:current=json.loads((root/"availability_confidence.json").read_text()).get("records",[])
    except (OSError,ValueError):current=[]
    frozen=load_jsonl(root/"availability_confidence_frozen.jsonl")
    new=freeze(current,frozen,now)
    if new:append_jsonl(root/"availability_confidence_frozen.jsonl",new)
    frozen+=new
    try:
        with (root/"qb_game_logs.csv").open(newline="") as file:logs=list(csv.DictReader(file))
    except OSError:logs=[]
    rows=reconcile(frozen,logs,now)
    summary=report(rows)
    summary.update(generated_utc=now.isoformat(),frozen_player_games=len(frozen),
                   newly_frozen=len(new))
    (root/"availability_outcome_validation.json").write_text(json.dumps({**summary,"records":rows},indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="records"}))
if __name__=="__main__":run()
