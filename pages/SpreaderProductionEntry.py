import datetime
import streamlit as st
import pandas as pd
from batching.spreaderprodentry import (
    insert_spreader_prod_entry,
    fetch_bins_with_stock,
)
from batching.rollestockbatchingquery import get_bin_no, get_jute_quality, get_maturity_hours, get_spreader_machine_no

st.set_page_config(page_title="Spreader Production Entry", page_icon="🧵", layout="wide")


st.title("Spreader Production Entry")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Production Entry", "Roll Stock", "Issue Roll", "Roll Stock Time", "Spreader Production"])

# --- Load dropdown options ---
bin_options = get_bin_no()
jq_df = get_jute_quality()
jq_options = jq_df['jute_quality'].tolist()
# Use 'id' instead of 'jute_quality_id'
jq_id_map = dict(zip(jq_df['jute_quality'], jq_df['id']))

# Spreader machine options: display name (code), use id for DB
spreader_df = get_spreader_machine_no()
if isinstance(spreader_df, pd.DataFrame) and not spreader_df.empty:
    spreader_df = spreader_df.fillna("")
    spreader_df['display'] = spreader_df['mechine_name'].astype(str) + " (" + spreader_df['mech_code'].astype(str) + ")"
    spreader_display_options = spreader_df['display'].tolist()
    spreader_id_map = dict(zip(spreader_df['display'], spreader_df['mechine_id']))
    spreader_bobbin_weight_map = dict(zip(spreader_df['display'], spreader_df.get('bobbin_weight', pd.Series([None]*len(spreader_df)))))
    # Reverse map for id -> display (used in daily summary table)
    spreader_display_by_id = dict(zip(spreader_df['mechine_id'], spreader_df['display']))
    # Also keep a string-keyed version to handle stored IDs saved as text
    spreader_display_by_id_str = {str(k): v for k, v in spreader_display_by_id.items()}
    # Provide a reusable mapper function
    def map_spreader_id_to_display(val):
        try:
            if val in spreader_display_by_id:
                return spreader_display_by_id[val]
            sval = str(val)
            if sval in spreader_display_by_id_str:
                return spreader_display_by_id_str[sval]
            if isinstance(val, str) and val.isdigit():
                ival = int(val)
                return spreader_display_by_id.get(ival, sval)
            return sval
        except Exception:
            return str(val)
else:
    spreader_display_options = []
    spreader_id_map = {}
    spreader_bobbin_weight_map = {}
    spreader_display_by_id = {}
    spreader_display_by_id_str = {}
    def map_spreader_id_to_display(val):
        return str(val)





with tab1:
    col1, col2, col3 = st.columns(3)
    now = datetime.datetime.now()
    now_hour = int(now.replace(minute=0, second=0, microsecond=0).hour)
    with col1:
        entry_date = st.date_input("Entry Date", datetime.date.today(), key="spe_entry_date")
        entry_time = st.number_input("Entry Time (hour, 0-23)", min_value=0, max_value=23, step=1, value=now_hour, key="spe_entry_time")
        def get_default_spell(_h):
            if 6 <= _h < 11:
                return "A1"
            elif 11 <= _h < 14:
                return "B1"
            elif 14 <= _h < 17:
                return "A2"
            elif 17 <= _h < 22:
                return "B2"
            else:
                return "C"
        default_spell = get_default_spell(int(entry_time))
        spell_options = ["A1", "A2", "B1", "B2", "C"]
        spell_index = spell_options.index(default_spell) if default_spell in spell_options else 0
        spell = st.selectbox("Spell", spell_options, index=spell_index, key="spe_spell")
    with col2:
        trolley_no = st.number_input("Trolley No", min_value=0, step=1, key="spe_trolley_no")
        if spreader_display_options:
            spreader_choice = st.selectbox("Spreader No", spreader_display_options, key="spe_spreader_no")
            spreader_no = spreader_id_map.get(spreader_choice)
            wt_per_roll = spreader_bobbin_weight_map.get(spreader_choice)
            # Coerce to float and make it read-only in the UI
            try:
                import math
                if wt_per_roll is None or (isinstance(wt_per_roll, float) and math.isnan(wt_per_roll)):
                    wt_per_roll = 0.0
            except Exception:
                wt_per_roll = 0.0
            # Display as read-only
            st.text_input("Wt per Roll (kg)", value=f"{float(wt_per_roll):.2f}", disabled=True, key="spe_wt_per_roll_display")
        else:
            st.warning("No spreader machines found.")
            spreader_no = None
            wt_per_roll = 0.0
            st.text_input("Wt per Roll (kg)", value=f"{wt_per_roll:.2f}", disabled=True, key="spe_wt_per_roll_display")
        st.text_input("EB No.", value="", disabled=True, key="spe_ebno")
    with col3:
        from batching.spreader_rules import evaluate_4hr_window
        from sqlalchemy import text
        from db import engine
        bin_no = st.selectbox("Bin No", bin_options, key="spe_bin_no")
        last_quality = None
        lock_quality = False
        block_entry = False
        with engine.connect() as conn:
            active_grp_sql = text(
                """
                SELECT z.entry_id_grp, z.jute_quality_id
                FROM (
                    SELECT p.entry_id_grp,
                           CAST(SUBSTRING_INDEX(MIN(CONCAT(p.entry_date,' ',LPAD(p.entry_time,2,'0'),':00:00','|',LPAD(p.jute_quality_id,6,'0'))),'|',-1) AS UNSIGNED) AS jute_quality_id
                    FROM EMPMILL12.spreader_prod_entry p
                    WHERE p.bin_no = :bin_no
                    GROUP BY p.entry_id_grp
                ) z
                JOIN (
                    SELECT p.entry_id_grp,
                           SUM(p.no_of_rolls) AS total_rolls,
                           COALESCE((SELECT SUM(i.no_of_rolls) FROM EMPMILL12.spreader_roll_issue i WHERE i.entry_id_grp = p.entry_id_grp),0) AS total_issued
                    FROM EMPMILL12.spreader_prod_entry p
                    WHERE p.bin_no = :bin_no
                    GROUP BY p.entry_id_grp
                ) s ON z.entry_id_grp = s.entry_id_grp
                WHERE (s.total_rolls - s.total_issued) > 0
                ORDER BY z.entry_id_grp DESC
                LIMIT 1
                """
            )
            r = conn.execute(active_grp_sql, {"bin_no": bin_no}).fetchone()
            if r:
                active_grp, last_quality = int(r[0]), int(r[1])
                lock_quality = True
                win = evaluate_4hr_window(active_grp, entry_date, int(entry_time))
                if win:
                    if not win.allowed:
                        block_entry = True
                        st.error(
                            f"Group {active_grp}: Base {win.base_dt:%Y-%m-%d %H}:00 → allowed until {win.allowed_end_dt:%Y-%m-%d %H}:00. "
                            f"Candidate {win.candidate_dt:%Y-%m-%d %H}:00 outside 4-hour window."
                        )
                    else:
                        if win.candidate_dt == win.base_dt:
                            st.caption(
                                f"Group {active_grp} window starts {win.base_dt:%Y-%m-%d %H}:00; entries allowed through {win.allowed_end_dt:%Y-%m-%d %H}:00 (inclusive)."
                            )
                        else:
                            st.caption(
                                f"Group {active_grp}: Base {win.base_dt:%Y-%m-%d %H}:00 → allowed until {win.allowed_end_dt:%Y-%m-%d %H}:00. "
                                f"Current entry {win.candidate_dt:%Y-%m-%d %H}:00 is within window."
                            )
                # Debug (optional): uncomment to display window info
                # st.caption(f"Same-day first hour: {sd_row[0] if sd_row and sd_row[0] is not None else 'N/A'} | Candidate hour: {entry_time} | Diff: {hours_diff if sd_row and sd_row[0] is not None else 0:.2f} hrs")
        if last_quality is not None and last_quality in jq_df['id'].values:
            default_quality = jq_df[jq_df['id'] == last_quality]['jute_quality'].values[0]
        else:
            default_quality = jq_options[0]
        quality_index = jq_options.index(default_quality) if default_quality in jq_options else 0
        if lock_quality and last_quality is not None:
            st.text_input("Jute Quality (locked)", value=default_quality, disabled=True, key="spe_quality_display")
            jute_quality_id = last_quality
        else:
            jute_quality_display = st.selectbox("Jute Quality", jq_options, key="spe_quality_display", index=quality_index)
            jute_quality_id = jq_id_map.get(jute_quality_display, 0)
        no_of_rolls = st.number_input("No. of Rolls", min_value=0, step=1, value=24, key="spe_no_of_rolls")
    submit_clicked = st.button("Save Entry")
    if submit_clicked:
        errors = []
        if block_entry:
            errors.append("Cannot add to this group after 4 hours from the first entry. Please start a new group when stock is zero.")
        if spreader_no is None or spreader_no == "":
            errors.append("Spreader No must be selected.")
        if jute_quality_id <= 0:
            errors.append("Jute Quality must be selected.")
        if no_of_rolls <= 0:
            errors.append("No. of Rolls must be > 0.")
        if entry_time < 0:
            errors.append("Entry Time cannot be negative.")
        if bin_no is None or bin_no == "":
            errors.append("Bin No must be selected.")
        if errors:
            for e in errors:
                st.error(e)
        else:
            try:
                rid = insert_spreader_prod_entry(
                    entry_date=entry_date,
                    spell=spell,
                    spreader_no=str(spreader_no),
                    jute_quality_id=int(jute_quality_id),
                    no_of_rolls=int(no_of_rolls),
                    entry_time=int(entry_time),
                    bin_no=int(bin_no),
                    trolley_no=int(trolley_no),
                    wt_per_roll=float(wt_per_roll),
                )
            except ValueError as e:
                rid = None
                st.error(str(e))
            if rid is not None:
                st.success(f"Saved with ID {rid}")
                st.toast("Entry saved", icon="✅")
                st.session_state["_spe_refresh_key"] = st.session_state.get("_spe_refresh_key", 0) + 1
                st.rerun()
            else:
                st.warning("Saved entry but couldn't retrieve insert id.")

    # --- Daily entries summary (for selected entry_date) ---
    # Display all production entries for the chosen date (not filtered by spell/time) below the submit section
    from sqlalchemy import text as _text
    from db import engine as _engine
    try:
        with _engine.connect() as _conn:
            day_rows = pd.read_sql(
                _text(
                    """
                    SELECT 
                        spreader_prod_entry_id,
                        entry_id_grp,
                        bin_no,
                        entry_time,spell,
                        spreader_no,
                        jute_quality_id,
                        no_of_rolls,
                        wt_per_roll,
                        trolley_no
                    FROM EMPMILL12.spreader_prod_entry
                    WHERE entry_date = :d
                    ORDER BY entry_time
                    """
                ),
                _conn,
                params={"d": entry_date},
            )
        if not day_rows.empty:
            # Map quality name
            jq_map_local = dict(zip(jq_df['id'], jq_df['jute_quality']))
            day_rows['Jute Quality'] = day_rows['jute_quality_id'].map(jq_map_local)
            # Map spreader_no (id) to human-friendly display (machine name + code)
            try:
                def _map_spreader(val):
                    # Try direct (numeric) match
                    if val in spreader_display_by_id:
                        return spreader_display_by_id[val]
                    # Try string match
                    sval = str(val)
                    if sval in spreader_display_by_id_str:
                        return spreader_display_by_id_str[sval]
                    # Try int conversion if possible
                    if isinstance(val, str) and val.isdigit():
                        ival = int(val)
                        return spreader_display_by_id.get(ival, sval)
                    return sval
                day_rows['Spreader Display'] = day_rows['spreader_no'].apply(_map_spreader)
            except Exception:
                day_rows['Spreader Display'] = day_rows['spreader_no'].astype(str)
            # Compute weight columns
            day_rows['Produced Weight (kg)'] = (day_rows['no_of_rolls'] * day_rows['wt_per_roll'].fillna(0)).round(2)
            day_rows['Produced Weight (MT)'] = (day_rows['Produced Weight (kg)'] / 1000).round(2)
            # Build display WITHOUT showing internal ID/group; add an autogenerated index column
            display_cols = [
                'bin_no','entry_time','spell','Spreader Display','Jute Quality','no_of_rolls','wt_per_roll','Produced Weight (kg)','Produced Weight (MT)','trolley_no'
            ]
            day_display = day_rows[display_cols].rename(columns={
                'bin_no':'Bin',
                'entry_time':'Hour',
                'spell':'Spell',
                'Spreader Display':'Spreader',
                'no_of_rolls':'Rolls',
                'wt_per_roll':'Wt/Roll (kg)',
                'trolley_no':'Trolley'
            })
            # Autogenerated sequential index (1-based)
            day_display.insert(0, 'Index', range(1, len(day_display) + 1))
            # Totals row
            totals = {
                'Index': '',
                'Bin': 'Total',
                'Spell': '',
                'Hour': '',
                'Spreader': '',
                'Jute Quality': '',
                'Rolls': int(day_display['Rolls'].sum()),
                'Wt/Roll (kg)': None,
                'Produced Weight (kg)': round(day_display['Produced Weight (kg)'].sum(), 2),
                'Produced Weight (MT)': round(day_display['Produced Weight (MT)'].sum(), 2),
                'Trolley': ''
            }
            day_display = pd.concat([day_display, pd.DataFrame([totals])], ignore_index=True)
            # Ensure numeric columns are proper dtype before styling (prevents format code 'f' error)
            for _col in ['Wt/Roll (kg)', 'Produced Weight (kg)', 'Produced Weight (MT)']:
                if _col in day_display.columns:
                    day_display[_col] = pd.to_numeric(day_display[_col], errors='coerce')
            st.markdown("#### Entries for Selected Date")
            st.dataframe(
                day_display.style.format({
                    'Produced Weight (kg)': '{:.2f}',
                    'Produced Weight (MT)': '{:.2f}',
                    'Wt/Roll (kg)': '{:.2f}'
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.markdown("#### Entries for Selected Date")
            st.info("No entries recorded for the selected date.")
    except Exception as _e:
        st.warning(f"Could not load daily entries: {_e}")


with tab2:
    stock_df = fetch_bins_with_stock()
    if not stock_df.empty:
        jq_map = dict(zip(jq_df['id'], jq_df['jute_quality']))
        stock_df['Jute Quality'] = stock_df['jute_quality_id'].map(jq_map)

        # Quality filter buttons
        available_qualities = stock_df['Jute Quality'].dropna().unique().tolist()
        if 'selected_qualities' not in st.session_state:
            st.session_state['selected_qualities'] = []
        cols = st.columns(max(1, len(available_qualities)))
        for i, q in enumerate(available_qualities):
            btn_label = f"✅ {q}" if q in st.session_state['selected_qualities'] else q
            if cols[i].button(btn_label, key=f"quality_btn_{q}"):
                if q in st.session_state['selected_qualities']:
                    st.session_state['selected_qualities'].remove(q)
                else:
                    st.session_state['selected_qualities'].append(q)
                st.rerun()

        # Apply filter
        if st.session_state['selected_qualities']:
            filtered_df = stock_df[stock_df['Jute Quality'].isin(st.session_state['selected_qualities'])].copy()
        else:
            filtered_df = stock_df.copy()

        # Compute current rolls and maturity using avg_entry_ts per bin/group
        filtered_df['Current Rolls'] = filtered_df['no_of_rolls'] - filtered_df['issued_rolls'].fillna(0)
        now_ts = int(datetime.datetime.now().timestamp())
        # avg_entry_ts comes from backend in seconds; fallback: synthesize from entry_date + entry_time
        if 'avg_entry_ts' in filtered_df.columns:
            avg_ts = filtered_df['avg_entry_ts'].fillna(0).astype(float).astype(int)
        else:
            # fallback
            dt_series = pd.to_datetime(filtered_df['entry_date']) + pd.to_timedelta(filtered_df['entry_time'], unit='h')
            avg_ts = (dt_series.view('int64') // 10**9).astype(int)
        filtered_df['Maturity (hrs)'] = ((now_ts - avg_ts) / 3600).clip(lower=0).round(0).astype(int)

        # Target maturity mapping
        maturity_df = get_maturity_hours()
        if isinstance(maturity_df, pd.DataFrame) and not maturity_df.empty:
            maturity_map = dict(zip(maturity_df['jute_quality_id'], maturity_df['maturity_hours']))
        else:
            maturity_map = {}
        filtered_df['Target Maturity (hrs)'] = filtered_df['jute_quality_id'].map(maturity_map).fillna(48).astype(int)

        # Prepare display with totals
        show_df = filtered_df.copy()
        # Use backend-computed current_weight_mt if available; fallback to compute from kg if needed
        if 'current_weight_mt' in show_df.columns:
            show_df['Quantity (MT)'] = pd.to_numeric(show_df['current_weight_mt'], errors='coerce').round(2)
        elif 'current_weight_kg' in show_df.columns:
            show_df['Quantity (MT)'] = (pd.to_numeric(show_df['current_weight_kg'], errors='coerce') / 1000).round(2)
        else:
            show_df['Quantity (MT)'] = (show_df['Current Rolls'] * 58 / 1000).round(2)
        show_df = show_df.rename(columns={
            'bin_no': 'Bin No',
            'entry_id_grp': 'Entry Group',
        })
        # Round/astype for clarity
        show_df['Current Rolls'] = show_df['Current Rolls'].astype(int)
        if 'no_of_rolls' in show_df.columns:
            show_df['no_of_rolls'] = show_df['no_of_rolls'].astype(int)
        if 'issued_rolls' in show_df.columns:
            show_df['issued_rolls'] = show_df['issued_rolls'].fillna(0).astype(int)
        display_cols = ['Bin No', 'Entry Group', 'Jute Quality', 'Current Rolls', 'Quantity (MT)', 'Maturity (hrs)', 'Target Maturity (hrs)', 'no_of_rolls', 'issued_rolls']
        show_df = show_df[display_cols]

        import numpy as np
        total_row = pd.DataFrame({
            'Bin No': [np.nan],
            'Entry Group': [np.nan],
            'Jute Quality': ['Total'],
            'Current Rolls': [show_df['Current Rolls'].sum()],
            'Quantity (MT)': [round(pd.to_numeric(show_df['Quantity (MT)'], errors='coerce').sum(), 2)],
            'Maturity (hrs)': [np.nan],
            'Target Maturity (hrs)': [np.nan],
            'no_of_rolls': [show_df['no_of_rolls'].sum()],
            'issued_rolls': [show_df['issued_rolls'].sum()],
        })
        show_df = pd.concat([show_df, total_row], ignore_index=True)

        # Round integer-like columns to 0 decimals and keep Quantity (MT) at 2 decimals
        int_cols = ['Bin No', 'Entry Group', 'Current Rolls', 'Maturity (hrs)', 'Target Maturity (hrs)', 'no_of_rolls', 'issued_rolls']
        for col in int_cols:
            if col in show_df.columns:
                show_df[col] = pd.to_numeric(show_df[col], errors='coerce').round(0).astype('Int64')
        if 'Quantity (MT)' in show_df.columns:
            show_df['Quantity (MT)'] = pd.to_numeric(show_df['Quantity (MT)'], errors='coerce').round(2)
        st.markdown("#### Current Roll Stock (Bin/Group/Quality-wise)")

        # Build display DataFrame with default hidden columns
        hide_cols_default = ['Entry Group', 'no_of_rolls', 'issued_rolls']
        show_detailed = st.checkbox("Show detailed columns (group/raw)", value=False, key="roll_stock_show_detailed")
        if show_detailed:
            display_df = show_df.copy()
        else:
            drop_cols = [c for c in hide_cols_default if c in show_df.columns]
            display_df = show_df.drop(columns=drop_cols)

        # Conditional formatting for Maturity vs Target
        def _highlight_row(row):
            try:
                actual = row['Maturity (hrs)']
                target = row['Target Maturity (hrs)']
            except Exception:
                return [''] * len(row)
            styles = [''] * len(row)
            if pd.notna(actual) and pd.notna(target):
                # Find column index for 'Maturity (hrs)'
                try:
                    m_idx = list(row.index).index('Maturity (hrs)')
                except ValueError:
                    m_idx = None
                if m_idx is not None:
                    if abs(actual - target) <= 2:
                        styles[m_idx] = 'background-color: #d4edda'  # green: within ±2 hours
                    elif actual < target:
                        styles[m_idx] = 'background-color: #fff3cd'  # yellow: below target maturity
                    else:
                        styles[m_idx] = 'background-color: #f8d7da'  # red: above target maturity
            return styles

        styled = display_df.style.apply(_highlight_row, axis=1).format({"Quantity (MT)": "{:.2f}"})
        try:
            styled = styled.hide(axis='index')
        except Exception:
            pass
        st.dataframe(styled, use_container_width=True, hide_index=True)
        # Quality-wise summary (exclude the existing total summary row labeled 'Total')
        try:
            base_q_df = show_df[show_df['Jute Quality'] != 'Total'].copy()
            q_agg = base_q_df.groupby('Jute Quality', dropna=False).agg({
                'Current Rolls':'sum',
                'Quantity (MT)':'sum'
            }).reset_index()
            q_agg = q_agg.rename(columns={'Current Rolls':'Closing Rolls'})
            q_agg.insert(0, 'Index', range(1, len(q_agg)+1))
            q_tot = {
                'Index':'',
                'Jute Quality':'Total',
                'Closing Rolls': int(q_agg['Closing Rolls'].sum()),
                'Quantity (MT)': round(q_agg['Quantity (MT)'].sum(),2)
            }
            q_agg = pd.concat([q_agg, pd.DataFrame([q_tot])], ignore_index=True)
            # Coerce numerics
            for qc in ['Closing Rolls','Quantity (MT)']:
                if qc in q_agg.columns:
                    q_agg[qc] = pd.to_numeric(q_agg[qc], errors='coerce')
            st.markdown("#### Quality-wise Closing Stock Summary")
            st.dataframe(
                q_agg.style.format({'Quantity (MT)':'{:.2f}'}),
                use_container_width=True,
                hide_index=True
            )
        except Exception as _tab2qex:
            st.warning(f"Could not build quality summary: {_tab2qex}")
    else:
        st.markdown("#### Current Roll Stock (Bin/Group/Quality-wise)")
        st.info("No bins with stock.")




with tab3:
    stock_df = fetch_bins_with_stock()
    if not stock_df.empty:
        # Find the latest entry for each bin (to avoid duplicate bin_no)
        latest_entries = stock_df.groupby('bin_no').apply(lambda x: x.loc[x['entry_date'].idxmax()]).reset_index(drop=True)
        bin_info = latest_entries.set_index('bin_no').to_dict('index')
        bins_with_stock = stock_df['bin_no'].unique().tolist()
    else:
        bin_info = {}
        bins_with_stock = []
    from batching.spreader_roll_issue import insert_spreader_roll_issue
    from batching.spreaderprodentry import fetch_available_weights_for_group
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        issue_bin_no = st.selectbox("Bin No (to issue)", bins_with_stock, key="issue_bin_no")
        issue_date = st.date_input("Issue Date", datetime.date.today(), key="issue_date")
    with col2:
        now_hour = int(datetime.datetime.now().replace(minute=30 if datetime.datetime.now().minute >= 30 else 0).hour)
        issue_time = st.number_input("Issue Time (hour, 0-23)", min_value=0, max_value=23, step=1, value=now_hour, key="issue_time")

        # Use the same spell logic as in production entry
        def get_default_spell(entry_time):
            if 6 <= entry_time < 11:
                return "A1"
            elif 11 <= entry_time < 14:
                return "B1"
            elif 14 <= entry_time < 17:
                return "A2"
            elif 17 <= entry_time < 22:
                return "B2"
            else:
                return "C"

        default_issue_spell = get_default_spell(issue_time)
        spell_options = ["A1", "A2", "B1", "B2", "C"]
        spell_index = spell_options.index(default_issue_spell) if default_issue_spell in spell_options else 0
        issue_spell = st.selectbox("Issue Spell", spell_options, index=spell_index, key="issue_spell")
    with col3:
        # Autofill jute quality from selected bin, not editable
        if issue_bin_no in bin_info:
            jq_id = bin_info[issue_bin_no]['jute_quality_id']
            jq_display = jq_df[jq_df['id'] == jq_id]['jute_quality'].values[0] if not jq_df[jq_df['id'] == jq_id].empty else str(jq_id)
            # Find the latest spreader_prod_entry_id for this bin and entry_id_grp
            import sqlalchemy
            from db import engine as _engine
            entry_id_grp = bin_info[issue_bin_no]['entry_id_grp']
            find_id_sql = sqlalchemy.text("""
                SELECT entry_id_grp FROM EMPMILL12.spreader_prod_entry
                WHERE bin_no = :bin_no AND entry_id_grp = :entry_id_grp
                ORDER BY entry_date DESC, entry_time DESC LIMIT 1
            """)
            with _engine.connect() as conn:
                row = conn.execute(find_id_sql, {"bin_no": issue_bin_no, "entry_id_grp": entry_id_grp}).fetchone()
                spreader_prod_entry_id = row[0] if row else None
            # Fetch available weights for the group
            weights_df = fetch_available_weights_for_group(entry_id_grp)
            if not weights_df.empty:
                # Build options as "<wt_per_roll> kg (available: X)"
                weights_df = weights_df.sort_values('wt_per_roll')
                weight_options = [f"{w:.2f} kg (available: {int(a)})" for w, a in zip(weights_df['wt_per_roll'], weights_df['available_rolls'])]
                if len(weight_options) == 1:
                    selected_weight_display = weight_options[0]
                    selected_wt_per_roll = float(weights_df.iloc[0]['wt_per_roll'])
                    available_for_selected = int(weights_df.iloc[0]['available_rolls'])
                    st.text_input("Wt per Roll", value=selected_weight_display, disabled=True, key="issue_wt_per_roll_display")
                else:
                    selected_weight_display = st.selectbox("Wt per Roll", weight_options, key="issue_wt_per_roll_display")
                    # Parse selected weight back
                    try:
                        selected_wt_per_roll = float(selected_weight_display.split(' kg')[0])
                    except Exception:
                        selected_wt_per_roll = float(weights_df.iloc[0]['wt_per_roll'])
                    # Find available for selected
                    match = weights_df[weights_df['wt_per_roll'] == selected_wt_per_roll]
                    available_for_selected = int(match['available_rolls'].iloc[0]) if not match.empty else 0
            else:
                selected_wt_per_roll = None
                available_for_selected = 0
        else:
            jq_display = ""
            spreader_prod_entry_id = None
            selected_wt_per_roll = None
            available_for_selected = 0
        st.text_input("Jute Quality (auto)", value=jq_display, disabled=True, key="issue_jute_quality_display")
        # Determine current stock for selected weight and cap max
        current_stock = int(available_for_selected)
        issue_rolls = st.number_input(f"Issue Rolls (available: {current_stock})", min_value=0, max_value=int(current_stock), step=1, key="issue_rolls")
    with col4:
        breaker_inter_no = st.text_input("Breaker Inter No", value="", key="breaker_inter_no")
        st.write("")
    issue_submitted = st.button("Save Issue Entry")
    if issue_submitted:
        errors = []
        if issue_bin_no is None or issue_bin_no == "":
            errors.append("Bin No must be selected.")
        if issue_rolls <= 0:
            errors.append("Issue Rolls must be > 0.")
        if not spreader_prod_entry_id:
            errors.append("Could not determine spreader_prod_entry_id for this bin/group.")
        if not selected_wt_per_roll:
            errors.append("No weight available to issue for this group.")
        if errors:
            for e in errors:
                st.error(e)
            # Do not proceed to save if any validation errors exist
            st.stop()
        else:
            try:
                rid = insert_spreader_roll_issue(
                    breaker_inter_no=breaker_inter_no,
                    no_of_rolls=int(issue_rolls),
                    issue_time=int(issue_time),
                    issue_date=issue_date,
                    spell=issue_spell,
                    spreader_prod_entry_id=spreader_prod_entry_id,
                    wt_per_roll=float(selected_wt_per_roll)
                )
            except ValueError as e:
                # Backend validation failed; ensure nothing is saved and show error
                rid = None
                st.error(str(e))
                st.stop()
            if rid is not None:
                st.success(f"Issue entry saved for Bin {issue_bin_no}")
                st.toast("Issue entry saved", icon="✅")
                st.session_state["_spe_refresh_key"] = st.session_state.get("_spe_refresh_key", 0) + 1
                st.rerun()
            else:
                # Treat missing insert id as a failure to save to avoid accidental duplicates/misleading state
                st.error("Issue entry was not saved due to validation or system error.")
                st.stop()

    # --- Daily issue entries summary (for selected issue_date) ---
    from sqlalchemy import text as _itext
    from db import engine as _iengine
    try:
        with _iengine.connect() as _conn:
            issue_rows = pd.read_sql(
                _itext(
                    """
                    SELECT 
                        i.entry_id_grp,
                        i.issue_time,
                        i.spell,
                        i.issue_date,
                        i.wt_per_roll,
                        i.no_of_rolls,
                        i.breaker_inter_no,
                        p.bin_no,
                        p.jute_quality_id
                    FROM EMPMILL12.spreader_roll_issue i
                    LEFT JOIN (
                        SELECT entry_id_grp, bin_no, jute_quality_id
                        FROM EMPMILL12.spreader_prod_entry
                        GROUP BY entry_id_grp, bin_no, jute_quality_id
                    ) p ON p.entry_id_grp = i.entry_id_grp
                    WHERE i.issue_date = :d
                    ORDER BY i.issue_time, i.entry_id_grp
                    """
                ),
                _conn,
                params={"d": issue_date},
            )
        if not issue_rows.empty:
            # Derive weight issued (kg/MT)
            issue_rows['Issued Weight (kg)'] = (issue_rows['no_of_rolls'] * issue_rows['wt_per_roll'].fillna(0)).round(2)
            issue_rows['Issued Weight (MT)'] = (issue_rows['Issued Weight (kg)'] / 1000).round(2)
            # Map jute quality
            jq_map_local = dict(zip(jq_df['id'], jq_df['jute_quality']))
            issue_rows['Jute Quality'] = issue_rows['jute_quality_id'].map(jq_map_local)
            display_cols = ['issue_time','spell','bin_no','Jute Quality','wt_per_roll','no_of_rolls','Issued Weight (kg)','Issued Weight (MT)','breaker_inter_no']
            issue_display = issue_rows[display_cols].rename(columns={
                'issue_time':'Hour',
                'spell':'Spell',
                'bin_no':'Bin',
                'wt_per_roll':'Wt/Roll (kg)',
                'no_of_rolls':'Rolls',
                'breaker_inter_no':'Breaker Inter'
            })
            # Add index and drop internal group if user wants only index? (Keep Group for now unless hide requirement arises)
            issue_display.insert(0, 'Index', range(1, len(issue_display) + 1))
            totals_issue = {
                'Index':'',
                'Hour':'',
                'Spell':'',
                'Bin':'',
                'Jute Quality':'',
                'Wt/Roll (kg)':None,
                'Rolls': int(issue_display['Rolls'].sum()),
                'Issued Weight (kg)': round(issue_display['Issued Weight (kg)'].sum(),2),
                'Issued Weight (MT)': round(issue_display['Issued Weight (MT)'].sum(),2),
                'Breaker Inter':''
            }
            issue_display = pd.concat([issue_display, pd.DataFrame([totals_issue])], ignore_index=True)
            for _col in ['Wt/Roll (kg)','Issued Weight (kg)','Issued Weight (MT)']:
                if _col in issue_display.columns:
                    issue_display[_col] = pd.to_numeric(issue_display[_col], errors='coerce')
            st.markdown("#### Issue Entries for Selected Date")
            st.dataframe(
                issue_display.style.format({
                    'Wt/Roll (kg)':'{:.2f}',
                    'Issued Weight (kg)':'{:.2f}',
                    'Issued Weight (MT)':'{:.2f}'
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.markdown("#### Issue Entries for Selected Date")
            st.info("No issue entries recorded for the selected date.")
    except Exception as _ie:
        st.warning(f"Could not load issue entries: {_ie}")
# New tab: Roll Stock Time
with tab4:
    st.markdown("#### Roll Stock Position at Snapshot Time")
    st.caption("Shows opening rolls (before snapshot), production and issues within lookback window, and closing rolls at snapshot.")
    from sqlalchemy import text as _t4text
    from db import engine as _t4engine

    # New UX: user selects Closing (snapshot) date/hour; Opening is auto 24h prior
    c1, c2 = st.columns(2)
    with c1:
        closing_date = st.date_input("Closing (Snapshot) Date", datetime.date.today(), key="rst_closing_date")
    with c2:
        closing_hour = st.number_input("Closing Hour (0-23)", min_value=0, max_value=23, step=1, value=6, key="rst_closing_hour")

    closing_dt = datetime.datetime.combine(closing_date, datetime.time(int(closing_hour)))
    opening_dt = closing_dt - datetime.timedelta(hours=24)
    closing_str = closing_dt.strftime("%Y-%m-%d %H")
    opening_str = opening_dt.strftime("%Y-%m-%d %H")
    st.caption(f"Opening: {opening_str}:00 | Closing: {closing_str}:00 (24h window)")

    # Parameterized adaptation of provided SQL template.
    # Logic:
    #  - openstock: production minus issues strictly before snapshot
    #  - prodroll / issueroll: activity between start_dt and snapshot_dt inclusive
    #  - closing = opening + prod - issue
    raw_sql = _t4text(
        """
        SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
               SUM(openstock) AS openstock,
               SUM(prodroll)  AS prodroll,
               SUM(issueroll) AS issueroll,
               SUM(openstock) + SUM(prodroll) - SUM(issueroll) AS closstock
        FROM (
            -- Opening stock from production before snapshot
            SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
                   SUM(no_of_rolls) AS openstock, 0 AS prodroll, 0 AS issueroll
            FROM (
                SELECT spe.entry_id_grp, spe.entry_date, spe.entry_time, spe.bin_no, spe.wt_per_roll,
                       spe.jute_quality_id, spe.no_of_rolls,
                       CASE WHEN spe.entry_time < 6 THEN DATE_ADD(spe.entry_date, INTERVAL -1 DAY) ELSE spe.entry_date END AS proddate
                FROM EMPMILL12.spreader_prod_entry spe
            ) sprdprod
            WHERE STR_TO_DATE(CONCAT(proddate, ' ', entry_time), '%Y-%m-%d %H') < STR_TO_DATE(:opening_dt, '%Y-%m-%d %H')
            GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id

            UNION ALL

            -- Opening stock negative adjustment from issues before snapshot
            SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
                   -SUM(no_of_rolls) AS openstock, 0 AS prodroll, 0 AS issueroll
            FROM (
                SELECT sri.entry_id_grp, spe.jute_quality_id, spe.bin_no, sri.wt_per_roll,
                       CASE WHEN sri.issue_time < 6 THEN DATE_ADD(sri.issue_date, INTERVAL -1 DAY) ELSE sri.issue_date END AS issudate,
                       sri.issue_time, sri.no_of_rolls
                FROM EMPMILL12.spreader_roll_issue sri
                LEFT JOIN EMPMILL12.spreader_prod_entry spe ON spe.entry_id_grp = sri.entry_id_grp
            ) sprdissu
            WHERE STR_TO_DATE(CONCAT(issudate, ' ', issue_time), '%Y-%m-%d %H') < STR_TO_DATE(:opening_dt, '%Y-%m-%d %H')
            GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id

            UNION ALL

            -- Production within window
            SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
                   0 AS openstock, SUM(no_of_rolls) AS prodroll, 0 AS issueroll
            FROM (
                SELECT spe.entry_id_grp, spe.entry_date, spe.entry_time, spe.bin_no, spe.wt_per_roll,
                       spe.jute_quality_id, spe.no_of_rolls,
                       CASE WHEN spe.entry_time < 6 THEN DATE_ADD(spe.entry_date, INTERVAL -1 DAY) ELSE spe.entry_date END AS proddate
                FROM EMPMILL12.spreader_prod_entry spe
            ) sprdprod2
            WHERE STR_TO_DATE(CONCAT(proddate, ' ', entry_time), '%Y-%m-%d %H') BETWEEN STR_TO_DATE(:opening_dt, '%Y-%m-%d %H') AND STR_TO_DATE(:closing_dt, '%Y-%m-%d %H')
            GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id

            UNION ALL

            -- Issues within window
            SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
                   0 AS openstock, 0 AS prodroll, SUM(no_of_rolls) AS issueroll
            FROM (
                SELECT sri.entry_id_grp, spe.jute_quality_id, spe.bin_no, sri.wt_per_roll,
                       CASE WHEN sri.issue_time < 6 THEN DATE_ADD(sri.issue_date, INTERVAL -1 DAY) ELSE sri.issue_date END AS issudate,
                       sri.issue_time, sri.no_of_rolls
                FROM EMPMILL12.spreader_roll_issue sri
                LEFT JOIN EMPMILL12.spreader_prod_entry spe ON spe.entry_id_grp = sri.entry_id_grp
            ) sprdissu2
            WHERE STR_TO_DATE(CONCAT(issudate, ' ', issue_time), '%Y-%m-%d %H') BETWEEN STR_TO_DATE(:opening_dt, '%Y-%m-%d %H') AND STR_TO_DATE(:closing_dt, '%Y-%m-%d %H')
            GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
        ) g
        GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
        HAVING closstock <> 0 OR openstock <> 0 OR prodroll <> 0 OR issueroll <> 0
        ORDER BY bin_no, entry_id_grp, wt_per_roll
        """
    )

    load_btn = st.button("Load 24h Window", key="rst_load_btn")
    if load_btn:
        try:
            with _t4engine.connect() as conn:
                pos_df = pd.read_sql(raw_sql, conn, params={"opening_dt": opening_str, "closing_dt": closing_str})
            if pos_df.empty:
                st.info("No data for the selected window.")
            else:
                # Display the effective 24h period (after successful load)
                st.markdown(f"**Period:** {opening_str}:00 to {closing_str}:00 (inclusive, 24h)")
                # Map quality names
                jq_map = dict(zip(jq_df['id'], jq_df['jute_quality']))
                pos_df['Jute Quality'] = pos_df['jute_quality_id'].map(jq_map)
                # Derived columns
                pos_df['Open Rolls'] = pos_df['openstock'].fillna(0).astype(int)
                pos_df['Produced Rolls'] = pos_df['prodroll'].fillna(0).astype(int)
                pos_df['Issued Rolls'] = pos_df['issueroll'].fillna(0).astype(int)
                pos_df['Closing Rolls'] = pos_df['closstock'].fillna(0).astype(int)
                # Weight metrics (optional) if wt_per_roll present
                pos_df['Closing Weight (kg)'] = (pos_df['Closing Rolls'] * pos_df['wt_per_roll'].fillna(0)).round(2)
                pos_df['Closing Weight (MT)'] = (pos_df['Closing Weight (kg)'] / 1000).round(2)
                display_cols = [
                    'bin_no','entry_id_grp','wt_per_roll','Jute Quality',
                    'Open Rolls','Produced Rolls','Issued Rolls','Closing Rolls',
                    'Closing Weight (kg)','Closing Weight (MT)'
                ]
                show_df = pos_df[display_cols].rename(columns={
                    'bin_no':'Bin',
                    'entry_id_grp':'Group',
                    'wt_per_roll':'Wt/Roll (kg)'
                })
                # Totals row
                totals = {
                    'Bin':'', 'Group':'', 'Wt/Roll (kg)':None, 'Jute Quality':'Total',
                    'Open Rolls': show_df['Open Rolls'].sum(),
                    'Produced Rolls': show_df['Produced Rolls'].sum(),
                    'Issued Rolls': show_df['Issued Rolls'].sum(),
                    'Closing Rolls': show_df['Closing Rolls'].sum(),
                    'Closing Weight (kg)': round(show_df['Closing Weight (kg)'].sum(),2),
                    'Closing Weight (MT)': round(show_df['Closing Weight (MT)'].sum(),2)
                }
                show_df = pd.concat([show_df, pd.DataFrame([totals])], ignore_index=True)
                # Numeric coercion for formatting
                for nc in ['Wt/Roll (kg)','Closing Weight (kg)','Closing Weight (MT)']:
                    if nc in show_df.columns:
                        show_df[nc] = pd.to_numeric(show_df[nc], errors='coerce')
                # Style
                styled = show_df.style.format({
                    'Wt/Roll (kg)':'{:.2f}',
                    'Closing Weight (kg)':'{:.2f}',
                    'Closing Weight (MT)':'{:.2f}'
                })
                try:
                    styled = styled.hide(axis='index')
                except Exception:
                    pass
                st.dataframe(styled, use_container_width=True, hide_index=True)

                # Quality-wise aggregation table
                try:
                    q_cols_needed = ['Jute Quality','Closing Rolls','Closing Weight (kg)','Closing Weight (MT)']
                    qdf = pos_df[q_cols_needed].groupby('Jute Quality', dropna=False).sum(numeric_only=True).reset_index()
                    qdf = qdf.rename(columns={'Closing Rolls':'Closing Rolls','Closing Weight (kg)':'Closing Weight (kg)','Closing Weight (MT)':'Closing Weight (MT)'})
                    qdf = qdf[['Jute Quality','Closing Rolls','Closing Weight (kg)','Closing Weight (MT)']]
                    # Add index
                    qdf.insert(0, 'Index', range(1, len(qdf)+1))
                    # Totals row
                    q_totals = {
                        'Index':'',
                        'Jute Quality':'Total',
                        'Closing Rolls': qdf['Closing Rolls'].sum(),
                        'Closing Weight (kg)': round(qdf['Closing Weight (kg)'].sum(),2),
                        'Closing Weight (MT)': round(qdf['Closing Weight (MT)'].sum(),2)
                    }
                    qdf = pd.concat([qdf, pd.DataFrame([q_totals])], ignore_index=True)
                    # Coerce numerics
                    for qc in ['Closing Rolls','Closing Weight (kg)','Closing Weight (MT)']:
                        if qc in qdf.columns:
                            qdf[qc] = pd.to_numeric(qdf[qc], errors='coerce')
                    st.markdown("#### Closing Stock by Jute Quality")
                    st.dataframe(
                        qdf.style.format({
                            'Closing Weight (kg)':'{:.2f}',
                            'Closing Weight (MT)':'{:.2f}'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                except Exception as _qex:
                    st.warning(f"Could not build quality summary: {_qex}")
        except Exception as ex:
            st.error(f"Error loading position: {ex}")

with tab5:
    st.markdown("#### Spreader Production (Spreader & Spell-wise Rolls)")
    from sqlalchemy import text as _t5text
    from db import engine as _t5engine
    # Controls: Date + multi-select spells
    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        prod_date = st.date_input("Production Date", datetime.date.today(), key="spq_prod_date")
    with c2:
        all_spells = ["A1","A2","B1","B2","C"]
        selected_spells = st.multiselect("Spells", all_spells, default=all_spells, key="spq_spells")
    with c3:
        # Spreader filter (multi-select) using display labels
        spreader_multi = st.multiselect("Spreader(s)", spreader_display_options, default=spreader_display_options, key="spq_spreader_filter")
        # Derive selected spreader IDs for filtering
        selected_spreader_ids = [spreader_id_map.get(lbl) for lbl in spreader_multi if lbl in spreader_id_map]
    if not selected_spells:
        st.info("Select at least one spell to view production summary.")
    else:
        # Query production entries filtered by date and spells, group by spreader_no
        try:
            spell_params = {f"s{i}": sp for i, sp in enumerate(selected_spells)}
            spell_placeholders = ",".join([f":s{i}" for i in range(len(selected_spells))])
            # Add optional spreader filter
            params = {"pdate": prod_date}
            params.update(spell_params)
            spreader_filter_clause = ""
            if selected_spreader_ids and len(selected_spreader_ids) != len(spreader_display_options):
                # Build dynamic placeholders for spreader IDs
                sp_params = {f"sp{i}": sid for i, sid in enumerate(selected_spreader_ids)}
                sp_placeholders = ",".join([f":sp{i}" for i in range(len(selected_spreader_ids))])
                spreader_filter_clause = f" AND spreader_no IN ({sp_placeholders})"
                params.update(sp_params)
            q = _t5text(f"""
                SELECT spreader_no, spell, SUM(no_of_rolls) AS rolls, 
                       SUM(no_of_rolls * wt_per_roll) AS weight_kg
                FROM EMPMILL12.spreader_prod_entry
                WHERE entry_date = :pdate AND spell IN ({spell_placeholders}) {spreader_filter_clause}
                GROUP BY spreader_no, spell
                ORDER BY spreader_no, spell
            """)
            with _t5engine.connect() as conn:
                prod_df = pd.read_sql(q, conn, params=params)
            if prod_df.empty:
                st.info("No production for selected date/spells.")
            else:
                # Map spreader number to display label
                prod_df['Spreader'] = prod_df['spreader_no'].apply(map_spreader_id_to_display)
                prod_df['Spell'] = prod_df['spell']
                prod_df['Rolls'] = prod_df['rolls'].fillna(0).astype(int)
                prod_df['Weight (kg)'] = prod_df['weight_kg'].fillna(0).round(2)
                prod_df['Weight (MT)'] = (prod_df['Weight (kg)'] / 1000).round(2)
                display_cols = ['Spreader','Spell','Rolls','Weight (kg)','Weight (MT)']
                show_df = prod_df[display_cols].copy().sort_values(['Spreader','Spell'])
                show_df.insert(0, 'Index', range(1, len(show_df)+1))
                totals = {
                    'Index':'',
                    'Spreader':'Total',
                    'Spell':'',
                    'Rolls': show_df['Rolls'].sum(),
                    'Weight (kg)': round(show_df['Weight (kg)'].sum(),2),
                    'Weight (MT)': round(show_df['Weight (MT)'].sum(),2)
                }
                show_df = pd.concat([show_df, pd.DataFrame([totals])], ignore_index=True)
                for nc in ['Weight (kg)','Weight (MT)']:
                    show_df[nc] = pd.to_numeric(show_df[nc], errors='coerce')
                st.caption(f"Date: {prod_date} | Spells: {', '.join(selected_spells)}")
                st.dataframe(show_df.style.format({'Weight (kg)':'{:.2f}','Weight (MT)':'{:.2f}'}), use_container_width=True, hide_index=True)
        except Exception as _t5ex:
            st.error(f"Error loading production summary: {_t5ex}")

