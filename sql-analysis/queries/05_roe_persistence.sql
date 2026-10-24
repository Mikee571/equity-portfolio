-- 05. Do high-ROE companies stay high-ROE?
--
-- Each fiscal year 2014-2021, rank companies into ROE quintiles (net income / year-end equity, positive
-- equity, revenue > $100mm). Then look up the same company's quintile three years later. The output is a
-- transition matrix: of the companies in quintile X, what share ends up in each quintile three years on?
-- With no persistence every cell would be about 20%.

WITH roe AS (
    SELECT cik, fiscal_year, net_income / equity AS roe
    FROM annual_financials
    WHERE fiscal_year BETWEEN 2014 AND 2024
      AND equity > 0 AND revenue > 100e6 AND net_income IS NOT NULL
),
ranked AS (
    SELECT *, NTILE(5) OVER (PARTITION BY fiscal_year ORDER BY roe) AS q
    FROM roe
),
pairs AS (
    SELECT a.q AS q_start, b.q AS q_after_3y
    FROM ranked a
    JOIN ranked b ON a.cik = b.cik AND b.fiscal_year = a.fiscal_year + 3
    WHERE a.fiscal_year BETWEEN 2014 AND 2021
)
SELECT q_start AS roe_quintile_start,
       COUNT(*) AS company_years,
       ROUND(AVG(CASE WHEN q_after_3y = 1 THEN 1 ELSE 0 END), 3) AS to_q1_lowest,
       ROUND(AVG(CASE WHEN q_after_3y = 2 THEN 1 ELSE 0 END), 3) AS to_q2,
       ROUND(AVG(CASE WHEN q_after_3y = 3 THEN 1 ELSE 0 END), 3) AS to_q3,
       ROUND(AVG(CASE WHEN q_after_3y = 4 THEN 1 ELSE 0 END), 3) AS to_q4,
       ROUND(AVG(CASE WHEN q_after_3y = 5 THEN 1 ELSE 0 END), 3) AS to_q5_highest
FROM pairs
GROUP BY q_start
ORDER BY q_start;
