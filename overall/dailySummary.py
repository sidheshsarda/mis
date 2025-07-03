import streamlit as st
from overall.query import get_dofftable_data, get_dofftable_sum_by_date
import pandas as pd
import datetime 

def daily_summary():
    st.title("Spinning Summary - Dofftable Data")
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    selected_date = st.date_input("Select Date", value=yesterday, key="daily_summary_date")

    end_date = selected_date.replace(day=1) if selected_date else None
    num_days = (selected_date - end_date).days + 1 if end_date else 0

    if selected_date:
        df, json_data = get_dofftable_data(selected_date)
        if end_date:
            mtd_df, mtd_json = get_dofftable_sum_by_date(end_date, selected_date)
            mtd_df = mtd_df.rename(columns={'value': 'MTD'})
            df = pd.merge(df, mtd_df, on='metric', how='left')

        st.subheader("JSON Data")
        st.code(json_data, language="json")

        # Rename first column to 'Metric' if needed
        if df.columns[0] != 'Metric':
            df.rename(columns={df.columns[0]: 'Metric'}, inplace=True)

        # Convert A/B/C to numeric
        for col in ['A', 'B', 'C']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Add Total and fill MTD
        if all(col in df.columns for col in ['A', 'B', 'C']):
            df['Total'] = df[['A', 'B', 'C']].sum(axis=1, skipna=True)
            df['MTD'] = df['MTD'].fillna(0)

        # Add Average and Utilisation rows
        try:
            prod_row = df[df['Metric'] == 'PRODUCTION (MT)'].iloc[0]
            frame_row = df[df['Metric'] == 'NO OF FRAME RUNS'].iloc[0]

            avg_row = {
                'Metric': 'AVG PER FRAME (Kg)',
                'A': round((prod_row['A'] * 1000) / frame_row['A'], 1) if frame_row['A'] else None,
                'B': round((prod_row['B'] * 1000) / frame_row['B'], 1) if frame_row['B'] else None,
                'C': round((prod_row['C'] * 1000) / frame_row['C'], 1) if frame_row['C'] else None,
                'Total': round((prod_row['Total'] * 1000) / frame_row['Total'], 1) if frame_row['Total'] else None,
                'MTD': round((prod_row['MTD'] * 1000) / frame_row['MTD'], 1) if frame_row['MTD'] else None
            }

            utilisation_row = {
                'Metric': 'Utilisation (%)',
                'A': round((frame_row['A'] / 48)*100, 0) if frame_row['A'] else None,
                'B': round((frame_row['B'] / 48)*100, 0) if frame_row['B'] else None,
                'C': round((frame_row['C'] / 48)*100, 0) if frame_row['C'] else None,
                'Total': round((frame_row['Total'] / (48*3))*100, 0) if frame_row['Total'] else None,
                'MTD': round((frame_row['MTD'] / (48*3*num_days))*100, 0) if frame_row['MTD'] else None
            }

            df = pd.concat([df, pd.DataFrame([avg_row, utilisation_row])], ignore_index=True)

        except (IndexError, KeyError) as e:
            st.warning(f"Could not calculate average per frame: {e}")

        # Move 'MTD' to the end
        if 'MTD' in df.columns:
            column_order = [col for col in df.columns if col != 'MTD'] + ['MTD']
        else:
            column_order = df.columns.tolist()

        # Configure column widths and formats
        column_config = {}
        for col in df.columns:
            if col == 'Metric':
                column_config[col] = st.column_config.TextColumn(width="medium")
            else:
                column_config[col] = st.column_config.NumberColumn(format="%.1f", width="60px")

        # Display final table
        st.subheader("Dofftable Data")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_order=column_order,
            column_config=column_config,
            row_height=28  # Compact layout
        )
