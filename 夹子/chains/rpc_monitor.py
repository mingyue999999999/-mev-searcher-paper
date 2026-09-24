import asyncio
import aiohttp

RPC_ENDPOINTS = {
    "BSC": [
        "https://bsc-dataseed.bnbchain.org",
        "https://bsc-dataseed1.defibit.io",
    ],
    "Ethereum": [
        "https://ethereum-rpc.publicnode.com",
        "https://eth.llamarpc.com",
        "https://1rpc.io/eth",
    ],
    "Solana": [
        "https://api.mainnet-beta.solana.com",
        "https://solana-rpc.publicnode.com",
    ],
}

async def _call(session, name, url):
    payload={"jsonrpc":"2.0","id":1,"method":"getSlot" if name=="Solana" else "eth_blockNumber","params":[]}
    async with session.post(url,json=payload,timeout=aiohttp.ClientTimeout(total=8)) as response:
        response.raise_for_status(); data=await response.json()
        if "error" in data: raise RuntimeError(data["error"])
        result=data.get("result")
        if result is None: raise RuntimeError("RPC returned no result")
        return int(result) if name=="Solana" else int(result,16)

async def rpc_call(session,name,urls):
    errors=[]
    for url in urls:
        try:
            height=await _call(session,name,url)
            return {"chain":name,"status":"ONLINE","height":height,"rpc":url,"error":None}
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    return {"chain":name,"status":"OFFLINE","height":None,"rpc":None,"error":" | ".join(errors)}

async def check_all_chains():
    async with aiohttp.ClientSession(headers={"User-Agent":"mev-searcher-readonly/1.0"}) as session:
        return await asyncio.gather(*(rpc_call(session,n,u) for n,u in RPC_ENDPOINTS.items()))

async def main():
    print("="*60); print("MULTI-CHAIN RPC MONITOR"); print("="*60)
    results=await check_all_chains(); online=0
    for r in results:
        print(f"{r['chain']:<10} {r['status']:<7} {r.get('height') or '-'} {r.get('rpc') or ''}")
        online += r['status']=='ONLINE'
    print(f"ONLINE: {online}/{len(results)}")

if __name__=="__main__": asyncio.run(main())
