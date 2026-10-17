"""
Five-Factor Equity Screener — Configuration
============================================

Thresholds and universe settings for the screener. All numeric parameters
live here so the rest of the code stays declarative.

Three reference profiles are documented below. Uncomment one of them, or
set your own values in the ACTIVE THRESHOLDS block at the bottom.

Reference profiles (based on academic and practitioner literature):

    VALUE_CLASSIC  (Graham/Damodaran deep-value):
        PE_MAX = 15.0
        ROE_MIN = 0.15
        DE_MAX = 0.5
        PEG_MAX = 1.0
        FCF_MIN = 0.0

    QUALITY_VALUE  (Buffett-style compounder at reasonable price):
        PE_MAX = 20.0
        ROE_MIN = 0.12
        DE_MAX = 1.0
        PEG_MAX = 1.5
        FCF_MIN = 0.0

    GARP  (Growth At Reasonable Price, Lynch/Fisher):
        PE_MAX = 25.0
        ROE_MIN = 0.15
        DE_MAX = 1.0
        PEG_MAX = 1.2
        FCF_MIN = 0.0

Notes on methodology:
    - Financial-sector stocks (banks, insurance) are excluded by design.
      Their FCF is not comparable and D/E is structurally elevated.
      This is standard practice in equity research (Damodaran, McKinsey).
    - Micro-caps excluded via MARKET_CAP_MIN. Below $1B liquidity and
      data quality degrade rapidly.
"""

# ============================================================
# UNIVERSE SETTINGS
# ============================================================

# Markets to screen. TradingView identifiers.
MARKETS = ['america', 'germany', 'france', 'italy', 'spain',
           'netherlands', 'switzerland', 'uk']

# Home country of each market. The query only asks for that country's
# domestic exchanges (EXCHANGE_COUNTRY below). Without this filter, OTC
# listings filled the US query and foreign companies cross-listed on German
# venues filled the German one: until v0.7, a 2,000-row limit cut the US
# universe at $12.5B market cap and the German one at $89B.
MARKET_COUNTRY = {
    'america': 'United States', 'germany': 'Germany', 'france': 'France',
    'italy': 'Italy', 'spain': 'Spain', 'netherlands': 'Netherlands',
    'switzerland': 'Switzerland', 'uk': 'United Kingdom',
}

# Minimum market cap in USD. Filters out micro-caps.
MARKET_CAP_MIN = 1_000_000_000  # $1B

# Sectors to exclude (financials excluded because FCF/D/E not comparable)
EXCLUDED_SECTORS = ['Finance', 'Financials']

# Primary listing = (exchange, country) match. A stock passes only if its
# exchange is a domestic exchange for its country. Eliminates all
# secondary listings (Alphabet on LSE as 0HD6, Teradata on LSE as 0LEE,
# Lyft on Xetra as 1LYFT, etc.) — those have exchange!=home country.
#
# Domestic pairings:
EXCHANGE_COUNTRY = {
    'NASDAQ':   {'United States'},
    'NYSE':     {'United States'},
    'AMEX':     {'United States'},
    'XETR':     {'Germany'},
    'FWB':      {'Germany'},
    'EURONEXT': {'France', 'Netherlands', 'Belgium', 'Portugal', 'Ireland'},
    'MIL':      {'Italy'},
    'BME':      {'Spain'},
    'SIX':      {'Switzerland'},
    'LSE':      {'United Kingdom'},
}

# ============================================================
# ACTIVE FIVE-FACTOR THRESHOLDS
# ============================================================
# Edit these values to tune the screener. Start conservative and
# loosen if the output universe is too small (<20 tickers).
#
# IMPORTANT: TradingView returns ROE as a percentage number
# (e.g. 48.67 = 48.67%), NOT as a decimal (0.4867). Set ROE_MIN
# in percent units.

PE_MAX = 20.0       # Price / Earnings (TTM), lower = cheaper
ROE_MIN = 12.0      # Return on Equity in PERCENT (12.0 = 12%)
DE_MAX = 1.0        # Debt / Equity, lower = less leveraged
PEG_MAX = 1.5       # PE / Growth, lower = growth is cheap
FCF_MIN = 0.0       # Free Cash Flow (TTM) absolute, positive required

# Sanity bounds — values outside realistic ranges are flagged OOB_<factor>
# and quarantined (see src/validation.py), not silently dropped.
# Protects against TradingView data errors (misplaced decimals, stale figures).
# ROE > 200% is possible for buyback-heavy names (AAPL ~148%) — allow it.
# PEG = 0.00 is TradingView's code for missing data and is treated as NaN
# before these bounds apply.
SANITY_BOUNDS = {
    'price_earnings_ttm':          (0.1,  200.0),
    'return_on_equity_fq':         (-100.0, 500.0),
    'debt_to_equity':              (0.0,  20.0),
    'price_earnings_growth_ttm':   (0.01, 10.0),
    'free_cash_flow_ttm':          (-1e12, 1e12),
}

# ============================================================
# DATA VALIDATION (cross-field consistency, src/validation.py)
# ============================================================
# Calibrated on the full cleaned universe of 2026-10-06 (965 tickers).

VALIDATION = {
    # (market cap / P/E) / net income TTM. Both are company-level figures in
    # the same currency, so clean data gives ~1.0 (median 0.99, p1-p95
    # 0.82-1.06). Outside this band -> error. LISPE scored 10.0.
    'pe_earnings_ratio': (0.5, 2.0),

    # Reported ROE / (net income TTM / closing total equity). Legitimate gaps
    # exist (average vs closing equity, minorities inside total equity,
    # buybacks), so only gross gaps are flagged, as a warning.
    'roe_equity_ratio': (0.5, 2.0),
    'roe_min_gap_pp': 10.0,          # ...and only if the gap is >= 10 pp
}

# ============================================================
# SCORING
# ============================================================
# After hard filters pass, survivors are ranked by a composite score.
# Weights sum to 1.0. Each factor is winsorised, z-scored across survivors,
# then combined. Lower-is-better factors (PE, DE, PEG) are inverted.

SCORE_WEIGHTS = {
    'pe': 0.20,
    'roe': 0.30,     # Quality gets highest weight (Buffett bias)
    'de': 0.15,
    'peg': 0.20,
    'fcf': 0.15,     # scored as FCF yield = FCF / market cap (v0.7)
}

assert abs(sum(SCORE_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

# Winsorisation: before z-scoring, each factor is clipped to these
# percentiles of the survivors, so one extreme value (ROE 131%) cannot
# stretch the mean and std that every other ticker is scored against.
# None disables it. With ~55 survivors, 5/95 clips about 3 names per tail.
WINSOR_QUANTILES = (0.05, 0.95)

# PEG base effect: TradingView's PEG is trailing (P/E / TTM YoY EPS growth).
# Implied growth above this (in %) comes off a depressed base (cyclical
# trough, one-off loss), not from the business, so the PEG is treated as not
# measurable: excluded from the PEG mean/std and given a neutral z = 0.
# The same threshold raises the PEG_BASE_EFFECT warning in src/validation.py.
PEG_MAX_IMPLIED_GROWTH_PCT = 100.0

# ============================================================
# OUTPUT SETTINGS
# ============================================================

TOP_N = 10                    # Number of top tickers to report
OUTPUT_DIR = 'output'         # Directory for Excel exports

# ============================================================
# WEEKLY HISTORY (src/history.py)
# ============================================================

HISTORY_PATH = 'data/screener_history.csv'   # relative to the project root
HISTORY_LOOKBACK = 4          # snapshots used for score trend (~1 month)
FADING_SCORE_DELTA = -0.05    # top-N names losing more than this over the
                              # lookback are listed as "fading" in Telegram
