"""Pregame QB forecast capture: no current-game outcomes, no injury hindsight.

This is an EXPERIMENTAL workload/matchup candidate. Champion remains raw shrink_normal
until a prospective evaluation demonstrates improvement.
"""
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import nflreadpy as nfl
from market_capture import append_jsonl,now_utc
from validation_v05 import normal_survival

THRESHOLDS=(199.5,224.5,249.5,274.5,299.5)
def project(history,opponent_history,mode):
    recent=history[-12:]
    yards=[float(x["pass_yards"]) for x in recent]
    if len(yards)<6:return None
    n=len(yards)
    base=(sum(yards)+6*220)/(n+6)
    sd=max(55.0,statistics.stdev(yards))
    if mode=="champion":
        return base,sd
    attempts=[float(x["pass_attempts"]) for x in recent]
    # Shrink attempt rate and yards per attempt to stable priors.
    a=(sum(attempts)+6*32)/(n+6)
    ypa=(sum(yards)+6*32*6.9)/(sum(attempts)+6*32) if sum(attempts)>0 else 6.9
    workload=a*ypa
    # Defense allowed is built from COMPLETED prior games only, shrunk to league 220.
    opp=opponent_history[-12:]
    defense=(sum(opp)+8*220)/(len(opp)+8)
    adjusted=0.55*base+0.35*workload+0.10*(base+defense-220)
    return adjusted,max(sd,55.0)

def prepare(rows):
    # QB game logs sorted chronologically; use opponent's allowed yards from earlier games.
    player=defaultdict(list); defense=defaultdict(list)
    for r in sorted(rows,key=lambda x:(x["game_date"],x["game_id"])):
        player[r["player_id"]].append(r)
        if r["opponent"]:defense[r["opponent"]].append(float(r["pass_yards"]))
    return player,defense

def upcoming(now,days=8):
    games=nfl.load_schedules(seasons=now.year).to_dicts()
    upcoming=[]
    for g in games:
        if str(g.get("game_type","REG")).upper() not in ("REG","REGULAR"):continue
        kickoff=g.get("gametime")
        date=str(g.get("gameday") or "")[:10]
        if not date:continue
        # gametime from nflverse is local eastern; use timezone-aware kickoff where available.
        # Avoid assuming a timezone: prefer an ISO timestamp provided by schedule.
        timestamp=g.get("start_time") or g.get("kickoff")
        try:
            if timestamp:
                dt=datetime.fromisoformat(str(timestamp).replace("Z","+00:00"))
                if dt.tzinfo is None:continue
            elif kickoff and date:
                # nflverse schedule 'gametime' is US Eastern local clock time.
                dt=datetime.fromisoformat(date+"T"+str(kickoff)).replace(tzinfo=ZoneInfo("America/New_York"))
            else:continue
            dt=dt.astimezone(timezone.utc)
        except (ValueError,TypeError):continue
        if now<dt<=now+timedelta(days=days):upcoming.append((g,dt))
    return upcoming

def run():
    now=datetime.now(timezone.utc);root=Path("data")
    with (root/"qb_game_logs.csv").open(newline="") as f:rows=list(csv.DictReader(f))
    # Never forecast for a game already represented in downloaded outcomes.
    played={r["game_id"] for r in rows}
    players,defense=prepare(rows)
    games=upcoming(now)
    snapshot=[]
    for game,kickoff in games:
        gid=str(game.get("game_id") or "")
        if not gid or gid in played:continue
        for team,opp in ((game.get("home_team"),game.get("away_team")),(game.get("away_team"),game.get("home_team"))):
            if not team or not opp:continue
            # Last observed team is not evidence of being today's starter.
            eligible=[]
            for pid,h in players.items():
                if h[-1]["team"]==team and len(h)>=6:eligible.append((pid,h))
            for pid,h in eligible:
                for model in ("champion","workload_matchup_experimental"):
                    mu,sd=project(h,defense[opp],model)
                    for threshold in THRESHOLDS:
                        snapshot.append({"forecast_created_utc":now.isoformat(),"kickoff_utc":kickoff.isoformat(),
                            "game_id":gid,"player_id":pid,"player":h[-1]["player"],"team":team,"opponent":opp,
                            "threshold":threshold,"p_over":normal_survival(threshold,mu,sd),
                            "model_id":model,"mu":round(mu,3),"sd":round(sd,3),
                            "starter_verified":False,"injury_status_verified":False,
                            "status":"RESEARCH_ONLY_UNVERIFIED_STARTER",
                            "source":"Prior completed nflverse QB games only"})
    if snapshot:append_jsonl(root/"pregame_forecast_snapshots.jsonl",snapshot)
    (root/"pregame_status.json").write_text(json.dumps({
        "captured_utc":now.isoformat(),"upcoming_games_with_verified_utc_kickoff":len(games),
        "forecasts_written":len(snapshot),"status":"RESEARCH_ONLY",
        "limitations":"Not starter-verified; injuries not yet joined; no automatic settlement mapping; do not trade."},indent=2)+"\n")
    print("Pregame snapshots",len(snapshot),"upcoming games",len(games))

if __name__=="__main__":run()
