import streamlit as st
import datetime
from WvgS4.query import S4_day_details_eff_day

def s4_eff_daywise_view():
    st.title("S4 Daywise Efficiency Details")
    selected_date = st.date_input("Select Date", value=datetime.date.today())
    if selected_date:
        df, _ = S4_day_details_eff_day(selected_date)
        if not df.empty:
            st.dataframe(df)
        else:
            st.info("No data available for the selected date.")



