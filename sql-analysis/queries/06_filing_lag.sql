-- 06. How fast do companies file their annual report, and does size matter?
--
-- Days from fiscal year end to the first 10-K that reported that year's net income, by company size
-- (total assets) and fiscal year. SEC deadlines are 60 days for large accelerated filers, 75 for
-- accelerated filers and 90 for everyone else.

WITH lag AS (
    SELECT a.cik,
           CASE WHEN month(a.period_end) <= 1 THEN year(a.period_end) - 1 ELSE year(a.period_end) END AS fiscal_year,
           date_diff('day', a.period_end, a.first_filed) AS days_to_file,
           f.assets
    FROM annual_facts a
    JOIN annual_financials f ON f.cik = a.cik AND f.period_end = a.period_end
    WHERE a.tag = 'NetIncomeLoss' AND f.assets > 0
),
bucketed AS (
    SELECT *,
           CASE WHEN assets >= 10e9 THEN '1. > $10bn'
                WHEN assets >= 1e9  THEN '2. $1-10bn'
                WHEN assets >= 100e6 THEN '3. $100mm-1bn'
                ELSE '4. < $100mm' END AS size_bucket
    FROM lag
    WHERE days_to_file BETWEEN 20 AND 400
)
SELECT size_bucket,
       COUNT(*)                                                      AS filings,
       ROUND(MEDIAN(days_to_file))                                   AS median_days,
       ROUND(QUANTILE_CONT(days_to_file, 0.9))                       AS p90_days,
       ROUND(AVG(CASE WHEN days_to_file > 90 THEN 1 ELSE 0 END), 3)  AS share_after_90_days,
       ROUND(MEDIAN(CASE WHEN fiscal_year BETWEEN 2012 AND 2015 THEN days_to_file END)) AS median_2012_15,
       ROUND(MEDIAN(CASE WHEN fiscal_year BETWEEN 2022 AND 2025 THEN days_to_file END)) AS median_2022_25
FROM bucketed
WHERE fiscal_year BETWEEN 2012 AND 2025
GROUP BY size_bucket
ORDER BY size_bucket;
