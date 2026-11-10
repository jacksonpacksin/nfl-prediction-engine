"""NFL QB game-log ingestion and chronological probability baseline.
Research only. No live market quotes or trading. Requires nflreadpy.
"""
import csv
import json
import math
import os
import statistics
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import nflreadpy as nfl

OUT = Path("data")
FIELDS = ("player","player_id","season","week","game_id","game_date","team","opponent","pass_attempts","pass_yards","source_url","retrieved_utc","verified")
SOURCE = "https://github.com/nflverse/nflverse-data/releases"
THRESHOLDS = (199.5,224.5,249.5,274.5,299.5)

def records(frame):
    return frame.to_dicts() if hasattr(frame,"to_dicts") else list(frame)

def collect(now):
    cutoff=now.date().isoformat()
    all_rows=[]
    meta=[]
    for season in range(2022,now.year+1):
        schedules=records(nfl.load_schedules(seasons=season))
        stats=records(nfl.load_player_stats(seasons=season,summary_level="week"))
        games={}
        by_team_week={}
        for s in schedules:
            if str(s.get("game_type","REG")).upper() not in ("REG","REGULAR"):
                continue
            day=str(s.get("gameday") or s.get("game_date") or "")[:10]
            if not day or day>=cutoff: continue
            gid=str(s.get("game_id") or "")
            if not gid: continue
            games[gid]=(day,s)
            week=s.get("week")
            for team,opponent in ((s.get("home_team"),s.get("away_team")),(s.get("away_team"),s.get("home_team"))):
                if team and week is not None:
                    by_team_week[(int(week),str(team))]=(gid,day,str(opponent))
        count=0
        for r in stats:
            if str(r.get("position","")).upper()!="QB":continue
            if str(r.get("season_type","REG")).upper() not in ("REG","REGULAR"):continue
            pid=str(r.get("player_id") or "")
            if not pid:raise ValueError("Missing QB player ID")
            team=str(r.get("team") or r.get("recent_team") or "")
            week=int(r.get("week") or 0)
            gid=str(r.get("game_id") or "")
            if gid in games:
                day,s=games[gid]
                opponent=str(s.get("away_team") if team==s.get("home_team") else s.get("home_team"))
            else:
                found=by_team_week.get((week,team))
                if found is None: continue
                gid,day,opponent=found
            attempts=r.get("attempts")
            yards=r.get("passing_yards")
            if attempts is None or yards is None:raise ValueError("Missing QB passing data")
            attempts=int(attempts);yards=int(yards)
            if attempts<0 or yards<0:raise ValueError("Negative QB stats")
            all_rows.append(dict(player=str(r.get("player_display_name") or r.get("player_name") or pid),player_id=pid,season=season,week=week,game_id=gid,game_date=day,team=team,opponent=opponent,pass_attempts=attempts,pass_yards=yards,source_url=SOURCE,retrieved_utc=now.isoformat(),verified="true"))
            count+=1
        meta.append(dict(season=season,rows=count))
    if not all_rows:raise RuntimeError("No NFL QB records downloaded")
    keys=set()
    for r in all_rows:
        key=(r["player_id"],r["game_id"])
        if key in keys:raise ValueError("Duplicate player/game "+str(key))
        keys.add(key)
    all_rows.sort(key=lambda r:(r["game_date"],r["game_id"],r["player_id"]))
    return all_rows,meta

def backtest(rows):
    history=defaultdict(list)
    preds=[]
    dates=sorted({r["game_date"] for r in rows})
    for day in dates:
        today=[r for r in rows if r["game_date"]==day]
        for r in today:
            prev=history[r["player_id"]]
            if len(prev)<6:continue
            values=prev[-12:]
            mean=statistics.mean(values)
            sd=max(55.0,statistics.stdev(values))
            weight=len(values)/(len(values)+6)
            mu=weight*mean+(1-weight)*220.0
            for threshold in THRESHOLDS:
                p=max(.001,min(.999,.5*math.erfc((threshold-mu)/(sd*math.sqrt(2)))))
                actual=int(r["pass_yards"]>threshold)
                preds.append(dict(game_date=day,player_id=r["player_id"],player=r["player"],game_id=r["game_id"],threshold=threshold,p_over=round(p,6),actual=actual,brier=round((p-actual)**2,8),history_n=len(prev)))
        for r in today:history[r["player_id"]].append(r["pass_yards"])
    if not preds:return [],dict(status="insufficient_data",predictions=0)
    brier=sum(x["brier"] for x in preds)/len(preds)
    logloss=-sum(x["actual"]*math.log(x["p_over"])+(1-x["actual"])*math.log(1-x["p_over"]) for x in preds)/len(preds)
    return preds,dict(status="evaluated",predictions=len(preds),unique_player_games=len({(x["game_date"],x["player_id"]) for x in preds}),brier=round(brier,6),log_loss=round(logloss,6),model="Prespecified shrinkage normal baseline; not calibrated",caveat="Historical box-score outcomes are not proof of a market edge. Multiple thresholds per game are correlated.")

def write_csv(path,rows,fields):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def main():
    now=datetime.now(timezone.utc)
    rows,season_meta=collect(now)
    OUT.mkdir(exist_ok=True)
    old=OUT/"qb_game_logs.csv"
    if old.exists():
        with old.open(newline="") as f:prior=list(csv.DictReader(f))
        old_keys={(x["player_id"],x["game_id"]) for x in prior}
        new_keys={(x["player_id"],x["game_id"]) for x in rows}
        if not old_keys.issubset(new_keys):raise RuntimeError("Historical records disappeared; refusing update")
    preds,summary=backtest(rows)
    metadata=dict(retrieved_utc=now.isoformat(),cutoff_exclusive=now.date().isoformat(),source=SOURCE,season_rows=season_meta,total_rows=len(rows),notes="Source-reported statistics, not independently audited. Current UTC day excluded.")
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)
        write_csv(p/"qb_game_logs.csv",rows,FIELDS)
        write_csv(p/"backtest_predictions.csv",preds,tuple(preds[0]) if preds else ("game_date","player_id","threshold","p_over","actual","brier"))
        (p/"backtest_summary.json").write_text(json.dumps(summary,indent=2))
        (p/"metadata.json").write_text(json.dumps(metadata,indent=2))
        for name in ("qb_game_logs.csv","backtest_predictions.csv","backtest_summary.json","metadata.json"):
            os.replace(p/name,OUT/name)
    print(json.dumps(dict(metadata=metadata,backtest=summary),indent=2))

if __name__=="__main__":main()
