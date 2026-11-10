import unittest
from availability_confidence import evaluate

F={"game_id":"G","player_id":"P","player":"Test QB","team":"KC",
   "forecast_created_utc":"2026-11-10T17:00:00Z"}
class ConfidenceTests(unittest.TestCase):
    def test_no_data_is_insufficient(self):
        x=evaluate(F,[],[],[])
        self.assertIsNone(x["score"])
        self.assertEqual(x["label"],"INSUFFICIENT_EVIDENCE")
        self.assertEqual(x["starter_confirmation"],"NOT_ASSESSED_BY_THIS_SCORE")
    def test_projection_and_workload_not_confirmation(self):
        d=[{"player_id":"P","team":"KC","depth_rank":1,"captured_utc":"2026-11-10T16:00:00Z"}]
        logs=[{"player_id":"P","team":"KC","game_date":"2026-11-08","pass_attempts":"30"}]
        x=evaluate(F,[],d,logs)
        self.assertEqual(x["score"],80)
        self.assertEqual(x["label"],"STRONG_INDICATORS")
        self.assertEqual(x["starter_confirmation"],"NOT_ASSESSED_BY_THIS_SCORE")
    def test_future_reports_not_used(self):
        injuries=[{"player_id":"P","captured_utc":"2026-11-10T18:00:00Z","report_status":"out"}]
        self.assertIsNone(evaluate(F,injuries,[],[])["factors"]["injury"]["points"])
    def test_out_flag_overrides_strong_workload(self):
        injuries=[{"player_id":"P","captured_utc":"2026-11-10T16:00:00Z","report_status":"out"}]
        depth=[{"player_id":"P","team":"KC","depth_rank":1,"captured_utc":"2026-11-10T16:00:00Z"}]
        logs=[{"player_id":"P","team":"KC","game_date":"2026-11-08","pass_attempts":"30"}]
        self.assertEqual(evaluate(F,injuries,depth,logs)["label"],"HIGH_RISK_INJURY_FLAG")
    def test_old_depth_chart_excluded(self):
        depth=[{"player_id":"P","team":"KC","depth_rank":1,"captured_utc":"2026-11-01T16:00:00Z"}]
        self.assertIsNone(evaluate(F,[],depth,[])["factors"]["depth_chart"]["points"])
if __name__=="__main__":unittest.main()
