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
    # st.write("Sheet columns:", list(df.columns))
    # Try to use the correct date column (show a selectbox for user to pick if unsure)
    date_col = st.selectbox("Select the Date column", list(df.columns), index=1)
    # Single date selector
    if not df.empty:
        all_dates = pd.to_datetime(df[date_col], errors='coerce').dt.date.dropna().unique()
        if len(all_dates) > 0:
            default_date = max(all_dates)
        else:
            default_date = pd.to_datetime('today').date()
        selected_date = st.date_input("Select Date", value=default_date, min_value=min(all_dates), max_value=max(all_dates), key="gs_date")
        # Filter by selected date
        mask = pd.to_datetime(df[date_col], errors='coerce').dt.date == selected_date
        filtered = df[mask]
        # Columns to display
        display_cols = [col for col in ["Date", "Quality", "Wt /450 yds in Gms1", "MR"] if col in filtered.columns]
        filtered_display = filtered[display_cols]
        # st.dataframe(filtered_display)
        # Group by Quality and calculate averages
        if not filtered_display.empty:
            grouped = filtered_display.groupby("Quality").agg({
                "Wt /450 yds in Gms1": lambda x: pd.to_numeric(x, errors='coerce').mean(),
                "MR": lambda x: pd.to_numeric(x, errors='coerce').mean()
            }).reset_index()
            grouped = grouped.rename(columns={
                "Wt /450 yds in Gms1": "Avg Wt /450 yds in Gms1",
                "MR": "Avg MR"
            })
            grouped["Avg MR"] = grouped["Avg MR"].apply(lambda x: round(x, 2) if pd.notnull(x) else None)
            grouped["Observed Count (Lbs)"] = grouped["Avg Wt /450 yds in Gms1"].apply(lambda k: round((k / 450) * 14400 / 454, 2) if pd.notnull(k) else None)
            # --- Read STD parameters from the STD worksheet ---
            std_count_df = pd.DataFrame()
            std_mr_df = pd.DataFrame()
            try:
                std_sheet = gc.open("new R-08-16 Yarn Parameter Entry (Responses)").worksheet("STD")
                std_values = std_sheet.get_all_values()
                # Table 1: Quality-wise std count (columns A and B)
                std_count_data = [[row[0], row[1]] for row in std_values[1:] if len(row) > 1 and row[0] and row[1]]
                std_count_df = pd.DataFrame(std_count_data, columns=["Quality", "Std Count"])
                # Table 2: Quality-wise std MR% (columns D and E)
                std_mr_data = [[row[3], row[4]] for row in std_values[1:] if len(row) > 4 and row[3] and row[4]]
                std_mr_df = pd.DataFrame(std_mr_data, columns=["Quality", "Std MR%"])
            except Exception as e:
                st.error(f"Error loading STD parameters: {e}")
            # Merge STD columns into the grouped table (unique Quality only)
            if not grouped.empty and not std_count_df.empty and not std_mr_df.empty:
                # Drop duplicates in std_count_df and std_mr_df to ensure unique Quality
                std_count_df = std_count_df.drop_duplicates(subset=["Quality"])
                std_mr_df = std_mr_df.drop_duplicates(subset=["Quality"])
                merged = grouped.merge(std_count_df, on="Quality", how="left")
                merged = merged.merge(std_mr_df, on="Quality", how="left")
                # Remove columns that look like serial numbers or 'Avg Wt /450 yds in Gms1'
                drop_cols = [col for col in merged.columns if 'sr' in col.lower() or 'serial' in col.lower() or col == 'Avg Wt /450 yds in Gms1']
                merged = merged.drop(columns=drop_cols, errors='ignore')
                # Calculate Corr Count column
                if all(col in merged.columns for col in ["Observed Count (Lbs)", "Avg MR", "Std MR%"]):
                    merged["Corr Count"] = merged.apply(
                        lambda row: round(
                            float(row["Observed Count (Lbs)"]) * (100 + float(row["Avg MR"])) / (100 + float(row["Std MR%"])), 2
                        ) if pd.notnull(row["Observed Count (Lbs)"]) and pd.notnull(row["Avg MR"]) and pd.notnull(row["Std MR%"])
                        else None,
                        axis=1
                    )
                    # Calculate Hvy/Light % column
                    if "Std Count" in merged.columns:
                        merged["Hvy/Light %"] = merged.apply(
                            lambda row: f"{round(((float(row['Corr Count']) - float(row['Std Count'])) / float(row['Std Count']) * 100), 2)}%" if pd.notnull(row["Corr Count"]) and pd.notnull(row["Std Count"]) and float(row["Std Count"]) != 0 else None,
                            axis=1
                        )
                    # Insert Corr Count and Hvy/Light % after Observed Count (Lbs), exclude Std MR%
                    col_order = ["Quality", "Std Count", "Observed Count (Lbs)", "Corr Count", "Hvy/Light %", "Avg MR"]
                    merged = merged[[col for col in col_order if col in merged.columns]]
                st.subheader("Summary with STD Parameters")
                st.dataframe(merged, hide_index=True)
        else:
            st.info("No data for selected date.")
    else:
        st.info("Sheet is empty.")
except Exception as e:
    st.error(f"Error: {e}")