import streamlit as st
import datetime
from WvgHessian.query import hess_day_details_eff
import pandas as pd

def hessian_low_producer_view():
    st.title("Hessian Low Producer Report")

    # --- Date selection controls ---
    today = datetime.date.today()
    default_start = today - datetime.timedelta(days=30)
    col_date1, col_date2 = st.columns(2)
    with col_date1:
        start_date = st.date_input("From Date", value=default_start, max_value=today, key="hess_from_date")
    with col_date2:
        end_date = st.date_input("To Date", value=today, min_value=start_date, max_value=today, key="hess_to_date")
    st.write(f"**Selected End Date:** {end_date}")
    st.write(f"**Selected Start Date:** {start_date}")
    st.info("This report is considering data from the selected date range")

    df, _ = hess_day_details_eff(end_date, start_date)
    if not df.empty:
        # --- Add typeable selectboxes for Shift, EBNO, and LoomNo ---
        shift_options = ['All'] + sorted([str(x) for x in df['Shift'].dropna().unique()]) if 'Shift' in df.columns else []
        ebno_options = ['All'] + sorted([str(x) for x in df['EBNO'].dropna().unique()]) if 'EBNO' in df.columns else []
        loom_options = ['All'] + sorted([str(x) for x in df['LOOM_NO'].dropna().unique()]) if 'LOOM_NO' in df.columns else []
        col3, col4, col5 = st.columns(3)
        with col3:
            selected_shift = st.selectbox("Shift", shift_options, index=0, key="hess_shift_select") if shift_options else None
        with col4:
            selected_ebno = st.selectbox("EBNO", ebno_options, index=0, key="hess_ebno_select") if ebno_options else None
        with col5:
            selected_loom = st.selectbox("Loom No", loom_options, index=0, key="hess_loom_select") if loom_options else None
        # Filter dataframe based on selections
        filtered_df = df.copy()
        if selected_shift and selected_shift != 'All':
            filtered_df = filtered_df[filtered_df['Shift'].astype(str) == selected_shift]
        if selected_ebno and selected_ebno != 'All':
            filtered_df = filtered_df[filtered_df['EBNO'].astype(str) == selected_ebno]
        if selected_loom and selected_loom != 'All':
            filtered_df = filtered_df[filtered_df['LOOM_NO'].astype(str) == selected_loom]

        st.subheader("Base Data")
        # Hide specified columns if present
        cols_to_hide = ['q_oza_yds', 'q_width', 'q_finish_length']
        display_df = filtered_df.drop(columns=[col for col in cols_to_hide if col in filtered_df.columns], errors='ignore')
        st.dataframe(display_df, hide_index=True)

        # --- Table: Number of Days Worked (DaysAttended) for each EBNO with filter and shiftwise eff ---
        ebno_days_cols = ['EBNO', 'Date', 'Shift', 'EFF']
        missing_days_cols = [col for col in ebno_days_cols if col not in filtered_df.columns]
        if not filtered_df.empty and not missing_days_cols:
            group_rows = []
            for ebno, group in filtered_df.groupby(['EBNO']):
                row = {'EBNO': ebno}
                row['DaysAttended'] = group['Date'].nunique()
                # Shiftwise average eff
                for shift in ['A', 'B', 'C']:
                    effs = group[(group['Shift'] == shift) & (group['EFF'] > 0) & (~group['EFF'].isnull())]['EFF']
                    row[shift] = round(effs.mean(), 2) if not effs.empty else ''
                effs_all = group[(group['EFF'] > 0) & (~group['EFF'].isnull())]['EFF']
                row['Avg Eff'] = round(effs_all.mean(), 2) if not effs_all.empty else ''
                group_rows.append(row)
            group_df = pd.DataFrame(group_rows)
            # Add DaysAttended filter controls
            colf1, colf2 = st.columns(2)
            with colf1:
                days_filter_type = st.selectbox('DaysAttended: Above/Below', ['All', 'Above', 'Below'], key='hess_days_filter_type')
            with colf2:
                days_filter_value = st.number_input('DaysAttended Value', min_value=0, value=0, key='hess_days_filter_value')
            # Apply DaysAttended filter
            if days_filter_type != 'All':
                if days_filter_type == 'Above':
                    group_df = group_df[group_df['DaysAttended'] > days_filter_value]
                elif days_filter_type == 'Below':
                    group_df = group_df[group_df['DaysAttended'] < days_filter_value]
            group_df = group_df.sort_values(by='DaysAttended', ascending=False).reset_index(drop=True)
            st.markdown('**Number of Days Worked (DaysAttended) and Shiftwise Eff per EBNO**')
            st.dataframe(group_df, hide_index=True)

        # --- New Table: Date, Shift, EBNO, LoomNo, Eff, EffA, EffB, EffC, AvgEff (filtered by selected EBNO) ---
        if selected_ebno and selected_ebno != 'All' and 'EBNO' in filtered_df.columns:
            ebno_df = filtered_df[filtered_df['EBNO'].astype(str) == selected_ebno]
            if not ebno_df.empty:
                # Use the original (unfiltered) df for EffA, EffB, EffC
                orig_df = df.copy()
                grouped = ebno_df.groupby(['Date', 'Shift', 'LOOM_NO'], as_index=False)
                rows = []
                for (date, shift, loomno), group in grouped:
                    # Eff: average for selected EBNO, date, shift, loomno
                    eff_vals = group['EFF']
                    eff_vals = eff_vals[(eff_vals > 0) & (~eff_vals.isnull())]
                    eff = round(eff_vals.mean(), 2) if not eff_vals.empty else ''
                    # EffA, EffB, EffC: average for ALL spinners (all EBNOs) who worked on that date, loomno, and shift A/B/C (from original df, not filtered by EBNO)
                    eff_a = orig_df[(orig_df['Date'] == date) & (orig_df['LOOM_NO'] == loomno) & (orig_df['Shift'] == 'A')]['EFF']
                    eff_a = eff_a[(eff_a > 0) & (~eff_a.isnull())]
                    eff_b = orig_df[(orig_df['Date'] == date) & (orig_df['LOOM_NO'] == loomno) & (orig_df['Shift'] == 'B')]['EFF']
                    eff_b = eff_b[(eff_b > 0) & (~eff_b.isnull())]
                    eff_c = orig_df[(orig_df['Date'] == date) & (orig_df['LOOM_NO'] == loomno) & (orig_df['Shift'] == 'C')]['EFF']
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
                        'LoomNo': loomno,
                        'Eff': eff,
                        'EffA': eff_a_val,
                        'EffB': eff_b_val,
                        'EffC': eff_c_val,
                        'AvgEff': avg_eff_val
                    })
                result_df = pd.DataFrame(rows)
                # Add summary row for averages
                if not result_df.empty:
                    avg_row = {'Date': 'Avg', 'Shift': '', 'EBNO': selected_ebno, 'LoomNo': ''}
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
        if selected_ebno and selected_ebno != 'All' and 'EBNO' in filtered_df.columns:
            ebno_df = filtered_df[filtered_df['EBNO'].astype(str) == selected_ebno]
            if not ebno_df.empty:
                # Group by date and shift, aggregate average eff across all looms for that EBNO
                grouped = ebno_df.groupby(['Date', 'Shift'], as_index=False)
                rows = []
                for (date, shift), group in grouped:
                    eff_vals = group['EFF']
                    eff_vals = eff_vals[(eff_vals > 0) & (~eff_vals.isnull())]
                    avg_eff = round(eff_vals.mean(), 2) if not eff_vals.empty else ''
                    looms = ', '.join(sorted([str(f) for f in group['LOOM_NO'].unique()]))
                    rows.append({
                        'Date': date,
                        'Shift': shift,
                        'LoomNos': looms,
                        'AvgEff': avg_eff
                    })
                result_df = pd.DataFrame(rows)
                # Add summary row for averages
                if not result_df.empty:
                    avg_row = {'Date': 'Avg', 'Shift': '', 'LoomNos': ''}
                    vals = pd.to_numeric(result_df['AvgEff'], errors='coerce')
                    vals = vals[~vals.isnull()]
                    avg_row['AvgEff'] = round(vals.mean(), 2) if not vals.empty else ''
                    result_df = pd.concat([result_df, pd.DataFrame([avg_row])], ignore_index=True)
                st.markdown('**Daywise Avg Eff and Shift for Spinner**')
                st.dataframe(result_df, hide_index=True)

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
    else:
        st.warning("No data available for the selected period.")
