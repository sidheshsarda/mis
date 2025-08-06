import streamlit as st
import datetime
import pandas as pd
from doff10.query import get_dofftable_details, get_frame_quality_details

def spgframe_view():
    st.title("SPG Frame Doff Table")

    # Date selection controls
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    default_start = yesterday - datetime.timedelta(days=7)
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=default_start, max_value=yesterday, key="spgframe_start_date")
    with col2:
        end_date = st.date_input("End Date", value=yesterday, min_value=start_date, max_value=yesterday, key="spgframe_end_date")

    # Fetch data
    df, _ = get_dofftable_details(start_date, end_date)
    if not df.empty:
        # Create a 'quality' column for display (concatenated q_code-quality_name if available)
        if 'q_code' in df.columns and 'quality_name' in df.columns:
            df['quality'] = df['q_code'].astype(str) + '-' + df['quality_name'].astype(str)
        elif 'q_code' in df.columns:
            df['quality'] = df['q_code']
        # Add quality filter (only once)
        quality_options = ['All'] + sorted(df['quality'].dropna().unique().tolist())
        selected_quality = st.selectbox('Filter by Quality', quality_options, index=0, key='spgframe_quality')
        filtered_df = df.copy()
        if selected_quality != 'All':
            filtered_df = filtered_df[filtered_df['quality'] == selected_quality]

        # --- Quality vs Shift Average Netwt Table ---
        if not filtered_df.empty and 'shift' in filtered_df.columns and 'quality' in filtered_df.columns:
            avg_table = filtered_df.groupby(['quality', 'shift'], as_index=False)['total_netwt'].mean()
            avg_pivot = avg_table.pivot_table(index='quality', columns='shift', values='total_netwt', fill_value=0)
            avg_pivot = avg_pivot.round(2).reset_index()
            st.markdown('**Average Netwt by Quality and Shift**')
            st.dataframe(avg_pivot, hide_index=True)

        # Pivot the table: frameno, quality, then date columns
        pivot_df = filtered_df.pivot_table(
            index=['frameno', 'quality'],
            columns='doffdate',
            values='total_netwt',
            aggfunc='sum',
            fill_value=0
        )
        # Reset index to get frameno and quality as columns
        pivot_df = pivot_df.reset_index()
        # Sort columns: frameno, quality, then dates in order
        date_cols = sorted([col for col in pivot_df.columns if isinstance(col, (str, datetime.date)) and col not in ['frameno', 'quality']])
        ordered_cols = ['frameno', 'quality'] + date_cols
        pivot_df = pivot_df[ordered_cols]

        # For each (frameno, quality, date), divide netwt by number of shifts that frame ran for that quality on that date
        for date_col in date_cols:
            # For each row, count how many shifts for this frameno, quality, date
            for idx, row in pivot_df.iterrows():
                frameno = row['frameno']
                quality = row['quality']
                # Count unique shifts in filtered_df for this frameno, quality, date
                mask = (
                    (filtered_df['frameno'] == frameno) &
                    (filtered_df['quality'] == quality) &
                    (filtered_df['doffdate'] == date_col)
                )
                n_shifts = filtered_df[mask]['shift'].nunique() if 'shift' in filtered_df.columns else 1
                if n_shifts > 0 and row[date_col] != 0:
                    pivot_df.at[idx, date_col] = round(row[date_col] / n_shifts, 2)

        # Add Average, Max, Min columns at the end
        value_cols = date_cols
        def avg_ignore_zeros(row):
            vals = [v for v in row if v != 0]
            return round(sum(vals)/len(vals), 2) if vals else 0
        def min_ignore_zeros(row):
            vals = [v for v in row if v != 0]
            return min(vals) if vals else 0
        pivot_df['Average'] = pivot_df[value_cols].apply(avg_ignore_zeros, axis=1)
        pivot_df['Max'] = pivot_df[value_cols].max(axis=1)
        pivot_df['Min'] = pivot_df[value_cols].apply(min_ignore_zeros, axis=1)
        st.dataframe(pivot_df, hide_index=True)

        # --- Frameno filter and shift-wise production table ---
        st.markdown('---')
        all_framenos = sorted(filtered_df['frameno'].dropna().unique().tolist())
        selected_frameno = st.selectbox('Filter by Frame No', [''] + all_framenos, index=0, key='spgframe_frameno')
        if selected_frameno != '':
            # Filter for selected frameno
            frame_df = filtered_df[filtered_df['frameno'] == selected_frameno]
            if not frame_df.empty:
                # Group by date and shift, sum netwt
                shiftwise = frame_df.groupby(['doffdate', 'shift'], as_index=False)['total_netwt'].sum()
                # Pivot: rows = date, columns = shift, values = total_netwt
                shiftwise_pivot = shiftwise.pivot_table(index='doffdate', columns='shift', values='total_netwt', fill_value=0)
                shiftwise_pivot = shiftwise_pivot.reset_index()
                st.markdown(f'**Shift-wise Production for Frame {selected_frameno}**')
                # Add average, min, max rows (ignore 0 values)
                data_cols = [col for col in shiftwise_pivot.columns if col != 'doffdate']
                def avg_ignore_zeros_col(col):
                    vals = [v for v in col if v != 0]
                    return round(sum(vals)/len(vals), 2) if vals else 0
                def min_ignore_zeros_col(col):
                    vals = [v for v in col if v != 0]
                    return min(vals) if vals else 0
                def max_ignore_zeros_col(col):
                    vals = [v for v in col if v != 0]
                    return max(vals) if vals else 0
                avg_row = {c: avg_ignore_zeros_col(shiftwise_pivot[c]) for c in data_cols}
                min_row = {c: min_ignore_zeros_col(shiftwise_pivot[c]) for c in data_cols}
                max_row = {c: max_ignore_zeros_col(shiftwise_pivot[c]) for c in data_cols}
                avg_row['doffdate'] = 'Average'
                min_row['doffdate'] = 'Min'
                max_row['doffdate'] = 'Max'
                shiftwise_pivot = pd.concat([shiftwise_pivot, pd.DataFrame([avg_row, min_row, max_row])], ignore_index=True)
                st.dataframe(shiftwise_pivot, hide_index=True)
                # Show line chart for the same data (excluding summary rows)
                chart_df = shiftwise_pivot[~shiftwise_pivot['doffdate'].isin(['Average', 'Min', 'Max'])].copy()
                chart_df = chart_df.set_index('doffdate')
                st.line_chart(chart_df)
            else:
                st.info('No data for selected Frame No.')

            # --- Frame-Quality Details Table ---
            # Only show if all filters are selected
            if selected_quality != 'All' and start_date and end_date and selected_frameno != '':
                # Parse q_code and quality_name from selected_quality
                if '-' in selected_quality:
                    q_code, quality_name = selected_quality.split('-', 1)
                else:
                    q_code = selected_quality
                    quality_name = ''
                details_df, _ = get_frame_quality_details(start_date, end_date, selected_frameno, q_code)
                if not details_df.empty:
                    st.markdown(f'**Frame-Quality Details for Frame {selected_frameno}, Quality {selected_quality}**')
                    st.dataframe(details_df, hide_index=True)
                else:
                    st.info('No frame-quality details for the selected filters.')
    else:
        st.info("No data available for the selected date range.")

