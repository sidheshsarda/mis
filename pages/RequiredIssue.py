import streamlit as st
import datetime
import pandas as pd
from batching.rollestockbatchingquery import get_required_issue, get_maturity_hours, get_jute_quality
from batching.spreaderprodentry import fetch_bins_with_stock

st.set_page_config(page_title="Required Issue", page_icon="📅", layout="wide")
st.title("Required Issue")

def_date = datetime.date(2025, 9, 15)
selected_date = st.date_input("Select Date", def_date, key="req_issue_date")

# Format date as yyyy-mm-dd for SQL
sql_date = selected_date.strftime("%Y-%m-%d")

# Fetch data
with st.spinner("Loading required issue data..."):
    df = get_required_issue(sql_date)

if not df.empty:
    # Only keep relevant columns
    df = df[['yarn_type', 'jute_quality', 'percentage']]
    # Group by yarn_type
    yarn_types = df['yarn_type'].unique().tolist()
    st.markdown("### Required Issue Table")
    # Store all required issues for summary
    all_required_issues = []
    for yarn in yarn_types:
        st.markdown(f"**Yarn Type: {yarn}**")
        # Input for expected production for this yarn type
        exp_prod = st.number_input(f"Expected Production for {yarn}", min_value=0.0, step=1.0, key=f"exp_prod_{yarn}")
        # Subset for this yarn type
        subdf = df[df['yarn_type'] == yarn].copy()
        # Calculate required issue
        if exp_prod > 0:
            subdf['Required Issue'] = (subdf['percentage'] * exp_prod / 100).round(2)
        else:
            subdf['Required Issue'] = 0.0
        all_required_issues.append(subdf[['jute_quality', 'Required Issue']])
        # Display table
        st.dataframe(subdf[['jute_quality', 'percentage', 'Required Issue']], use_container_width=True, hide_index=True)
    # --- Summary Table ---
    if all_required_issues:
        summary_df = pd.concat(all_required_issues)
        # Try to get jute_quality_id for each jute_quality
        if 'jute_quality_id' in df.columns:
            jq_map = df[['jute_quality', 'jute_quality_id']].drop_duplicates().set_index('jute_quality')['jute_quality_id'].to_dict()
        else:
            jq_master = get_jute_quality()
            jq_map = jq_master.set_index('jute_quality')['id'].to_dict()
        summary_df['jute_quality_id'] = summary_df['jute_quality'].map(jq_map)
        # Get maturity hours from get_maturity_hours
        jq_maturity_df = get_maturity_hours()
        maturity_map = jq_maturity_df.set_index('jute_quality_id')['maturity_hours'].to_dict() if not jq_maturity_df.empty else {}
        summary_df['maturity_hours'] = summary_df['jute_quality_id'].map(maturity_map)
        summary_df['maturity_hours'] = summary_df['maturity_hours'].fillna(48)
        summary = summary_df.groupby(['jute_quality', 'jute_quality_id', 'maturity_hours'], as_index=False)['Required Issue'].sum()
        summary = summary.rename(columns={'Required Issue': 'Total Required Issue'})
        summary['Roll Requirement'] = ((summary['Total Required Issue'] * 1000 / 58) * (summary['maturity_hours'] / 24)).round(0).astype(int)
        # --- Add current roll stock ---
        # Get current roll stock from SpreaderProductionEntry.py's summary table
        stock_df = fetch_bins_with_stock()
        jq_master = get_jute_quality()
        jqid_to_name = jq_master.set_index('id')['jute_quality'].to_dict()
        if not stock_df.empty:
            # Map jute_quality_id to current rolls
            jq_map_stock = jq_master.set_index('id')['jute_quality'].to_dict()
            stock_df['jute_quality'] = stock_df['jute_quality_id'].map(jq_map_stock)
            stock_df['Current Rolls'] = stock_df['no_of_rolls'] - stock_df['issue_rolls'].fillna(0)
            stock_summary = stock_df.groupby('jute_quality_id', as_index=False)['Current Rolls'].sum()
            stock_map = stock_summary.set_index('jute_quality_id')['Current Rolls'].to_dict()
        else:
            stock_map = {}
        # Add current roll stock to summary, add missing jute_quality_ids if needed
        summary['Current Roll Stock'] = summary['jute_quality_id'].map(stock_map).fillna(0).astype(int)
        # Ensure all jute qualities in current roll stock are included
        # Get all unique jute_quality_id and jute_quality from stock
        if not stock_df.empty:
            stock_df['Current Rolls'] = stock_df['no_of_rolls'] - stock_df['issue_rolls'].fillna(0)
            stock_summary = stock_df.groupby('jute_quality_id', as_index=False)['Current Rolls'].sum()
            stock_summary['jute_quality'] = stock_summary['jute_quality_id'].map(jqid_to_name)
            # Merge with summary on jute_quality_id
            summary = pd.merge(summary, stock_summary[['jute_quality_id', 'Current Rolls', 'jute_quality']], on='jute_quality_id', how='outer', suffixes=('', '_stock'))
            # Fill missing columns
            summary['jute_quality'] = summary['jute_quality'].combine_first(summary['jute_quality_stock'])
            summary['Current Roll Stock'] = summary['Current Roll Stock'].combine_first(summary['Current Rolls']).fillna(0).astype(int)
            summary = summary.drop(columns=['Current Rolls', 'jute_quality_stock'], errors='ignore')
            # Fill missing values for other columns
            for col in ['Total Required Issue', 'maturity_hours', 'Roll Requirement']:
                if col in summary:
                    summary[col] = summary[col].fillna(0)
        # Filter: only show if either required issue > 0 or current roll stock > 0
        summary = summary[(summary['Total Required Issue'] > 0) | (summary['Current Roll Stock'] > 0)]
        # Sort by Roll Requirement descending
        summary = summary.sort_values('Roll Requirement', ascending=False)
        # Add Roll Stock Short and Stock Short (MT)
        summary['Roll Stock Short'] = summary['Roll Requirement'] - summary['Current Roll Stock']
        summary['Roll Stock Short'] = summary['Roll Stock Short'].apply(lambda x: x if x > 0 else 0)
        summary['Stock Short (MT)'] = (summary['Roll Stock Short'] * 58/1000).round(2)
        summary['Stock Short (MT)'] = summary['Stock Short (MT)'].apply(lambda x: x if x > 0 else 0)
        summary['Issue Required (MT)'] = (summary['Stock Short (MT)'] + summary['Total Required Issue']).round(2)
        st.markdown("### Jute Quality-wise Required Issue Summary")
        st.dataframe(summary[['jute_quality', 'Total Required Issue', 'maturity_hours', 'Roll Requirement', 'Current Roll Stock', 'Roll Stock Short', 'Stock Short (MT)', 'Issue Required (MT)']], use_container_width=True, hide_index=True)
else:
    st.info("No required issue data for the selected date.")
