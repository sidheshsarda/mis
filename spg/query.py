import pandas as pd
from db import engine

def spg_details_date(selected_date, start_date):
	query = f"""
select doffdate,substr(spell,1,1) shift,attendance_type,ifnull(ebno,"Contract") as ebno,frameno,q_code,quality,
	sum(netwt) netwt,
	sum(whrs) whrs,  sum(stdprod) stdprod,
	sum(noofframe) noofframe,round(sum(netwt)/sum(stdprod)*100,2)  eff from
	(
	select prd.*,concat(sm.std_count,' - Lbs ',sm.subgroup_type) quality,   dea.mc_id,
	case when (prd.spell='C' and ebno is null) then ifnull((da.working_hours),7.5)
	when (prd.spell='A1' and ebno is null) then ifnull((da.working_hours),5)
	when (prd.spell='A2' and ebno is null) then ifnull((da.working_hours),3)
	when (prd.spell='B1' and ebno is null) then ifnull((da.working_hours),3)
	when (prd.spell='B2' and ebno is null) then ifnull((da.working_hours),5) else (da.working_hours-da.idle_hours) end
    whrs,sdt.act_count,sdt.speed,sm.spindle,sdt.twist_per_inch,
	case when (prd.spell='C' and ebno is null) then round((sdt.speed*(7.5)*60*sdt.act_count*spindle)/(sdt.twist_per_inch*14400*2.2046*36),2)
	when (prd.spell='A1' and ebno is null) then round((sdt.speed*(5)*60*sdt.act_count*spindle)/(sdt.twist_per_inch*14400*2.2046*36),2)
	when (prd.spell='A2' and ebno is null) then round((sdt.speed*(3)*60*sdt.act_count*spindle)/(sdt.twist_per_inch*14400*2.2046*36),2)
	when (prd.spell='B1' and ebno is null) then round((sdt.speed*(3)*60*sdt.act_count*spindle)/(sdt.twist_per_inch*14400*2.2046*36),2)
	when (prd.spell='B2' and ebno is null) then round((sdt.speed*(5)*60*sdt.act_count*spindle)/(sdt.twist_per_inch*14400*2.2046*36),2)
	else
    round((sdt.speed*(da.working_hours-da.idle_hours)*60*sdt.act_count*spindle)/(sdt.twist_per_inch*14400*2.2046*36),2) end stdprod,
    case when (prd.spell='C' and ebno is null) then 1
    when (prd.spell='A1' and ebno is null) then .625
    when (prd.spell='A2' and ebno is null) then .375
    when (prd.spell='B2' and ebno is null) then .625
    when (prd.spell='B1' and ebno is null) then .375
    when (prd.spell<>'C' and ebno is not null) then (da.working_hours-da.idle_hours)/8
    else (da.working_hours-da.idle_hours)/7.5 end noofframe,da.attendance_type
	from (
	select dft.company_id,doffdate,dft.spell,ebno,frameno,q_code,mechine_id,round(sum(netwt),2) netwt from dofftable dft
	left join mechine_master mm on mm.company_id =dft.company_id and mm.mach_shr_code =dft.frameno
	where doffdate between '{start_date}'and '{selected_date}' and dft.company_id=2 and mm.type_of_mechine=36
	group by dft.company_id,doffdate,dft.spell,ebno,frameno,q_code,mechine_id  
	) prd
	left join daily_ebmc_attendance dea on dea.company_id =prd.company_id and prd.spell=dea.spell
	and dea.attendace_date =prd.doffdate and dea.mc_id =prd.mechine_id and dea.is_active =1
	left join daily_attendance da on da.daily_atten_id =dea.daily_atten_id and da.is_active =1
	left join EMPMILL12.spining_daily_transaction sdt on sdt.company_id=prd.company_id and sdt.q_code =prd.q_code
	and sdt.tran_date=prd.doffdate
	left join EMPMILL12.spining_master sm on sdt.company_id=sm.company_id and sdt.q_code =sm.q_code
	where  (da.worked_designation_id in (213,50,55,241,252,195,242) or prd.ebno is null)
	) g where g.spell = 'C'
	group by doffdate,substr(spell,1,1),ebno,frameno,q_code,quality,attendance_type
	order by frameno ,substr(spell,1,1)
	"""
	with engine.connect() as conn:
		df = pd.read_sql(query, conn)
	# Format doffdate as YYYY-MM-DD if present
	if 'doffdate' in df.columns:
		df['doffdate'] = pd.to_datetime(df['doffdate']).dt.strftime('%Y-%m-%d')
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