"""
SEC EDGAR data: ticker -> CIK map and XBRL company facts.

companyfacts.zip (~1.4 GB, rebuilt nightly by the SEC) holds one JSON per
filer with every XBRL fact it has reported, each tagged with the filing that
reported it (accn, form, filed). Only the concepts in CONCEPTS and the
periodic-report forms in FORMS are kept.

The SEC asks every client to declare a User-Agent with a contact email;
it is read from SEC_USER_AGENT in .env. Requests are kept well under the
SEC's 10 per second.
"""

import json
import os
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
SEC_DIR = ROOT / 'data' / 'sec'
COMPANYFACTS_URL = 'https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip'
TICKERS_URL = 'https://www.sec.gov/files/company_tickers_exchange.json'

# Concepts kept, by taxonomy. Several are fallbacks for the same quantity;
# src/backtest/fundamentals.py decides which one each company uses.
CONCEPTS = {
    'us-gaap': [
        # Net income attributable to the parent, then fallbacks
        'NetIncomeLoss', 'ProfitLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic',
        # Diluted EPS, then fallbacks
        'EarningsPerShareDiluted', 'EarningsPerShareBasicAndDiluted', 'EarningsPerShareBasic',
        'WeightedAverageNumberOfDilutedSharesOutstanding',
        # Cash flow
        'NetCashProvidedByUsedInOperatingActivities',
        'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        'PaymentsToAcquirePropertyPlantAndEquipment', 'PaymentsToAcquireProductiveAssets',
        'PaymentsForCapitalImprovements', 'PaymentsToAcquireOtherPropertyPlantAndEquipment',
        # Gross profitability (quality factor, src/backtest/quality.py)
        'GrossProfit', 'Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax',
        'RevenueFromContractWithCustomerIncludingAssessedTax', 'SalesRevenueNet',
        'CostOfRevenue', 'CostOfGoodsAndServicesSold', 'CostOfGoodsSold', 'Assets',
        # Equity
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        # Debt components (the definition is calibrated against TradingView)
        'LongTermDebt', 'LongTermDebtNoncurrent', 'LongTermDebtCurrent', 'DebtCurrent',
        'ShortTermBorrowings', 'CommercialPaper',
        'LongTermDebtAndCapitalLeaseObligations', 'LongTermDebtAndCapitalLeaseObligationsCurrent',
        'LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities',
        'DebtAndCapitalLeaseObligations', 'DebtLongtermAndShorttermCombinedAmount',
        'LongTermNotesPayable',
        'FinanceLeaseLiability', 'FinanceLeaseLiabilityNoncurrent', 'FinanceLeaseLiabilityCurrent',
        'OperatingLeaseLiability', 'OperatingLeaseLiabilityNoncurrent', 'OperatingLeaseLiabilityCurrent',
    ],
    'dei': ['EntityCommonStockSharesOutstanding', 'EntityPublicFloat'],
}

UNITS = {'USD', 'USD/shares', 'shares'}

# Periodic reports. Registration statements (S-1, S-4) also carry
# historical financials, but before the company was listed.
FORMS = {'10-K', '10-K/A', '10-Q', '10-Q/A', '10-KT', '10-KT/A', '10-QT', '10-QT/A',
         '20-F', '20-F/A', '40-F', '40-F/A'}


def user_agent() -> str:
    load_dotenv(ROOT / '.env')
    ua = os.getenv('SEC_USER_AGENT', '').strip()
    if not ua or 'example.com' in ua:
        raise RuntimeError('Set SEC_USER_AGENT in .env (name and contact email, required by the SEC)')
    return ua


def download(url: str, dest: Path, max_age_days: float = 7.0) -> Path:
    """Download url to dest unless a copy younger than max_age_days exists."""
    if dest.exists() and (time.time() - dest.stat().st_mtime) < max_age_days * 86400:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.part')
    with requests.get(url, headers={'User-Agent': user_agent()}, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.replace(dest)
    time.sleep(0.2)
    return dest


def load_tickers() -> pd.DataFrame:
    """Current SEC ticker map: cik, name, ticker (yfinance style, BRK-B), exchange."""
    path = download(TICKERS_URL, SEC_DIR / 'company_tickers_exchange.json', max_age_days=1)
    raw = json.loads(path.read_text(encoding='utf-8'))
    return pd.DataFrame(raw['data'], columns=raw['fields'])


def parse_company(doc: dict) -> list:
    """Rows (cik, concept, unit, start, end, val, accn, form, filed) for one filer."""
    rows = []
    cik = int(doc.get('cik') or 0)
    facts = doc.get('facts', {})
    for taxonomy, concepts in CONCEPTS.items():
        tax = facts.get(taxonomy, {})
        for concept in concepts:
            for unit, items in tax.get(concept, {}).get('units', {}).items():
                if unit not in UNITS:
                    continue
                for it in items:
                    if it.get('form') not in FORMS:
                        continue
                    rows.append((cik, concept, unit, it.get('start'), it['end'], it['val'],
                                 it['accn'], it['form'], it['filed']))
    return rows


def extract_facts(ciks: set = None, zip_path: Path = None) -> pd.DataFrame:
    """
    Parse companyfacts.zip into one long DataFrame. With `ciks`, only those
    filers are parsed (the zip holds ~19,000; the universe needs ~4,000).
    """
    zip_path = zip_path or download(COMPANYFACTS_URL, SEC_DIR / 'companyfacts.zip')
    rows = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.startswith('CIK'):
                continue
            if ciks is not None and int(name[3:13]) not in ciks:
                continue
            with zf.open(name) as fh:
                rows.extend(parse_company(json.load(fh)))
    df = pd.DataFrame(rows, columns=['cik', 'concept', 'unit', 'start', 'end', 'val',
                                     'accn', 'form', 'filed'])
    for c in ('start', 'end', 'filed'):
        df[c] = pd.to_datetime(df[c])
    df['val'] = df['val'].astype(float)
    df['concept'] = df['concept'].astype('category')
    return df


def extract_public_float(zip_path: Path = None) -> pd.DataFrame:
    """
    dei:EntityPublicFloat from every filer's annual reports: cik, end, val,
    filed. Used only to measure survivorship bias (how many companies that
    were large at the time are still listed today).
    """
    zip_path = zip_path or SEC_DIR / 'companyfacts.zip'
    rows = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.startswith('CIK'):
                continue
            with zf.open(name) as fh:
                doc = json.load(fh)
            items = doc.get('facts', {}).get('dei', {}).get('EntityPublicFloat', {}).get('units', {}).get('USD', [])
            cik = int(doc.get('cik') or 0)
            rows.extend((cik, it['end'], it['val'], it['filed']) for it in items
                        if it.get('form') in {'10-K', '10-K/A', '20-F', '40-F'})
    df = pd.DataFrame(rows, columns=['cik', 'end', 'val', 'filed'])
    df['val'] = df['val'].astype(float)
    df['end'] = pd.to_datetime(df['end'])
    df['filed'] = pd.to_datetime(df['filed'])
    return df
