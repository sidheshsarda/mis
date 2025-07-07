import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Load credentials
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_file(
    "C:\\code\\mis\\careful-analyst-441615-j6-ac33950f3271.json", scopes=scope
)

# Show service account email for sharing
st.info(f"Share your Google Sheet with: {credentials.service_account_email}")

try:
    # Connect to Google Sheets
    gc = gspread.authorize(credentials)
    # Open the Google Sheet and worksheet
    sheet = gc.open("new R-08-16 Yarn Parameter Entry (Responses)").worksheet("YARN")
    # Read data
    df = pd.DataFrame(sheet.get_all_records())
    st.write("Sheet columns:", list(df.columns))
    # Try to use the correct date column (show a selectbox for user to pick if unsure)
    date_col = st.selectbox("Select the Date column", list(df.columns), index=1)
    # Date range selector
    if not df.empty:
        min_date = pd.to_datetime(df[date_col], errors='coerce').min().date()
        max_date = pd.to_datetime(df[date_col], errors='coerce').max().date()
        start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date, key="gs_start")
        end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date, key="gs_end")
        # Filter by date range
        mask = (pd.to_datetime(df[date_col], errors='coerce').dt.date >= start_date) & (pd.to_datetime(df[date_col], errors='coerce').dt.date <= end_date)
        filtered = df[mask]
        st.dataframe(filtered)
        # Sum numeric columns
        if not filtered.empty:
            sum_row = {col: pd.to_numeric(filtered[col], errors='coerce').sum() if pd.api.types.is_numeric_dtype(filtered[col]) else '' for col in filtered.columns}
            sum_row[date_col] = 'Total'
            st.write("**Sum for selected range:**")
            st.dataframe(pd.DataFrame([sum_row], columns=filtered.columns))
        else:
            st.info("No data in selected date range.")
    else:
        st.info("Sheet is empty.")
except Exception as e:
    st.error(f"Error: {e}")