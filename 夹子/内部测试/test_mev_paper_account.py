import tempfile
import unittest
from pathlib import Path
from engine.mev_paper_account import new_account,choose_candidates,apply_paper_trades,update_account,load_account

def candidate(chain="BSC",snapshot=1,net=5.0,start=500.0,passes=True,route=None,impact=0.1,gas=0.1):
    return {"chain":chain,"snapshot":snapshot,"route":route or ["USDT","WBNB","USDC","USDT"],
            "start_amount":start,"gross_profit":net+gas,"gas_cost":gas,"net_profit":net,
            "roi_percent":net/start*100,"max_curve_impact_percent":impact,
            "passes_filters":passes}

class TestMevPaperAccount(unittest.TestCase):
    def test_empty_partial_and_invalid_existing_accounts_never_reset(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.json'
            bad_list=new_account(); bad_list['paper_trades']={}
            for payload in ('{}', '{"equity_usd":9990}', __import__('json').dumps(bad_list)):
                p.write_text(payload)
                with self.assertRaises(RuntimeError): load_account(p)
                self.assertEqual(p.read_text(),payload)

    def test_cap_is_ten_percent(self):
        a=new_account(); self.assertEqual(len(choose_candidates(a,[candidate(start=1000,net=10)])),1)
        self.assertEqual(choose_candidates(a,[candidate(start=2500,net=30)]),[])
    def test_probability_ev_terms_present(self):
        s=choose_candidates(new_account(),[candidate()])
        self.assertEqual(len(s),1)
        self.assertGreater(s[0]["_success_probability"],0)
        self.assertGreater(s[0]["_expected_value_usd"],0)
        self.assertGreater(s[0]["_latency_loss_usd"],0)
        self.assertGreater(s[0]["_failure_cost_usd"],0)
    def test_dynamic_size_selects_ev_max_for_same_route(self):
        a=new_account()
        small=candidate(start=100,net=2)
        large=candidate(start=500,net=8)
        s=choose_candidates(a,[small,large])
        self.assertEqual(len(s),1)
        self.assertEqual(s[0]["start_amount"],500)
    def test_probability_declines_with_impact(self):
        low=choose_candidates(new_account(),[candidate(route=["USDT","A","B","USDT"],impact=0.01)])[0]
        high=choose_candidates(new_account(),[candidate(route=["USDT","C","D","USDT"],impact=1.5)])[0]
        self.assertGreater(low["_success_probability"],high["_success_probability"])
    def test_deterministic_sample_books_success_or_failure(self):
        a=new_account(); s=choose_candidates(a,[candidate()])
        a=apply_paper_trades(a,s); t=a["paper_trades"][0]
        self.assertIn(t["sampled_success"],(True,False))
        expected=t["success_probability"]*s[0]["_success_net_profit_usd"]-(1-t["success_probability"])*t["failure_cost_usd"]
        self.assertAlmostEqual(t["expected_value_usd"],expected)
    def test_one_per_chain(self):
        cs=[candidate(snapshot=1),candidate(snapshot=2,net=6)]
        self.assertEqual(len(choose_candidates(new_account(),cs)),1)
    def test_idempotency(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/"a.json"); _,s1=update_account([candidate()],p); _,s2=update_account([candidate()],p)
            self.assertEqual(len(s1),1); self.assertEqual(s2,[])
    def test_rejected_not_booked(self):
        self.assertEqual(choose_candidates(new_account(),[candidate(passes=False)]),[])
    def test_missing_created_at_is_backfilled_without_reset(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"legacy.json"
            legacy=new_account(); legacy["created_at_utc"]=None; legacy["equity_usd"]=10023.45
            p.write_text(__import__("json").dumps(legacy),encoding="utf-8")
            loaded=load_account(str(p))
            self.assertEqual(loaded["created_at_utc"],"2026-09-19T16:37:42+00:00")
            self.assertEqual(loaded["equity_usd"],10023.45)
    def test_corrupt_account_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.json"; p.write_text("{broken",encoding="utf-8")
            with self.assertRaises(RuntimeError): load_account(str(p))

if __name__=="__main__": unittest.main()
