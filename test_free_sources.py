import unittest
from datetime import datetime,timezone
from free_depth_charts import qb_candidates
from availability_evidence import availability

class FreeSourceTests(unittest.TestCase):
    def test_qb_only(self):
        rows=[{"position":"QB","gsis_id":"00-1","club_code":"KC","depth_team":1},
              {"position":"WR","gsis_id":"00-2","club_code":"KC"}]
        result=qb_candidates(rows,"2026-11-10T12:00:00Z")
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["status"],"PROJECTED_DEPTH_CHART_ONLY")
    def test_projection_is_not_confirmation(self):
        forecast={"game_id":"G","player_id":"00-1","team":"KC",
                  "forecast_created_utc":"2026-11-10T12:00:00Z",
                  "kickoff_utc":"2026-11-10T20:00:00Z"}
        depth=[{"player_id":"00-1","team":"KC","captured_utc":"2026-11-10T11:00:00Z","depth_rank":1}]
        result=availability(forecast,[],[],depth_charts=depth)
        self.assertEqual(result["depth_chart_status"],"PROJECTED_ONLY")
        self.assertEqual(result["starter_status"],"UNVERIFIED")
        self.assertFalse(result["actionable"])
    def test_future_depth_snapshot_is_not_used(self):
        forecast={"game_id":"G","player_id":"00-1","team":"KC",
                  "forecast_created_utc":"2026-11-10T12:00:00Z",
                  "kickoff_utc":"2026-11-10T20:00:00Z"}
        depth=[{"player_id":"00-1","team":"KC","captured_utc":"2026-11-10T13:00:00Z"}]
        self.assertEqual(availability(forecast,[],[],depth_charts=depth)["depth_chart_status"],"UNKNOWN")
if __name__=="__main__":unittest.main()
