-- 03. How often is an annual number changed after it was first filed?
--
-- For revenue and net income, compare the value in the first 10-K that reported a fiscal year with the
-- latest value filed for that same year (usually a comparative column in later 10-Ks, or an amendment).
-- A revision above 1% is counted as material. Fiscal years 2012-2023, so every year had later 10-Ks
-- that could revise it. Changes include true restatements, reclassifications and discontinued operations.

WITH one_tag AS (
    -- a company can file revenue under two tags in the same year: keep one, in the same order as query 01
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY cik, period_end, tag = 'NetIncomeLoss'
                              ORDER BY CASE tag WHEN 'Revenues' THEN 1
                                                WHEN 'RevenueFromContractWithCustomerExcludingAssessedTax' THEN 2
                                                ELSE 3 END) AS rn
    FROM annual_facts
    WHERE tag IN ('Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'NetIncomeLoss')
      AND ABS(first_value) > 10e6
      AND n_filings >= 2
),
revisions AS (
    SELECT a.tag,
           CASE WHEN month(a.period_end) <= 1 THEN year(a.period_end) - 1 ELSE year(a.period_end) END AS fiscal_year,
           a.first_value,
           a.latest_value,
           (a.latest_value - a.first_value) / NULLIF(ABS(a.first_value), 0) AS rel_change
    FROM one_tag a
    WHERE a.rn = 1
)
SELECT CASE WHEN tag = 'NetIncomeLoss' THEN 'Net income' ELSE 'Revenue' END AS item,
       fiscal_year,
       COUNT(*)                                                               AS company_years,
       ROUND(AVG(CASE WHEN ABS(rel_change) > 0.01 THEN 1 ELSE 0 END), 3)      AS share_revised_over_1pct,
       ROUND(AVG(CASE WHEN rel_change < -0.01 THEN 1 ELSE 0 END), 3)          AS share_revised_down,
       ROUND(AVG(CASE WHEN rel_change > 0.01 THEN 1 ELSE 0 END), 3)           AS share_revised_up,
       ROUND(MEDIAN(CASE WHEN ABS(rel_change) > 0.01 THEN ABS(rel_change) END), 3) AS median_size_when_revised
FROM revisions
WHERE fiscal_year BETWEEN 2012 AND 2023
GROUP BY item, fiscal_year
ORDER BY item, fiscal_year;
