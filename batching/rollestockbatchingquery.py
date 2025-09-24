import pandas as pd
from db import engine

def get_batch_data():
    query = """
    SELECT * FROM rollestock
    WHERE status = 'active'
    """
    df = pd.read_sql(query, engine)
    return df

def get_bin_no():
    query = """
    SELECT bn.bin_id, bn.bin_no FROM EMPMILL12.spreader_roll_bin_master bn;
    """
    df = pd.read_sql(query, engine)
    return df['bin_no'].tolist()

def get_jute_quality():
    query = """
    SELECT jq.id, jq.jute_quality
    FROM vowsls.jute_quality_price_master jq
    WHERE jq.company_id = 2 ;
    """
    df = pd.read_sql(query, engine)
    return df

def get_maturity_hours():
    query = """
    select mtm.jute_quality_id , mtm.maturity_hours  from EMPMILL12.maturity_time_master mtm ;
    """
    df = pd.read_sql(query, engine)
    if not df.empty:
        return df
    else:
        return pd.DataFrame({'jute_quality_id': [], 'maturity_hours': []})

def get_required_issue(date):
    query = f"""
    select bph.plan_hdr_id, bph.plan_code, bph.yarn_type_id, ytm.yarn_type  ,
bpd.jute_quality_id, jqpm.jute_quality, bph.percentage
from vowsls.batch_plan_hdr bph 
left join vowsls.batch_plan_dtl bpd on bpd.batch_plan_hdr_id = bph.plan_hdr_id and bpd.is_active=1
left join vowsls.jute_quality_price_master jqpm on jqpm.id = bpd.jute_quality_id
left join vowsls.yarn_type_master ytm on ytm.yarn_type_id = bph.yarn_type_id 
where bph.company_id =2 and bph.is_active=1 and bph.plan_code in (select bpdi.batch_plan_code
from vowsls.batch_plan_daily_implement bpdi 
left join vowsls.yarn_type_master ytm on ytm.yarn_type_id = bpdi.yarn_type_id and ytm.company_id =2
where bpdi.is_active = 1  and bpdi.company_id =2 and bpdi.plan_date = '{date}'
);
    """
    df = pd.read_sql(query, engine)
    return df

def get_spreader_machine_no():
    query = """select mm.mechine_id,mm.mech_code, mm.mechine_name , mm.bobbin_weight 
from vowsls.mechine_master mm where mm.company_id =2 and mm.type_of_mechine = 8 and substr(mm.mechine_name,1,1)='S';"""
    df = pd.read_sql(query, engine)
    return df

def get_recent_jute_quality_ids_90d() -> list[int]:
    """
    Returns distinct jute quality IDs (smli.actual_quality) received in the last 90 days
    for company_id = 2 based on scm_mr tables. This is used to restrict selectable
    jute qualities in Tab 1 without altering the base get_jute_quality() query.
    """
    query = """
    SELECT DISTINCT smli.actual_quality AS id
    FROM vowsls.scm_mr_line_item smli 
    LEFT JOIN vowsls.scm_mr_hdr smh ON smh.jute_receive_no = smli.jute_receive_no 
    LEFT JOIN vowsls.jute_quality_price_master jqpm ON jqpm.id = smli.actual_quality AND jqpm.company_id = smh.company_id 
    WHERE smh.company_id = 2 
      AND SUBSTR(smli.auto_datetime_insert,1,10) >= DATE_ADD(CURRENT_DATE(), INTERVAL -90 DAY)
    ;
    """
    df = pd.read_sql(query, engine)
    if 'id' in df.columns and not df.empty:
        try:
            return df['id'].dropna().astype(int).unique().tolist()
        except Exception:
            return [int(x) for x in df['id'].dropna().unique().tolist()]
    return []

def get_roll_stock_time(start_dt_str: str, end_dt_str: str) -> pd.DataFrame:
    """
    Returns roll stock summary between the fixed start window and selected end window.
    start_dt_str and end_dt_str must be in '%Y-%m-%d %H' format.
    """
    import pandas as _pd
    from sqlalchemy import text as _text
    # Previous query retained for reference (commented out):
    # query = _text("""
    #   ... previous open/prod/issue/close stock windowed SQL ...
    # """)

    # New query: closing stock (rolls and weight) up to a cutoff datetime
    query = _text(
        """
        WITH combined AS (
            -- Entries (production)
            SELECT 
                spe.entry_id_grp,
                spe.bin_no,
                spe.jute_quality_id,
                spe.wt_per_roll,
                SUM(spe.no_of_rolls) AS rolls,
                SUM(spe.no_of_rolls * spe.wt_per_roll) AS weight
            FROM EMPMILL12.spreader_prod_entry spe
            WHERE STR_TO_DATE(CONCAT(spe.entry_date, ' ', spe.entry_time), '%Y-%m-%d %H') 
                  <= STR_TO_DATE(:cutoff_dt, '%Y-%m-%d %H')
            GROUP BY spe.entry_id_grp, spe.bin_no, spe.jute_quality_id, spe.wt_per_roll
            UNION ALL
            -- Issues (negative)
            SELECT 
                sri.entry_id_grp,
                sri.breaker_inter_no AS bin_no,
                NULL AS jute_quality_id,  -- quality comes via entry_id_grp
                sri.wt_per_roll,
                -SUM(sri.no_of_rolls) AS rolls,
                -SUM(sri.no_of_rolls * sri.wt_per_roll) AS weight
            FROM EMPMILL12.spreader_roll_issue sri
            WHERE STR_TO_DATE(CONCAT(sri.issue_date, ' ', sri.issue_time), '%Y-%m-%d %H') 
                  <= STR_TO_DATE(:cutoff_dt, '%Y-%m-%d %H')
            GROUP BY sri.entry_id_grp, sri.breaker_inter_no, sri.wt_per_roll
        )
        SELECT 
            entry_id_grp,
            bin_no,
            MAX(jute_quality_id) AS jute_quality_id,  -- from entries
            wt_per_roll,
            SUM(rolls) AS closing_rolls,
            SUM(weight) AS closing_weight
        FROM combined
        GROUP BY entry_id_grp, bin_no, wt_per_roll
        ORDER BY entry_id_grp, bin_no, wt_per_roll
        """
    )
    with engine.connect() as conn:
        df = _pd.read_sql(query, conn, params={"cutoff_dt": end_dt_str})
    return df
