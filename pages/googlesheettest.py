import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Load credentials
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_file(
    "C:\\code\\mis\\careful-analyst-441615-j6-ac33950f3271.json", scopes=scope
)

# Connect to Google Sheets
gc = gspread.authorize(credentials)

# Open a Google Sheet by name or by key
sheet = gc.open("trialStreamlit").sheet1  # or use .worksheet("Sheet1")

# Read data
data = sheet.get_all_records()
st.dataframe(data)

# Example: Append a new row
if st.button("Add dummy row"):
    sheet.append_row(["Test", "123", "More Data"])
    st.success("Row added!")

all_values = sheet.get_all_values()
# Header + data
headers = all_values[0]
rows = all_values[1:]

# Only rows where the first column matches the target date
target_date = "2025-07-02"
filtered_rows = [row for row in rows if row[0] == target_date]

# Convert to DataFrame
df = pd.DataFrame(filtered_rows, columns=headers)
st.dataframe(df)

# Date range selector
st.subheader("Filter and Sum by Date Range")
if rows:
    # Try to parse dates from the first column
    import datetime
    date_format = "%Y-%m-%d"
    # Get min/max date from data
    try:
        date_list = [datetime.datetime.strptime(row[0], date_format).date() for row in rows]
        min_date = min(date_list)
        max_date = max(date_list)
    except Exception:
        min_date = max_date = datetime.date.today()
    start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date, key="gs_start")
    end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date, key="gs_end")
    # Filter rows by date range
    filtered_rows = [row for row in rows if start_date <= datetime.datetime.strptime(row[0], date_format).date() <= end_date]
    df = pd.DataFrame(filtered_rows, columns=headers)
    st.dataframe(df)
    # Sum numeric columns
    if not df.empty:
        sum_row = {}
        for col in df.columns:
            try:
                sum_row[col] = pd.to_numeric(df[col], errors='coerce').sum()
            except Exception:
                sum_row[col] = ''
        sum_row[headers[0]] = 'Total'
        st.write("**Sum for selected range:**")
        st.dataframe(pd.DataFrame([sum_row], columns=headers))
else:
    st.info("No data available to filter.")