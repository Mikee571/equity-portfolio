-- 02. Which sectors have the highest and the most cyclical operating margins? (2012-2025)
--
-- Universe: the ~2,600 US stocks in the screener backtest, classified by sector, company-years with revenue
-- above $100mm. For each sector and year take the median company margin, then summarise each sector across
-- years: typical level, worst and best year, and how much the yearly median moves (a cyclicality measure).

WITH company_years AS (
    SELECT s.sector, f.fiscal_year, f.operating_income / f.revenue AS operating_margin
    FROM annual_financials f
    JOIN sectors s USING (cik)
    WHERE f.fiscal_year BETWEEN 2012 AND 2025
      AND f.revenue > 100e6
      AND f.operating_income IS NOT NULL
      AND s.sector IS NOT NULL
),
sector_years AS (
    SELECT sector, fiscal_year,
           MEDIAN(operating_margin) AS median_margin,
           COUNT(*)                 AS n_companies
    FROM company_years
    GROUP BY sector, fiscal_year
    HAVING COUNT(*) >= 15
)
SELECT sector,
       ROUND(MEDIAN(median_margin), 3)                                  AS typical_margin,
       ROUND(MIN(median_margin), 3)                                     AS worst_year_margin,
       arg_min(fiscal_year, median_margin)                              AS worst_year,
       ROUND(MAX(median_margin), 3)                                     AS best_year_margin,
       arg_max(fiscal_year, median_margin)                              AS best_year,
       ROUND(STDDEV_SAMP(median_margin), 3)                             AS cyclicality,
       ROUND(AVG(n_companies))                                          AS avg_companies
FROM sector_years
GROUP BY sector
ORDER BY typical_margin DESC;
