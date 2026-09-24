"""Constant-product AMM V2 mathematics. Pure/read-only calculations."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Quote:
    amount_in: float
    amount_out: float
    fee_paid: float
    spot_price: float
    execution_price: float
    fee_drag_percent: float
    curve_impact_percent: float
    total_price_impact_percent: float

def _validate(amount_in, reserve_in, reserve_out, fee_percent):
    if amount_in <= 0: raise ValueError("amount_in must be > 0")
    if reserve_in <= 0 or reserve_out <= 0: raise ValueError("reserves must be > 0")
    if not 0 <= fee_percent < 100: raise ValueError("fee_percent must be in [0, 100)")

def get_amount_out(amount_in, reserve_in, reserve_out, fee_percent=0.25):
    _validate(amount_in, reserve_in, reserve_out, fee_percent)
    after_fee = amount_in * (1.0 - fee_percent / 100.0)
    return (after_fee * reserve_out) / (reserve_in + after_fee)

def quote_swap(amount_in, reserve_in, reserve_out, fee_percent=0.25):
    out = get_amount_out(amount_in, reserve_in, reserve_out, fee_percent)
    spot = reserve_out / reserve_in
    execution = out / amount_in
    no_fee_out = get_amount_out(amount_in, reserve_in, reserve_out, 0.0)
    no_fee_execution = no_fee_out / amount_in
    curve = max(0.0, (spot - no_fee_execution) / spot * 100.0)
    total = max(0.0, (spot - execution) / spot * 100.0)
    return Quote(
        amount_in=amount_in, amount_out=out,
        fee_paid=amount_in * fee_percent / 100.0,
        spot_price=spot, execution_price=execution,
        fee_drag_percent=fee_percent,
        curve_impact_percent=curve,
        total_price_impact_percent=total,
    )
