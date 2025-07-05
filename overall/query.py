import pandas as pd
from db import engine

def get_dofftable_data(selected_date):
    query = f"""
WITH base_day AS (
  SELECT
    spell,
    frameno,
    round(SUM(netwt), 3) AS total_netwt
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
    round(SUM(CASE WHEN spell IN ('A1', 'A2') THEN total_netwt ELSE 0 END),3) AS A_netwt,
    round(SUM(CASE WHEN spell IN ('B1', 'B2') THEN total_netwt ELSE 0 END),3) AS B_netwt,
    round(SUM(CASE WHEN spell = 'C' THEN total_netwt ELSE 0 END),3) AS C_netwt
  FROM base_day
),
combined AS (
  SELECT
    d.A_netwt AS A_netwt_day, d.B_netwt AS B_netwt_day, d.C_netwt AS C_netwt_day,
    f.A_frames AS A_frames_day, f.B_frames AS B_frames_day, f.C_frames AS C_frames_day
  FROM prod_day d, frame_day f
)
-- PIVOTED FINAL OUTPUT
SELECT 'PRODUCTION (MT)' AS DoffWtProd,
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

def get_dofftable_sum_by_date(selected_date, start_date):
    query = f"""
WITH base_mtd AS (
  SELECT DISTINCT spell, frameno, doffdate
  FROM dofftable
  WHERE doffdate BETWEEN '{selected_date}' AND '{start_date}'
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
  WHERE doffdate BETWEEN '{selected_date}' AND '{start_date}'
    AND company_id = 2
    AND is_active = 1
)
SELECT 'NO OF FRAME RUNS' AS DoffWtProd,
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
    query = f"""          select 'Overall' as side, 
     round(sum((sdt.prd_a+sdt.prd_b+sdt.prd_c)*sdt.act_count)/sum(sdt.prd_a+sdt.prd_b+sdt.prd_c),2) as ActualCount,
     round(sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c),0) as KgPerFrame,
     round(sum(sdt.hunprod)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c),0) as TrgtKgPerFrame ,
     round(sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.winder ),0) as ProdPerWinder
     from EMPMILL12.spining_daily_transaction sdt  where sdt.tran_date = '{selected_date}' and company_id =2 
     union all
     select substr(sdt.q_code,1,1) as side, 
     round(sum((sdt.prd_a+sdt.prd_b+sdt.prd_c)*sdt.act_count)/sum(sdt.prd_a+sdt.prd_b+sdt.prd_c),2) as ActualCount,
     round(sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c),0) as KgPerFrame,
     round(sum(sdt.hunprod)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c),0) as TrgtKgPerFrame ,
     round(sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.winder ),0) as ProdPerWinder
     from EMPMILL12.spining_daily_transaction sdt  where sdt.tran_date = '{selected_date}' and company_id =2 
     group by substr(sdt.q_code,1,1) ;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def get_spg_sid_mtd(selected_date, start_date):
    query = f"""
          select 'MTD' as side, 
     round(sum((sdt.prd_a+sdt.prd_b+sdt.prd_c)*sdt.act_count)/sum(sdt.prd_a+sdt.prd_b+sdt.prd_c),2) as ActualCount,
     round(sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c),0) as KgPerFrame,
     round(sum(sdt.hunprod)/sum(sdt.mc_a+sdt.mc_b+sdt.mc_c),0) as TrgtKgPerFrame ,
     round(sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.winder ),0) as ProdPerWinder
     from EMPMILL12.spining_daily_transaction sdt  where sdt.tran_date between '{start_date}' and '{selected_date}' and company_id =2
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")


def get_quality_winding_details(selected_date, start_date):
    query = f"""
     select tdtprod.TDQuality  as Quality, IFNULL(tdyprod.act_count,0) as ActCount, 
     tdyprod.ProdPerWinder as ProdPerWinder,
     tdyprod.WdgProd as WdgProd, 
     tdyprod.STDPROD as StdProd , 
     tdyprod.diff as Difference,
     tdtprod.diff as MTD_Difference
     from (
     select sdt.q_code ,concat(sm.std_count ,' - ', sm.subgroup_type) as TDQuality , 
     round(sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.winder ),0) as ProdPerWinder ,
     round(sum(sdt.prd_a+sdt.prd_b+sdt.prd_c),0) as WdgProd, 
     round(sum((sdt.hunprod)/(sdt.winder)),0) as STDPROD ,
     round((sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.winder))-(sum(sdt.hunprod)/sum(sdt.winder)),0) as diff
     from EMPMILL12.spining_daily_transaction sdt  
     left join EMPMILL12.spining_master sm  on sm.q_code  = sdt.q_code
     where sdt.tran_date between '{start_date}' and '{selected_date}' group by sdt.q_code ,concat(sm.std_count ,' - ', sm.subgroup_type)) 
     tdtprod left join (     
     select sdt.q_code  , 
     sdt.act_count , 
     round(sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.winder ),0) as ProdPerWinder ,
     round(sum(sdt.prd_a+sdt.prd_b+sdt.prd_c),0) as WdgProd, 
     round(sum(sdt.hunprod/sdt.winder),0) as STDPROD ,
    round((sum(sdt.prd_a+sdt.prd_b+sdt.prd_c)/sum(sdt.winder))-(sum(sdt.hunprod)/sum(sdt.winder)),0) as diff
     from EMPMILL12.spining_daily_transaction sdt  
     left join EMPMILL12.spining_master sm  on sm.q_code  = sdt.q_code
     where sdt.tran_date = '{selected_date}' group by sdt.q_code  , sdt.act_count) tdyprod 
     on tdtprod.q_code = tdyprod.q_code ;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")


def weaving_details(selected_date):
    query = f"""
     select 
     case when QualityType = '1' then 'Hessian'
     when QualityType = '2' then 'Sacking' else 'PackSheet' end 
     as Quality,
     sum(actkgs) as Production, 
     sum(mc_a + mc_b + mc_c ) as McRun,  
     round(sum(actkgs)/sum(mc_a + mc_b + mc_c ),2) as KgPerLoom,
     round((sum(actyds)/sum(actyds_ashots))*100,2) as Eff, 
     case when QualityType ='1' then 200
     when QualityType ='2' then 114 else 4 end as TotalLooms from (
     select 
     substr(wm.q_code,1,1) as QualityType,
     wdt.mc_a, 
     wdt.mc_b, 
     wdt.mc_c, 
     wdt.actkgs, 
     actyds , 
     actyds_ashots 
     from EMPMILL12.weaving_daily_transaction wdt 
     left join 
     EMPMILL12.weaving_master wm on wm.q_code = wdt.q_code
     where wdt.company_id=2 and wdt.tran_date = '{selected_date}') a group by a.QualityType  ;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def get_weaving_shiftwise(selected_date):
    query = f"""
     select 
     case when QualityType = '1' then 'Hessian'
     when QualityType = '2' then 'Sacking' 
     else 'PackSheet' end 
     as Quality, 
     sum(A_prod) as A, 
     sum(B_prod) as B,
     sum(C_prod) as C, 
     round(sum(Total)/1000,3) as Total from (
     select 
     substr(wm.q_code,1,1) as QualityType,
     round(((wdt.yds_a * 28.35* (wm.q_ozs_yds/1000)))/1000,3) as A_prod,
     round(((wdt.yds_b * 28.35* (wm.q_ozs_yds/1000)))/1000,3) as B_prod,
     round(((wdt.yds_c * 28.35* (wm.q_ozs_yds/1000)))/1000,3) as C_prod,
     wdt.actkgs as Total 
     from EMPMILL12.weaving_daily_transaction wdt 
     left join 
     EMPMILL12.weaving_master wm on wm.q_code = wdt.q_code
     where wdt.company_id=2 and wdt.tran_date = '{selected_date}') a group by a.QualityType 
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def get_weaving_total_mtd(selected_date, start_date):
    query = f"""
     select 
     case when QualityType = '1' then 'Hessian'
     when QualityType = '2' then 'Sacking' 
     else 'PackSheet' end 
     as Quality, 
     round(sum(Total)/1000,3) as Total from (
     select 
     substr(wm.q_code,1,1) as QualityType,
     wdt.actkgs as Total 
     from EMPMILL12.weaving_daily_transaction wdt 
     left join 
     EMPMILL12.weaving_master wm on wm.q_code = wdt.q_code
     where wdt.company_id=2 and wdt.tran_date between '{start_date}' and '{selected_date}') a group by a.QualityType 
     ;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def get_hands_details(selected_date):
    query = f"""
SELECT shift,
       CASE 
         WHEN shift = 'A' THEN ROUND(whrs / 8, 2)
         WHEN shift = 'B' THEN ROUND(whrs / 8, 2)
         ELSE ROUND(whrs / 7.5, 2)
       END AS hands
FROM (
    SELECT 
        SUBSTR(spell, 1, 1) AS shift,
        SUM(working_hours - idle_hours) AS whrs
    FROM daily_attendance da
    LEFT JOIN (
        SELECT * FROM tbl_hrms_ed_official_details 
        WHERE is_active = 1
    ) theod ON da.eb_id = theod.eb_id
    WHERE da.company_id = 2 
      AND da.is_active = 1 
      AND da.attendance_date = '{selected_date}'
      AND theod.catagory_id NOT IN (30)
    GROUP BY SUBSTR(spell, 1, 1)
) AS g;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def get_hands_mtd_details(selected_date, start_date):
    query = f"""
SELECT shift,
       CASE 
         WHEN shift = 'A' THEN ROUND(whrs / 8, 2)
         WHEN shift = 'B' THEN ROUND(whrs / 8, 2)
         ELSE ROUND(whrs / 7.5, 2)
       END AS hands
FROM (
    SELECT 
        SUBSTR(spell, 1, 1) AS shift,
        SUM(working_hours - idle_hours) AS whrs
    FROM daily_attendance da
    LEFT JOIN (
        SELECT * FROM tbl_hrms_ed_official_details 
        WHERE is_active = 1
    ) theod ON da.eb_id = theod.eb_id
    WHERE da.company_id = 2 
      AND da.is_active = 1 
      AND da.attendance_date BETWEEN '{start_date}' AND '{selected_date}'
      AND theod.catagory_id NOT IN (30)
    GROUP BY SUBSTR(spell, 1, 1)
) AS g;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")
