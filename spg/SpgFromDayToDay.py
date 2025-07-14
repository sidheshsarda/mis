import streamlit as st
import datetime
from spg.query import spg_details_date


def spg_from_day_to_day_view():

    st.title("SPG From Day To Day Efficiency Details")
    
    # Date input for selecting the day
    selected_date = st.date_input("Select Date", value=datetime.date.today())
    
    if selected_date:
        # Convert selected date to string in YYYY-MM-DD format for the query
        selected_date_str = selected_date.strftime("%Y-%m-%d")
        
        # Query the data
        df, _ = spg_details_date(selected_date_str)
        
        if not df.empty:
            st.dataframe(df, hide_index=True)
        else:
            st.info("No data available for the selected date.")






