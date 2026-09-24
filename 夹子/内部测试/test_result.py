import unittest
from engine.result import RouteLeg, RouteResult

class TestResult(unittest.TestCase):
    def test_serialization(self):
        leg=RouteLeg('A','B','venue',1,2,0.3,0.1,100,{})
        r=RouteResult('X',('A','B'),1,2,1,0.1,0.9,90,0.1,True,(leg,),'fixed',1)
        d=r.to_dict(); self.assertEqual(d['route'],['A','B']); self.assertEqual(d['legs'][0]['venue'],'venue')
if __name__=='__main__': unittest.main()
