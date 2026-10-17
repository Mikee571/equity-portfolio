"""
Weekly automated runner — intended for Windows Task Scheduler.

Sequence:
    1. Run the screener (fetch → clean → validate → filter → rank).
    2. Append the run to the weekly history and compute streaks/trends.
    3. Save Excel export to output/ with timestamp.
    4. Send Telegram alert with top-N.
    5. Log everything to logs/weekly_YYYYMMDD.log.

Design principle: never let a failure in one stage kill the others.
If Telegram is down, the Excel is still saved and the failure is logged.
If the fetch is down, the log records the failure so tomorrow the
alert-of-nothing is diagnosable.

Usage from Task Scheduler:
    python path/to/equity-screener/run_weekly.py
"""

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Make imports work regardless of the cwd Task Scheduler happens to use
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from run_screener import run
from src import report, telegram_alerts, config, validation, history


def setup_logging() -> Path:
    """Configure a per-day log file and console echo."""
    logs_dir = PROJECT_ROOT / 'logs'
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"weekly_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file


def main() -> int:
    log_file = setup_logging()
    logging.info("=" * 60)
    logging.info(f"Weekly runner started. Log: {log_file}")

    # Stage 1: screener
    try:
        raw, clean, ranked, quarantine = run(verbose=False)
        logging.info(
            f"Screener OK. Raw={len(raw)}, Cleaned={len(clean)}, "
            f"Survivors={len(ranked)}, Quarantined={len(quarantine)}"
        )
        for _, row in quarantine.iterrows():
            logging.warning(f"Quarantined {row['name']} ({row['exchange']}): "
                            f"{row['data_errors']}")
        flags = validation.flag_counts(ranked)
        if flags:
            logging.info(f"Warnings among ranked: {flags}")
    except Exception:
        logging.error("Screener FAILED:\n" + traceback.format_exc())
        # Try to notify via Telegram that the run itself broke
        try:
            telegram_alerts.send_message(
                "<b>[FIVE-FACTOR] ⚠️ Weekly run FAILED</b>\n"
                f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M')}</i>\n\n"
                "Screener stage crashed. Check logs.")
        except Exception:
            logging.error("Telegram failure notification also failed.")
        return 1

    # Stage 2: weekly history (non-fatal: the alert still goes out without it)
    persistence = None
    try:
        n = history.append_snapshot(ranked, quarantine)
        persistence = history.persistence(history.load_history())
        logging.info(f"History: {n} rows appended to {history.history_path()}")
        for _, row in history.fading(persistence).iterrows():
            logging.info(f"Fading: {row['name']} score {row['score_delta']:+.3f} "
                         f"over {row['window_weeks']} weeks "
                         f"(own {row['d_own']:+.3f}, peers {row['d_peers']:+.3f})")
    except Exception:
        logging.error("History FAILED (non-fatal):\n" + traceback.format_exc())

    # Stage 3: Excel export
    try:
        xlsx_path = report.export_excel(ranked, quarantine=quarantine,
                                        persistence=persistence)
        logging.info(f"Excel saved: {xlsx_path}")
    except Exception:
        logging.error("Excel export FAILED (non-fatal):\n" + traceback.format_exc())

    # Stage 4: Telegram alert
    try:
        telegram_alerts.send_weekly_alert(
            ranked=ranked,
            raw_count=len(raw),
            clean_count=len(clean),
            top_n=config.TOP_N,
            quarantine=quarantine,
            persistence=persistence,
        )
        logging.info(f"Telegram alert sent ({config.TOP_N} tickers).")
    except Exception:
        logging.error("Telegram send FAILED:\n" + traceback.format_exc())
        return 2

    logging.info("Weekly runner completed successfully.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
