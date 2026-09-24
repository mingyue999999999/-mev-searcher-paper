"""BNB Smart Chain configuration for the read-only searcher."""
CHAIN_ID = 56
CHAIN_NAME = "BNB Smart Chain"
RPC_URLS = [
    "https://bsc-dataseed.bnbchain.org",
    "https://bsc-dataseed1.defibit.io",
    "https://bsc-dataseed1.ninicoin.io",
]
TOKENS = {
    "WBNB": {"address": "0xBB4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c", "decimals": 18},
    "USDT": {"address": "0x55d398326f99059fF775485246999027B3197955", "decimals": 18},
    "USDC": {"address": "0x8AC76a51cc950d9822D68b83Fe1Ad97B32Cd580d", "decimals": 18},
}
DEXES = {
    "pancakeswap_v2": {
        "enabled": True,
        "type": "v2",
        "factory": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
        "fee_percent": 0.25,
    },
    # Reserved adapter slot. V3 is intentionally not priced with V2 x*y=k math.
    "pancakeswap_v3": {
        "enabled": False,
        "type": "v3",
        "factory": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
    },
}
SCAN_PAIRS = [("WBNB", "USDT"), ("WBNB", "USDC"), ("USDT", "USDC")]
BASE_TOKEN = "USDT"
# Dense enough to find useful sizing without pretending to be a continuous optimizer.
TEST_AMOUNTS_USD = [25, 50, 100, 250, 500, 1000, 2500, 5000, 7500, 10000, 15000, 25000]
MIN_NET_PROFIT_USD = 1.00
MIN_ROI_PERCENT = 0.05
MAX_CURVE_IMPACT_PERCENT = 1.00
GAS_UNITS_ESTIMATE = 450_000
GAS_SAFETY_MULTIPLIER = 1.25
MAX_BLOCK_DRIFT = 0  # all reads use one fixed block snapshot
SIMULATION_MODE = True
ALLOW_TRANSACTION_SIGNING = False
ALLOW_REAL_TRADING = False
