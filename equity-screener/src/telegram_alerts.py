"""
Telegram alerts — sends the weekly screener top-N to a private chat.

Reads credentials from environment (loaded by python-dotenv from .env):
    TELEGRAM_BOT_TOKEN   — from @BotFather
    TELEGRAM_CHAT_ID     — from api.telegram.org/bot<TOKEN>/getUpdates

Uses only the standard `requests` library — no telegram SDK dependency.
"""

import html
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv


# Load .env from project root (parent of src/)
load_dotenv(Path(__file__).resolve().parent.parent / '.env', override=True)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


class TelegramError(RuntimeError):
    """Raised when the Telegram API call fails."""


def _check_credentials():
    if not TOKEN or not CHAT_ID:
        raise TelegramError(
            "Missing credentials. Create a .env file at the project root with:\n"
            "  TELEGRAM_BOT_TOKEN=<token from @BotFather>\n"
            "  TELEGRAM_CHAT_ID=<your chat id>"
        )


def send_message(text: str, parse_mode: str = 'HTML') -> dict:
    """Send a plain text message. Returns the Telegram API JSON response."""
    _check_credentials()
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True,
    }
    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code != 200:
        raise TelegramError(f"Telegram API {resp.status_code}: {resp.text}")
    return resp.json()


def format_quarantine(quarantine: pd.DataFrame, max_names: int = 5) -> str:
    """One-paragraph summary of quarantined tickers ('' if none)."""
    if quarantine is None or quarantine.empty:
        return ""
    items = [f"{html.escape(str(r['name']))} ({html.escape(str(r['data_errors']))})"
             for _, r in quarantine.head(max_names).iterrows()]
    more = len(quarantine) - len(items)
    if more > 0:
        items.append(f"+{more} more")
    return (f"\n⚠️ <b>Quarantined ({len(quarantine)})</b>, data errors, not ranked:\n"
            + ", ".join(items) + "\n")


def _pct(x) -> str:
    """Whole-number signed percentage; avoids printing '-0%'."""
    return "n/a" if pd.isna(x) else f"{round(x):+d}%"


def format_fading(fading: pd.DataFrame) -> str:
    """
    Top-N names losing score over the lookback window ('' if none).
    Each line splits the change into the stock's own data vs the peer
    distribution (see src/history.py), then price vs implied EPS.
    """
    if fading is None or fading.empty:
        return ""
    items = [f"{html.escape(str(r['name']))} {r['score_delta']:+.2f} = "
             f"own {r['d_own']:+.2f} / peers {r['d_peers']:+.2f} "
             f"(price {_pct(r['price_chg_pct'])}, EPS {_pct(r['eps_chg_pct'])})"
             for _, r in fading.iterrows()]
    return ("\n📉 <b>Fading</b>, score change over the last "
            f"{int(fading['window_weeks'].max())} weeks:\n"
            + "\n".join(items) + "\n")


def format_top_n(ranked: pd.DataFrame,
                 raw_count: int,
                 clean_count: int,
                 top_n: int = 10,
                 quarantine: pd.DataFrame = None,
                 persistence: pd.DataFrame = None) -> str:
    """
    Compose the weekly Telegram message.

    Mobile-first: monospaced ticker column, factors compact, one line each.
    Uses HTML for bold headers. Safe against long descriptions and NaN.
    Tickers with a data warning are marked '*'; quarantined tickers are
    listed below the table. With a persistence table (src/history.py), a
    'Wk' column shows consecutive weeks in the top N and fading names are
    listed.
    """
    quarantine_block = format_quarantine(quarantine)
    streaks = {}
    fading_block = ""
    if persistence is not None and not persistence.empty:
        streaks = dict(zip(persistence['ticker'], persistence['streak']))
        # Local import keeps `python src/telegram_alerts.py` (smoke test) working
        from .history import fading
        fading_block = format_fading(fading(persistence, top_n))

    if ranked.empty:
        return ("<b>[FIVE-FACTOR]</b> Weekly Screener\n"
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                "No tickers survived the filters this week.\n"
                "Consider loosening thresholds in config.py.\n"
                + quarantine_block)

    top = ranked.head(top_n)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')

    header = (
        f"<b>[FIVE-FACTOR] Weekly Screener</b>\n"
        f"<i>{ts}</i>\n\n"
        f"Universe: {raw_count:,} → cleaned {clean_count:,} → "
        f"<b>{len(ranked)}</b> survivors\n\n"
        f"<b>Top {min(top_n, len(top))}:</b>\n"
    )

    wk_header = f" {'Wk':>2}" if streaks else ""
    lines = ["<pre>",
             f"{'#':>2} {'Ticker':<7} {'PE':>5} {'ROE':>6} {'Score':>6}{wk_header}",
             "-" * (32 + len(wk_header))]
    warned = False
    for i, (_, row) in enumerate(top.iterrows(), 1):
        flag = '*' if (row.get('data_warnings', '') or '') else ''
        warned = warned or bool(flag)
        wk = ""
        if streaks:
            streak = streaks.get(row.get('ticker', row['name']))
            wk = f" {int(streak):>2}" if pd.notna(streak) else f" {'-':>2}"
        lines.append(
            f"{i:>2} {html.escape(str(row['name']) + flag):<7} "
            f"{row['price_earnings_ttm']:>5.1f} "
            f"{row['return_on_equity_fq']:>5.1f}% "
            f"{row['score']:>+6.2f}{wk}"
        )
    lines.append("</pre>")

    legend = "<i>* data warning, see Excel (data_warnings).</i>\n" if warned else ""
    if streaks:
        legend += "<i>Wk = consecutive weekly runs in the top 10.</i>\n"
    footer = "\n<i>Full ranking in Excel; run notebook for detail.</i>"

    return (header + "\n".join(lines) + "\n" + legend
            + fading_block + quarantine_block + footer)


def send_weekly_alert(ranked: pd.DataFrame,
                      raw_count: int,
                      clean_count: int,
                      top_n: int = 10,
                      quarantine: pd.DataFrame = None,
                      persistence: pd.DataFrame = None) -> None:
    """End-to-end: format the message and send it."""
    text = format_top_n(ranked, raw_count, clean_count, top_n, quarantine,
                        persistence)
    send_message(text)


if __name__ == '__main__':
    # Smoke test — sends a test message
    print("Sending test message to Telegram...")
    resp = send_message(
        "<b>[FIVE-FACTOR]</b> ✅ Bot connection test\n"
        f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n\n"
        "If you're reading this, the token, chat_id, and env loading "
        "are all working. Ready for weekly automation."
    )
    print(f"OK. Message id: {resp.get('result', {}).get('message_id')}")
