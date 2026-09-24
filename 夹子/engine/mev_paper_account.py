"""Probability-adjusted PAPER account for multi-chain arbitrage research."""
from __future__ import annotations
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from config.paper_account import (
    INITIAL_CAPITAL_USD, MAX_CAPITAL_PER_OPPORTUNITY_PCT,
    MIN_CASH_RESERVE_PCT, EXECUTION_BUFFER_BPS_BY_CHAIN,
    MIN_BOOKED_PROFIT_USD_BY_CHAIN, MAX_PAPER_TRADES_PER_RUN,
    MAX_PAPER_TRADES_PER_CHAIN_PER_RUN, MAX_ACCOUNT_DRAWDOWN_PCT,
    BASE_SUCCESS_PROBABILITY_BY_CHAIN, LATENCY_LOSS_BPS_BY_CHAIN,
    TAIL_BUFFER_BPS_BY_CHAIN, FAILURE_COST_USD_BY_CHAIN,
    MIN_EXPECTED_ROI_BPS, ACCOUNT_FILE,
)

LEGACY_ACCOUNT_CREATED_AT_UTC="2026-09-19T16:37:42+00:00"

def now_utc(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def new_account():
    return {
        "version":3,"created_at_utc":now_utc(),"initial_capital_usd":INITIAL_CAPITAL_USD,
        "equity_usd":INITIAL_CAPITAL_USD,"peak_equity_usd":INITIAL_CAPITAL_USD,
        "realized_pnl_usd":0.0,"return_percent":0.0,"max_drawdown_percent":0.0,
        "quoted_net_profit_total_usd":0.0,"expected_value_total_usd":0.0,
        "execution_buffer_total_usd":0.0,"latency_loss_total_usd":0.0,
        "tail_buffer_total_usd":0.0,"failed_execution_cost_total_usd":0.0,
        "successful_executions":0,"failed_executions":0,
        "paper_trades":[],"processed_keys":[],
        "chain_pnl_usd":{"BSC":0.0,"Ethereum":0.0,"Solana":0.0},
        "last_updated_utc":None,
        "notes":["MODELED PAPER PNL ONLY","No transaction submission",
                 "EV includes success probability, latency, failure cost and tail buffer",
                 "Outcome is deterministic pseudo-random by immutable opportunity key"],
    }

def load_account(path=ACCOUNT_FILE):
    p=Path(path)
    if not p.exists(): return new_account()
    try:
        data=json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data,dict): raise ValueError("账户文件顶层必须是对象")
        required={"initial_capital_usd","equity_usd","peak_equity_usd","realized_pnl_usd","paper_trades","processed_keys"}
        if (not required.issubset(data)
                or float(data["initial_capital_usd"])!=INITIAL_CAPITAL_USD
                or not isinstance(data["paper_trades"],list) or not isinstance(data["processed_keys"],list)
                or any(not math.isfinite(float(data[k])) for k in ("equity_usd","peak_equity_usd","realized_pnl_usd"))):
            raise ValueError("invalid existing financial state; refusing defaults")
    except Exception as e: raise RuntimeError(f"夹子模拟账户读取失败，拒绝重置账户：{e}") from e
    base=new_account(); base.update(data); base["version"]=3
    for k in ("paper_trades","processed_keys"): base.setdefault(k,[])
    if not base.get("created_at_utc"):
        trade_times=[
            t.get("time_utc") for t in base["paper_trades"]
            if isinstance(t,dict) and isinstance(t.get("time_utc"),str) and t.get("time_utc")
        ]
        base["created_at_utc"]=min(trade_times) if trade_times else LEGACY_ACCOUNT_CREATED_AT_UTC
    base.setdefault("chain_pnl_usd",{"BSC":0.0,"Ethereum":0.0,"Solana":0.0})
    return base

def save_account(account,path=ACCOUNT_FILE):
    p=Path(path); tmp=p.with_name(p.name+".tmp")
    with tmp.open("w",encoding="utf-8") as f:
        json.dump(account,f,indent=2,ensure_ascii=False); f.flush()
        import os; os.fsync(f.fileno())
    tmp.replace(p)

def _snapshot_key(c):
    return f"{c.get('chain')}|{c.get('snapshot')}|{'>'.join(c.get('route') or [])}|{float(c.get('start_amount') or 0):.8f}"

def _route_key(c):
    return f"{c.get('chain')}|{c.get('snapshot')}|{'>'.join(c.get('route') or [])}"

def _deterministic_unit(key):
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],16)/float(16**16-1)

def _probability_terms(c,cap):
    chain=str(c.get("chain") or "Unknown"); start=float(c.get("start_amount") or 0)
    impact=max(0.0,float(c.get("max_curve_impact_percent") or 0))
    base=float(BASE_SUCCESS_PROBABILITY_BY_CHAIN.get(chain,0.45))
    size_ratio=start/cap if cap>0 else 1.0
    probability=max(0.05,min(0.95,base-0.12*min(1.0,size_ratio)-0.08*min(2.0,impact)))
    execution_bps=float(EXECUTION_BUFFER_BPS_BY_CHAIN.get(chain,15.0))
    latency_bps=float(LATENCY_LOSS_BPS_BY_CHAIN.get(chain,10.0))
    tail_bps=float(TAIL_BUFFER_BPS_BY_CHAIN.get(chain,12.0))
    execution_usd=start*execution_bps/10_000
    latency_usd=start*latency_bps/10_000
    tail_usd=start*tail_bps/10_000
    failure_cost=max(float(FAILURE_COST_USD_BY_CHAIN.get(chain,1.0)),
                     max(0.0,float(c.get("gas_cost") or 0))*0.75)
    return probability,execution_bps,execution_usd,latency_bps,latency_usd,tail_bps,tail_usd,failure_cost

def _refresh_metrics(a):
    equity=float(a["equity_usd"]); peak=max(float(a.get("peak_equity_usd",equity)),equity)
    a["peak_equity_usd"]=peak; dd=((peak-equity)/peak*100) if peak else 0.0
    a["max_drawdown_percent"]=max(float(a.get("max_drawdown_percent",0.0)),dd)
    initial=float(a["initial_capital_usd"]); a["realized_pnl_usd"]=equity-initial
    a["return_percent"]=(equity/initial-1)*100 if initial else 0.0
    a["last_updated_utc"]=now_utc()

def choose_candidates(account,candidates):
    equity=float(account["equity_usd"]); peak=float(account.get("peak_equity_usd",equity))
    if peak and (peak-equity)/peak>=MAX_ACCOUNT_DRAWDOWN_PCT: return []
    cap=min(equity*MAX_CAPITAL_PER_OPPORTUNITY_PCT,equity*(1-MIN_CASH_RESERVE_PCT))
    processed=set(account.get("processed_keys",[])); eligible=[]
    for c in candidates:
        if not c.get("passes_filters"): continue
        start=float(c.get("start_amount") or 0); quoted=float(c.get("net_profit") or 0)
        if start<=0 or start>cap: continue
        key=_snapshot_key(c)
        if key in processed: continue
        chain=str(c.get("chain") or "Unknown")
        p,ebps,eusd,lbps,lusd,tbps,tusd,fail=_probability_terms(c,cap)
        success_net=quoted-eusd-lusd-tusd
        ev=p*success_net-(1-p)*fail
        ev_roi_bps=ev/start*10_000
        min_ev=float(MIN_BOOKED_PROFIT_USD_BY_CHAIN.get(chain,1.0))
        if ev<min_ev or ev_roi_bps<MIN_EXPECTED_ROI_BPS: continue
        x=dict(c); x.update(
            _paper_key=key,_success_probability=p,_execution_buffer_bps=ebps,
            _execution_buffer_usd=eusd,_latency_loss_bps=lbps,_latency_loss_usd=lusd,
            _tail_buffer_bps=tbps,_tail_buffer_usd=tusd,_failure_cost_usd=fail,
            _success_net_profit_usd=success_net,_expected_value_usd=ev,
            _expected_roi_percent=ev/start*100)
        eligible.append(x)
    # Dynamic sizing: retain the EV-maximising tested amount for each route/snapshot.
    best={}
    for x in eligible:
        k=_route_key(x)
        if k not in best or (x["_expected_value_usd"],x["_expected_roi_percent"])>(best[k]["_expected_value_usd"],best[k]["_expected_roi_percent"]):
            best[k]=x
    eligible=list(best.values())
    eligible.sort(key=lambda x:(x["_expected_roi_percent"],x["_expected_value_usd"]),reverse=True)
    selected=[]; per_chain={}
    for x in eligible:
        chain=x.get("chain")
        if per_chain.get(chain,0)>=MAX_PAPER_TRADES_PER_CHAIN_PER_RUN: continue
        selected.append(x); per_chain[chain]=per_chain.get(chain,0)+1
        if len(selected)>=MAX_PAPER_TRADES_PER_RUN: break
    return selected

def apply_paper_trades(account,selected):
    for c in selected:
        key=c["_paper_key"]; p=float(c["_success_probability"])
        success=_deterministic_unit(key)<p
        booked=float(c["_success_net_profit_usd"]) if success else -float(c["_failure_cost_usd"])
        quoted=float(c.get("net_profit") or 0); chain=str(c.get("chain") or "Unknown")
        before=float(account["equity_usd"]); after=before+booked; account["equity_usd"]=after
        account["quoted_net_profit_total_usd"]=float(account.get("quoted_net_profit_total_usd",0))+quoted
        account["expected_value_total_usd"]=float(account.get("expected_value_total_usd",0))+float(c["_expected_value_usd"])
        account["execution_buffer_total_usd"]=float(account.get("execution_buffer_total_usd",0))+float(c["_execution_buffer_usd"])
        account["latency_loss_total_usd"]=float(account.get("latency_loss_total_usd",0))+float(c["_latency_loss_usd"])
        account["tail_buffer_total_usd"]=float(account.get("tail_buffer_total_usd",0))+float(c["_tail_buffer_usd"])
        if success: account["successful_executions"]=int(account.get("successful_executions",0))+1
        else:
            account["failed_executions"]=int(account.get("failed_executions",0))+1
            account["failed_execution_cost_total_usd"]=float(account.get("failed_execution_cost_total_usd",0))+float(c["_failure_cost_usd"])
        account.setdefault("chain_pnl_usd",{})
        account["chain_pnl_usd"][chain]=float(account["chain_pnl_usd"].get(chain,0))+booked
        account.setdefault("paper_trades",[]).append({
            "time_utc":now_utc(),"chain":chain,"snapshot":c.get("snapshot"),"route":c.get("route"),
            "start_amount_usd":float(c.get("start_amount") or 0),"quoted_net_profit_usd":quoted,
            "success_probability":p,"sampled_success":success,
            "execution_buffer_usd":float(c["_execution_buffer_usd"]),
            "latency_loss_usd":float(c["_latency_loss_usd"]),"tail_buffer_usd":float(c["_tail_buffer_usd"]),
            "failure_cost_usd":float(c["_failure_cost_usd"]),"expected_value_usd":float(c["_expected_value_usd"]),
            "expected_roi_percent":float(c["_expected_roi_percent"]),"booked_profit_usd":booked,
            "equity_before_usd":before,"equity_after_usd":after,"paper_key":key})
        account.setdefault("processed_keys",[]).append(key)
    account["processed_keys"]=account.get("processed_keys",[])[-5000:]
    _refresh_metrics(account); return account

def update_account(candidates,path=ACCOUNT_FILE):
    a=load_account(path); selected=choose_candidates(a,candidates)
    a=apply_paper_trades(a,selected); save_account(a,path); return a,selected

def performance_lines(a):
    trades=a.get("paper_trades",[]); cp=a.get("chain_pnl_usd",{})
    return ["="*72,"MEV PROBABILISTIC-EV PAPER ACCOUNT","="*72,
            f"Initial capital:       {a['initial_capital_usd']:,.2f} USD",
            f"Current equity:        {a['equity_usd']:,.2f} USD",
            f"Cumulative modeled PnL:{a['realized_pnl_usd']:+,.2f} USD",
            f"Modeled return:        {a['return_percent']:+.4f}%",
            f"Max modeled drawdown:  {a['max_drawdown_percent']:.4f}%",
            f"Paper outcomes:        {len(trades)} | success {a.get('successful_executions',0)} | failed {a.get('failed_executions',0)}",
            f"Cumulative modeled EV: {a.get('expected_value_total_usd',0):+,.2f} USD",
            "Chain modeled PnL:    "+" | ".join(f"{k} {float(v):+,.2f}" for k,v in cp.items()),
            "NOTE: PAPER model only; no wallet, signature or transaction submission."]
