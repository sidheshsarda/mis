import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import text
from db import engine
from batching.rollestockbatchingquery import (
	get_jute_quality,
	get_maturity_hours,
	get_spreader_machine_no,
)

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
	st.markdown("### Spreader Production (Shift & Quality Summary)")
	st.caption("Shift logic: A1 06-11, B1 11-14, A2 14-17, B2 17-22, C 22:00 to next day 06:00.")
	report_date = st.date_input("Production Date", datetime.date.today(), key="prod_report_date")

	# Load reference data
	jq_df = get_jute_quality()
	jq_map = dict(zip(jq_df['id'], jq_df['jute_quality'])) if not jq_df.empty else {}
	spreader_df = get_spreader_machine_no()
	if isinstance(spreader_df, pd.DataFrame) and not spreader_df.empty:
		spreader_df = spreader_df.fillna("")
		spreader_df['display'] = spreader_df['mechine_name'].astype(str) + " (" + spreader_df['mech_code'].astype(str) + ")"
		spreader_display_map = dict(zip(spreader_df['mechine_id'], spreader_df['display']))
	else:
		spreader_display_map = {}

	# Query production rows covering required window (report_date 06:00 .. 21:59 plus 22:00..23:59 and next day 00:00..05:59 for C)
	from sqlalchemy import text as _t2text
	from db import engine as _t2engine
	q = _t2text(
		"""
		SELECT entry_date, entry_time, spreader_no, jute_quality_id, no_of_rolls, wt_per_roll
		FROM EMPMILL12.spreader_prod_entry
		WHERE (entry_date = :d OR entry_date = DATE_ADD(:d, INTERVAL 1 DAY))
		  AND (
				(entry_date = :d)  -- whole selected day
				OR (entry_date = DATE_ADD(:d, INTERVAL 1 DAY) AND entry_time < 6) -- next-day early hours for C shift
			  )
		ORDER BY entry_date, entry_time
		"""
	)
	try:
		with _t2engine.connect() as conn:
			raw_df = pd.read_sql(q, conn, params={"d": report_date})
	except Exception as e:
		st.error(f"Error loading production data: {e}")
		raw_df = pd.DataFrame()

	if raw_df.empty:
		st.info("No production entries found for the selected date / window.")
		st.stop()

	# Compute shift bucket based on time and date relative to report_date
	def map_shift(row):
		d = row['entry_date']
		h = int(row['entry_time']) if pd.notna(row['entry_time']) else -1
		if d == report_date:
			if 6 <= h < 11:
				return 'A1'
			elif 11 <= h < 14:
				return 'B1'
			elif 14 <= h < 17:
				return 'A2'
			elif 17 <= h < 22:
				return 'B2'
			elif h >= 22:
				return 'C'
			else:
				return None  # early hours belong to previous day's C
		elif d == (report_date + datetime.timedelta(days=1)):
			if h < 6:
				return 'C'
		return None

	raw_df['Shift'] = raw_df.apply(map_shift, axis=1)
	raw_df = raw_df[raw_df['Shift'].notna()].copy()
	if raw_df.empty:
		st.info("No rows fall into defined shifts for this date.")
		st.stop()

	# Enhance with display fields
	raw_df['Spreader'] = raw_df['spreader_no'].map(spreader_display_map).fillna(raw_df['spreader_no'].astype(str))
	raw_df['Quality'] = raw_df['jute_quality_id'].map(jq_map).fillna(raw_df['jute_quality_id'].astype(str))
	raw_df['Weight (kg)'] = (raw_df['no_of_rolls'] * raw_df['wt_per_roll'].fillna(0)).round(2)

	# Filters (multi-selects)
	all_spreaders = sorted(raw_df['Spreader'].unique().tolist())
	all_shifts = ['A1','A2','B1','B2','C']
	all_qualities = sorted(raw_df['Quality'].unique().tolist())
	fc1, fc2, fc3, fc4 = st.columns([1,1,1,2])
	with fc1:
		sel_spreaders = st.multiselect("Spreader(s)", all_spreaders, default=all_spreaders, key="spr_filter")
	with fc2:
		sel_shifts = st.multiselect("Shift(s)", all_shifts, default=all_shifts, key="shift_filter")
	with fc3:
		sel_qualities = st.multiselect("Quality(s)", all_qualities, default=all_qualities, key="qual_filter")
	with fc4:
		show_weight = st.checkbox("Show Weight Columns", value=False, key="show_weight_cols")

	fdf = raw_df[raw_df['Spreader'].isin(sel_spreaders) & raw_df['Shift'].isin(sel_shifts) & raw_df['Quality'].isin(sel_qualities)].copy()
	if fdf.empty:
		st.warning("Filters removed all data.")
		st.stop()

	# Helper to pivot shift metrics per entity (Spreader or Quality)
	def build_shift_table(df: pd.DataFrame, entity_col: str, value_label: str):
		base = df.groupby([entity_col, 'Shift'], dropna=False)['no_of_rolls'].sum().reset_index()
		pivot = base.pivot(index=entity_col, columns='Shift', values='no_of_rolls').fillna(0).astype(int)
		# Ensure all shift columns present
		for s in all_shifts:
			if s not in pivot.columns:
				pivot[s] = 0
		# Ordered columns
		pivot = pivot[['A1','A2','B1','B2','C']]
		pivot['A'] = pivot['A1'] + pivot['A2']
		pivot['B'] = pivot['B1'] + pivot['B2']
		pivot['Total'] = pivot[['A1','A2','B1','B2','C']].sum(axis=1)
		pivot = pivot.reset_index()
		pivot.insert(0, 'Index', range(1, len(pivot)+1))
		totals = {col: '' for col in pivot.columns}
		totals['Index'] = ''
		totals[entity_col] = 'Total'
		for c in ['A1','A2','A','B1','B2','B','C','Total']:
			totals[c] = pivot[c].sum()
		pivot = pd.concat([pivot, pd.DataFrame([totals])], ignore_index=True)
		# Optional weight columns
		if show_weight:
			wbase = df.groupby([entity_col, 'Shift'], dropna=False)['Weight (kg)'].sum().reset_index()
			wpivot = wbase.pivot(index=entity_col, columns='Shift', values='Weight (kg)').fillna(0).round(2)
			for s in all_shifts:
				if s not in wpivot.columns:
					wpivot[s] = 0.0
			wpivot = wpivot[['A1','A2','B1','B2','C']]
			wpivot['A'] = wpivot['A1'] + wpivot['A2']
			wpivot['B'] = wpivot['B1'] + wpivot['B2']
			wpivot['Total Wt (kg)'] = wpivot[['A1','A2','B1','B2','C']].sum(axis=1)
			wpivot = wpivot.reset_index()
			# Merge into pivot (rolls) table aligning order
			pivot = pivot.merge(wpivot[[entity_col,'A1','A2','A','B1','B2','B','C','Total Wt (kg)']], on=entity_col, how='left')
			# Add totals for weight
			if 'Total Wt (kg)' in pivot.columns:
				pivot.loc[pivot[pivot[entity_col]=='Total'].index, 'Total Wt (kg)'] = round(pivot[pivot[entity_col]!='Total']['Total Wt (kg)'].sum(),2)
		return pivot

	st.markdown("#### Spreader-wise Production (Rolls)")
	spreader_table = build_shift_table(fdf, 'Spreader', 'Rolls')
	st.dataframe(spreader_table, use_container_width=True, hide_index=True)

	st.markdown("#### Quality-wise Production (Rolls)")
	quality_table = build_shift_table(fdf, 'Quality', 'Rolls')
	st.dataframe(quality_table, use_container_width=True, hide_index=True)

	# Overall KPIs
	total_rolls = int(fdf['no_of_rolls'].sum())
	total_weight = round(fdf['Weight (kg)'].sum(), 2)
	k1,k2 = st.columns(2)
	k1.metric("Total Rolls (Filtered)", f"{total_rolls}")
	if show_weight:
		k2.metric("Total Weight (kg) (Filtered)", f"{total_weight:.2f}")
	else:
		k2.metric("Unique Spreaders", f"{fdf['Spreader'].nunique()}")

