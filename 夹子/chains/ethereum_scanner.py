"""Ethereum Uniswap V2/V3 read-only triangle scanner.

Uses a fixed block for all pool discovery/state reads and QuoterV2 eth_call requests.
No wallet, signing, approvals, or transactions.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path
from web3 import Web3

from config.ethereum import *
from engine.amm_v2 import quote_swap
from engine.result import RouteLeg, RouteResult

ZERO = "0x0000000000000000000000000000000000000000"
V2_FACTORY_ABI = [{"inputs":[{"name":"tokenA","type":"address"},{"name":"tokenB","type":"address"}],"name":"getPair","outputs":[{"name":"pair","type":"address"}],"stateMutability":"view","type":"function"}]
V2_PAIR_ABI = [
    {"inputs":[],"name":"getReserves","outputs":[{"name":"_reserve0","type":"uint112"},{"name":"_reserve1","type":"uint112"},{"name":"_blockTimestampLast","type":"uint32"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token0","outputs":[{"name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token1","outputs":[{"name":"","type":"address"}],"stateMutability":"view","type":"function"},
]
V3_FACTORY_ABI = [{"inputs":[{"name":"tokenA","type":"address"},{"name":"tokenB","type":"address"},{"name":"fee","type":"uint24"}],"name":"getPool","outputs":[{"name":"pool","type":"address"}],"stateMutability":"view","type":"function"}]
V3_POOL_ABI = [
    {"inputs":[],"name":"token0","outputs":[{"name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token1","outputs":[{"name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"liquidity","outputs":[{"name":"","type":"uint128"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"slot0","outputs":[{"name":"sqrtPriceX96","type":"uint160"},{"name":"tick","type":"int24"},{"name":"observationIndex","type":"uint16"},{"name":"observationCardinality","type":"uint16"},{"name":"observationCardinalityNext","type":"uint16"},{"name":"feeProtocol","type":"uint8"},{"name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"},
]
QUOTER_ABI = [{"inputs":[{"components":[{"name":"tokenIn","type":"address"},{"name":"tokenOut","type":"address"},{"name":"amountIn","type":"uint256"},{"name":"fee","type":"uint24"},{"name":"sqrtPriceLimitX96","type":"uint160"}],"name":"params","type":"tuple"}],"name":"quoteExactInputSingle","outputs":[{"name":"amountOut","type":"uint256"},{"name":"sqrtPriceX96After","type":"uint160"},{"name":"initializedTicksCrossed","type":"uint32"},{"name":"gasEstimate","type":"uint256"}],"stateMutability":"nonpayable","type":"function"}]

def checksum(a): return Web3.to_checksum_address(a)

def connect():
    errs=[]
    for url in RPC_URLS:
        try:
            w3=Web3(Web3.HTTPProvider(url,request_kwargs={"timeout":12}))
            if w3.is_connected() and w3.eth.chain_id == CHAIN_ID:
                return w3,url
        except Exception as e: errs.append(f"{url}: {e}")
    raise RuntimeError("No Ethereum RPC available: "+" | ".join(errs))

def sym(addr):
    for s,t in TOKENS.items():
        if t["address"].lower()==addr.lower(): return s
    return "UNKNOWN"

def human(raw, symbol): return raw/(10**TOKENS[symbol]["decimals"])
def raw(amount, symbol): return int(amount*(10**TOKENS[symbol]["decimals"]))
def pkey(a,b): return frozenset((a,b))

def discover_v2(w3, block):
    f=w3.eth.contract(address=checksum(DEXES["uniswap_v2"]["factory"]),abi=V2_FACTORY_ABI)
    pools={}
    for a,b in [("WETH","USDT"),("WETH","USDC"),("USDT","USDC")]:
        addr=f.functions.getPair(checksum(TOKENS[a]["address"]),checksum(TOKENS[b]["address"])).call(block_identifier=block)
        if addr.lower()==ZERO: continue
        c=w3.eth.contract(address=checksum(addr),abi=V2_PAIR_ABI)
        t0=c.functions.token0().call(block_identifier=block); t1=c.functions.token1().call(block_identifier=block)
        r0,r1,_=c.functions.getReserves().call(block_identifier=block)
        s0,s1=sym(t0),sym(t1)
        pools[pkey(a,b)]={"venue":"Uniswap V2","address":checksum(addr),"symbol0":s0,"symbol1":s1,"reserve0":human(r0,s0),"reserve1":human(r1,s1)}
    return pools

def discover_v3(w3, block):
    f=w3.eth.contract(address=checksum(DEXES["uniswap_v3"]["factory"]),abi=V3_FACTORY_ABI)
    pools={}
    for a,b in [("WETH","USDT"),("WETH","USDC"),("USDT","USDC")]:
        key=pkey(a,b); pools[key]=[]
        for fee in DEXES["uniswap_v3"]["fee_tiers"]:
            addr=f.functions.getPool(checksum(TOKENS[a]["address"]),checksum(TOKENS[b]["address"]),fee).call(block_identifier=block)
            if addr.lower()==ZERO: continue
            c=w3.eth.contract(address=checksum(addr),abi=V3_POOL_ABI)
            liq=int(c.functions.liquidity().call(block_identifier=block))
            if liq<=0: continue
            t0=c.functions.token0().call(block_identifier=block); t1=c.functions.token1().call(block_identifier=block)
            slot0=c.functions.slot0().call(block_identifier=block)
            pools[key].append({"venue":f"Uniswap V3 {fee/10000:.2f}%","address":checksum(addr),"fee":fee,"liquidity":liq,"token0":t0,"token1":t1,"symbol0":sym(t0),"symbol1":sym(t1),"sqrtPriceX96":int(slot0[0])})
        pools[key].sort(key=lambda x:x["liquidity"],reverse=True)
    return pools

def v2_quote(pool, token_in, token_out, amount):
    if pool["symbol0"]==token_in:
        rin,rout=pool["reserve0"],pool["reserve1"]
    else:
        rin,rout=pool["reserve1"],pool["reserve0"]
    q=quote_swap(amount,rin,rout,DEXES["uniswap_v2"]["fee_percent"])
    return RouteLeg(token_in,token_out,pool["venue"],amount,q.amount_out,DEXES["uniswap_v2"]["fee_percent"],q.total_price_impact_percent,V2_GAS_PER_LEG,{"pool":pool["address"],"curve_impact_percent":q.curve_impact_percent})

def v3_spot(pool, token_in, token_out):
    raw_ratio=(pool["sqrtPriceX96"]**2)/(2**192)
    s0,s1=pool["symbol0"],pool["symbol1"]
    human_ratio=raw_ratio*(10**(TOKENS[s0]["decimals"]-TOKENS[s1]["decimals"]))
    if token_in==s0 and token_out==s1: return human_ratio
    return 1.0/human_ratio

def v3_quote(w3, quoter, pool, token_in, token_out, amount, block):
    params=(checksum(TOKENS[token_in]["address"]),checksum(TOKENS[token_out]["address"]),raw(amount,token_in),int(pool["fee"]),0)
    out,_,ticks,gas=quoter.functions.quoteExactInputSingle(params).call(block_identifier=block)
    amount_out=human(int(out),token_out)
    spot=v3_spot(pool,token_in,token_out); exec_rate=amount_out/amount if amount else 0
    impact=max(0.0,(spot-exec_rate)/spot*100) if spot>0 else 0.0
    return RouteLeg(token_in,token_out,pool["venue"],amount,amount_out,pool["fee"]/10000.0,impact,int(gas),{"pool":pool["address"],"ticks_crossed":int(ticks)})

def best_leg(w3,quoter,v2,v3,token_in,token_out,amount,block):
    candidates=[]; key=pkey(token_in,token_out)
    if key in v2:
        try: candidates.append(v2_quote(v2[key],token_in,token_out,amount))
        except Exception: pass
    for pool in v3.get(key,[])[:3]:
        try: candidates.append(v3_quote(w3,quoter,pool,token_in,token_out,amount,block))
        except Exception: continue
    if not candidates: raise RuntimeError(f"No quote source for {token_in}/{token_out}")
    return max(candidates,key=lambda x:x.amount_out)

def native_usdt_spot(v2):
    p=v2.get(pkey("WETH","USDT"))
    if not p: raise RuntimeError("WETH/USDT V2 pool required for gas conversion")
    if p["symbol0"]=="WETH": return p["reserve1"]/p["reserve0"]
    return p["reserve0"]/p["reserve1"]

def scan(output_dir="output"):
    w3,url=connect(); block=w3.eth.block_number
    v2=discover_v2(w3,block); v3=discover_v3(w3,block)
    quoter=w3.eth.contract(address=checksum(DEXES["uniswap_v3"]["quoter_v2"]),abi=QUOTER_ABI)
    gas_price=int(w3.eth.gas_price); weth_usdt=native_usdt_spot(v2)
    routes=[(BASE_TOKEN,a,b,BASE_TOKEN) for a,b in permutations([x for x in TOKENS if x!=BASE_TOKEN],2)]
    results=[]
    print("="*72); print("ETHEREUM READ-ONLY UNISWAP V2/V3 SEARCHER"); print("="*72); print(f"RPC: {url}\nSnapshot block: {block:,}")
    for route in routes:
        for start in TEST_AMOUNTS_USD:
            cur=float(start); legs=[]
            try:
                for a,b in zip(route,route[1:]):
                    leg=best_leg(w3,quoter,v2,v3,a,b,cur,block); legs.append(leg); cur=leg.amount_out
            except Exception:
                continue
            gas_units=ROUTE_OVERHEAD_GAS+sum((x.gas_units or V2_GAS_PER_LEG) for x in legs)
            network_cost=gas_price*gas_units/1e18*GAS_SAFETY_MULTIPLIER*weth_usdt
            gross=cur-start; net=gross-network_cost; roi=net/start*100; maximpact=max((x.impact_percent or 0) for x in legs)
            passes=net>=MIN_NET_PROFIT_USD and roi>=MIN_ROI_PERCENT and maximpact<=MAX_TOTAL_IMPACT_PERCENT
            results.append(RouteResult(CHAIN_NAME,route,start,cur,gross,network_cost,net,roi,maximpact,passes,tuple(legs),"fixed_block",block))
    results.sort(key=lambda x:x.net_profit,reverse=True)
    for r in results[:10]:
        print(f"{'PASS' if r.passes_filters else 'REJECT':6} | {' -> '.join(r.route):32} | in {r.start_amount:8.2f} | net {r.net_profit:+10.4f} | ROI {r.roi_percent:+8.4f}% | impact {r.max_impact_percent:.4f}%")
    passing=[x for x in results if x.passes_filters]
    payload={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"chain":CHAIN_NAME,"block":block,"rpc":url,"simulation_only":True,"gas":{"gwei":gas_price/1e9,"weth_usdt":weth_usdt,"safety_multiplier":GAS_SAFETY_MULTIPLIER},"venues":{"v2_pools":len(v2),"v3_pools":sum(len(v) for v in v3.values())},"candidates_tested":len(results),"passing_filters":len(passing),"results":[x.to_dict() for x in results]}
    d=Path(output_dir); d.mkdir(parents=True,exist_ok=True); p=d/"latest_ethereum_scan.json"; p.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print(f"Candidates tested: {len(results)} | Passing filters: {len(passing)}\nResult file: {p}\nSIMULATION ONLY: no wallet, no private key, no transaction signing.")
    return payload

if __name__=="__main__": scan()
