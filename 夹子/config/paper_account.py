"""Risk-adjusted paper-account settings for the MEV searcher."""
INITIAL_CAPITAL_USD = 10_000.0
MAX_CAPITAL_PER_OPPORTUNITY_PCT = 0.10
MIN_CASH_RESERVE_PCT = 0.50

# Execution uncertainty differs materially by chain. Scanner net profit already
# includes quoted swap fees, price impact and network cost; this is an extra
# haircut for quote decay / fill uncertainty.
EXECUTION_BUFFER_BPS_BY_CHAIN = {
    "Solana": 5.0,
    "BSC": 10.0,
    "Ethereum": 15.0,
}
MIN_BOOKED_PROFIT_USD_BY_CHAIN = {
    "Solana": 0.05,
    "BSC": 0.25,
    "Ethereum": 1.00,
}

MAX_PAPER_TRADES_PER_RUN = 2
MAX_PAPER_TRADES_PER_CHAIN_PER_RUN = 1
MAX_ACCOUNT_DRAWDOWN_PCT = 0.05
# Probability/latency model. These are conservative PAPER assumptions and are
# deliberately visible so they can be recalibrated from observed results.
BASE_SUCCESS_PROBABILITY_BY_CHAIN = {
    "Solana": 0.58, "BSC": 0.62, "Ethereum": 0.52,
}
LATENCY_LOSS_BPS_BY_CHAIN = {
    "Solana": 4.0, "BSC": 7.0, "Ethereum": 10.0,
}
TAIL_BUFFER_BPS_BY_CHAIN = {
    "Solana": 4.0, "BSC": 8.0, "Ethereum": 12.0,
}
FAILURE_COST_USD_BY_CHAIN = {
    "Solana": 0.03, "BSC": 0.12, "Ethereum": 1.50,
}
MIN_EXPECTED_ROI_BPS = 0.5
ACCOUNT_FILE = "mev_account.json"
