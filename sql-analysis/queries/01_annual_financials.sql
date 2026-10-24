-- 01. Annual financial statements, one row per company and fiscal year.
--
-- Step 1, annual_facts: the same annual number usually appears in several filings (the original 10-K, next
-- year's 10-K as a comparative, amendments). Keep the first and the latest value filed for each
-- company / tag / fiscal-year end, and how many versions there were.
-- Step 2, annual_financials: pivot the tags into columns. Revenue has three common tags, depending on the
-- year and the filer, so it takes the first one available.

CREATE OR REPLACE TABLE annual_facts AS
WITH annual AS (
    SELECT cik, tag, period_end, value, filed, accn
    FROM facts
    WHERE form IN ('10-K', '10-K/A')
      AND (
            -- flow items (income and cash flow statement): a ~12-month period
            (period_start IS NOT NULL AND date_diff('day', period_start, period_end) BETWEEN 350 AND 380)
            -- stock items (balance sheet): a point in time
         OR (period_start IS NULL AND tag IN ('StockholdersEquity', 'Assets', 'LongTermDebt',
                                              'CashAndCashEquivalentsAtCarryingValue'))
      )
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY cik, tag, period_end ORDER BY filed, accn)           AS rn_first,
           ROW_NUMBER() OVER (PARTITION BY cik, tag, period_end ORDER BY filed DESC, accn DESC) AS rn_latest
    FROM annual
)
SELECT cik, tag, period_end,
       MAX(CASE WHEN rn_first = 1 THEN value END)  AS first_value,
       MAX(CASE WHEN rn_latest = 1 THEN value END) AS latest_value,
       MIN(filed)                                  AS first_filed,
       MAX(filed)                                  AS last_filed,
       COUNT(DISTINCT accn)                        AS n_filings
FROM ranked
GROUP BY cik, tag, period_end;

CREATE OR REPLACE TABLE annual_financials AS
SELECT cik,
       period_end,
       -- fiscal years ending in January (retailers) belong to the previous calendar year
       CASE WHEN month(period_end) <= 1 THEN year(period_end) - 1 ELSE year(period_end) END AS fiscal_year,
       COALESCE(MAX(CASE WHEN tag = 'Revenues' THEN latest_value END),
                MAX(CASE WHEN tag = 'RevenueFromContractWithCustomerExcludingAssessedTax' THEN latest_value END),
                MAX(CASE WHEN tag = 'SalesRevenueNet' THEN latest_value END))                    AS revenue,
       MAX(CASE WHEN tag = 'OperatingIncomeLoss' THEN latest_value END)                          AS operating_income,
       MAX(CASE WHEN tag = 'NetIncomeLoss' THEN latest_value END)                                AS net_income,
       MAX(CASE WHEN tag = 'StockholdersEquity' THEN latest_value END)                           AS equity,
       MAX(CASE WHEN tag = 'Assets' THEN latest_value END)                                       AS assets,
       MAX(CASE WHEN tag = 'NetCashProvidedByUsedInOperatingActivities' THEN latest_value END)   AS cfo,
       MAX(CASE WHEN tag = 'PaymentsToAcquirePropertyPlantAndEquipment' THEN latest_value END)   AS capex,
       MAX(CASE WHEN tag = 'PaymentsForRepurchaseOfCommonStock' THEN latest_value END)           AS buybacks,
       COALESCE(MAX(CASE WHEN tag = 'PaymentsOfDividendsCommonStock' THEN latest_value END),
                MAX(CASE WHEN tag = 'PaymentsOfDividends' THEN latest_value END))                AS dividends,
       MAX(CASE WHEN tag = 'WeightedAverageNumberOfDilutedSharesOutstanding' THEN latest_value END) AS diluted_shares,
       MIN(first_filed)                                                                          AS first_filed
FROM annual_facts
GROUP BY cik, period_end;

-- Output: coverage by fiscal year
SELECT fiscal_year,
       COUNT(*)                                  AS company_years,
       COUNT(revenue)                            AS with_revenue,
       COUNT(operating_income)                   AS with_operating_income,
       COUNT(diluted_shares)                     AS with_diluted_shares,
       ROUND(SUM(revenue) / 1e12, 1)             AS total_revenue_usd_tn
FROM annual_financials
WHERE fiscal_year BETWEEN 2010 AND 2025
GROUP BY fiscal_year
ORDER BY fiscal_year;
