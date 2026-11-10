"""Free nflverse depth-chart snapshots: projected QB candidates, NEVER confirmed starters.

Historical depth charts are not a timestamped starter feed. Capture time is the
only admissible as-of timestamp. No paid API key or scraping required.
"""
import json
from datetime import datetime,timezone
from pathlib import Path
import nflreadpy as nfl

def qb_candidates(rows,captured):
    out=[]
    for r in rows:
        pos=str(r.get("position") or r.get("pos") or "").upper()
        if pos!="QB":continue
        player_id=r.get("gsis_id") or r.get("player_id")
        team=r.get("club_code") or r.get("team")
        if not player_id or not team:continue
        out.append({"player_id":str(player_id),"team":str(team),
                    "player":r.get("full_name") or r.get("player_name"),
                    "depth_rank":r.get("depth_team") or r.get("depth_chart_order") or r.get("rank"),
                    "season":r.get("season"),"week":r.get("week"),
                    "captured_utc":captured,"status":"PROJECTED_DEPTH_CHART_ONLY",
                    "source":"nflverse depth charts; not a confirmed game starter"})
    return out

def run():
    root=Path("data");root.mkdir(exist_ok=True)
    captured=datetime.now(timezone.utc).isoformat()
    status={"captured_utc":captured,"status":"UNAVAILABLE","qb_rows":0}
    try:
        loader=getattr(nfl,"load_depth_charts",None)
        if loader is None:raise RuntimeError("nflreadpy version has no load_depth_charts")
        frame=loader(seasons=datetime.now(timezone.utc).year)
        rows=qb_candidates(frame.to_dicts(),captured)
        # Store a fresh snapshot; never backdate historical depth charts.
        (root/"free_depth_chart_qbs.json").write_text(json.dumps(rows,indent=2,default=str)+"\n")
        status.update(status="PROJECTED_ONLY",qb_rows=len(rows))
    except Exception as exc:
        status["error"]=str(exc)
    (root/"free_depth_chart_status.json").write_text(json.dumps(status,indent=2)+"\n")
    print(json.dumps(status))
if __name__=="__main__":run()
