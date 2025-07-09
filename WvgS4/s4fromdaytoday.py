import streamlit as st
import datetime
from WvgS4.query import S4_day_details_eff
import re
import pandas as pd

def s4_from_day_to_day_view():
    st.title("S4 Efficiency: From Day to Day")
    today = datetime.date.today()
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From Date", value=today.replace(day=1), key="from_date")
    with col2:
        to_date = st.date_input("To Date", value=today, key="to_date")
    if start_date and to_date and start_date <= to_date:
        df, _ = S4_day_details_eff(to_date, start_date)
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
                selected_shift = st.selectbox("Shift", shift_options, index=0, key="shift_select") if shift_options else None
            with col4:
                selected_ebno = st.selectbox("EBNO", ebno_options, index=0, key="ebno_select") if ebno_options else None
            with col5:
                selected_loomgroup = st.selectbox("LoomGroup", loomgroup_options, index=0, key="loomgroup_select") if loomgroup_options else None
            # Filter dataframe based on selections
            filtered_df = df.copy()
            if selected_shift and selected_shift != 'All':
                filtered_df = filtered_df[filtered_df['Shift'].astype(str) == selected_shift]
            if selected_ebno and selected_ebno != 'All':
                filtered_df = filtered_df[filtered_df['EBNO'].astype(str) == selected_ebno]
            if selected_loomgroup and selected_loomgroup != 'All':
                filtered_df = filtered_df[filtered_df['LoomGroup'].astype(str) == selected_loomgroup]
            st.dataframe(filtered_df, hide_index=True)

            # --- Summary Table as per user request ---
            if not filtered_df.empty:
                # Ensure columns exist
                for col in ['Shift', 'ActProd', 'EFF', 'LOOM_NO', 'Date']:
                    if col not in filtered_df.columns:
                        st.warning(f"Column '{col}' missing in data.")
                        return
                filtered_df['Date'] = filtered_df['Date'].astype(str)
                shifts = ['A', 'B', 'C']
                summary = {}
                dates = sorted(filtered_df['Date'].unique())
                # ActProd Sum
                for shift in shifts:
                    actprod = filtered_df[(filtered_df['Shift'] == shift)].groupby('Date')['ActProd'].sum()
                    summary[f'ActProd {shift}'] = [actprod.get(date, 0) for date in dates]
                # ActProd Total
                actprod_total = filtered_df.groupby('Date')['ActProd'].sum()
                summary['ActProd Total'] = [actprod_total.get(date, 0) for date in dates]
                # Avg Eff (ignore Eff==0 or ActProd==0)
                for shift in shifts:
                    eff = filtered_df[(filtered_df['Shift'] == shift) & (filtered_df['ActProd'] > 0) & (filtered_df['EFF'] > 0)].groupby('Date')['EFF'].mean()
                    summary[f'Avg Eff {shift}'] = [round(eff.get(date, float('nan')), 2) if not pd.isna(eff.get(date, float('nan'))) else '' for date in dates]
                # Weighted Avg Eff Total (by looms run)
                weighted_eff_total = []
                for date in dates:
                    effs = []
                    counts = []
                    for shift in shifts:
                        mask = (
                            (filtered_df['Date'] == date) &
                            (filtered_df['Shift'] == shift) &
                            (filtered_df['ActProd'] > 0) &
                            (filtered_df['EFF'] > 0)
                        )
                        eff_vals = filtered_df.loc[mask, 'EFF']
                        count = eff_vals.count()
                        if count > 0:
                            effs.append(eff_vals.mean())
                            counts.append(count)
                    if sum(counts) > 0:
                        weighted_avg = sum(e * c for e, c in zip(effs, counts)) / sum(counts)
                        weighted_eff_total.append(round(weighted_avg, 2))
                    else:
                        weighted_eff_total.append('')
                summary['Avg Eff Total'] = weighted_eff_total
                # LoomsRun (ActProd > 0)
                for shift in shifts:
                    looms_run = filtered_df[(filtered_df['Shift'] == shift) & (filtered_df['ActProd'] > 0)].groupby('Date')['LOOM_NO'].nunique()
                    summary[f'LoomsRun{shift}'] = [looms_run.get(date, 0) for date in dates]
                # TotalLoomsRun as sum of LoomsRunA, LoomsRunB, LoomsRunC
                summary['TotalLoomsRun'] = [
                    (summary['LoomsRunA'][i] if 'LoomsRunA' in summary else 0) +
                    (summary['LoomsRunB'][i] if 'LoomsRunB' in summary else 0) +
                    (summary['LoomsRunC'][i] if 'LoomsRunC' in summary else 0)
                    for i in range(len(dates))
                ]
                # Kg/Loom rows (ActProd / LoomsRun)
                kg_loom_a = [round(summary['ActProd A'][i] / summary['LoomsRunA'][i], 2) if summary['LoomsRunA'][i] else '' for i in range(len(dates))]
                kg_loom_b = [round(summary['ActProd B'][i] / summary['LoomsRunB'][i], 2) if summary['LoomsRunB'][i] else '' for i in range(len(dates))]
                kg_loom_c = [round(summary['ActProd C'][i] / summary['LoomsRunC'][i], 2) if summary['LoomsRunC'][i] else '' for i in range(len(dates))]
                kg_loom_total = [round(summary['ActProd Total'][i] / summary['TotalLoomsRun'][i], 2) if summary['TotalLoomsRun'][i] else '' for i in range(len(dates))]
                # Build DataFrame
                summary_rows = [
                    'ActProd A', 'ActProd B', 'ActProd C', 'ActProd Total',
                    'Avg Eff A', 'Avg Eff B', 'Avg Eff C', 'Avg Eff Total',
                    'LoomsRunA', 'LoomsRunB', 'LoomsRunC', 'TotalLoomsRun',
                    'Kg/LoomA', 'Kg/LoomB', 'Kg/LoomC', 'Kg/LoomTotal'
                ]
                summary_df = pd.DataFrame(
                    [
                        summary['ActProd A'], summary['ActProd B'], summary['ActProd C'], summary['ActProd Total'],
                        summary['Avg Eff A'], summary['Avg Eff B'], summary['Avg Eff C'], summary['Avg Eff Total'],
                        summary['LoomsRunA'], summary['LoomsRunB'], summary['LoomsRunC'], summary['TotalLoomsRun'],
                        kg_loom_a, kg_loom_b, kg_loom_c, kg_loom_total
                    ],
                    index=summary_rows, columns=dates
                )
                summary_df.insert(0, 'Row', summary_df.index)
                st.markdown('**Summary Table**')
                st.dataframe(summary_df.reset_index(drop=True), hide_index=True)
                # Looms entered but not run (ActProd == 0)
                looms_not_run = filtered_df[filtered_df['ActProd'] == 0]['LOOM_NO'].nunique()
                st.info(f"Looms entered but not run (ActProd = 0): {looms_not_run}")

                # --- Line Graphs for ActProd, Avg Eff, LoomsRun, Kg/Loom ---
                chart_dates = dates
                # Prepare data for plotting
                chart_data = {
                    'ActProd': {
                        'A': summary['ActProd A'],
                        'B': summary['ActProd B'],
                        'C': summary['ActProd C']
                    },
                    'Avg Eff': {
                        'A': summary['Avg Eff A'],
                        'B': summary['Avg Eff B'],
                        'C': summary['Avg Eff C'],
                        'Total': summary['Avg Eff Total']
                    },
                    'LoomsRun': {
                        'A': summary['LoomsRunA'],
                        'B': summary['LoomsRunB'],
                        'C': summary['LoomsRunC']
                    },
                    'Kg/Loom': {
                        'A': kg_loom_a,
                        'B': kg_loom_b,
                        'C': kg_loom_c,
                        'Total': kg_loom_total
                    }
                }
                for metric in ['ActProd', 'Avg Eff', 'LoomsRun', 'Kg/Loom']:
                    st.markdown(f"### {metric} (Day-wise, Shift-wise)")
                    plot_dict = {'Date': chart_dates}
                    if metric in ['ActProd', 'LoomsRun']:
                        plot_dict['A'] = chart_data[metric]['A']
                        plot_dict['B'] = chart_data[metric]['B']
                        plot_dict['C'] = chart_data[metric]['C']
                    else:
                        plot_dict['A'] = chart_data[metric]['A']
                        plot_dict['B'] = chart_data[metric]['B']
                        plot_dict['C'] = chart_data[metric]['C']
                        plot_dict['Total'] = chart_data[metric]['Total']
                    plot_df = pd.DataFrame(plot_dict)
                    plot_df = plot_df.set_index('Date')
                    st.line_chart(plot_df)
            # --- Grouped DataFrame by LoomGroup and EBNO (with filters applied) ---
            group_base_df = df.copy()
            if selected_shift and selected_shift != 'All':
                group_base_df = group_base_df[group_base_df['Shift'].astype(str) == selected_shift]
            if selected_ebno and selected_ebno != 'All':
                group_base_df = group_base_df[group_base_df['EBNO'].astype(str) == selected_ebno]
            if selected_loomgroup and selected_loomgroup != 'All':
                group_base_df = group_base_df[group_base_df['LoomGroup'].astype(str) == selected_loomgroup]
            if not group_base_df.empty and all(col in group_base_df.columns for col in ['LoomGroup', 'EBNO', 'Shift', 'EFF']):
                group_rows = []
                for (loomgroup, ebno), group in group_base_df.groupby(['LoomGroup', 'EBNO']):
                    row = {'LoomGroup': loomgroup, 'EBNO': ebno}
                    for shift in ['A', 'B', 'C']:
                        effs = group[(group['Shift'] == shift) & (group['EFF'] > 0) & (~group['EFF'].isnull())]['EFF']
                        row[shift] = round(effs.mean(), 2) if not effs.empty else ''
                    effs_all = group[(group['EFF'] > 0) & (~group['EFF'].isnull())]['EFF']
                    row['Avg Eff'] = round(effs_all.mean(), 2) if not effs_all.empty else ''
                    group_rows.append(row)
                group_df = pd.DataFrame(group_rows)
                # Order LoomGroup rows numerically by group start
                def loomgroup_sort_key(val):
                    m = re.match(r'(\d+)to(\d+)', str(val))
                    return int(m.group(1)) if m else float('inf')
                group_df = group_df.sort_values(by='LoomGroup', key=lambda col: col.map(loomgroup_sort_key)).reset_index(drop=True)
                st.markdown('**LoomGroup/EBNO/Shiftwise Avg Eff Table**')
                st.dataframe(group_df, hide_index=True)
            # --- Grouped DataFrame by LoomGroup with Avg/Max/Min Eff per shift (with filters applied) ---
            if not group_base_df.empty and all(col in group_base_df.columns for col in ['LoomGroup', 'Shift', 'EFF']):
                agg_rows = []
                for loomgroup, group in group_base_df.groupby('LoomGroup'):
                    row = {'LoomGroup': loomgroup}
                    for shift in ['A', 'B', 'C']:
                        effs = group[(group['Shift'] == shift) & (group['EFF'] > 0) & (~group['EFF'].isnull())]['EFF']
                        row[f'AvgEff{shift}'] = round(effs.mean(), 2) if not effs.empty else ''
                        row[f'MaxEff{shift}'] = round(effs.max(), 2) if not effs.empty else ''
                        row[f'MinEff{shift}'] = round(effs.min(), 2) if not effs.empty else ''
                    effs_all = group[(group['EFF'] > 0) & (~group['EFF'].isnull())]['EFF']
                    row['AvgEffTotal'] = round(effs_all.mean(), 2) if not effs_all.empty else ''
                    agg_rows.append(row)
                agg_df = pd.DataFrame(agg_rows)
                agg_df = agg_df.sort_values(by='LoomGroup', key=lambda col: col.map(loomgroup_sort_key)).reset_index(drop=True)
                st.markdown('**LoomGroup Shiftwise Avg/Max/Min Eff Table**')
                st.dataframe(agg_df, hide_index=True)
            # --- LoomGroup x Date table with AvgEff (with filters applied) ---
            if not group_base_df.empty and all(col in group_base_df.columns for col in ['LoomGroup', 'Date', 'EFF']):
                group_base_df['Date'] = group_base_df['Date'].astype(str)
                date_cols = sorted(group_base_df['Date'].unique())
                loomgroup_rows = []
                for loomgroup, group in group_base_df.groupby('LoomGroup'):
                    row = {'LoomGroup': loomgroup}
                    effs_all = []
                    for date in date_cols:
                        effs = group[(group['Date'] == date) & (group['EFF'] > 0) & (~group['EFF'].isnull())]['EFF']
                        row[date] = round(effs.mean(), 2) if not effs.empty else ''
                        if not effs.empty:
                            effs_all.extend(effs.tolist())
                    row['AvgEff'] = round(pd.Series(effs_all).mean(), 2) if effs_all else ''
                    loomgroup_rows.append(row)
                loomgroup_df = pd.DataFrame(loomgroup_rows)
                # Order LoomGroup rows numerically by group start
                loomgroup_df = loomgroup_df.sort_values(by='LoomGroup', key=lambda col: col.map(loomgroup_sort_key)).reset_index(drop=True)
                st.markdown('**LoomGroup x Date Avg Eff Table**')
                st.dataframe(loomgroup_df, hide_index=True)
        else:
            st.info("No data available for the selected period.")
    elif start_date and to_date:
        st.warning("From Date should be before or equal to To Date.")

def get_loom_group(loom_no):
    try:
        loom_str = str(loom_no)
        # Extract the rightmost group of digits
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


