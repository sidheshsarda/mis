import pandas as pd
from db import engine

def hess_day_details_eff_day(selected_date):
    query = f"""
         select 
     substr(dld.SPELL,1,1) as Shift, 
     dld.LOOM_NO ,
     wm2.q_ozs_yds ,
     wm2.q_finish_length ,
     wm2.q_width ,
     dld.EBNO , 
     concat(wm2.q_width, " - ", round((wm2.q_ozs_yds),2)) as Quality,
     concat(wm.worker_name,' ',ifnull(wm.middle_name,' '),' ',ifnull(wm.last_name ,'') ) as Name, 
     round(((sum(dld.QUANTITY)/16)*wm2.q_finish_length)*28.35*wm2.q_ozs_yds /1000,2) as ActProd, 
     round(((sum(dld.STDPROD)/16)*wm2.q_finish_length)*28.35*wm2.q_ozs_yds/1000,2) as 100Prod, 
     round(sum((dld.EFFICIENCY/8)*dld.WRK_HOURS),2) as EFF, 
     sum(dld.WRK_HOURS) as Hrs
     from EMPMILL12.DAILY_LOOM_DATA dld 
     left join vowsls.worker_master wm on wm.eb_no = dld.EBNO and wm.company_id =2 and length(wm.eb_no) >2
     left join EMPMILL12.weaving_master wm2 on wm2.q_code = dld.Q_CODE
     where substr(dld.LOOM_NO,1,2) = 41 and dld.TRAN_DATE = '{selected_date}'
     GROUP BY 
          substr(dld.SPELL,1,1), 
     dld.LOOM_NO ,
     wm2.q_ozs_yds ,
     wm2.q_finish_length ,
     wm2.q_width ,
     dld.EBNO , 
     concat(wm.worker_name,' ',ifnull(wm.middle_name,' '),' ',ifnull(wm.last_name ,'') )  
         ;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")

def hess_day_details_eff(selected_date, start_date):
    query = f"""
            select 
     dld.tran_date as Date,
substr(dld.SPELL,1,1) as Shift, 
     dld.LOOM_NO ,
     wm2.q_ozs_yds ,
     wm2.q_finish_length ,
     wm2.q_width ,
     dld.EBNO , 
     concat(wm2.q_width, " - ", round((wm2.q_ozs_yds),2)) as Quality,
     concat(wm.worker_name,' ',ifnull(wm.middle_name,' '),' ',ifnull(wm.last_name ,'') ) as Name, 
     round(((sum(dld.QUANTITY)/16)*wm2.q_finish_length)*28.35*wm2.q_ozs_yds /1000,2) as ActProd, 
     round(((sum(dld.STDPROD)/16)*wm2.q_finish_length)*28.35*wm2.q_ozs_yds/1000,2) as 100Prod, 
     round(sum((dld.EFFICIENCY/8)*dld.WRK_HOURS),2) as EFF, 
     sum(dld.WRK_HOURS) as Hrs
     from EMPMILL12.DAILY_LOOM_DATA dld 
     left join vowsls.worker_master wm on wm.eb_no = dld.EBNO and wm.company_id =2 and length(wm.eb_no) >2
     left join EMPMILL12.weaving_master wm2 on wm2.q_code = dld.Q_CODE
     where substr(dld.LOOM_NO,1,2) = 41 and dld.TRAN_DATE between '{start_date}' and '{selected_date}'
     GROUP BY 
     dld.tran_date,
     substr(dld.SPELL,1,1), 
     dld.LOOM_NO ,
     wm2.q_ozs_yds ,
     wm2.q_finish_length ,
     wm2.q_width ,
     dld.EBNO , 
     concat(wm.worker_name,' ',ifnull(wm.middle_name,' '),' ',ifnull(wm.last_name ,'') ) ;
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df, df.to_json(orient="records")