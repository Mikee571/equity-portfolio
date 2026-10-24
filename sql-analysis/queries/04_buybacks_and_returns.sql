-- 04. Did companies that shrank their share count go on to outperform?
--
-- Sort stocks by the change in diluted share count over FY2015-FY2020 (negative = net buybacks), then
-- measure the share-price total return (adjusted close, dividends reinvested) from January 2021 to
-- December 2025. Survivorship caveat: the price universe only holds companies still listed today.

WITH shares AS (
    SELECT cik,
           MAX(CASE WHEN fiscal_year = 2015 THEN diluted_shares END) AS shares_2015,
           MAX(CASE WHEN fiscal_year = 2020 THEN diluted_shares END) AS shares_2020
    FROM annual_financials
    GROUP BY cik
),
change AS (
    SELECT s.cik, sec.symbol, sec.sector, shares_2020 / shares_2015 - 1 AS share_change
    FROM shares s
    JOIN sectors sec USING (cik)
    WHERE shares_2015 > 0 AND shares_2020 > 0
      AND shares_2020 / shares_2015 BETWEEN 0.3 AND 3      -- drop splits misread as issuance and data errors
),
returns AS (
    SELECT symbol,
           MAX(CASE WHEN month_end = DATE '2025-12-31' THEN adj_close END)
         / MAX(CASE WHEN month_end = DATE '2020-12-31' THEN adj_close END) - 1 AS return_2021_2025
    FROM prices
    WHERE month_end IN (DATE '2020-12-31', DATE '2025-12-31')
    GROUP BY symbol
),
joined AS (
    SELECT c.*, r.return_2021_2025,
           NTILE(5) OVER (ORDER BY c.share_change) AS quintile
    FROM change c
    JOIN returns r USING (symbol)
    WHERE r.return_2021_2025 IS NOT NULL
)
SELECT quintile,
       CASE quintile WHEN 1 THEN 'Most shrinkage' WHEN 5 THEN 'Most dilution' ELSE '' END AS label,
       COUNT(*)                                     AS stocks,
       ROUND(MEDIAN(share_change), 3)               AS median_share_change_2015_20,
       ROUND(MEDIAN(return_2021_2025), 3)           AS median_return_2021_25,
       ROUND(AVG(return_2021_2025), 3)              AS mean_return_2021_25,
       ROUND(AVG(CASE WHEN return_2021_2025 < 0 THEN 1 ELSE 0 END), 3) AS share_with_loss
FROM joined
GROUP BY quintile
ORDER BY quintile;
