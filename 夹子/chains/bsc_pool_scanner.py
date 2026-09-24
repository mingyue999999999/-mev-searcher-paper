"""BSC PancakeSwap V2 snapshot scanner and read-only opportunity searcher."""
import json
from datetime import datetime, timezone
from pathlib import Path
from web3 import Web3
from config.bsc import (
    RPC_URLS,TOKENS,DEXES,SCAN_PAIRS,BASE_TOKEN,TEST_AMOUNTS_USD,
    MIN_NET_PROFIT_USD,MIN_ROI_PERCENT,MAX_CURVE_IMPACT_PERCENT,
    GAS_UNITS_ESTIMATE,GAS_SAFETY_MULTIPLIER,
)
from engine.opportunity import pool_key, search_triangles

ZERO="0x0000000000000000000000000000000000000000"
FACTORY_ABI=[{"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"}],"name":"getPair","outputs":[{"internalType":"address","name":"pair","type":"address"}],"stateMutability":"view","type":"function"}]
PAIR_ABI=[
 {"inputs":[],"name":"getReserves","outputs":[{"internalType":"uint112","name":"_reserve0","type":"uint112"},{"internalType":"uint112","name":"_reserve1","type":"uint112"},{"internalType":"uint32","name":"_blockTimestampLast","type":"uint32"}],"stateMutability":"view","type":"function"},
 {"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
 {"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
]

def checksum(x): return Web3.to_checksum_address(x)
def symbol(address):
    for s,t in TOKENS.items():
        if t['address'].lower()==address.lower(): return s
    return 'UNKNOWN'
def norm(raw,address):
    s=symbol(address); return float(raw) if s=='UNKNOWN' else raw/(10**TOKENS[s]['decimals'])

def connect():
    errors=[]
    for url in RPC_URLS:
        try:
            w3=Web3(Web3.HTTPProvider(url,request_kwargs={'timeout':10}))
            if w3.is_connected() and w3.eth.chain_id==56: return w3,url
        except Exception as e: errors.append(f"{url}: {e}")
    raise RuntimeError("No BSC RPC available: "+" | ".join(errors))

def get_pair(w3,a,b,block):
    f=w3.eth.contract(address=checksum(DEXES['pancakeswap_v2']['factory']),abi=FACTORY_ABI)
    p=f.functions.getPair(checksum(TOKENS[a]['address']),checksum(TOKENS[b]['address'])).call(block_identifier=block)
    return None if p.lower()==ZERO else checksum(p)

def read_pair(w3,address,block):
    p=w3.eth.contract(address=address,abi=PAIR_ABI)
    t0=p.functions.token0().call(block_identifier=block); t1=p.functions.token1().call(block_identifier=block)
    r0,r1,ts=p.functions.getReserves().call(block_identifier=block)
    return {'pair':address,'token0':t0,'token1':t1,'symbol0':symbol(t0),'symbol1':symbol(t1),'reserve0':norm(r0,t0),'reserve1':norm(r1,t1),'timestamp':ts}

def gas_cost_usdt(w3,pools):
    gas_price=int(w3.eth.gas_price)
    bnb_cost=gas_price*GAS_UNITS_ESTIMATE/1e18*GAS_SAFETY_MULTIPLIER
    p=pools[pool_key('WBNB','USDT')]
    if p['symbol0']=='WBNB': bnb_usdt=p['reserve1']/p['reserve0']
    else: bnb_usdt=p['reserve0']/p['reserve1']
    return bnb_cost*bnb_usdt, gas_price/1e9, bnb_usdt

def scan(output_dir='output'):
    w3,url=connect(); block=w3.eth.block_number
    pools={}
    print('='*72); print('BSC READ-ONLY MEV / ARBITRAGE SEARCHER'); print('='*72)
    print(f'RPC: {url}\nSnapshot block: {block:,}')
    for a,b in SCAN_PAIRS:
        addr=get_pair(w3,a,b,block)
        if not addr: print(f'{a}/{b}: NOT FOUND'); continue
        p=read_pair(w3,addr,block); pools[pool_key(a,b)]=p
        print(f"{a}/{b}: {addr} | {p['symbol0']}={p['reserve0']:,.4f} | {p['symbol1']}={p['reserve1']:,.4f}")
    if pool_key('WBNB','USDT') not in pools: raise RuntimeError('WBNB/USDT pool required for gas conversion')
    gas,gas_gwei,bnb_usdt=gas_cost_usdt(w3,pools)
    fee=DEXES['pancakeswap_v2']['fee_percent']
    results=search_triangles(list(TOKENS),BASE_TOKEN,TEST_AMOUNTS_USD,pools,fee,gas,MIN_NET_PROFIT_USD,MIN_ROI_PERCENT,MAX_CURVE_IMPACT_PERCENT)
    print('\n'+'='*72); print('TOP OPPORTUNITIES (after fees + dynamic gas estimate)'); print('='*72)
    for r in results[:10]:
        route=' -> '.join(r.route); status='PASS' if r.passes_filters else 'REJECT'
        print(f'{status:6} | {route:34} | in {r.start_amount:>9,.2f} | net {r.net_profit:>+10.4f} | ROI {r.roi_percent:>+8.4f}% | curve {r.max_curve_impact_percent:.4f}%')
    passing=[r for r in results if r.passes_filters]
    print(f'\nGas price: {gas_gwei:.4f} gwei | WBNB spot: {bnb_usdt:,.2f} USDT | estimated atomic-route gas: {gas:.4f} USDT')
    print(f'Candidates tested: {len(results)} | Passing filters: {len(passing)}')
    payload={
      'generated_at_utc':datetime.now(timezone.utc).isoformat(),'chain':'BSC','block':block,'rpc':url,
      'simulation_only':True,'gas':{'gwei':gas_gwei,'estimated_usdt':gas,'gas_units':GAS_UNITS_ESTIMATE,'safety_multiplier':GAS_SAFETY_MULTIPLIER},
      'thresholds':{'min_net_profit_usd':MIN_NET_PROFIT_USD,'min_roi_percent':MIN_ROI_PERCENT,'max_curve_impact_percent':MAX_CURVE_IMPACT_PERCENT},
      'pools':list(pools.values()),'candidates_tested':len(results),'passing_filters':len(passing),'results':[r.to_dict() for r in results],
    }
    d=Path(output_dir); d.mkdir(parents=True,exist_ok=True); path=d/'latest_bsc_scan.json'; path.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(f'Result file: {path}')
    print('SIMULATION ONLY: no wallet, no private key, no transaction signing.')
    return payload

if __name__=='__main__': scan()
