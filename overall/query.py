import pandas as pd
from db import engine

def get_dofftable_data(selected_date):
    query = f"""
WITH base_day AS (
  SELECT
    spell,
    frameno,
    SUM(netwt) AS total_netwt
  FROM dofftable
  WHERE doffdate = '{selected_date}'
    AND company_id = 2
    AND is_active = 1
  GROUP BY spell, frameno
),
frame_day AS (
  SELECT
    SUM(CASE WHEN spell = 'A1' THEN 1 * 5/8
             WHEN spell = 'A2' THEN 1 * 3/8 ELSE 0 END) AS A_frames,
    SUM(CASE WHEN spell = 'B1' THEN 1 * 3/8
             WHEN spell = 'B2' THEN 1 * 5/8 ELSE 0 END) AS B_frames,
    SUM(CASE WHEN spell = 'C' THEN 1 ELSE 0 END) AS C_frames
  FROM (SELECT DISTINCT spell, frameno FROM base_day) AS distinct_frames
),
prod_day AS (
  SELECT
    SUM(CASE WHEN spell IN ('A1', 'A2') THEN total_netwt ELSE 0 END) AS A_netwt,
    SUM(CASE WHEN spell IN ('B1', 'B2') THEN total_netwt ELSE 0 END) AS B_netwt,
    SUM(CASE WHEN spell = 'C' THEN total_netwt ELSE 0 END) AS C_netwt
  FROM base_day
),
combined AS (
  SELECT
    d.A_netwt AS A_netwt_day, d.B_netwt AS B_netwt_day, d.C_netwt AS C_netwt_day,
    f.A_frames AS A_frames_day, f.B_frames AS B_frames_day, f.C_frames AS C_frames_day
  FROM prod_day d, frame_day f
)
-- PIVOTED FINAL OUTPUT
SELECT 'PRODUCTION (MT)' AS metric,
       ROUND(A_netwt_day / 1000, 3) AS A,
       ROUND(B_netwt_day / 1000, 3) AS B,
       ROUND(C_netwt_day / 1000, 3) AS C
FROM combined
UNION ALL
SELECT 'NO OF FRAME RUNS',
       ROUND(A_frames_day, 3),
       ROUND(B_frames_day, 3),
       ROUND(C_frames_day, 3)
FROM combined;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def get_dofftable_sum_by_date(selected_date, end_date):
    query = f"""
WITH base_mtd AS (
  SELECT DISTINCT spell, frameno, doffdate
  FROM dofftable
  WHERE doffdate BETWEEN '{selected_date}' AND '{end_date}'
    AND company_id = 2
    AND is_active = 1
),
frame_mtd_weighted AS (
  SELECT 
    doffdate,
    SUM(CASE WHEN spell = 'A1' THEN 1 * 5/8 ELSE 0 END +
        CASE WHEN spell = 'A2' THEN 1 * 3/8 ELSE 0 END +
        CASE WHEN spell = 'B1' THEN 1 * 3/8 ELSE 0 END +
        CASE WHEN spell = 'B2' THEN 1 * 5/8 ELSE 0 END +
        CASE WHEN spell = 'C'  THEN 1 ELSE 0 END) AS daily_weighted_frames
  FROM base_mtd
  GROUP BY doffdate
),
total_frames_mtd AS (
  SELECT SUM(daily_weighted_frames) AS total_frames FROM frame_mtd_weighted
),
prod_mtd AS (
  SELECT SUM(netwt) AS total_netwt
  FROM dofftable
  WHERE doffdate BETWEEN '{selected_date}' AND '{end_date}'
    AND company_id = 2
    AND is_active = 1
)
SELECT 'NO OF FRAME RUNS' AS metric,
       ROUND(f.total_frames, 3) AS value
FROM total_frames_mtd f

UNION ALL

SELECT 'PRODUCTION (MT)',
       ROUND(p.total_netwt / 1000, 3)
FROM prod_mtd p;

    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")


def get_spg_fine_coarse(selected_date):
    query = f"""     select 'Overall' as side, sum(sdt.hunprod)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c) as TrgtKgPerFrame ,
     sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c) as ActualProduction,
     sum((sdt.prd_a+sdt.prd_b+sdt.prd_c)*sdt.act_count)/sum(sdt.prd_a+sdt.prd_b+sdt.prd_c) as ActualCount,
     sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.winder ) as ProdPerWinder
     from EMPMILL12.spining_daily_transaction sdt  where tran_date = '2025-07-02' and company_id =2 
     union all
     select substr(sdt.q_code,1,1) as side, sum(sdt.hunprod)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c) as TrgtKgPerFrame ,
     sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c) as ActualProduction,
     sum((sdt.prd_a+sdt.prd_b+sdt.prd_c)*sdt.act_count)/sum(sdt.prd_a+sdt.prd_b+sdt.prd_c) as ActualCount,
     sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.winder ) as ProdPerWinder
     from EMPMILL12.spining_daily_transaction sdt  where tran_date = '{selected_date}' and company_id =2 
     group by substr(sdt.q_code,1,1) ;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def get_spg_sid_mtd(selected_date, end_date):
    query = f"""
     select 'MTD' as side, sum(sdt.hunprod)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c) as TrgtKgPerFrame ,
     sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c) as ActualProduction,
     sum((sdt.prd_a+sdt.prd_b+sdt.prd_c)*sdt.act_count)/sum(sdt.prd_a+sdt.prd_b+sdt.prd_c) as ActualCount,
     sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.winder ) as ProdPerWinder
     from EMPMILL12.spining_daily_transaction sdt  where tran_date between '{end_date}' and '{selected_date}' and company_id =2 
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")