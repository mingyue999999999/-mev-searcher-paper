import unittest
from engine.amm_v2 import get_amount_out, quote_swap
class TestAMM(unittest.TestCase):
    def test_output_positive_and_below_reserve(self):
        out=get_amount_out(100,10000,5000,0.25); self.assertGreater(out,0); self.assertLess(out,5000)
    def test_size_increases_curve_impact(self):
        a=quote_swap(10,10000,5000,0.25); b=quote_swap(1000,10000,5000,0.25); self.assertGreater(b.curve_impact_percent,a.curve_impact_percent)
    def test_fee_separate_from_curve(self):
        q=quote_swap(1,1_000_000,500_000,0.25); self.assertLess(q.curve_impact_percent,0.001); self.assertGreater(q.total_price_impact_percent,0.24)
if __name__=='__main__': unittest.main()
