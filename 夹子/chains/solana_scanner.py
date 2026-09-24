"""Solana read-only triangle scanner using Jupiter quote routes.

Jupiter is used only for quotes. No swap transaction is requested or signed.
"""
from __future__ import annotations
import asyncio, json, statistics
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path
import aiohttp

from config.solana import *
from engine.result import RouteLeg, RouteResult

async def rpc(session,url,method,params=None):
    async with session.post(url,json={"jsonrpc":"2.0","id":1,"method":method,"params":params or []},timeout=aiohttp.ClientTimeout(total=12)) as r:
        r.raise_for_status(); data=await r.json()
        if "error" in data: raise RuntimeError(data["error"])
        return data["result"]

async def connect_rpc(session):
    errs=[]
    for url in RPC_URLS:
        try:
            slot=int(await rpc(session,url,"getSlot")); return url,slot
        except Exception as e: errs.append(f"{url}: {e}")
    raise RuntimeError("No Solana RPC available: "+" | ".join(errs))

async def jquote(session, token_in, token_out, raw_amount, only_direct=True):
    params={"inputMint":TOKENS[token_in]["mint"],"outputMint":TOKENS[token_out]["mint"],"amount":str(int(raw_amount)),"slippageBps":str(SLIPPAGE_BPS),"onlyDirectRoutes":"true" if only_direct else "false","restrictIntermediateTokens":"true"}
    async with session.get(JUPITER_QUOTE_URL,params=params,timeout=aiohttp.ClientTimeout(total=15)) as r:
        r.raise_for_status(); data=await r.json()
        if data.get("error"): raise RuntimeError(data["error"])
        return data

def raw(amount,symbol): return int(amount*(10**TOKENS[symbol]["decimals"]))
def human(amount,symbol): return int(amount)/(10**TOKENS[symbol]["decimals"])

def venues_from_route(data):
    labels=[]
    for x in data.get("routePlan",[]):
        info=x.get("swapInfo",{}); label=info.get("label") or info.get("ammKey")
        if label and label not in labels: labels.append(label)
    return "+".join(labels[:4]) or "Jupiter"

async def priority_cost_usdc(session,rpc_url,sol_usdc):
    try:
        fees=await rpc(session,rpc_url,"getRecentPrioritizationFees")
        vals=[int(x.get("prioritizationFee",0)) for x in fees if int(x.get("prioritizationFee",0))>0]
        micro_lamports_per_cu=statistics.median(vals) if vals else 0
    except Exception:
        micro_lamports_per_cu=0
    priority_lamports=micro_lamports_per_cu*COMPUTE_UNITS_ESTIMATE/1_000_000
    lamports=(BASE_FEE_LAMPORTS+priority_lamports)*PRIORITY_FEE_SAFETY_MULTIPLIER
    return lamports/1e9*sol_usdc, micro_lamports_per_cu

async def _scan(output_dir="output"):
    async with aiohttp.ClientSession(headers={"User-Agent":"mev-searcher-readonly/1.0"}) as session:
        rpc_url,start_slot=await connect_rpc(session)
        sol_price_q=await jquote(session,"SOL","USDC",raw(1.0,"SOL"),only_direct=False)
        sol_usdc=human(sol_price_q["outAmount"],"USDC")
        network_cost,priority_rate=await priority_cost_usdc(session,rpc_url,sol_usdc)
        routes=[(BASE_TOKEN,a,b,BASE_TOKEN) for a,b in permutations([x for x in TOKENS if x!=BASE_TOKEN],2)]
        results=[]
        print("="*72); print("SOLANA READ-ONLY JUPITER ROUTE SEARCHER"); print("="*72); print(f"RPC: {rpc_url}\nStart slot: {start_slot:,}\nSOL/USDC quote: {sol_usdc:.4f}")
        for route in routes:
            for start in TEST_AMOUNTS_USD:
                cur=float(start); legs=[]; slots=[]; failed=False
                for a,b in zip(route,route[1:]):
                    try:
                        q=await jquote(session,a,b,raw(cur,a),only_direct=True)
                        out=human(q["outAmount"],b); impact=float(q.get("priceImpactPct") or 0)*100
                        slots.append(int(q.get("contextSlot") or 0))
                        legs.append(RouteLeg(a,b,venues_from_route(q),cur,out,None,impact,None,{"contextSlot":q.get("contextSlot"),"timeTaken":q.get("timeTaken"),"otherAmountThreshold":q.get("otherAmountThreshold")})); cur=out
                    except Exception:
                        failed=True; break
                if failed: continue
                valid_slots=[s for s in slots if s>0]; drift=(max(valid_slots)-min(valid_slots)) if valid_slots else 0
                gross=cur-start; net=gross-network_cost; roi=net/start*100; maximpact=max((x.impact_percent or 0) for x in legs)
                passes=net>=MIN_NET_PROFIT_USD and roi>=MIN_ROI_PERCENT and maximpact<=MAX_PRICE_IMPACT_PERCENT and drift<=MAX_QUOTE_SLOT_DRIFT
                results.append(RouteResult("Solana",route,start,cur,gross,network_cost,net,roi,maximpact,passes,tuple(legs),f"best_effort_slot_drift={drift}",max(valid_slots) if valid_slots else start_slot))
        results.sort(key=lambda x:x.net_profit,reverse=True)
        for r in results[:10]:
            print(f"{'PASS' if r.passes_filters else 'REJECT':6} | {' -> '.join(r.route):31} | in {r.start_amount:8.2f} | net {r.net_profit:+10.4f} | ROI {r.roi_percent:+8.4f}% | impact {r.max_impact_percent:.4f}% | {r.consistency}")
        passing=[x for x in results if x.passes_filters]
        payload={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"chain":"Solana","rpc":rpc_url,"start_slot":start_slot,"simulation_only":True,"quote_source":"Jupiter","network_cost":{"estimated_usdc":network_cost,"priority_micro_lamports_per_cu":priority_rate,"compute_units":COMPUTE_UNITS_ESTIMATE,"sol_usdc":sol_usdc},"consistency_note":"Jupiter quotes are sequential read-only snapshots, not an atomic on-chain snapshot; candidates exceeding configured slot drift are rejected.","candidates_tested":len(results),"passing_filters":len(passing),"results":[x.to_dict() for x in results]}
        d=Path(output_dir); d.mkdir(parents=True,exist_ok=True); p=d/"latest_solana_scan.json"; p.write_text(json.dumps(payload,indent=2),encoding="utf-8")
        print(f"Candidates tested: {len(results)} | Passing filters: {len(passing)}\nEstimated network cost: {network_cost:.6f} USDC\nResult file: {p}\nSIMULATION ONLY: no wallet, no private key, no transaction signing.")
        return payload

def scan(output_dir="output"): return asyncio.run(_scan(output_dir))
if __name__=="__main__": scan()
