import pandas as pd
from db import engine

def wdg_details_date(selected_date, start_date):
	query = f"""
select tran_date,shift,eb_no,mechine_name,quality,vps.attendance_type, sum(prod) prod,sum(atthrs) atthrs,
		round(sum(prod)/sum(target_prod/8*atthrs)*100,2) eff,
		case when shift<>'C' then sum(atthrs)/8 else sum(atthrs)/7.5 end noofwinders  
		from EMPMILL12.view_proc_spellwindingdata vps where tran_date 
		between '{start_date}' and '{selected_date}'	
		group by tran_date,shift,eb_no,mechine_name,quality,attendance_type 
	"""
	with engine.connect() as conn:
		df = pd.read_sql(query, conn)
		if 'tran_date' in df.columns:
			df['tran_date'] = pd.to_datetime(df['tran_date']).dt.strftime('%Y-%m-%d')
	return df, df.to_json(orient="records")

def get_name (ebno):
	query = f"""
		select wm.eb_no as EBNO, concat(wm.worker_name,' ',ifnull(wm.middle_name,' '),' ',ifnull(wm.last_name ,'') ) 
	as Name from vowsls.worker_master wm  where wm.eb_no = '{ebno}' and wm.company_id = 2;
	"""
	with engine.connect() as conn:
		df = pd.read_sql(query, conn)
	if not df.empty:
		return df.iloc[0]['Name']
	else:
		return "Unknown"