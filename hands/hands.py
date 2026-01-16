import streamlit as st
import pandas as pd
import datetime
from hands.query import (
    get_daily_hand_comparison,
    get_daily_hand_summary,
    get_hand_comparison_by_occupation,
    get_hand_summary_by_department
)


def hands_report():
    """Display the Hands Comparison Report with date range selection."""
    
    st.title("Daily Hands Comparison Report")
    
    # Date range selection
    col1, col2 = st.columns(2)
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    
    with col1:
        start_date = st.date_input(
            "Start Date", 
            value=yesterday,
            key="hands_start_date"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date", 
            value=yesterday,
            key="hands_end_date"
        )
    
    if start_date > end_date:
        st.error("Start date must be before or equal to end date.")
        return
    
    # View selection
    view_option = st.radio(
        "Select View",
        ["Detailed View", "Summary by Date", "Summary by Occupation"],
        horizontal=True
    )
    
    try:
        if view_option == "Detailed View":
            display_detailed_view(start_date, end_date)
        elif view_option == "Summary by Date":
            display_summary_by_date(start_date, end_date)
        else:
            display_summary_by_occupation(start_date, end_date)
            
    except Exception as e:
        st.error(f"Error loading data: {e}")


def display_detailed_view(start_date, end_date):
    """Display detailed hand comparison data."""
    
    df = get_daily_hand_comparison(start_date, end_date)
    
    if df.empty:
        st.warning("No data found for the selected date range.")
        return
    
    st.markdown(f"### Detailed Hand Comparison ({start_date} to {end_date})")
    
    # Format the date column
    df['tran_date'] = pd.to_datetime(df['tran_date']).dt.strftime('%Y-%m-%d')
    
    # Calculate totals
    df['total_actual'] = df['shift_a'] + df['shift_b'] + df['shift_c'] + df['shift_g']
    df['total_target'] = df['target_a'] + df['target_b'] + df['target_c']
    
    # Display filters
    col1, col2, col3 = st.columns(3)
    with col1:
        departments = ['All'] + sorted(df['department'].dropna().unique().tolist())
        selected_department = st.selectbox("Filter by Department", departments)
    
    with col2:
        occupations = ['All'] + sorted(df['occupation'].unique().tolist())
        selected_occupation = st.selectbox("Filter by Occupation", occupations)
    
    with col3:
        direct_indirect = ['All'] + sorted(df['DIRECT_INDIRECT'].dropna().unique().tolist())
        selected_di = st.selectbox("Filter by Direct/Indirect", direct_indirect)
    
    # Apply filters
    filtered_df = df.copy()
    if selected_department != 'All':
        filtered_df = filtered_df[filtered_df['department'] == selected_department]
    if selected_occupation != 'All':
        filtered_df = filtered_df[filtered_df['occupation'] == selected_occupation]
    if selected_di != 'All':
        filtered_df = filtered_df[filtered_df['DIRECT_INDIRECT'] == selected_di]
    
    # Summary metrics
    st.markdown("### Summary Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Records", len(filtered_df))
    with col2:
        st.metric("Total Actual Hands", f"{filtered_df['total_actual'].sum():.2f}")
    with col3:
        st.metric("Total Excess", f"{filtered_df['excess_hands'].sum():.2f}")
    with col4:
        st.metric("Total Short", f"{filtered_df['short_hands'].sum():.2f}")
    
    # Option to show shift-wise details
    show_shift_details = st.checkbox("Show shift-wise details", value=False, key="detailed_shift_details")
    
    # Display the dataframe
    if show_shift_details:
        display_columns = [
            'tran_date', 'department', 'occupation', 'short_name', 'DIRECT_INDIRECT',
            'shift_a', 'shift_b', 'shift_c', 'shift_g',
            'target_a', 'target_b', 'target_c',
            'total_actual', 'total_target',
            'excess_hands', 'short_hands'
        ]
    else:
        display_columns = [
            'tran_date', 'department', 'occupation', 'short_name', 'DIRECT_INDIRECT',
            'total_actual', 'total_target',
            'excess_hands', 'short_hands'
        ]
    
    column_config = {
        'tran_date': st.column_config.TextColumn("Date", width="small"),
        'department': st.column_config.TextColumn("Department", width="medium"),
        'occupation': st.column_config.TextColumn("Occupation", width="medium"),
        'short_name': st.column_config.TextColumn("Short Name", width="small"),
        'DIRECT_INDIRECT': st.column_config.TextColumn("D/I", width="small"),
        'shift_a': st.column_config.NumberColumn("Shift A", format="%.2f"),
        'shift_b': st.column_config.NumberColumn("Shift B", format="%.2f"),
        'shift_c': st.column_config.NumberColumn("Shift C", format="%.2f"),
        'shift_g': st.column_config.NumberColumn("Shift G", format="%.2f"),
        'target_a': st.column_config.NumberColumn("Target A", format="%.2f"),
        'target_b': st.column_config.NumberColumn("Target B", format="%.2f"),
        'target_c': st.column_config.NumberColumn("Target C", format="%.2f"),
        'total_actual': st.column_config.NumberColumn("Total Actual", format="%.2f"),
        'total_target': st.column_config.NumberColumn("Total Target", format="%.2f"),
        'excess_hands': st.column_config.NumberColumn("Excess", format="%.2f"),
        'short_hands': st.column_config.NumberColumn("Short", format="%.2f"),
    }
    
    st.dataframe(
        filtered_df[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config=column_config
    )


def display_summary_by_date(start_date, end_date):
    """Display summary of hands by date."""
    
    df_raw = get_daily_hand_summary(start_date, end_date)
    
    if df_raw.empty:
        st.warning("No data found for the selected date range.")
        return
    
    st.markdown(f"### Daily Summary ({start_date} to {end_date})")
    
    # Calculate Direct/Indirect totals from raw data (before filtering)
    df_raw['total_actual'] = df_raw['total_shift_a'] + df_raw['total_shift_b'] + df_raw['total_shift_c'] + df_raw['total_shift_g']
    direct_total = df_raw[df_raw['DIRECT_INDIRECT'] == 'D']['total_actual'].sum()
    indirect_total = df_raw[df_raw['DIRECT_INDIRECT'] == 'I']['total_actual'].sum()
    
    # Filter for Direct/Indirect
    direct_indirect_options = ['All'] + sorted(df_raw['DIRECT_INDIRECT'].dropna().unique().tolist())
    selected_di = st.selectbox("Filter by Direct/Indirect", direct_indirect_options, key="date_di_filter")
    
    # Apply filter
    df = df_raw.copy()
    if selected_di != 'All':
        df = df[df['DIRECT_INDIRECT'] == selected_di]
    
    # Group by date after filtering (to aggregate D and I if showing All)
    df = df.groupby('tran_date', as_index=False).agg({
        'total_shift_a': 'sum',
        'total_shift_b': 'sum',
        'total_shift_c': 'sum',
        'total_shift_g': 'sum',
        'total_target_a': 'sum',
        'total_target_b': 'sum',
        'total_target_c': 'sum',
        'total_excess_hands': 'sum',
        'total_short_hands': 'sum',
    }).sort_values('tran_date')
    
    # Format the date column
    df['tran_date'] = pd.to_datetime(df['tran_date']).dt.strftime('%Y-%m-%d')
    
    # Calculate totals
    df['total_actual'] = df['total_shift_a'] + df['total_shift_b'] + df['total_shift_c'] + df['total_shift_g']
    df['total_target'] = df['total_target_a'] + df['total_target_b'] + df['total_target_c']
    
    # Option to show shift-wise details
    show_shift_details = st.checkbox("Show shift-wise details", value=False, key="date_shift_details")
    
    column_config = {
        'tran_date': st.column_config.TextColumn("Date", width="small"),
        'total_shift_a': st.column_config.NumberColumn("Shift A", format="%.2f"),
        'total_shift_b': st.column_config.NumberColumn("Shift B", format="%.2f"),
        'total_shift_c': st.column_config.NumberColumn("Shift C", format="%.2f"),
        'total_shift_g': st.column_config.NumberColumn("Shift G", format="%.2f"),
        'total_target_a': st.column_config.NumberColumn("Target A", format="%.2f"),
        'total_target_b': st.column_config.NumberColumn("Target B", format="%.2f"),
        'total_target_c': st.column_config.NumberColumn("Target C", format="%.2f"),
        'total_actual': st.column_config.NumberColumn("Total Actual", format="%.2f"),
        'total_target': st.column_config.NumberColumn("Total Target", format="%.2f"),
        'total_excess_hands': st.column_config.NumberColumn("Excess", format="%.2f"),
        'total_short_hands': st.column_config.NumberColumn("Short", format="%.2f"),
    }
    
    if show_shift_details:
        display_columns = [
            'tran_date', 'total_shift_a', 'total_shift_b', 'total_shift_c', 'total_shift_g',
            'total_target_a', 'total_target_b', 'total_target_c',
            'total_actual', 'total_target', 'total_excess_hands', 'total_short_hands'
        ]
    else:
        display_columns = [
            'tran_date', 'total_actual', 'total_target', 'total_excess_hands', 'total_short_hands'
        ]
    
    st.dataframe(
        df[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config=column_config
    )
    
    # Summary metrics
    st.markdown("### Period Totals")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("Total Days", len(df))
    with col2:
        st.metric("Avg Daily Hands", f"{df['total_actual'].mean():.2f}")
    with col3:
        st.metric("Direct Total", f"{direct_total:.2f}")
    with col4:
        st.metric("Indirect Total", f"{indirect_total:.2f}")
    with col5:
        st.metric("Total Excess", f"{df['total_excess_hands'].sum():.2f}")
    with col6:
        st.metric("Total Short", f"{df['total_short_hands'].sum():.2f}")


def display_summary_by_occupation(start_date, end_date):
    """Display summary of hands by occupation."""
    
    df = get_hand_comparison_by_occupation(start_date, end_date)
    
    if df.empty:
        st.warning("No data found for the selected date range.")
        return
    
    # First show department-wise summary
    st.markdown(f"### Department-wise Summary ({start_date} to {end_date})")
    display_department_summary(start_date, end_date)
    
    st.divider()
    
    st.markdown(f"### Occupation-wise Details ({start_date} to {end_date})")
    
    # Calculate totals
    df['total_actual'] = df['total_shift_a'] + df['total_shift_b'] + df['total_shift_c'] + df['total_shift_g']
    df['total_target'] = df['total_target_a'] + df['total_target_b'] + df['total_target_c']
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        departments = ['All'] + sorted(df['department'].dropna().unique().tolist())
        selected_department = st.selectbox("Filter by Department", departments, key="occ_dept_filter")
    
    with col2:
        direct_indirect = ['All'] + sorted(df['DIRECT_INDIRECT'].dropna().unique().tolist())
        selected_di = st.selectbox("Filter by Direct/Indirect", direct_indirect, key="occ_filter")
    
    filtered_df = df.copy()
    if selected_department != 'All':
        filtered_df = filtered_df[filtered_df['department'] == selected_department]
    if selected_di != 'All':
        filtered_df = filtered_df[filtered_df['DIRECT_INDIRECT'] == selected_di]
    
    # Option to show shift-wise details
    show_shift_details = st.checkbox("Show shift-wise details", value=False, key="occ_shift_details")
    
    column_config = {
        'department': st.column_config.TextColumn("Department", width="medium"),
        'occupation': st.column_config.TextColumn("Occupation", width="medium"),
        'short_name': st.column_config.TextColumn("Short Name", width="small"),
        'DIRECT_INDIRECT': st.column_config.TextColumn("D/I", width="small"),
        'VARIABLE_FIXED': st.column_config.TextColumn("V/F", width="small"),
        'total_shift_a': st.column_config.NumberColumn("Shift A", format="%.2f"),
        'total_shift_b': st.column_config.NumberColumn("Shift B", format="%.2f"),
        'total_shift_c': st.column_config.NumberColumn("Shift C", format="%.2f"),
        'total_shift_g': st.column_config.NumberColumn("Shift G", format="%.2f"),
        'total_actual': st.column_config.NumberColumn("Total Actual", format="%.2f"),
        'total_target': st.column_config.NumberColumn("Total Target", format="%.2f"),
        'total_excess_hands': st.column_config.NumberColumn("Excess", format="%.2f"),
        'total_short_hands': st.column_config.NumberColumn("Short", format="%.2f"),
    }
    
    if show_shift_details:
        display_columns = [
            'department', 'occupation', 'short_name', 'DIRECT_INDIRECT', 'VARIABLE_FIXED',
            'total_shift_a', 'total_shift_b', 'total_shift_c', 'total_shift_g',
            'total_actual', 'total_target',
            'total_excess_hands', 'total_short_hands'
        ]
    else:
        display_columns = [
            'department', 'occupation', 'short_name', 'DIRECT_INDIRECT', 'VARIABLE_FIXED',
            'total_actual', 'total_target',
            'total_excess_hands', 'total_short_hands'
        ]
    
    st.dataframe(
        filtered_df[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config=column_config
    )
    
    # Summary metrics
    st.markdown("### Overall Totals")
    
    # Calculate Direct and Indirect totals from unfiltered df
    direct_total = df[df['DIRECT_INDIRECT'] == 'D']['total_actual'].sum() if 'D' in df['DIRECT_INDIRECT'].values else 0
    indirect_total = df[df['DIRECT_INDIRECT'] == 'I']['total_actual'].sum() if 'I' in df['DIRECT_INDIRECT'].values else 0
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("Occupations", len(filtered_df))
    with col2:
        st.metric("Total Actual", f"{filtered_df['total_actual'].sum():.2f}")
    with col3:
        st.metric("Direct Total", f"{direct_total:.2f}")
    with col4:
        st.metric("Indirect Total", f"{indirect_total:.2f}")
    with col5:
        st.metric("Total Excess", f"{filtered_df['total_excess_hands'].sum():.2f}")
    with col6:
        st.metric("Total Short", f"{filtered_df['total_short_hands'].sum():.2f}")


def display_department_summary(start_date, end_date):
    """Display department-wise summary table."""
    
    dept_df = get_hand_summary_by_department(start_date, end_date)
    
    if dept_df.empty:
        st.info("No department data available.")
        return
    
    # Filter for Direct/Indirect
    direct_indirect_options = ['All'] + sorted(dept_df['DIRECT_INDIRECT'].dropna().unique().tolist())
    selected_di = st.selectbox("Filter by Direct/Indirect", direct_indirect_options, key="dept_di_filter")
    
    # Apply filter
    if selected_di != 'All':
        dept_df = dept_df[dept_df['DIRECT_INDIRECT'] == selected_di]
    
    # Group by department after filtering (to aggregate D and I if showing All)
    dept_df = dept_df.groupby(['dept_code', 'department'], as_index=False).agg({
        'total_shift_a': 'sum',
        'total_shift_b': 'sum',
        'total_shift_c': 'sum',
        'total_shift_g': 'sum',
        'total_target_a': 'sum',
        'total_target_b': 'sum',
        'total_target_c': 'sum',
        'total_excess_hands': 'sum',
        'total_short_hands': 'sum',
    }).sort_values('dept_code')
    
    # Calculate totals
    dept_df['total_actual'] = (dept_df['total_shift_a'] + dept_df['total_shift_b'] + 
                                dept_df['total_shift_c'] + dept_df['total_shift_g'])
    dept_df['total_target'] = (dept_df['total_target_a'] + dept_df['total_target_b'] + 
                                dept_df['total_target_c'])
    
    # Add grand total row
    grand_total = pd.DataFrame([{
        'department': 'GRAND TOTAL',
        'total_shift_a': dept_df['total_shift_a'].sum(),
        'total_shift_b': dept_df['total_shift_b'].sum(),
        'total_shift_c': dept_df['total_shift_c'].sum(),
        'total_shift_g': dept_df['total_shift_g'].sum(),
        'total_target_a': dept_df['total_target_a'].sum(),
        'total_target_b': dept_df['total_target_b'].sum(),
        'total_target_c': dept_df['total_target_c'].sum(),
        'total_excess_hands': dept_df['total_excess_hands'].sum(),
        'total_short_hands': dept_df['total_short_hands'].sum(),
        'total_actual': dept_df['total_actual'].sum(),
        'total_target': dept_df['total_target'].sum(),
    }])
    
    dept_df = pd.concat([dept_df, grand_total], ignore_index=True)
    
    # Option to show shift-wise details
    show_shift_details = st.checkbox("Show shift-wise details", value=False, key="dept_shift_details")
    
    column_config = {
        'department': st.column_config.TextColumn("Department", width="medium"),
        'total_shift_a': st.column_config.NumberColumn("Shift A", format="%.2f"),
        'total_shift_b': st.column_config.NumberColumn("Shift B", format="%.2f"),
        'total_shift_c': st.column_config.NumberColumn("Shift C", format="%.2f"),
        'total_shift_g': st.column_config.NumberColumn("Shift G", format="%.2f"),
        'total_actual': st.column_config.NumberColumn("Total Actual", format="%.2f"),
        'total_target': st.column_config.NumberColumn("Total Target", format="%.2f"),
        'total_excess_hands': st.column_config.NumberColumn("Excess", format="%.2f"),
        'total_short_hands': st.column_config.NumberColumn("Short", format="%.2f"),
    }
    
    if show_shift_details:
        display_columns = [
            'department', 'total_shift_a', 'total_shift_b', 'total_shift_c', 'total_shift_g',
            'total_actual', 'total_target', 'total_excess_hands', 'total_short_hands'
        ]
    else:
        display_columns = [
            'department', 'total_actual', 'total_target', 'total_excess_hands', 'total_short_hands'
        ]
    
    st.dataframe(
        dept_df[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config=column_config
    )
