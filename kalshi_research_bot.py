"""Grounded, no-key Kalshi research assistant. Never fabricates actionable picks."""
from datetime import datetime,timezone,timedelta
from market_ev import parse_utc

def analyze(question,forecasts,quotes,candidates,availability,readiness,reconciled,now=None):
    now=now or datetime.now(timezone.utc)
    q=question.lower().strip()
    verified={r.get("ticker") for r in reconciled if r.get("status")=="VERIFIED_REVIEWED"}
    fresh=[]
    for row in quotes:
        try:
            if row.get("ticker") in verified and now-timedelta(minutes=15)<=parse_utc(row["captured_utc"])<=now and (row.get("yes_ask") is not None or row.get("no_ask") is not None):
                fresh.append(row)
        except (KeyError,ValueError,TypeError):continue
    latest={}
    for row in fresh:
        ticker=row["ticker"]
        if ticker not in latest or row["captured_utc"]>latest[ticker]["captured_utc"]:latest[ticker]=row
    status=readiness.get("market_edge_status","NOT_ESTABLISHED")
    if any(term in q for term in ("pick","bet","buy","trade","best","recommend","edge","value","today","tonight")):
        if not latest:
            return ("**Current decision: NO VERIFIED PICK.**\n\n"
                    "I cannot responsibly name a Kalshi side because there is no recent (≤15-minute) quote "
                    "linked to a manually reviewed contract in the saved research data. "
                    "The player forecasts, starter evidence and exact settlement rules must also match.\n\n"
                    f"**Market-edge validation:** {status}. This is a data-readiness decision, not a claim that every market is fairly priced.\n\n"
                    "To unlock a candidate, capture a fresh order book, verify the exact Kalshi ticker/game/player/threshold and rules, "
                    "and independently attest the starter. Do not treat a depth-chart projection or an availability score as confirmation.")
        tickers=", ".join(sorted(latest)[:8])
        return (f"**Reviewed contracts with recent quote snapshots:** {tickers}.\n\n"
                "These are **not picks**: a reviewed contract and recent quote alone do not establish "
                "matched pre-kickoff model probability, starter verification, fee-adjusted positive EV, "
                "executable depth or out-of-sample calibration. No trade recommendation is authorized.\n\n"
                f"**Market-edge validation:** {status}.")
    if any(term in q for term in ("injur","starter","available","confidence","qb")):
        rows=availability.get("records",[])
        if not rows:return "No pregame availability scores are stored yet. Run the scheduled NFL refresh. Scores are not starter confirmations."
        matches=[r for r in rows if str(r.get("player","")).lower() in q and r.get("player")] if len(q)>20 else []
        shown=(matches or rows)[:5]
        lines=[f"- {r.get('player','Unknown')}: {r.get('score','—')}/100, {r.get('label','UNKNOWN')}; starter confirmation: **separate and unverified by this index**" for r in shown]
        return "**Saved availability evidence (uncalibrated):**\n"+"\n".join(lines)+"\n\nNo score should be interpreted as a starting probability."
    if any(term in q for term in ("accur","backtest","valid","perform")):
        return (f"**Research validation:** {status}. Historical prop backtests do not demonstrate a live Kalshi edge. "
                "Check the Outcome validation tab for prospective passing-activity counts and unknown outcomes.")
    return ("Ask me **'What should I pick on Kalshi?'**, **'Show QB availability'**, "
            "or **'Is the model validated?'**. I use only saved repository evidence, "
            "not live unsourced news. No subscription or AI API key is required.")

