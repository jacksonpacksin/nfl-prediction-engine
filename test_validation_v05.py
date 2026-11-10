import unittest
from validation_v05 import chronological_predictions,pav_fit,calibrate,metrics,evaluate,THRESHOLDS,MODELS

class ValidationTests(unittest.TestCase):
    def test_pav_monotonic(self):
        blocks=pav_fit([(0.1,1),(0.2,0),(0.3,1),(0.4,0)])
        probs=[calibrate(x/100,blocks) for x in range(101)]
        self.assertEqual(probs,sorted(probs))

    def test_same_day_no_leakage(self):
        rows=[]
        for i in range(9):
            rows.append(dict(game_date=f"2025-01-{i+1:02d}",season=2025,
                             player_id="a",player="A",game_id=f"a{i}",pass_yards=200))
        rows.append(dict(game_date="2025-01-09",season=2025,
                         player_id="a",player="A",game_id="b9",pass_yards=999))
        p=chronological_predictions(rows)
        games=[r for r in p if r["game_date"]=="2025-01-09" and r["model"]=="shrink_normal" and r["threshold"]==224.5]
        self.assertEqual(len(games),2)
        self.assertAlmostEqual(games[0]["p_raw"],games[1]["p_raw"])

    def test_no_current_game_leakage(self):
        rows=[]
        for i in range(7):
            rows.append(dict(game_date=f"2025-01-{i+1:02d}",season=2025,
                             player_id="a",player="A",game_id=str(i),pass_yards=200))
        a=chronological_predictions(rows)
        rows[-1]["pass_yards"]=900
        b=chronological_predictions(rows)
        self.assertEqual([x["p_raw"] for x in a],[x["p_raw"] for x in b])
        self.assertNotEqual([x["actual"] for x in a],[x["actual"] for x in b])

    def test_holdout_outcomes_do_not_change_selected_model_or_calibration(self):
        rows=[]
        for season in (2022,2023,2024,2025,2026):
            for i in range(12):
                rows.append(dict(game_date=f"{season}-09-{i+1:02d}",season=season,
                    player_id="a",player="A",game_id=f"{season}-{i}",pass_yards=190+i*8))
        report_a,cal_a,_=evaluate(rows)
        for r in rows:
            if r["season"]==2026:r["pass_yards"]=500
        report_b,cal_b,_=evaluate(rows)
        self.assertEqual(report_a["selected_model"],report_b["selected_model"])
        self.assertEqual(cal_a,cal_b)

    def test_metrics(self):
        rows=[dict(p_raw=0.8,actual=1),dict(p_raw=0.2,actual=0)]
        self.assertAlmostEqual(metrics(rows)["brier"],0.04)

if __name__=="__main__":unittest.main()
