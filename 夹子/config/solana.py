"""Solana read-only Jupiter route scanner configuration."""
RPC_URLS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
]
JUPITER_QUOTE_URL = "https://lite-api.jup.ag/swap/v1/quote"
TOKENS = {
    "SOL": {"mint": "So11111111111111111111111111111111111111112", "decimals": 9},
    "USDC": {"mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "decimals": 6},
    "USDT": {"mint": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", "decimals": 6},
    "JUP": {"mint": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", "decimals": 6},
    "BONK": {"mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6k4dVfkD5m6PBo", "decimals": 5},
}
BASE_TOKEN = "USDC"
# More granularity inside the paper account's current $1,000/opportunity cap.
# This helps discover the size where edge peaks instead of testing only a few
# widely spaced notionals.
TEST_AMOUNTS_USD = [25, 50, 100, 250, 500, 750, 1000]

# Scanner gate is intentionally permissive in paper mode. Realistic execution
# uncertainty is applied centrally by engine/mev_paper_account.py. Keeping a
# second, stricter profit/ROI gate here previously hid positive candidates
# before the paper-account model could evaluate them.
MIN_NET_PROFIT_USD = 0.0
MIN_ROI_PERCENT = 0.0
MAX_PRICE_IMPACT_PERCENT = 1.00
MAX_QUOTE_SLOT_DRIFT = 12
SLIPPAGE_BPS = 30
COMPUTE_UNITS_ESTIMATE = 500_000
BASE_FEE_LAMPORTS = 5_000
PRIORITY_FEE_SAFETY_MULTIPLIER = 1.25
