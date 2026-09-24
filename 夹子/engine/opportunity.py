"""Generic V2 cycle search over a pool graph."""
from dataclasses import dataclass, asdict
from itertools import permutations
from engine.amm_v2 import quote_swap

@dataclass(frozen=True)
class Leg:
    token_in: str
    token_out: str
    amount_in: float
    amount_out: float
    curve_impact_percent: float
    total_impact_percent: float

@dataclass(frozen=True)
class Opportunity:
    route: tuple
    start_amount: float
    final_amount: float
    gross_profit: float
    gas_cost: float
    net_profit: float
    roi_percent: float
    max_curve_impact_percent: float
    passes_filters: bool
    legs: tuple
    def to_dict(self):
        d=asdict(self); d['route']=list(self.route); d['legs']=[asdict(x) for x in self.legs]; return d

def pool_key(a,b): return frozenset((a,b))

def directed_reserves(pool, token_in, token_out):
    if pool['symbol0']==token_in and pool['symbol1']==token_out: return pool['reserve0'], pool['reserve1']
    if pool['symbol1']==token_in and pool['symbol0']==token_out: return pool['reserve1'], pool['reserve0']
    raise ValueError(f"pool lacks {token_in}/{token_out}")

def enumerate_triangles(tokens, base):
    others=[x for x in tokens if x != base]
    return [(base,a,b,base) for a,b in permutations(others,2)]

def simulate_route(route, amount, pools, fee_percent, gas_cost, min_profit, min_roi, max_curve_impact):
    current=amount; legs=[]
    for a,b in zip(route,route[1:]):
        pool=pools.get(pool_key(a,b))
        if not pool: raise ValueError(f"missing pool {a}/{b}")
        rin,rout=directed_reserves(pool,a,b)
        q=quote_swap(current,rin,rout,fee_percent)
        legs.append(Leg(a,b,current,q.amount_out,q.curve_impact_percent,q.total_price_impact_percent))
        current=q.amount_out
    gross=current-amount; net=gross-gas_cost; roi=net/amount*100.0
    maximpact=max(x.curve_impact_percent for x in legs)
    passes=net>=min_profit and roi>=min_roi and maximpact<=max_curve_impact
    return Opportunity(tuple(route),amount,current,gross,gas_cost,net,roi,maximpact,passes,tuple(legs))

def search_triangles(tokens, base, amounts, pools, fee_percent, gas_cost, min_profit, min_roi, max_curve_impact):
    results=[]
    for route in enumerate_triangles(tokens,base):
        if all(pool_key(a,b) in pools for a,b in zip(route,route[1:])):
            for amount in amounts:
                results.append(simulate_route(route,float(amount),pools,fee_percent,gas_cost,min_profit,min_roi,max_curve_impact))
    return sorted(results,key=lambda x:x.net_profit,reverse=True)
