import streamlit as st
import datetime
from WvgS4.query import S4_day_details_eff
import pandas as pd

def s4_eff_todatewise_view():
    st.title("S4 Efficiency To-Date (Monthwise)")
    selected_date = st.date_input("Select End Date", value=datetime.date.today())
    if selected_date:
        start_date = selected_date.replace(day=1)
        df, _ = S4_day_details_eff(selected_date, start_date)
        if not df.empty:
            # Add typeable dropdown for EBNO
            ebno_list = sorted(df['EBNO'].dropna().unique().astype(str))
            selected_ebno = st.selectbox("Select EBNO (type to search, leave blank for all)", ["All"] + ebno_list, key="ebno_filter")
            if selected_ebno != "All":
                df = df[df['EBNO'].astype(str) == selected_ebno]
            st.dataframe(df)
            # --- Pivot Table: EBNO, Name, Shift as index; days as columns; avg EFF as values ---
            if 'tran_date' in df.columns and 'EBNO' in df.columns and 'Name' in df.columns and 'Shift' in df.columns and 'EFF' in df.columns:
                # Convert tran_date to datetime and extract day
                df['tran_date'] = pd.to_datetime(df['tran_date'])
                df['day'] = df['tran_date'].dt.day
                # Use day as columns
                pivot = pd.pivot_table(
                    df,
                    index=['EBNO', 'Name', 'Shift'],
                    columns='day',
                    values='EFF',
                    aggfunc='mean'
                )
                pivot = pivot.reset_index()
                # Round all values under the date columns to 0 decimals (including non-average rows)
                for day in pivot.columns[3:]:
                    pivot[day] = pivot[day].apply(lambda x: int(round(x, 0)) if pd.notnull(x) else '')
                # Add average row for each day, show empty string if NaN, round to 0 decimals
                avg_row = ['Average', '', '']
                for day in pivot.columns[3:]:
                    col_vals = pd.to_numeric(pivot[day], errors='coerce')
                    mean_val = col_vals.mean()
                    avg_row.append(int(round(mean_val, 0)) if pd.notnull(mean_val) else '')
                pivot_with_avg = pd.concat([pivot, pd.DataFrame([avg_row], columns=pivot.columns)], ignore_index=True)
                # Add overall average column at the end (row-wise mean, ignoring NaN and blanks)
                def row_overall_avg(row):
                    vals = pd.to_numeric(row[3:], errors='coerce')
                    vals = vals[pd.notnull(vals)]
                    return int(round(vals.mean(), 0)) if len(vals) > 0 else ''
                pivot_with_avg['Overall Avg'] = pivot_with_avg.apply(lambda row: row_overall_avg(row), axis=1)
                # Replace None/NaN with blank in the whole table
                pivot_with_avg = pivot_with_avg.where(pd.notnull(pivot_with_avg), '')
                # Show month and year in subheader
                month_year = selected_date.strftime('%B %Y')
                # Sort by Overall Avg (lowest to highest), keep 'Average' row at the bottom
                data_rows = pivot_with_avg[pivot_with_avg['EBNO'] != 'Average']
                avg_row_df = pivot_with_avg[pivot_with_avg['EBNO'] == 'Average']
                # Convert Overall Avg to numeric for sorting, blanks become NaN
                data_rows['Overall Avg (sort)'] = pd.to_numeric(data_rows['Overall Avg'], errors='coerce')
                data_rows = data_rows.sort_values(by='Overall Avg (sort)', ascending=True, na_position='last').drop(columns=['Overall Avg (sort)'])
                # Concatenate sorted data rows with the average row
                pivot_with_avg_sorted = pd.concat([data_rows, avg_row_df], ignore_index=True)
                st.markdown("---")
                st.subheader(f"Pivot Table: EFF by Day ({month_year})")
                st.dataframe(pivot_with_avg_sorted)
            else:
                st.info("Pivot table cannot be created: required columns missing.")
        else:
            st.info("No data available for the selected period.")
