import unittest
from engine.opportunity import pool_key, search_triangles
class TestOpportunity(unittest.TestCase):
    def test_two_directions(self):
        pools={
          pool_key('USDT','WBNB'):{'symbol0':'USDT','symbol1':'WBNB','reserve0':1_000_000,'reserve1':2000},
          pool_key('WBNB','USDC'):{'symbol0':'WBNB','symbol1':'USDC','reserve0':2000,'reserve1':1_000_000},
          pool_key('USDT','USDC'):{'symbol0':'USDT','symbol1':'USDC','reserve0':1_000_000,'reserve1':1_000_000},
        }
        r=search_triangles(['USDT','WBNB','USDC'],'USDT',[100],pools,0.25,0.1,1,0.05,1)
        self.assertEqual(len(r),2)
if __name__=='__main__': unittest.main()
