import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import text
from db import engine
from batching.rollestockbatchingquery import get_jute_quality, get_maturity_hours

st.set_page_config(page_title="Roll Stock Reports", page_icon="📊", layout="wide")
st.title("Roll Stock Reports")

tab1, tab2 = st.tabs(["Maturity Time Report", "Spreader Production"])

with tab1:
	st.markdown("### Maturity Time Report (Per Production Entry)")
	report_date = st.date_input("Issue Date", datetime.date.today(), key="maturity_issue_date")
	jq_df = get_jute_quality()
	jq_map = dict(zip(jq_df['id'], jq_df['jute_quality']))
	maturity_df = get_maturity_hours()
	maturity_map = dict(zip(maturity_df['jute_quality_id'], maturity_df['maturity_hours'])) if not maturity_df.empty else {}

	# Query each issue joined to ALL production entries of that group & weight (no aggregation)
	sql = text(
		"""
		SELECT 
			i.entry_id_grp,
			i.issue_date,
			i.issue_time,
			i.spell AS issue_spell,
			i.no_of_rolls AS issue_rolls,
			i.wt_per_roll,
			p.bin_no,
			p.jute_quality_id,
			p.entry_date AS prod_entry_date,
			p.entry_time AS prod_entry_time,
			p.no_of_rolls AS prod_rolls
		FROM EMPMILL12.spreader_roll_issue i
		LEFT JOIN EMPMILL12.spreader_prod_entry p
			ON p.entry_id_grp = i.entry_id_grp AND p.wt_per_roll = i.wt_per_roll
		WHERE i.issue_date = :d
		ORDER BY i.issue_time, i.entry_id_grp, p.entry_date, p.entry_time
		"""
	)
	try:
		with engine.connect() as conn:
			df = pd.read_sql(sql, conn, params={"d": report_date})
		if df.empty:
			st.info("No issues recorded for the selected date.")
		else:
			# Compute per production-entry maturity relative to issue
			issue_dt = pd.to_datetime(df['issue_date']) + pd.to_timedelta(df['issue_time'], unit='h')
			prod_dt = pd.to_datetime(df['prod_entry_date']) + pd.to_timedelta(df['prod_entry_time'], unit='h')
			# Round maturity to whole hours as requested
			df['Maturity (hrs)'] = ((issue_dt - prod_dt).dt.total_seconds() / 3600).round(0).astype(int)
			df['Target Maturity (hrs)'] = df['jute_quality_id'].map(maturity_map).fillna(48).astype(int)
			df['Quality'] = df['jute_quality_id'].map(jq_map)
			df['Issued Weight (kg)'] = (df['issue_rolls'] * df['wt_per_roll'].fillna(0)).round(2)
			df['Issued Weight (MT)'] = (df['Issued Weight (kg)'] / 1000).round(2)
			# Build display with production entry details
			display_cols = [
				'issue_time','issue_spell','entry_id_grp','bin_no','Quality','wt_per_roll','issue_rolls',
				'prod_entry_date','prod_entry_time','prod_rolls','Maturity (hrs)','Target Maturity (hrs)'
			]
			show_df = df[display_cols].rename(columns={
				'issue_time':'Issue Hour',
				'issue_spell':'Issue Spell',
				'entry_id_grp':'Group',
				'bin_no':'Bin',
				'wt_per_roll':'Wt/Roll (kg)',
				'issue_rolls':'Issue Rolls',
				'prod_entry_date':'Prod Date',
				'prod_entry_time':'Prod Hour',
				'prod_rolls':'Prod Rolls'
			}).copy()
			# Index
			show_df.insert(0,'Index', range(1, len(show_df)+1))
			# Summary (issue totals) - compute once per issue event (Group+Issue Hour+Wt/Roll maybe) but for simplicity total all displayed
			totals = {
				'Index':'', 'Issue Hour':'', 'Issue Spell':'', 'Group':'', 'Bin':'', 'Quality':'Total',
				'Wt/Roll (kg)':None, 'Issue Rolls': int(show_df['Issue Rolls'].unique().sum()) if len(show_df)>0 else 0,
				'Prod Date':'', 'Prod Hour':'', 'Prod Rolls': '', 'Maturity (hrs)':'', 'Target Maturity (hrs)':''
			}
			show_df = pd.concat([show_df, pd.DataFrame([totals])], ignore_index=True)

			def highlight(row):
				if row.get('Quality') == 'Total':
					return [''] * len(row)
				try:
					m = float(row['Maturity (hrs)']) if row['Maturity (hrs)'] != '' else None
					t = float(row['Target Maturity (hrs)']) if row['Target Maturity (hrs)'] != '' else None
				except Exception:
					m, t = None, None
				styles = [''] * len(row)
				if m is not None and t is not None:
					if abs(m - t) <= 2:
						color = '#d4edda'
					elif m < t - 2:
						color = '#fff3cd'
					else:
						color = '#f8d7da'
					try:
						idx = list(row.index).index('Maturity (hrs)')
						styles[idx] = f'background-color: {color}'
					except ValueError:
						pass
				return styles

			styled = show_df.style.apply(highlight, axis=1)
			try:
				styled = styled.hide(axis='index')
			except Exception:
				pass
			st.dataframe(styled, use_container_width=True, hide_index=True)
	except Exception as e:
		st.error(f"Error loading maturity time report: {e}")

with tab2:
	st.markdown("### Spreader Production (Report Placeholder)")
	st.info("This report will be implemented in a future update.")

