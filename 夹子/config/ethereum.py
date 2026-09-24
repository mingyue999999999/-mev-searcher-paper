"""Ethereum read-only scanner configuration."""
CHAIN_ID = 1
CHAIN_NAME = "Ethereum"
RPC_URLS = [
    "https://ethereum-rpc.publicnode.com",
    "https://eth.llamarpc.com",
    "https://1rpc.io/eth",
]
TOKENS = {
    "WETH": {"address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "decimals": 18},
    "USDT": {"address": "0xdAC17F958D2ee523a2206206994597C13D831ec7", "decimals": 6},
    "USDC": {"address": "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "decimals": 6},
}
BASE_TOKEN = "USDT"
TEST_AMOUNTS_USD = [25, 50, 100, 250, 500, 1000, 2500, 5000]
MIN_NET_PROFIT_USD = 2.0
MIN_ROI_PERCENT = 0.08
MAX_TOTAL_IMPACT_PERCENT = 1.50
GAS_SAFETY_MULTIPLIER = 1.20
V2_GAS_PER_LEG = 125_000
ROUTE_OVERHEAD_GAS = 80_000
DEXES = {
    "uniswap_v2": {
        "type": "v2",
        "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
        "fee_percent": 0.30,
    },
    "uniswap_v3": {
        "type": "v3",
        "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
        "quoter_v2": "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
        "fee_tiers": [100, 500, 3000, 10000],
    },
}
