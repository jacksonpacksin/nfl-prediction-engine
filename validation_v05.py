"""v0.5: strictly chronological QB passing-yard benchmark and holdout evaluation.

All model inputs are from games strictly earlier than the prediction's game date.
Candidate models are selected on 2025; isotonic calibration is fit on 2025;
2026 is an untouched holdout. No market data or trading is used.
"""
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

THRESHOLDS=(199.5,224.5,249.5,274.5,299.5)
MODELS=("shrink_normal","rolling_normal","empirical","league_prior")
MIN_GAMES=6
EPS=1e-4

def clip(p):
    return min(1-EPS,max(EPS,p))

def normal_survival(x,mu,sd):
    return clip(0.5*math.erfc((x-mu)/(sd*math.sqrt(2))))

def forecast(model,player_history,league_history,threshold):
    values=player_history[-12:]
    n=len(values)
    if model=="shrink_normal":
        mu=(n*statistics.mean(values)+6*220)/(n+6)
        sd=max(55,statistics.stdev(values))
        return normal_survival(threshold,mu,sd)
    if model=="rolling_normal":
        return normal_survival(threshold,statistics.mean(values),max(55,statistics.stdev(values)))
    if model=="empirical":
        # Laplace smoothing; deliberately simple and auditable.
        return clip((sum(v>threshold for v in values)+1)/(n+2))
    if model=="league_prior":
        # Prior *player-games* only; never future or same-day games.
        return clip((sum(v>threshold for v in league_history)+1)/(len(league_history)+2))
    raise ValueError(model)

def chronological_predictions(rows):
    player_history=defaultdict(list)
    league_history=[]
    grouped=defaultdict(list)
    for row in rows:
        grouped[row["game_date"]].append(row)
    output=[]
    for date in sorted(grouped):
        games=grouped[date]
        for row in games:
            history=player_history[row["player_id"]]
            if len(history)<MIN_GAMES:
                continue
            for threshold in THRESHOLDS:
                outcome=int(int(row["pass_yards"])>threshold)
                for model in MODELS:
                    output.append(dict(game_date=date,season=int(row["season"]),player_id=row["player_id"],
                        player=row["player"],game_id=row["game_id"],threshold=threshold,actual=outcome,
                        model=model,p_raw=forecast(model,history,league_history,threshold),
                        history_n=len(history)))
        # Update only AFTER every game on the same date has been forecast.
        for row in games:
            value=int(row["pass_yards"])
            player_history[row["player_id"]].append(value)
            league_history.append(value)
    return output

def pav_fit(pairs):
    """Nondecreasing weighted isotonic regression; no sklearn dependency."""
    if not pairs:
        raise ValueError("Calibration needs validation observations")
    ordered=sorted(pairs,key=lambda x:x[0])
    blocks=[]
    for p,y in ordered:
        blocks.append([p,p,float(y),1])
        while len(blocks)>1 and blocks[-2][2]/blocks[-2][3]>blocks[-1][2]/blocks[-1][3]:
            b=blocks.pop(); a=blocks.pop()
            blocks.append([a[0],b[1],a[2]+b[2],a[3]+b[3]])
    return [{"low":b[0],"high":b[1],"probability":clip(b[2]/b[3]),"n":b[3]} for b in blocks]

def calibrate(p,blocks):
    # Piecewise-constant isotonic prediction, fixed before holdout.
    for block in blocks:
        if p<=block["high"]:
            return block["probability"]
    return blocks[-1]["probability"]

def metrics(rows,key="p_raw"):
    if not rows:return {"n":0}
    p=[clip(float(r[key])) for r in rows]
    y=[int(r["actual"]) for r in rows]
    n=len(rows)
    return {"n":n,"brier":round(sum((a-b)**2 for a,b in zip(p,y))/n,6),
        "log_loss":round(-sum(b*math.log(a)+(1-b)*math.log(1-a) for a,b in zip(p,y))/n,6),
        "mean_probability":round(statistics.mean(p),4),
        "observed_rate":round(statistics.mean(y),4),
        "ece_10_bins":round(sum(len(bucket)/n*abs(statistics.mean(float(r[key]) for r in bucket)-
                 statistics.mean(int(r["actual"]) for r in bucket))
                 for bucket in ([r for r in rows if min(9,int(clip(float(r[key]))*10))==i] for i in range(10))
                 if bucket),6)}

def reliability(rows,key="p_raw"):
    result=[]
    for i in range(10):
        group=[r for r in rows if min(9,int(clip(float(r[key]))*10))==i]
        result.append({"bin":i,"n":len(group),
            "mean_pred":round(statistics.mean(float(r[key]) for r in group),5) if group else None,
            "observed":round(statistics.mean(int(r["actual"]) for r in group),5) if group else None})
    return result

def evaluate(rows):
    all_predictions=chronological_predictions(rows)
    val=[r for r in all_predictions if r["season"]==2025]
    test=[r for r in all_predictions if r["season"]==2026]
    if not val or not test:
        raise ValueError("2025 validation and 2026 holdout predictions both required")
    validation_scores={m:metrics([r for r in val if r["model"]==m]) for m in MODELS}
    winner=min(MODELS,key=lambda m:(validation_scores[m]["brier"],validation_scores[m]["log_loss"],m))
    chosen_val=[r for r in val if r["model"]==winner]
    # Separate monotonic maps per threshold, fitted ONLY to 2025 validation.
    calibration={str(t):pav_fit([(r["p_raw"],r["actual"]) for r in chosen_val if r["threshold"]==t])
                 for t in THRESHOLDS}
    for r in test:
        if r["model"]==winner:
            r["p_calibrated"]=calibrate(r["p_raw"],calibration[str(r["threshold"])])
    selected=[r for r in test if r["model"]==winner]
    holdout_scores={m:metrics([r for r in test if r["model"]==m]) for m in MODELS}
    calibrated_score=metrics(selected,"p_calibrated")
    threshold_scores={str(t):{"raw":metrics([r for r in selected if r["threshold"]==t]),
                              "calibrated":metrics([r for r in selected if r["threshold"]==t],"p_calibrated")}
                      for t in THRESHOLDS}
    report={"version":"0.5","status":"evaluated","protocol":{
        "history_start":2022,"selection_period":2025,"holdout_period":2026,
        "minimum_prior_player_games":MIN_GAMES,"same_day_leakage_prevented":True,
        "model_selection":"lowest 2025 validation Brier score; fixed before 2026 evaluation",
        "calibration":"per-threshold isotonic regression fitted on 2025 only",
        "caveats":["The 2025 calibration data also selected the model; evaluate only on 2026 holdout.",
                   "Multiple thresholds for one player-game are correlated.",
                   "The 2026 holdout is partial and becomes longer as games finish.",
                   "Data are historical game summaries, not point-in-time archived market or injury feeds.",
                   "Do not treat this report as evidence of profitable trades."]},
        "validation_model_scores":validation_scores,"selected_model":winner,
        "holdout_model_scores":holdout_scores,
        "holdout_selected_raw":holdout_scores[winner],
        "holdout_selected_calibrated":calibrated_score,
        "holdout_by_threshold":threshold_scores,
        "holdout_reliability_raw":reliability(selected),
        "holdout_reliability_calibrated":reliability(selected,"p_calibrated"),
        "validation_n_player_games":len({(r["game_date"],r["player_id"],r["game_id"]) for r in chosen_val}),
        "holdout_n_player_games":len({(r["game_date"],r["player_id"],r["game_id"]) for r in selected})}
    return report,calibration,selected

def run(source="data/qb_game_logs.csv",output="data"):
    with open(source,newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    if not rows:raise ValueError("No QB game logs")
    report,calibration,selected=evaluate(rows)
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    (out/"v05_model_report.json").write_text(json.dumps(report,indent=2)+"\n")
    (out/"v05_calibration.json").write_text(json.dumps(calibration,indent=2)+"\n")
    fields=("game_date","season","player_id","player","game_id","threshold","actual","model","p_raw","p_calibrated","history_n")
    with (out/"v05_holdout_predictions.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in selected:writer.writerow({k:row[k] for k in fields})
    print(json.dumps({"selected_model":report["selected_model"],
                      "validation":report["validation_model_scores"][report["selected_model"]],
                      "holdout_raw":report["holdout_selected_raw"],
                      "holdout_calibrated":report["holdout_selected_calibrated"]},indent=2))
    return report

if __name__=="__main__":
    run()
