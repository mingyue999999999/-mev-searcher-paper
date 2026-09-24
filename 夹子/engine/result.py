from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class RouteLeg:
    token_in: str
    token_out: str
    venue: str
    amount_in: float
    amount_out: float
    fee_percent: float | None = None
    impact_percent: float | None = None
    gas_units: int | None = None
    metadata: dict | None = None

@dataclass(frozen=True)
class RouteResult:
    chain: str
    route: tuple[str, ...]
    start_amount: float
    final_amount: float
    gross_profit: float
    network_cost_usd: float
    net_profit: float
    roi_percent: float
    max_impact_percent: float
    passes_filters: bool
    legs: tuple[RouteLeg, ...]
    consistency: str
    snapshot: int | None = None

    def to_dict(self):
        d = asdict(self)
        d["route"] = list(self.route)
        d["legs"] = [asdict(x) for x in self.legs]
        return d
