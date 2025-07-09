import streamlit as st
import datetime
from doff10.query import get_dofftable_details
import pandas as pd

def doff10_detailed():
    st.title("Doff Table Details (Multi-Filter)")
    today = datetime.date.today()
    start_date = today.replace(day=1)
    end_date = today

    df, _ = get_dofftable_details(start_date, end_date)
    if not df.empty:
        # Filters for each column except total_netwt
        filter_cols = [col for col in df.columns if col != 'total_netwt']
        filtered_df = df.copy()
        for col in filter_cols:
            unique_vals = filtered_df[col].dropna().unique()
            if len(unique_vals) > 1:
                selected = st.multiselect(f"Filter by {col}", options=sorted(map(str, unique_vals)), default=sorted(map(str, unique_vals)))
                filtered_df = filtered_df[filtered_df[col].astype(str).isin(selected)]
        st.dataframe(filtered_df)
    else:
        st.info("No data available for the selected period.")

# To use: call doff10_detailed() in your Streamlit app
