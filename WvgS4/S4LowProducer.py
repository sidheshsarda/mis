def get_loom_group(loom_no):
    import re
    try:
        loom_str = str(loom_no)
        match = re.search(r'(\d+)$', loom_str)
        if not match:
            return "Unknown"
        num = int(match.group(1))
        if num >= 100:
            group_start = ((num - 1) // 6) * 6 + 1
            group_end = min(group_start + 5, 120)
            return f"{group_start}to{group_end}"
        else:
            group_start = ((num - 1) // 6) * 6 + 1
            group_end = min(group_start + 5, 99)
            return f"{group_start}to{group_end}"
    except Exception:
        return "Unknown"

def s4_low_producer_view():
    import streamlit as st
    import datetime
    from WvgS4.query import S4_day_details_eff
    import pandas as pd
    import re

    st.title("S4 Low Producer Report")

    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=30)
    st.write(f"**Selected End Date:** {today}")
    st.write(f"**Selected Start Date:** {start_date}")
    st.info("This report is considering last 30 days data")

    df, _ = S4_day_details_eff(today, start_date)
    if not df.empty:
        # Add LoomGroup column before LOOM_NO
        if 'LOOM_NO' in df.columns:
            df.insert(df.columns.get_loc('LOOM_NO'), 'LoomGroup', df['LOOM_NO'].apply(get_loom_group))
        # --- Add typeable selectboxes for Shift, EBNO, and LoomGroup ---
        shift_options = ['All'] + sorted([str(x) for x in df['Shift'].dropna().unique()]) if 'Shift' in df.columns else []
        ebno_options = ['All'] + sorted([str(x) for x in df['EBNO'].dropna().unique()]) if 'EBNO' in df.columns else []
        loomgroup_options = ['All'] + sorted([str(x) for x in df['LoomGroup'].dropna().unique()]) if 'LoomGroup' in df.columns else []
        col3, col4, col5 = st.columns(3)
        with col3:
            selected_shift = st.selectbox("Shift", shift_options, index=0, key="lp_shift_select") if shift_options else None
        with col4:
            selected_ebno = st.selectbox("EBNO", ebno_options, index=0, key="lp_ebno_select") if ebno_options else None
        with col5:
            selected_loomgroup = st.selectbox("LoomGroup", loomgroup_options, index=0, key="lp_loomgroup_select") if loomgroup_options else None
        # Filter dataframe based on selections
        filtered_df = df.copy()
        if selected_shift and selected_shift != 'All':
            filtered_df = filtered_df[filtered_df['Shift'].astype(str) == selected_shift]
        if selected_ebno and selected_ebno != 'All':
            filtered_df = filtered_df[filtered_df['EBNO'].astype(str) == selected_ebno]
        if selected_loomgroup and selected_loomgroup != 'All':
            filtered_df = filtered_df[filtered_df['LoomGroup'].astype(str) == selected_loomgroup]
        st.subheader("Base Data")
        st.dataframe(filtered_df, hide_index=True)

        # --- Show average EFF from Base Data (filtered_df), ignoring 0/null values ---
        if 'EFF' in filtered_df.columns:
            eff_values = filtered_df['EFF']
            eff_values = eff_values[(eff_values > 0) & (~eff_values.isnull())]
            avg_eff = eff_values.mean() if not eff_values.empty else None
            # --- Show unfiltered shed average (from df, not filtered_df) ---
            shed_eff = None
            if 'EFF' in df.columns:
                shed_eff_values = df['EFF']
                shed_eff_values = shed_eff_values[(shed_eff_values > 0) & (~shed_eff_values.isnull())]
                shed_eff = shed_eff_values.mean() if not shed_eff_values.empty else None
            col1, col2 = st.columns(2)
            with col1:
                if avg_eff is not None:
                    st.metric(label="Average EFF (Filtered)", value=f"{avg_eff:.2f}")
                else:
                    st.metric(label="Average EFF (Filtered)", value="N/A")
            with col2:
                if shed_eff is not None:
                    st.metric(label="Shed Eff Average (Unfiltered)", value=f"{shed_eff:.2f}")
                else:
                    st.metric(label="Shed Eff Average (Unfiltered)", value="N/A")

        # --- Grouped DataFrame by EBNO (with filters applied, LoomGroup removed) ---
        group_base_df = filtered_df.copy()
        # Only show table if all required columns exist and group_base_df is not empty
        ebno_table_columns = ['EBNO', 'Shift', 'EFF', 'Date', 'Name']
        missing_cols = [col for col in ebno_table_columns if col not in group_base_df.columns]
        if not group_base_df.empty and not missing_cols:
            # Add filter controls for DaysAttended and Avg Eff
            st.markdown('**EBNO/Shiftwise Avg Eff Table Filters**')
            colf1, colf2, colf3, colf4 = st.columns(4)
            with colf1:
                days_filter_type = st.selectbox('DaysAttended: Above/Below', ['All', 'Above', 'Below'], key='days_filter_type')
            with colf2:
                days_filter_value = st.number_input('DaysAttended Value', min_value=0, value=0, key='days_filter_value')
            with colf3:
                eff_filter_type = st.selectbox('Avg Eff: Above/Below', ['All', 'Above', 'Below'], key='eff_filter_type')
            with colf4:
                eff_filter_value = st.number_input('Avg Eff Value', min_value=0.0, value=0.0, key='eff_filter_value', step=0.1, format='%.2f')

            group_rows = []
            for ebno, group in group_base_df.groupby(['EBNO']):
                row = {'EBNO': ebno}
                # Get name (first non-null value for this EBNO)
                name_val = group['Name'].dropna().unique()
                row['Name'] = name_val[0] if len(name_val) > 0 else ''
                row['DaysAttended'] = group['Date'].nunique()
                # Calculate Avg LoomsRun: count of looms run where Eff > 0 divided by DaysAttended
                looms_run = group[group['EFF'] > 0]['LOOM_NO'].nunique() if 'LOOM_NO' in group.columns else group[group['EFF'] > 0].shape[0]
                row['Avg LoomsRun'] = round(looms_run / row['DaysAttended'], 0) if row['DaysAttended'] > 0 else ''
                for shift in ['A', 'B', 'C']:
                    effs = group[(group['Shift'] == shift) & (group['EFF'] > 0) & (~group['EFF'].isnull())]['EFF']
                    row[shift] = round(effs.mean(), 2) if not effs.empty else ''
                effs_all = group[(group['EFF'] > 0) & (~group['EFF'].isnull())]['EFF']
                row['Avg Eff'] = round(effs_all.mean(), 2) if not effs_all.empty else ''
                group_rows.append(row)
            group_df = pd.DataFrame(group_rows)
            # Apply DaysAttended filter
            if days_filter_type != 'All':
                if days_filter_type == 'Above':
                    group_df = group_df[group_df['DaysAttended'] > days_filter_value]
                elif days_filter_type == 'Below':
                    group_df = group_df[group_df['DaysAttended'] < days_filter_value]
            # Apply Avg Eff filter
            if eff_filter_type != 'All':
                if eff_filter_type == 'Above':
                    group_df = group_df[pd.to_numeric(group_df['Avg Eff'], errors='coerce') > eff_filter_value]
                elif eff_filter_type == 'Below':
                    group_df = group_df[pd.to_numeric(group_df['Avg Eff'], errors='coerce') < eff_filter_value]
            # Sort by Avg Eff (lowest to highest, blanks at the bottom)
            def avg_eff_sort_key(val):
                try:
                    return float(val)
                except:
                    return float('inf')
            group_df = group_df.sort_values(by='Avg Eff', key=lambda col: col.map(avg_eff_sort_key)).reset_index(drop=True)
            st.markdown('**EBNO/Shiftwise Avg Eff Table**')
            st.dataframe(group_df, hide_index=True)
        elif not group_base_df.empty and missing_cols:
            st.warning(f"Cannot display EBNO/Shiftwise Avg Eff Table. Missing columns: {', '.join(missing_cols)}")
        
        # --- New Table: Date, Shift, LoomGroup, Eff, EffA, EffB, EffC, AvgEff (filtered by selected EBNO) ---
        if selected_ebno and selected_ebno != 'All' and 'EBNO' in df.columns:
            base_df = df.copy()
            base_df['Date'] = base_df['Date'].astype(str)
            ebno_df = base_df[base_df['EBNO'].astype(str) == selected_ebno]
            if not ebno_df.empty:
                # Group by Date, Shift, LoomGroup to avoid repeated rows
                grouped = ebno_df.groupby(['Date', 'Shift', 'LoomGroup'], as_index=False)
                rows = []
                for (date, shift, loomgroup), group in grouped:
                    # Eff: average EFF for this Date, LoomGroup, and Shift (ignore 0/null)
                    eff_vals = base_df[(base_df['Date'] == date) & (base_df['LoomGroup'] == loomgroup) & (base_df['Shift'] == shift)]['EFF']
                    eff_vals = eff_vals[(eff_vals > 0) & (~eff_vals.isnull())]
                    eff = round(eff_vals.mean(), 2) if not eff_vals.empty else ''
                    # For EffA, EffB, EffC: get EFF for same Date and LoomGroup, but for shifts A, B, C, ignoring 0/null
                    eff_a = base_df[(base_df['Date'] == date) & (base_df['LoomGroup'] == loomgroup) & (base_df['Shift'] == 'A')]['EFF']
                    eff_a = eff_a[(eff_a > 0) & (~eff_a.isnull())]
                    eff_b = base_df[(base_df['Date'] == date) & (base_df['LoomGroup'] == loomgroup) & (base_df['Shift'] == 'B')]['EFF']
                    eff_b = eff_b[(eff_b > 0) & (~eff_b.isnull())]
                    eff_c = base_df[(base_df['Date'] == date) & (base_df['LoomGroup'] == loomgroup) & (base_df['Shift'] == 'C')]['EFF']
                    eff_c = eff_c[(eff_c > 0) & (~eff_c.isnull())]
                    eff_a_val = round(eff_a.mean(), 2) if not eff_a.empty else ''
                    eff_b_val = round(eff_b.mean(), 2) if not eff_b.empty else ''
                    eff_c_val = round(eff_c.mean(), 2) if not eff_c.empty else ''
                    avg_eff = [v for v in [eff_a_val, eff_b_val, eff_c_val] if isinstance(v, (int, float))]
                    avg_eff_val = round(sum(avg_eff) / len(avg_eff), 2) if avg_eff else ''
                    rows.append({
                        'Date': date,
                        'Shift': shift,
                        'LoomGroup': loomgroup,
                        'Eff': eff,
                        'EffA': eff_a_val,
                        'EffB': eff_b_val,
                        'EffC': eff_c_val,
                        'AvgEff': avg_eff_val
                    })
                result_df = pd.DataFrame(rows)
                # Add summary row for averages
                if not result_df.empty:
                    avg_row = {'Date': 'Avg', 'Shift': '', 'LoomGroup': ''}
                    for col in ['Eff', 'EffA', 'EffB', 'EffC', 'AvgEff']:
                        vals = pd.to_numeric(result_df[col], errors='coerce')
                        vals = vals[~vals.isnull()]
                        avg_row[col] = round(vals.mean(), 2) if not vals.empty else ''
                    result_df = pd.concat([result_df, pd.DataFrame([avg_row])], ignore_index=True)
                st.markdown('**EBNO/LoomGroup/Shiftwise Eff Table**')
                st.dataframe(result_df, hide_index=True)
            else:
                st.info('No data for selected EBNO.')
    else:
        st.warning("No data available for the selected period.")

