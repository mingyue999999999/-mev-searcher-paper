"""Three-chain MEV/arbitrage research harness. Execution is deliberately disabled."""
import argparse, asyncio
from chains.bsc_pool_scanner import scan as scan_bsc
from chains.ethereum_scanner import scan as scan_eth
from chains.solana_scanner import scan as scan_sol
from chains.multichain_scanner import scan_all
from chains.rpc_monitor import check_all_chains

async def health():
    results=await check_all_chains()
    for r in results: print(f"{r['chain']:<10} {r['status']:<7} {r.get('height') or '-'}")
    return all(r['status']=='ONLINE' for r in results)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['bsc-scan','eth-scan','sol-scan','all-scan','health'],default='all-scan')
    a=p.parse_args()
    if a.mode=='health': asyncio.run(health())
    elif a.mode=='bsc-scan': scan_bsc()
    elif a.mode=='eth-scan': scan_eth()
    elif a.mode=='sol-scan': scan_sol()
    else: scan_all()
if __name__=='__main__': main()
