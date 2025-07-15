import streamlit as st
import datetime
from wdg.query import wdg_details_date, get_name
import pandas as pd

def wdg_low_producer_view():
    st.title("WDG Low Producer Efficiency Details")

    # Date range input
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    seven_days_ago = today - datetime.timedelta(days=7)
    col_date1, col_date2 = st.columns(2)
    with col_date1:
        from_date = st.date_input("From Date", value=seven_days_ago, max_value=yesterday, key="wdg_from_date")
    with col_date2:
        to_date = st.date_input("To Date", value=yesterday, min_value=from_date, max_value=yesterday, key="wdg_to_date")
    if from_date and to_date:
        from_date_str = from_date.strftime("%Y-%m-%d")
        to_date_str = to_date.strftime("%Y-%m-%d")
        # Query the data
        df, _ = wdg_details_date(to_date_str, from_date_str)
        if not df.empty:
            # --- Add selectboxes for Shift, EBNO, Mechine, Quality, Attendance Type ---
            shift_options = ['All'] + sorted([str(x) for x in df['shift'].dropna().unique()]) if 'shift' in df.columns else []
            ebno_prefix_options = ['All', 'L', 'T', 'C']
            col_prefix, col1, col2, col3, col4, col5 = st.columns(6)
            with col_prefix:
                selected_ebno_prefix = st.selectbox("EBNO Prefix", ebno_prefix_options, index=0, key="wdg_ebno_prefix_select")
            if 'eb_no' in df.columns:
                all_ebnos = sorted([str(x) for x in df['eb_no'].dropna().unique()])
                if selected_ebno_prefix and selected_ebno_prefix != 'All':
                    ebno_options = ['All'] + [eb for eb in all_ebnos if eb.startswith(selected_ebno_prefix)]
                else:
                    ebno_options = ['All'] + all_ebnos
            else:
                ebno_options = []
            mechine_options = ['All'] + sorted([str(x) for x in df['mechine_name'].dropna().unique()]) if 'mechine_name' in df.columns else []
            quality_options = ['All'] + sorted([str(x) for x in df['quality'].dropna().unique()]) if 'quality' in df.columns else []
            att_options = ['All'] + sorted([str(x) for x in df['attendance_type'].dropna().unique()]) if 'attendance_type' in df.columns else []
            with col1:
                selected_shift = st.selectbox("Shift", shift_options, index=0, key="wdg_shift_select") if shift_options else None
            with col2:
                selected_ebno = st.selectbox("EBNO", ebno_options, index=0, key="wdg_ebno_select") if ebno_options else None
            with col3:
                selected_mechine = st.selectbox("Mechine", mechine_options, index=0, key="wdg_mechine_select") if mechine_options else None
            with col4:
                selected_quality = st.selectbox("Quality", quality_options, index=0, key="wdg_quality_select") if quality_options else None
            with col5:
                selected_att = st.selectbox("Attendance Type", att_options, index=0, key="wdg_att_select") if att_options else None

            # Show Spinner Name if EBNO is selected (not 'All')
            if selected_ebno and selected_ebno != 'All':
                spinner_name = get_name(selected_ebno)
                st.markdown(f"**Spinner Name:** {spinner_name}")

            # Filter dataframe based on selections
            filtered_df = df.copy()
            if selected_ebno_prefix and selected_ebno_prefix != 'All':
                filtered_df = filtered_df[filtered_df['eb_no'].astype(str).str.startswith(selected_ebno_prefix)]
            if selected_shift and selected_shift != 'All':
                filtered_df = filtered_df[filtered_df['shift'].astype(str) == selected_shift]
            if selected_ebno and selected_ebno != 'All':
                filtered_df = filtered_df[filtered_df['eb_no'].astype(str) == selected_ebno]
            if selected_mechine and selected_mechine != 'All':
                filtered_df = filtered_df[filtered_df['mechine_name'].astype(str) == selected_mechine]
            if selected_quality and selected_quality != 'All':
                filtered_df = filtered_df[filtered_df['quality'].astype(str) == selected_quality]
            if selected_att and selected_att != 'All':
                filtered_df = filtered_df[filtered_df['attendance_type'].astype(str) == selected_att]
            st.subheader("WDG Data Table (Filtered)")
            st.dataframe(filtered_df, hide_index=True)

            # --- Show average EFF from filtered_df, ignoring 0/null values ---
            if 'eff' in filtered_df.columns:
                eff_values = filtered_df['eff']
                eff_values = eff_values[(eff_values > 0) & (~eff_values.isnull())]
                avg_eff = eff_values.mean() if not eff_values.empty else None
                colm1, colm2 = st.columns(2)
                with colm1:
                    if avg_eff is not None:
                        st.metric(label="Average EFF (Filtered)", value=f"{avg_eff:.2f}")
                    else:
                        st.metric(label="Average EFF (Filtered)", value="N/A")
                # --- Show unfiltered shed average (from df, not filtered_df) ---
                shed_eff = None
                if 'eff' in df.columns:
                    shed_eff_values = df['eff']
                    shed_eff_values = shed_eff_values[(shed_eff_values > 0) & (~shed_eff_values.isnull())]
                    shed_eff = shed_eff_values.mean() if not shed_eff_values.empty else None
                with colm2:
                    if shed_eff is not None:
                        st.metric(label="Shed Eff Average (Unfiltered)", value=f"{shed_eff:.2f}")
                    else:
                        st.metric(label="Shed Eff Average (Unfiltered)", value="N/A")

            # --- EBNO/Shiftwise Avg Eff Table ---
            ebno_table_columns = ['eb_no', 'shift', 'eff', 'tran_date']
            missing_cols = [col for col in ebno_table_columns if col not in filtered_df.columns]
            if not filtered_df.empty and not missing_cols:
                st.markdown('**EBNO/Shiftwise Avg Eff Table Filters**')
                colf1, colf2 = st.columns(2)
                with colf1:
                    days_filter_type = st.selectbox('DaysAttended: Above/Below', ['All', 'Above', 'Below'], key='wdg_days_filter_type')
                with colf2:
                    days_filter_value = st.number_input('DaysAttended Value', min_value=0, value=0, key='wdg_days_filter_value')
                st.markdown('**EBNO/Shiftwise Avg Eff Table**')
                group_rows = []
                for ebno, group in filtered_df.groupby(['eb_no']):
                    row = {'EBNO': ebno}
                    row['DaysAttended'] = group['tran_date'].nunique()
                    for shift in ['A', 'B', 'C']:
                        effs = group[(group['shift'] == shift) & (group['eff'] > 0) & (~group['eff'].isnull())]['eff']
                        row[shift] = round(effs.mean(), 2) if not effs.empty else ''
                    effs_all = group[(group['eff'] > 0) & (~group['eff'].isnull())]['eff']
                    row['Avg Eff'] = round(effs_all.mean(), 2) if not effs_all.empty else ''
                    group_rows.append(row)
                group_df = pd.DataFrame(group_rows)
                # Apply DaysAttended filter
                if days_filter_type != 'All':
                    if days_filter_type == 'Above':
                        group_df = group_df[group_df['DaysAttended'] > days_filter_value]
                    elif days_filter_type == 'Below':
                        group_df = group_df[group_df['DaysAttended'] < days_filter_value]
                # Sort by Avg Eff (lowest to highest, blanks at the bottom)
                def avg_eff_sort_key(val):
                    try:
                        return float(val)
                    except:
                        return float('inf')
                group_df = group_df.sort_values(by='Avg Eff', key=lambda col: col.map(avg_eff_sort_key)).reset_index(drop=True)
                st.dataframe(group_df, hide_index=True)
            elif not filtered_df.empty and missing_cols:
                st.warning(f"Cannot display EBNO/Shiftwise Avg Eff Table. Missing columns: {', '.join(missing_cols)}")

            # --- New Table: Date, Shift, EBNO, Mechine, Eff, EffA, EffB, EffC, AvgEff (filtered by selected EBNO) ---
            if selected_ebno and selected_ebno != 'All' and 'eb_no' in filtered_df.columns:
                ebno_df = filtered_df[filtered_df['eb_no'].astype(str) == selected_ebno]
                if not ebno_df.empty:
                    # Use the original (unfiltered) df for EffA, EffB, EffC
                    orig_df = df.copy()
                    grouped = ebno_df.groupby(['tran_date', 'shift', 'mechine_name'], as_index=False)
                    rows = []
                    for (date, shift, mechine), group in grouped:
                        # Eff: average for selected EBNO, date, shift, mechine
                        eff_vals = group['eff']
                        eff_vals = eff_vals[(eff_vals > 0) & (~eff_vals.isnull())]
                        eff = round(eff_vals.mean(), 2) if not eff_vals.empty else ''
                        # EffA, EffB, EffC: average for ALL spinners (all EBNOs) who worked on that date, mechine, and shift A/B/C (from original df, not filtered by EBNO)
                        eff_a = orig_df[(orig_df['tran_date'] == date) & (orig_df['mechine_name'] == mechine) & (orig_df['shift'] == 'A')]['eff']
                        eff_a = eff_a[(eff_a > 0) & (~eff_a.isnull())]
                        eff_b = orig_df[(orig_df['tran_date'] == date) & (orig_df['mechine_name'] == mechine) & (orig_df['shift'] == 'B')]['eff']
                        eff_b = eff_b[(eff_b > 0) & (~eff_b.isnull())]
                        eff_c = orig_df[(orig_df['tran_date'] == date) & (orig_df['mechine_name'] == mechine) & (orig_df['shift'] == 'C')]['eff']
                        eff_c = eff_c[(eff_c > 0) & (~eff_c.isnull())]
                        eff_a_val = round(eff_a.mean(), 2) if not eff_a.empty else ''
                        eff_b_val = round(eff_b.mean(), 2) if not eff_b.empty else ''
                        eff_c_val = round(eff_c.mean(), 2) if not eff_c.empty else ''
                        avg_eff = [v for v in [eff_a_val, eff_b_val, eff_c_val] if isinstance(v, (int, float))]
                        avg_eff_val = round(sum(avg_eff) / len(avg_eff), 2) if avg_eff else ''
                        rows.append({
                            'Date': date,
                            'Shift': shift,
                            'EBNO': selected_ebno,
                            'Mechine': mechine,
                            'Eff': eff,
                            'EffA': eff_a_val,
                            'EffB': eff_b_val,
                            'EffC': eff_c_val,
                            'AvgEff': avg_eff_val
                        })
                    result_df = pd.DataFrame(rows)
                    # Add summary row for averages
                    if not result_df.empty:
                        avg_row = {'Date': 'Avg', 'Shift': '', 'EBNO': selected_ebno, 'Mechine': ''}
                        for col in ['Eff', 'EffA', 'EffB', 'EffC', 'AvgEff']:
                            vals = pd.to_numeric(result_df[col], errors='coerce')
                            vals = vals[~vals.isnull()]
                            avg_row[col] = round(vals.mean(), 2) if not vals.empty else ''
                        result_df = pd.concat([result_df, pd.DataFrame([avg_row])], ignore_index=True)
                    st.markdown('**EBNO/Shiftwise Eff Table (Details)**')
                    st.dataframe(result_df, hide_index=True)
                else:
                    st.info('No data for selected EBNO.')

            # --- New Table: Daywise Avg Eff and Shift for selected EBNO ---
            if selected_ebno and selected_ebno != 'All' and 'eb_no' in filtered_df.columns:
                ebno_df = filtered_df[filtered_df['eb_no'].astype(str) == selected_ebno]
                if not ebno_df.empty:
                    # Group by date and shift, aggregate average eff across all mechine for that EBNO
                    grouped = ebno_df.groupby(['tran_date', 'shift'], as_index=False)
                    rows = []
                    for (date, shift), group in grouped:
                        eff_vals = group['eff']
                        eff_vals = eff_vals[(eff_vals > 0) & (~eff_vals.isnull())]
                        avg_eff = round(eff_vals.mean(), 2) if not eff_vals.empty else ''
                        mechines = ', '.join(sorted([str(f) for f in group['mechine_name'].unique()]))
                        rows.append({
                            'Date': date,
                            'Shift': shift,
                            'Mechines': mechines,
                            'AvgEff': avg_eff
                        })
                    result_df = pd.DataFrame(rows)
                    # Add summary row for averages
                    if not result_df.empty:
                        avg_row = {'Date': 'Avg', 'Shift': '', 'Mechines': ''}
                        vals = pd.to_numeric(result_df['AvgEff'], errors='coerce')
                        vals = vals[~vals.isnull()]
                        avg_row['AvgEff'] = round(vals.mean(), 2) if not vals.empty else ''
                        result_df = pd.concat([result_df, pd.DataFrame([avg_row])], ignore_index=True)
                    st.markdown('**Daywise Avg Eff and Shift for Spinner**')
                    st.dataframe(result_df, hide_index=True)
        else:
            st.info("No data available for the selected period.")
