import pandas as pd
from db import engine

def wdg_details_date(selected_date):
    query = f"""
select tran_date,shift,eb_no,mechine_name,quality,vps.attendance_type, sum(prod) prod,sum(atthrs) atthrs,
        round(sum(prod)/sum(target_prod/8*atthrs)*100,2) eff,
        case when shift<>'C' then sum(atthrs)/8 else sum(atthrs)/7.5 end noofwinders  from EMPMILL12.view_proc_spellwindingdata vps where tran_date between '2025-07-01'
		and '{selected_date}'	
        group by tran_date,shift,eb_no,mechine_name,quality,attendance_type 
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")