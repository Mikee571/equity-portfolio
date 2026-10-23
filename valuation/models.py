"""Python versions of the two Excel DCFs (micron/ and gtt/), used by the dashboard and by monte_carlo.py.

The defaults are the same inputs as micron/build_model.py and gtt/build_model.py.
test_models.py checks that these functions reproduce the Excel results.
"""
from dataclasses import dataclass, field, replace

# ------------------------------------------------------------------ Micron ($mm)


@dataclass
class MicronScenario:
    growth: list
    margin: list
    capex: list
    norm_margin: float


MICRON_SCENARIOS = {
    "Bear": MicronScenario([0.60, -0.45, -0.35, 0.05, 0.08], [0.72, 0.35, 0.10, 0.15, 0.20],
                           [45000, 30000, 20000, 20000, 21000], 0.20),
    "Base": MicronScenario([1.07, 0.16, -0.25, -0.30, -0.10], [0.80, 0.75, 0.55, 0.40, 0.35],
                           [50000, 60000, 50000, 45000, 42000], 0.35),
    "Bull": MicronScenario([1.15, 0.25, 0.05, -0.05, 0.03], [0.82, 0.80, 0.70, 0.60, 0.50],
                           [55000, 70000, 70000, 65000, 65000], 0.50),
}


@dataclass
class MicronInputs:
    price: float = 878.84
    shares: float = 1147
    cash: float = 73480
    debt: float = 2792 + 2387
    deposits: float = 12747
    deposits_as_debt: bool = True
    rf: float = 0.051
    raw_beta: float = 2.23
    erp: float = 0.05
    kd: float = 0.055
    tax: float = 0.15
    g: float = 0.03
    ronic: float = 0.15
    nwc: float = 0.10
    da_catch_up: float = 0.20
    rev0: float = 133188
    da0: float = 9503
    capex0: float = 27370
    wacc_override: float = None

    @property
    def wacc(self):
        if self.wacc_override is not None:
            return self.wacc_override
        coe = self.rf + (0.67 * self.raw_beta + 0.33) * self.erp
        mcap = self.price * self.shares
        return (mcap * coe + self.debt * self.kd * (1 - self.tax)) / (mcap + self.debt)


def micron_value(s: MicronScenario, p: MicronInputs = MicronInputs()):
    """Returns value per share and the yearly table (FY2027-31)."""
    w = p.wacc
    rev_prev, da_prev, capex_prev = p.rev0, p.da0, p.capex0
    rows, pv_sum = [], 0.0
    for t in range(5):
        rev = rev_prev * (1 + s.growth[t])
        ebit = rev * s.margin[t]
        da = da_prev + p.da_catch_up * (capex_prev - da_prev)
        fcf = ebit * (1 - p.tax) + da - s.capex[t] - p.nwc * (rev - rev_prev)
        pv_sum += fcf / (1 + w) ** (t + 1)
        rows.append(dict(year=2027 + t, revenue=rev, operating_margin=s.margin[t], fcf=fcf))
        rev_prev, da_prev, capex_prev = rev, da, s.capex[t]
    tv_fcf = rev_prev * (1 + p.g) * s.norm_margin * (1 - p.tax) * (1 - p.g / p.ronic)
    pv_tv = tv_fcf / (w - p.g) / (1 + w) ** 5
    equity = pv_sum + pv_tv + p.cash - p.debt - p.deposits * p.deposits_as_debt
    return equity / p.shares, rows, pv_tv / (pv_sum + pv_tv)


def micron_implied_margin(p: MicronInputs = MicronInputs()):
    """Operating margin from FY29 onwards that justifies the price (base revenue and capex path)."""
    base = MICRON_SCENARIOS["Base"]

    def value(m):
        s = replace(base, margin=base.margin[:2] + [m] * 3, norm_margin=m)
        return micron_value(s, p)[0]
    v0, v1 = value(0.0), value(1.0)
    return (p.price - v0) / (v1 - v0)


# ------------------------------------------------------------------ GTT (€mm)

GTT_BACKLOG = {2026: 644.7, 2027: 655.0, 2028: 603.0, 2029: 221.3, 2030: 73.8}
GTT_SCENARIOS = {"Bear": dict(h2=15, orders=35, marine=0.03, g=0.00),
                 "Base": dict(h2=30, orders=60, marine=0.08, g=0.015),
                 "Bull": dict(h2=40, orders=75, marine=0.12, g=0.02)}


@dataclass
class GttInputs:
    price: float = 211.60
    shares: float = 37.067
    net_cash: float = 384.7 - 90.0
    debt: float = 90.0
    rf: float = 0.0475
    beta: float = 0.90
    erp: float = 0.055
    kd: float = 0.04
    tax: float = 0.16
    royalty: float = 9.5
    royalty_growth: float = 0.02
    profile: tuple = (0.20, 0.55, 0.25)
    core_costs: float = 193.0
    cost_growth: float = 0.03
    marine0: float = 70.0
    marine_margin: float = 0.18
    services0: float = 22.0
    services_growth: float = 0.02
    da: float = 30.0
    capex: float = 30.0
    nwc: float = 0.10
    h2_share: float = 0.50
    wacc_override: float = None

    @property
    def wacc(self):
        if self.wacc_override is not None:
            return self.wacc_override
        coe = self.rf + self.beta * self.erp
        mcap = self.price * self.shares
        return (mcap * coe + self.debt * self.kd * (1 - self.tax)) / (mcap + self.debt)


def gtt_value(h2: float, orders, marine: float, g: float, p: GttInputs = GttInputs()):
    """Returns value per share and the yearly table (2026-2035).

    `orders` is either one number (the same every year 2027-35) or a list of nine yearly values."""
    w = p.wacc
    years = list(range(2026, 2036))
    per_year = list(orders) if hasattr(orders, "__len__") else [orders] * 9
    units = [h2] + per_year
    order_value = [units[k] * p.royalty * (1 + p.royalty_growth) ** (y - 2026) for k, y in enumerate(years)]
    rows, prev_rev, marine_rev = [], None, p.marine0
    for k, y in enumerate(years):
        new = sum(order_value[k - d] * p.profile[d - 1] for d in (1, 2, 3) if k - d >= 0)
        if k:
            marine_rev *= 1 + marine
        services = p.services0 * (1 + p.services_growth) ** (y - 2026)
        rev = GTT_BACKLOG.get(y, 0.0) + new + marine_rev + services
        ebitda = rev - p.core_costs * (1 + p.cost_growth) ** (y - 2026) - marine_rev * (1 - p.marine_margin)
        nopat = (ebitda - p.da) * (1 - p.tax)
        fcf = nopat + p.da - p.capex - (p.nwc * (rev - prev_rev) if k else 0.0)
        rows.append(dict(year=y, revenue=rev, ebitda_margin=ebitda / rev, fcf=fcf))
        prev_rev = rev
    pv = sum(r["fcf"] / (1 + w) ** k for k, r in enumerate(rows) if k)
    pv_tv = rows[-1]["fcf"] * (1 + g) / (w - g) / (1 + w) ** 9
    equity = pv + pv_tv + p.net_cash + rows[0]["fcf"] * p.h2_share
    return equity / p.shares, rows, pv_tv / (pv + pv_tv)


def gtt_implied_orders(p: GttInputs = GttInputs()):
    """Orders a year 2027-35 that justify the price, everything else as in the base case."""
    b = GTT_SCENARIOS["Base"]
    v0 = gtt_value(b["h2"], 0, b["marine"], b["g"], p)[0]
    v1 = gtt_value(b["h2"], 1, b["marine"], b["g"], p)[0]
    return (p.price - v0) / (v1 - v0)


# ------------------------------------------------------------------ JPMorgan (residual income, $mm)

JPM_SCENARIOS = {
    "Bear": dict(rote=[0.19, 0.12, 0.11, 0.14, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15], lr=0.15, payout=0.45),
    "Base": dict(rote=[0.20, 0.19, 0.18, 0.175, 0.17, 0.17, 0.17, 0.17, 0.17, 0.17], lr=0.17, payout=0.60),
    "Bull": dict(rote=[0.21, 0.21, 0.21, 0.21, 0.21, 0.205, 0.20, 0.20, 0.20, 0.20], lr=0.20, payout=0.65),
}


@dataclass
class JpmInputs:
    price: float = 339.72
    total_equity: float = 372000
    preferred: float = 21200
    bvps: float = 132.30
    tbvps: float = 112.64
    rf: float = 0.051
    beta: float = 1.015
    erp: float = 0.05
    g: float = 0.04
    coe_override: float = None

    @property
    def shares(self):
        return (self.total_equity - self.preferred) / self.bvps

    @property
    def tce(self):
        return self.tbvps * self.shares

    @property
    def coe(self):
        if self.coe_override is not None:
            return self.coe_override
        return self.rf + (0.67 * self.beta + 0.33) * self.erp


def jpm_value(rote, lr, payout, p: JpmInputs = JpmInputs()):
    """Residual income: value = TCE + PV(net income - r x opening TCE) + PV(terminal). Returns value per share."""
    r, tce, pv = p.coe, p.tce, 0.0
    tce0 = tce
    for t, x in enumerate(rote, start=1):
        ni = x * tce
        pv += (ni - r * tce) / (1 + r) ** t
        tce += ni * (1 - payout)
    pv_tv = (lr - r) * tce / (r - p.g) / (1 + r) ** len(rote)
    return (tce0 + pv + pv_tv) / p.shares


def jpm_implied_rote(p: JpmInputs = JpmInputs()):
    """ROTE that justifies today's P/TBV forever: P/TBV = (ROTE - g) / (r - g)."""
    return p.price / p.tbvps * (p.coe - p.g) + p.g
