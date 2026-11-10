"""Read-only NFL prediction research dashboard. Deploy on Streamlit Community Cloud."""
import json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent/"data"
st.set_page_config(page_title="NFL Prediction Research",page_icon="🏈",layout="wide")
st.title("🏈 NFL Prediction Research")
st.caption("Independent research dashboard • Read-only • No trading or automatic orders")
st.warning("RESEARCH ONLY: Availability scores are uncalibrated heuristics, not probabilities. No verified executable market edge has been established.")

def json_file(name):
    try:return json.loads((ROOT/name).read_text())
    except (OSError,ValueError,json.JSONDecodeError):return {}

def jsonl(name):
    p=ROOT/name
    if not p.exists():return []
    rows=[]
    with p.open(encoding="utf-8") as file:
        for line in file:
            try:rows.append(json.loads(line))
            except ValueError:continue
    return rows

def table(rows,columns=None):
    if not rows:
        st.info("No records available yet. Run the GitHub Actions NFL refresh workflow.")
        return
    frame=pd.DataFrame(rows)
    if columns:frame=frame[[c for c in columns if c in frame.columns]]
    st.dataframe(frame,use_container_width=True,hide_index=True)

readiness=json_file("research_readiness.json")
availability=json_file("availability_confidence.json")
validation=json_file("availability_outcome_validation.json")
forecasts=jsonl("pregame_forecast_snapshots.jsonl")
quotes=jsonl("kalshi_orderbook_snapshots.jsonl")
candidates=jsonl("kalshi_discovered_candidates.jsonl")

with st.sidebar:
    st.header("Research controls")
    st.caption("Data comes from repository snapshots. Updates appear after the scheduled GitHub refresh and repository sync.")
    st.link_button("View source repository","https://github.com/jacksonpacksin/nfl-prediction-engine")
    st.link_button("Run GitHub refresh","https://github.com/jacksonpacksin/nfl-prediction-engine/actions/workflows/nfl-refresh.yml")
    st.write("Last readiness report:",readiness.get("generated_utc","Not available"))
    st.write("Last availability report:",availability.get("generated_utc","Not available"))
    st.write("Last validation report:",validation.get("generated_utc","Not available"))

a,b,c,d=st.columns(4)
a.metric("Upcoming games",readiness.get("upcoming_games","—"))
b.metric("Discovered contracts",readiness.get("unique_discovered_candidates","—"))
c.metric("Attested starters",readiness.get("player_games_with_attested_starter","—"))
d.metric("Validated outcomes",validation.get("known_outcomes","—"))
st.caption("Market edge status: "+str(readiness.get("market_edge_status","NOT ESTABLISHED")))

tab1,tab2,tab3,tab4=st.tabs(["Pregame forecasts","Availability evidence","Markets & quotes","Outcome validation"])
with tab1:
    st.subheader("Prospective QB passing-yard forecasts")
    st.caption("Model outputs are not starter-verified or market-executable recommendations.")
    latest={}
    for row in forecasts:
        key=(row.get("game_id"),row.get("player_id"),row.get("model_id"),str(row.get("threshold")))
        if key not in latest or row.get("forecast_created_utc","")>latest[key].get("forecast_created_utc",""):
            latest[key]=row
    upcoming=[]
    now=datetime.now(timezone.utc)
    for row in latest.values():
        try:
            kickoff=datetime.fromisoformat(row["kickoff_utc"].replace("Z","+00:00"))
            if kickoff>now:upcoming.append(row)
        except (ValueError,TypeError,KeyError):pass
    table(sorted(upcoming,key=lambda x:x.get("kickoff_utc","")),["kickoff_utc","player","team","opponent","threshold","p_over","model_id","starter_verified","status"])
with tab2:
    st.subheader("Pregame availability confidence")
    st.caption("Score is an evidence index out of 100, NOT the probability of starting. Missing evidence reduces coverage; actual starter confirmation is separate.")
    records=availability.get("records",[])
    labels=sorted({r.get("label","UNKNOWN") for r in records})
    selection=st.multiselect("Filter evidence label",labels,default=labels)
    table([r for r in records if r.get("label","UNKNOWN") in selection],
          ["player","team","game_id","score","evidence_coverage_weight","label","starter_confirmation","forecast_created_utc"])
    st.subheader("Independent starter confirmation")
    attest=json_file("availability_status.json")
    st.metric("Starter attestations",attest.get("starter_confirmed",0))
    st.caption("A strong evidence score cannot create an official starter attestation.")
with tab3:
    st.subheader("Kalshi candidate markets")
    st.caption("Discovery does not verify game, player, threshold or settlement rules. Quotes are timestamped snapshots, not guaranteed fills.")
    table(candidates[-250:],["ticker","title","event_ticker","status","captured_utc"])
    st.subheader("Captured orderbook quotes")
    table(quotes[-250:],["ticker","captured_utc","yes_bid","yes_ask","no_bid","no_ask","error"])
with tab4:
    st.subheader("Prospective passing-activity validation")
    st.write("Status:",validation.get("status","No report yet"))
    st.metric("Known passing-activity outcomes",validation.get("known_outcomes",0))
    st.metric("Unknown outcomes",validation.get("unknown_outcomes",0))
    table(validation.get("bins",[]),["band","n","passing_activity_rate"])
    st.caption("Passing activity (one or more attempts) is NOT official starting status. Missing player-game rows remain UNKNOWN. Small or biased samples cannot establish calibration.")
    with st.expander("Matched outcome records"):
        table(validation.get("records",[]),["game_id","player_id","score","label","outcome","outcome_status"])
with st.expander("Research readiness blockers"):
    for reason in readiness.get("blocking_reasons",[]):st.write("• "+reason)
st.divider()
st.caption("No order placement, authentication to trading accounts, or automated execution. Source: nflverse and publicly captured Kalshi metadata.")
