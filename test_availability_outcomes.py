import unittest
from datetime import datetime,timezone
from availability_outcomes import freeze,reconcile,report

NOW=datetime(2026,11,15,15,tzinfo=timezone.utc)
BASE={"game_id":"2026_11_KC_BUF","player_id":"P","score":80,
      "evidence_coverage_weight":80,"label":"STRONG_INDICATORS",
      "forecast_created_utc":"2026-11-15T14:00:00Z",
      "kickoff_utc":"2026-11-15T18:00:00Z"}
class OutcomesTests(unittest.TestCase):
    def test_freeze_only_before_kickoff(self):
        self.assertEqual(len(freeze([BASE],[],NOW)),1)
        self.assertEqual(freeze([BASE],[],datetime(2026,11,15,19,tzinfo=timezone.utc)),[])
    def test_missing_stats_unknown_after_game(self):
        row=freeze([BASE],[],NOW)[0]
        outcome=reconcile([row],[],datetime(2026,11,16,1,tzinfo=timezone.utc))[0]
        self.assertIsNone(outcome["outcome"])
        self.assertEqual(outcome["outcome_status"],"UNKNOWN_NO_PLAYER_GAME_STAT")
    def test_one_attempt_observed_not_starter(self):
        row=freeze([BASE],[],NOW)[0]
        logs=[{"game_id":BASE["game_id"],"player_id":"P","pass_attempts":"1"}]
        result=reconcile([row],logs,datetime(2026,11,16,1,tzinfo=timezone.utc))[0]
        self.assertEqual(result["outcome"],1)
        self.assertIn("NOT official start",result["outcome_definition"])
    def test_no_early_outcome(self):
        row=freeze([BASE],[],NOW)[0]
        self.assertEqual(reconcile([row],[],NOW),[])
    def test_small_sample_not_validated(self):
        r=report([{"score":80,"outcome":1,"evidence_coverage_weight":80}])
        self.assertEqual(r["status"],"INSUFFICIENT_PROSPECTIVE_DATA")
if __name__=="__main__":unittest.main()
