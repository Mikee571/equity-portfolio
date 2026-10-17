"""
Five-Factor Equity Screener — main entrypoint.

Usage as script:
    python run_screener.py

Usage as module (e.g. from Jupyter):
    from run_screener import run
    raw, clean, ranked, quarantine = run()
"""

from src import universe, screener, report


def run(verbose: bool = True):
    """
    Execute the full screener pipeline.

    Returns:
        raw:        DataFrame of all fetched tickers before cleaning
        clean:      DataFrame after universe cleaning
        ranked:     hard-filter survivors with clean data, ranked by composite score
        quarantine: hard-filter survivors held back by a data error (src/validation.py)
    """
    if verbose:
        print("Five-Factor Equity Screener")
        print("=" * 40)
        print("\n[1/3] Fetching universe...")

    raw = universe.fetch_universe()
    if verbose:
        print(f"  Total raw tickers: {len(raw)}")
        print("\n[2/3] Cleaning universe...")

    clean = universe.clean_universe(raw)

    if verbose:
        print("\n[3/3] Running screener...")
    ranked, quarantine = screener.run_screener(clean)

    return raw, clean, ranked, quarantine


def main():
    raw, clean, ranked, quarantine = run()
    report.print_top_n(ranked, quarantine)
    report.export_excel(ranked, quarantine=quarantine)
    print("\nDone.")


if __name__ == '__main__':
    main()
