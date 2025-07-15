import streamlit as st
import datetime
from spg.query import spg_details_date
import pandas as pd


def spg_from_day_to_day_view():

    st.title("SPG From Day To Day Efficiency Details")
    
    # Date range input for selecting from and to dates
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    seven_days_ago = today - datetime.timedelta(days=7)
    default_start = today - datetime.timedelta(days=30)
    col_date1, col_date2 = st.columns(2)
    with col_date1:
        from_date = st.date_input("From Date", value=seven_days_ago, max_value=yesterday, key="spg_from_date")
    with col_date2:
        to_date = st.date_input("To Date", value=yesterday, min_value=from_date, max_value=yesterday, key="spg_to_date")
    if from_date and to_date:
        from_date_str = from_date.strftime("%Y-%m-%d")
        to_date_str = to_date.strftime("%Y-%m-%d")
        
        # Query the data
        df, _ = spg_details_date(to_date_str, from_date_str)
        
        if not df.empty:
            # --- Add typeable selectboxes for Shift, EBNO, FrameNo, Q_Code, Quality ---
            shift_options = ['All'] + sorted([str(x) for x in df['shift'].dropna().unique()]) if 'shift' in df.columns else []
            # EBNO prefix filter
            ebno_prefix_options = ['All', 'L', 'T', 'C']
            col_prefix, col1, col2, col3, col4, col5 = st.columns(6)
            with col_prefix:
                selected_ebno_prefix = st.selectbox("EBNO Prefix", ebno_prefix_options, index=0, key="spg_ebno_prefix_select")
            # Filter EBNOs by prefix if selected
            if 'ebno' in df.columns:
                all_ebnos = sorted([str(x) for x in df['ebno'].dropna().unique()])
                if selected_ebno_prefix and selected_ebno_prefix != 'All':
                    ebno_options = ['All'] + [eb for eb in all_ebnos if eb.startswith(selected_ebno_prefix)]
                else:
                    ebno_options = ['All'] + all_ebnos
            else:
                ebno_options = []
            frameno_options = ['All'] + sorted([str(x) for x in df['frameno'].dropna().unique()]) if 'frameno' in df.columns else []
            qcode_options = ['All'] + sorted([str(x) for x in df['q_code'].dropna().unique()]) if 'q_code' in df.columns else []
            quality_options = ['All'] + sorted([str(x) for x in df['quality'].dropna().unique()]) if 'quality' in df.columns else []
            with col1:
                selected_shift = st.selectbox("Shift", shift_options, index=0, key="spg_shift_select") if shift_options else None
            with col2:
                selected_ebno = st.selectbox("EBNO", ebno_options, index=0, key="spg_ebno_select") if ebno_options else None
            with col3:
                selected_frameno = st.selectbox("Frame No", frameno_options, index=0, key="spg_frameno_select") if frameno_options else None
            with col4:
                selected_qcode = st.selectbox("Q Code", qcode_options, index=0, key="spg_qcode_select") if qcode_options else None
            with col5:
                selected_quality = st.selectbox("Quality", quality_options, index=0, key="spg_quality_select") if quality_options else None

            # Show Spinner Name if EBNO is selected (not 'All')
            if selected_ebno and selected_ebno != 'All':
                from spg.query import get_name
                spinner_name = get_name(selected_ebno)
                st.markdown(f"**Spinner Name:** {spinner_name}")

            # Filter dataframe based on selections
            filtered_df = df.copy()
            # Apply EBNO prefix filter first
            if selected_ebno_prefix and selected_ebno_prefix != 'All':
                filtered_df = filtered_df[filtered_df['ebno'].astype(str).str.startswith(selected_ebno_prefix)]
            if selected_shift and selected_shift != 'All':
                filtered_df = filtered_df[filtered_df['shift'].astype(str) == selected_shift]
            if selected_ebno and selected_ebno != 'All':
                filtered_df = filtered_df[filtered_df['ebno'].astype(str) == selected_ebno]
            if selected_frameno and selected_frameno != 'All':
                filtered_df = filtered_df[filtered_df['frameno'].astype(str) == selected_frameno]
            if selected_qcode and selected_qcode != 'All':
                filtered_df = filtered_df[filtered_df['q_code'].astype(str) == selected_qcode]
            if selected_quality and selected_quality != 'All':
                filtered_df = filtered_df[filtered_df['quality'].astype(str) == selected_quality]
            st.subheader("SPG Data Table (Filtered)")
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

            # --- EBNO/Shiftwise Avg Eff Table (like S4LowProducer) ---
            ebno_table_columns = ['ebno', 'shift', 'eff', 'doffdate']
            missing_cols = [col for col in ebno_table_columns if col not in filtered_df.columns]
            if not filtered_df.empty and not missing_cols:
                st.markdown('**EBNO/Shiftwise Avg Eff Table Filters**')
                colf1, colf2 = st.columns(2)
                with colf1:
                    days_filter_type = st.selectbox('DaysAttended: Above/Below', ['All', 'Above', 'Below'], key='spg_days_filter_type')
                with colf2:
                    days_filter_value = st.number_input('DaysAttended Value', min_value=0, value=0, key='spg_days_filter_value')
                st.markdown('**EBNO/Shiftwise Avg Eff Table**')
                group_rows = []
                for ebno, group in filtered_df.groupby(['ebno']):
                    row = {'EBNO': ebno}
                    row['DaysAttended'] = group['doffdate'].nunique()
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

            # --- New Table: Date, Shift, EBNO, FrameNo, Eff, EffA, EffB, EffC, AvgEff (filtered by selected EBNO) ---
            if selected_ebno and selected_ebno != 'All' and 'ebno' in filtered_df.columns:
                ebno_df = filtered_df[filtered_df['ebno'].astype(str) == selected_ebno]
                if not ebno_df.empty:
                    # Use the original (unfiltered) df for EffA, EffB, EffC
                    orig_df = df.copy()
                    grouped = ebno_df.groupby(['doffdate', 'shift', 'frameno'], as_index=False)
                    rows = []
                    for (date, shift, frameno), group in grouped:
                        # Eff: average for selected EBNO, date, shift, frameno
                        eff_vals = group['eff']
                        eff_vals = eff_vals[(eff_vals > 0) & (~eff_vals.isnull())]
                        eff = round(eff_vals.mean(), 2) if not eff_vals.empty else ''
                        # EffA, EffB, EffC: average for ALL spinners (all EBNOs) who worked on that date, frameno, and shift A/B/C (from original df, not filtered by EBNO)
                        eff_a = orig_df[(orig_df['doffdate'] == date) & (orig_df['frameno'] == frameno) & (orig_df['shift'] == 'A')]['eff']
                        eff_a = eff_a[(eff_a > 0) & (~eff_a.isnull())]
                        eff_b = orig_df[(orig_df['doffdate'] == date) & (orig_df['frameno'] == frameno) & (orig_df['shift'] == 'B')]['eff']
                        eff_b = eff_b[(eff_b > 0) & (~eff_b.isnull())]
                        eff_c = orig_df[(orig_df['doffdate'] == date) & (orig_df['frameno'] == frameno) & (orig_df['shift'] == 'C')]['eff']
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
                            'FrameNo': frameno,
                            'Eff': eff,
                            'EffA': eff_a_val,
                            'EffB': eff_b_val,
                            'EffC': eff_c_val,
                            'AvgEff': avg_eff_val
                        })
                    result_df = pd.DataFrame(rows)
                    # Add summary row for averages
                    if not result_df.empty:
                        avg_row = {'Date': 'Avg', 'Shift': '', 'EBNO': selected_ebno, 'FrameNo': ''}
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
            if selected_ebno and selected_ebno != 'All' and 'ebno' in filtered_df.columns:
                ebno_df = filtered_df[filtered_df['ebno'].astype(str) == selected_ebno]
                if not ebno_df.empty:
                    # Group by date and shift, aggregate average eff across all frames for that EBNO
                    grouped = ebno_df.groupby(['doffdate', 'shift'], as_index=False)
                    rows = []
                    for (date, shift), group in grouped:
                        eff_vals = group['eff']
                        eff_vals = eff_vals[(eff_vals > 0) & (~eff_vals.isnull())]
                        avg_eff = round(eff_vals.mean(), 2) if not eff_vals.empty else ''
                        frames = ', '.join(sorted([str(f) for f in group['frameno'].unique()]))
                        rows.append({
                            'Date': date,
                            'Shift': shift,
                            'FrameNos': frames,
                            'AvgEff': avg_eff
                        })
                    result_df = pd.DataFrame(rows)
                    # Add summary row for averages
                    if not result_df.empty:
                        avg_row = {'Date': 'Avg', 'Shift': '', 'FrameNos': ''}
                        vals = pd.to_numeric(result_df['AvgEff'], errors='coerce')
                        vals = vals[~vals.isnull()]
                        avg_row['AvgEff'] = round(vals.mean(), 2) if not vals.empty else ''
                        result_df = pd.concat([result_df, pd.DataFrame([avg_row])], ignore_index=True)
                    st.markdown('**Daywise Avg Eff and Shift for Spinner**')
                    st.dataframe(result_df, hide_index=True)
        else:
            st.info("No data available for the selected period.")






