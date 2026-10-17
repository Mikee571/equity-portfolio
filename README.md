# Marcelo Renere: investment research

Ingeniería Comercial and MSc in Finance (Universidad Adolfo Ibáñez) · Master in Big Data & Data Science (Universidad Complutense de Madrid) · Master in Finance (EAE Business School) · CFA Level I candidate

I studied finance twice and data science once, and this repository is where the two meet. It's the research I do on my own time. I'm starting with the equity screener I run every week and will add the rest (company valuations, an SQL project on SEC filings, and the systematic strategies I tested) as I tidy each one up.

## Equity screener

[`equity-screener/`](equity-screener) is a five-factor screen (P/E, ROE, D/E, FCF yield, PEG) over US and European stocks.

- It validates the data before scoring, keeps a history of each run and sends the results to Telegram.
- It has a point-in-time US backtest for 2012–2026, rebuilt from first-reported SEC XBRL filings so it only uses numbers that were public at the time. I calibrated it against TradingView and checked it for survivorship bias.
- A weight-robustness study checks whether the result depends on how the five factors are weighted.

The honest result: the top 10 beat the equal-weight universe by about 3% a year, with a t-stat around 1. That's not enough to call it an edge. The folder README has the full numbers and the caveats.

## How I test things

1. Write the rule and the pass criterion down before looking at results.
2. Use point-in-time data and walk-forward or out-of-sample periods.
3. Charge realistic costs and compare against a fair benchmark: buy and hold, the equal-weight universe, the same average exposure, or random timing.
4. Report confidence intervals and subperiods, not just the headline number.
5. If it fails, archive it with the evidence instead of tweaking it until it passes.

## Running the code

Python 3.11+.

```
pip install -r equity-screener/requirements.txt -r equity-screener/requirements-backtest.txt
```

Market data is downloaded from Yahoo Finance and SEC EDGAR on the first run and cached locally; it isn't included in the repo. The backtest needs a `SEC_USER_AGENT` in `equity-screener/.env` (see `.env.example`). The folder README has the exact commands.

## Tools

Python (pandas, statsmodels), SEC EDGAR and Yahoo Finance data. I use Claude as a coding and writing assistant; the questions, the test designs and the calls on what to keep or drop are mine.

## Disclaimer

Personal research. Nothing here is investment advice, and backtested results don't predict future returns.

## Contact

[LinkedIn](https://www.linkedin.com/in/marcelo-renere/) · mrenere@student.eae.es
