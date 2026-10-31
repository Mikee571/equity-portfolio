"""
sentiment.py
============
Sentimiento de mercado combinado: noticias financieras (fuente principal,
todos los activos) + señal social/Reddit (solo donde hay volumen suficiente,
ej. NVDA) — decisión tomada tras detectar que activos como GDX, GDXJ, Brent
o RHM.DE no tienen volumen de discusión social suficiente para una señal
fiable, mientras que las noticias sí cubren todos los activos de forma
consistente.
"""

import feedparser
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Léxico financiero extendido — VADER por defecto está calibrado para
# lenguaje general y subestima términos como "smashes earnings" o "downgrade".
FINANCIAL_LEXICON = {
    "surge": 3.0, "surges": 3.0, "surging": 3.0,
    "soar": 3.0, "soars": 3.0, "soaring": 3.0,
    "rally": 2.5, "rallies": 2.5, "rallying": 2.5,
    "beat": 2.0, "beats": 2.0, "beating": 2.0,
    "smashes": 2.5, "smashed": 2.5,
    "outperform": 2.0, "outperforms": 2.0,
    "upgrade": 2.0, "upgraded": 2.0, "upgrades": 2.0,
    "bullish": 2.5, "record high": 2.5, "all-time high": 2.5,
    "breakout": 1.5, "rebound": 1.5, "rebounds": 1.5,
    "plunge": -3.0, "plunges": -3.0, "plunging": -3.0,
    "crash": -3.0, "crashes": -3.0, "crashing": -3.0,
    "tumble": -2.5, "tumbles": -2.5, "tumbling": -2.5,
    "slump": -2.0, "slumps": -2.0,
    "miss": -2.0, "misses": -2.0, "missed": -2.0,
    "downgrade": -2.0, "downgraded": -2.0, "downgrades": -2.0,
    "bearish": -2.5, "sell-off": -2.0, "selloff": -2.0,
    "dumps": -1.5, "dump": -1.5, "dumping": -1.5,
    "recession": -2.0, "layoffs": -1.5, "layoff": -1.5,
    "lawsuit": -1.5, "probe": -1.5, "investigation": -1.5,
    "plummet": -3.0, "plummets": -3.0,
}


def get_analyzer() -> SentimentIntensityAnalyzer:
    a = SentimentIntensityAnalyzer()
    a.lexicon.update(FINANCIAL_LEXICON)
    return a


# Mapeo de ticker -> términos de búsqueda para filtrar titulares relevantes.
# Necesario porque los feeds generales (Yahoo Finance News) traen de todo;
# sin este filtro el sentimiento se mezclaría entre activos no relacionados.
TICKER_SEARCH_TERMS = {
    "GDX": ["gold miners", "gold mining stocks", "GDX"],
    "GDXJ": ["junior gold miners", "GDXJ"],
    "GLD": ["gold price", "gold etf"],
    "NVDA": ["nvidia", "NVDA"],
    "LMT": ["lockheed martin"],
    "RTX": ["RTX corp", "raytheon"],
    "RHM.DE": ["rheinmetall"],
    "USDJPY=X": ["dollar yen", "USD/JPY", "yen"],
    "HG=F": ["copper price", "copper futures"],
    "BZ=F": ["brent crude", "oil price"],
}

NEWS_FEEDS = {
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    "cnbc_top": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "marketwatch_topstories": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "investing_news": "https://www.investing.com/rss/news.rss",
}


def fetch_news_headlines(max_age_days: int = 5) -> pd.DataFrame:
    """
    Descarga titulares de los feeds RSS configurados.
    Devuelve DataFrame con columnas: title, published, source.
    """
    rows = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    for source, url in NEWS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            published = None
            if getattr(entry, "published_parsed", None):
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published is None or published >= cutoff:
                rows.append({
                    "title": entry.title,
                    "published": published or datetime.now(timezone.utc),
                    "source": source,
                })

    return pd.DataFrame(rows)


def score_headlines_for_ticker(headlines: pd.DataFrame, ticker: str,
                                analyzer: SentimentIntensityAnalyzer) -> pd.DataFrame:
    """Filtra titulares relevantes para un ticker y calcula su score de sentimiento."""
    terms = [t.lower() for t in TICKER_SEARCH_TERMS.get(ticker, [ticker.lower()])]

    if headlines.empty:
        return pd.DataFrame(columns=["title", "published", "source", "compound"])

    mask = headlines["title"].str.lower().apply(lambda t: any(term in t for term in terms))
    relevant = headlines[mask].copy()
    relevant["compound"] = relevant["title"].apply(
        lambda t: analyzer.polarity_scores(t)["compound"]
    )
    return relevant


def aggregate_daily_news_sentiment(scored: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega titulares a nivel diario: score promedio + volumen de menciones.
    Devuelve DataFrame indexado por fecha con columnas: news_sentiment, news_volume.
    """
    if scored.empty:
        return pd.DataFrame(columns=["news_sentiment", "news_volume"])

    scored = scored.copy()
    scored["date"] = pd.to_datetime(scored["published"]).dt.date
    daily = scored.groupby("date").agg(
        news_sentiment=("compound", "mean"),
        news_volume=("compound", "count"),
    )
    daily.index = pd.to_datetime(daily.index)
    return daily


def build_sentiment_features(ticker: str, price_index: pd.DatetimeIndex,
                              use_social: bool = False,
                              social_score: float = None) -> pd.DataFrame:
    """
    Construye features de sentimiento alineados al índice de fechas del precio.

    NOTA IMPORTANTE sobre el límite real de esta fuente: un feed RSS solo
    cubre ~5 días hacia atrás de titulares actuales, NO un histórico de 2 años.
    Por eso, para el entrenamiento histórico del modelo, esta función rellena
    con NaN -> 0 (neutral) fuera de la ventana real de noticias disponibles,
    y se documenta esta limitación explícitamente en las conclusiones del
    notebook en vez de fabricar datos sintéticos para el pasado.

    use_social=True simula la disponibilidad de un score social pre-calculado
    (ej. desde market_sentiment del MCP) para activos con volumen suficiente
    (NVDA). Si no se provee social_score, esta columna queda en 0.
    """
    analyzer = get_analyzer()
    headlines = fetch_news_headlines()
    scored = score_headlines_for_ticker(headlines, ticker, analyzer)
    daily_sentiment = aggregate_daily_news_sentiment(scored)

    features = pd.DataFrame(index=price_index)
    features = features.join(daily_sentiment, how="left")
    features["news_sentiment"] = pd.to_numeric(features["news_sentiment"], errors="coerce").fillna(0.0)
    features["news_volume"] = pd.to_numeric(features["news_volume"], errors="coerce").fillna(0.0)

    # Momentum del sentimiento: ¿mejora o empeora en los últimos días?
    features["news_sentiment_momentum"] = features["news_sentiment"].diff(3).fillna(0.0)

    if use_social:
        features["social_sentiment"] = social_score if social_score is not None else 0.0
    else:
        features["social_sentiment"] = 0.0

    return features
