"""Run all chain scanners, create one summary, and update the paper account."""
import json
from datetime import datetime, timezone
from pathlib import Path

from chains.bsc_pool_scanner import scan as bsc_scan
from chains.ethereum_scanner import scan as eth_scan
from chains.solana_scanner import scan as sol_scan
from engine.mev_paper_account import update_account, performance_lines

SCANNERS=[("BSC",bsc_scan),("Ethereum",eth_scan),("Solana",sol_scan)]


def _snapshot_from_payload(payload):
    return payload.get("block") or payload.get("start_slot") or payload.get("slot")


def scan_all(output_dir="output"):
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    chains={}; leaderboard=[]

    for name,fn in SCANNERS:
        try:
            payload=fn(output_dir)
            snapshot=_snapshot_from_payload(payload)
            chains[name]={
                "status":"OK",
                "passing_filters":payload.get("passing_filters",0),
                "candidates_tested":payload.get("candidates_tested",len(payload.get("results",[]))),
                "snapshot":snapshot,
            }
            for r in payload.get("results",[]):
                leaderboard.append({
                    "chain":name,
                    "snapshot":snapshot,
                    "route":r.get("route"),
                    "start_amount":r.get("start_amount"),
                    "gross_profit":r.get("gross_profit"),
                    "gas_cost":r.get("gas_cost"),
                    "net_profit":r.get("net_profit"),
                    "roi_percent":r.get("roi_percent"),
                    "max_curve_impact_percent":r.get("max_curve_impact_percent"),
                    "passes_filters":r.get("passes_filters"),
                })
        except Exception as e:
            chains[name]={
                "status":"ERROR",
                "error":str(e),
                "passing_filters":0,
                "candidates_tested":0,
                "snapshot":None,
            }

    leaderboard.sort(
        key=lambda x:(x.get("net_profit") if x.get("net_profit") is not None else -10**99),
        reverse=True,
    )

    account, selected = update_account(leaderboard)
    account_snapshot = {
        "initial_capital_usd":account["initial_capital_usd"],
        "equity_usd":account["equity_usd"],
        "realized_pnl_usd":account["realized_pnl_usd"],
        "return_percent":account["return_percent"],
        "max_drawdown_percent":account["max_drawdown_percent"],
        "paper_trade_count":len(account.get("paper_trades",[])),
        "chain_pnl_usd":account.get("chain_pnl_usd",{}),
        "execution_buffer_total_usd":account.get("execution_buffer_total_usd",0.0),
    }

    summary={
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "simulation_only":True,
        "chains":chains,
        "top_opportunities":leaderboard[:30],
        "paper_execution_this_run":[{
            "chain":x.get("chain"),
            "snapshot":x.get("snapshot"),
            "route":x.get("route"),
            "start_amount_usd":x.get("start_amount"),
            "quoted_net_profit_usd":x.get("net_profit"),
            "success_probability":x.get("_success_probability"),
            "expected_value_usd":x.get("_expected_value_usd"),
            "latency_loss_usd":x.get("_latency_loss_usd"),
            "failure_cost_usd":x.get("_failure_cost_usd"),
            "dynamic_size_selected":True,
        } for x in selected],
        "paper_account":account_snapshot,
    }

    p=out/"latest_multichain_summary.json"
    p.write_text(json.dumps(summary,indent=2),encoding="utf-8")

    print("\n"+"="*72); print("MULTI-CHAIN SUMMARY"); print("="*72)
    for n,s in chains.items():
        print(
            f"{n:<10} {s['status']:<5} candidates={s.get('candidates_tested',0)} "
            f"passing={s.get('passing_filters',0)}"
            +(f" error={s.get('error')}" if s['status']=='ERROR' else "")
        )

    print("Top candidates:")
    for r in leaderboard[:10]:
        print(
            f"{r['chain']:<10} {' -> '.join(r['route'] or [])[:28]:28} "
            f"net={r['net_profit']:+.4f} roi={r['roi_percent']:+.4f}% "
            f"{'PASS' if r['passes_filters'] else 'REJECT'}"
        )

    if selected:
        print("Paper execution this run:")
        for x in selected:
            print(
                f"{x['chain']:<10} {' -> '.join(x.get('route') or []):30} "
                f"capital={float(x['start_amount']):,.2f} "
                f"quoted_net={float(x['net_profit']):+,.4f} "
                f"p={float(x['_success_probability']):.3f} "
                f"EV={float(x['_expected_value_usd']):+,.4f} "
                f"size=EV-MAX"
            )
    else:
        print("Paper execution this run: NONE")

    print()
    for line in performance_lines(account):
        print(line)

    print(f"Summary file: {p}")
    return summary


if __name__=="__main__":
    scan_all()
