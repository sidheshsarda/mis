import pandas as pd
from db import engine

def get_dofftable_data(selected_date):
    query = f"""
        select frameno, q_code, quality_name, spell, netwt
        from dofftable d
        left join weaving_quality_master wqm on wqm.quality_code = d.q_code and d.company_id = wqm.company_id
        where d.doffdate = '{selected_date}'
          and d.company_id = 2
          and d.is_active = 1
        order by doffdate, auto_id desc
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def get_dofftable_sum_by_date(start_date, end_date):
    query = f"""
        SELECT 
            doffdate, 
            ROUND(SUM(netwt), 0) as total_netwt 
        FROM 
            dofftable d 
        WHERE 
            doffdate BETWEEN '{start_date}' AND '{end_date}' 
            AND company_id = 2 
            AND is_active = 1 
        GROUP BY 
            doffdate  
        ORDER BY 
            doffdate DESC;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def get_dofftable_withname(selected_date3):
    query = f""" select d.frameno, d.spell ,  CONCAT(d.q_code, "-",wqm.quality_name) as quality , d.ebno ,concat(wm.worker_name," ",wm.last_name) as name, d.netwt  from dofftable d 
left join weaving_quality_master wqm on wqm.quality_code = d.q_code and d.company_id = wqm.company_id
left join worker_master wm on wm.eb_no = d.ebno and wm.company_id = d.company_id
where d.company_id =2 and d.doffdate = '{selected_date3}' and d.is_active = 1;
    """
    with engine.connect() as conn:
        abc = pd.read_sql(query, conn)
    return abc, abc.to_json(orient="records")

def get_doff_details(selected_date3):
    query = f""" select 
d.spell ,
d.frameno,  
CONCAT(d.q_code, "-", wqm.quality_name) as quality , 
round((sum(d.netwt)),0) as netwt,
count(*) as num_of_doff,
round(((sum(d.netwt))/(count(*))),2) as averagewt
max(d.netwt) as maxwt,
min(d.netwt) as minwt
from dofftable d 
left join weaving_quality_master wqm on wqm.quality_code = d.q_code and d.company_id = wqm.company_id
where d.company_id =2 and d.doffdate = '{selected_date3}' and d.is_active = 1
group by  d.spell ,d.frameno, CONCAT(d.q_code, "-",wqm.quality_name) order by spell, cast(frameno as unsigned);
    """
    with engine.connect() as conn:
        abc = pd.read_sql(query, conn)
    return abc, abc.to_json(orient="records")

def get_dofftable_details(start_date, end_date):
    query = f"""
        SELECT 
            doffdate, 
            substr(spell,1,1) as shift,
            frameno ,
            q_code ,
            ebno ,
            ROUND(SUM(netwt), 0) as total_netwt 
        FROM 
            dofftable d 
        WHERE 
            doffdate BETWEEN '{start_date}' AND '{end_date}' 
            AND company_id = 2 
            AND is_active = 1 
        GROUP BY 
                        doffdate, 
            substr(spell,1,1),
            frameno ,
            q_code ,
            ebno
        ORDER BY 
            doffdate, 
            substr(spell,1,1),
            frameno ,
            q_code DESC;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def get_dofftable_details_lastdoff(selected_date3):
    query = f"""
SELECT 
  d.spell,
  d.frameno,
  CONCAT(d.q_code, "-", wqm.quality_name) AS quality, 
  ROUND(SUM(d.netwt), 0) AS netwt,
  COUNT(*) AS num_of_doff,
  ROUND(SUM(d.netwt) / COUNT(*), 2) AS averagewt,
  MAX(d.netwt) AS maxwt,
  MIN(d.netwt) AS minwt,
  latest_doffs.netwt AS l_dwt
FROM dofftable d
LEFT JOIN weaving_quality_master wqm 
  ON wqm.quality_code = d.q_code AND d.company_id = wqm.company_id
LEFT JOIN (
    SELECT dt.spell, dt.frameno, dt.doffdate, MAX(dt.auto_id) AS latest_doffid
    FROM dofftable dt
    WHERE dt.company_id = 2 AND dt.doffdate = '{selected_date3}' AND dt.is_active = 1
    GROUP BY dt.spell, dt.frameno, dt.doffdate
) latest_ids ON latest_ids.spell = d.spell 
             AND latest_ids.frameno = d.frameno 
             AND latest_ids.doffdate = d.doffdate
LEFT JOIN dofftable latest_doffs ON latest_doffs.auto_id = latest_ids.latest_doffid
WHERE d.company_id = 2 AND d.doffdate = '{selected_date3}' AND d.is_active = 1
GROUP BY d.spell, d.frameno, CONCAT(d.q_code, "-", wqm.quality_name), latest_doffs.netwt
ORDER BY d.spell, CAST(d.frameno AS UNSIGNED);
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

