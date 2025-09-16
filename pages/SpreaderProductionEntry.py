import datetime
import streamlit as st
import pandas as pd
from batching.spreaderprodentry import (
    insert_spreader_prod_entry,
    fetch_bins_with_stock,
)
from batching.rollestockbatchingquery import get_bin_no, get_jute_quality, get_maturity_hours

st.set_page_config(page_title="Spreader Production Entry", page_icon="🧵", layout="wide")

st.title("Spreader Production Entry")

# --- Load dropdown options ---
bin_options = get_bin_no()
jq_df = get_jute_quality()
jq_options = jq_df['jute_quality'].tolist()
# Use 'id' instead of 'jute_quality_id'
jq_id_map = dict(zip(jq_df['jute_quality'], jq_df['id']))

# --- Quality-wise roll stock summary ---
stock_df = fetch_bins_with_stock()
if not stock_df.empty:
    jq_map = dict(zip(jq_df['id'], jq_df['jute_quality']))
    stock_df['Jute Quality'] = stock_df['jute_quality_id'].map(jq_map)
    stock_df['Current Rolls'] = stock_df['no_of_rolls'] - stock_df['issue_rolls'].fillna(0)
    summary = stock_df.groupby('Jute Quality', as_index=False)['Current Rolls'].sum()
    summary['Quantity (MT)'] = (summary['Current Rolls'] * 58 / 1000).round(2)
    # Add total row
    total_rolls = summary['Current Rolls'].sum()
    total_mt = summary['Quantity (MT)'].sum().round(2)
    total_row = pd.DataFrame({'Jute Quality': ['Total'], 'Current Rolls': [total_rolls], 'Quantity (MT)': [total_mt]})
    summary = pd.concat([summary, total_row], ignore_index=True)
    st.markdown("#### Current Roll Stock (Quality-wise)")
    st.dataframe(summary, use_container_width=True, hide_index=True)
else:
    st.markdown("#### Current Roll Stock (Quality-wise)")
    st.info("No bins with stock.")

# --- Form for new entry ---
# Only allow bins not in bins_with_stock
empty_bins = [b for b in bin_options if b not in (stock_df['bin_no'].tolist() if not stock_df.empty else [])]
with st.form("spreader_prod_entry_form", clear_on_submit=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        entry_date = st.date_input("Entry Date", datetime.date.today(), key="spe_entry_date")
        spell = st.selectbox("Spell", ["A1", "A2", "B1", "B2", "C"], index=0, key="spe_spell")
    with col2:
        spreader_no = st.selectbox("Spreader No", [1, 2, 3, 4, 5], key="spe_spreader_no")
        # Jute quality dropdown
        jute_quality_display = st.selectbox("Jute Quality", jq_options, key="spe_quality_display")
        jute_quality_id = jq_id_map.get(jute_quality_display, 0)
    with col3:
        no_of_rolls = st.number_input("No. of Rolls", min_value=0, step=1, value=24, key="spe_no_of_rolls")
        now_hour = int(datetime.datetime.now().replace(minute=30 if datetime.datetime.now().minute >= 30 else 0).hour)
        entry_time = st.number_input("Entry Time (hour, 0-23)", min_value=0, max_value=23, step=1, value=now_hour, key="spe_entry_time")
    with col4:
        # Bin no dropdown (only bins with zero stock)
        bin_no = st.selectbox("Bin No", empty_bins, key="spe_bin_no")
        st.write("")
        submitted = st.form_submit_button("Save Entry")

    if submitted:
        # Basic validation
        errors = []
        if spreader_no is None or spreader_no == "":
            errors.append("Spreader No must be selected.")
        if jute_quality_id <= 0:
            errors.append("Jute Quality must be selected.")
        if no_of_rolls <= 0:
            errors.append("No. of Rolls must be > 0.")
        if entry_time < 0:
            errors.append("Entry Time cannot be negative.")
        if bin_no is None or bin_no == "":
            errors.append("Bin No must be selected.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            rid = insert_spreader_prod_entry(
                entry_date=entry_date,
                spell=spell,
                spreader_no=str(spreader_no),
                jute_quality_id=int(jute_quality_id),
                no_of_rolls=int(no_of_rolls),
                entry_time=int(entry_time),
                bin_no=int(bin_no),
            )
            if rid is not None:
                st.success(f"Saved with ID {rid}")
                st.toast("Entry saved", icon="✅")
                st.session_state["_spe_refresh_key"] = st.session_state.get("_spe_refresh_key", 0) + 1
                st.rerun()
            else:
                st.warning("Saved entry but couldn't retrieve insert id.")

# --- Display bins with current stock and maturity ---
st.markdown("---")
st.subheader("Bins With Current Stock")

# Quality filter buttons
if not stock_df.empty:
    available_qualities = stock_df['Jute Quality'].unique().tolist()
    if 'selected_qualities' not in st.session_state:
        st.session_state['selected_qualities'] = []
    cols = st.columns(len(available_qualities))
    for i, q in enumerate(available_qualities):
        if q in st.session_state['selected_qualities']:
            btn_label = f"✅ {q}"
        else:
            btn_label = q
        if cols[i].button(btn_label, key=f"quality_btn_{q}"):
            if q in st.session_state['selected_qualities']:
                st.session_state['selected_qualities'].remove(q)
            else:
                st.session_state['selected_qualities'].append(q)
            st.rerun()
    # Filter stock_df if any qualities selected
    if st.session_state['selected_qualities']:
        filtered_stock_df = stock_df[stock_df['Jute Quality'].isin(st.session_state['selected_qualities'])]
    else:
        filtered_stock_df = stock_df
else:
    filtered_stock_df = stock_df

if not filtered_stock_df.empty:
    # Calculate maturity (hours in bin)
    now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
    def calc_maturity(row):
        entry_dt = datetime.datetime.combine(row['entry_date'], datetime.time(hour=row['entry_time']))
        delta = now - entry_dt
        return max(int(delta.total_seconds() // 3600), 0)
    filtered_stock_df['Maturity (hrs)'] = filtered_stock_df.apply(calc_maturity, axis=1)
    jq_map = dict(zip(jq_df['id'], jq_df['jute_quality']))
    filtered_stock_df['Jute Quality'] = filtered_stock_df['jute_quality_id'].map(jq_map)
    maturity_df = get_maturity_hours()
    if isinstance(maturity_df, pd.DataFrame):
        maturity_map = dict(zip(maturity_df['jute_quality_id'], maturity_df['maturity_hours']))
    else:
        maturity_map = {}
    filtered_stock_df['Target Maturity (hrs)'] = filtered_stock_df['jute_quality_id'].map(maturity_map).fillna(48).astype(int)
    # Sort by Maturity (hrs) descending
    filtered_stock_df = filtered_stock_df.sort_values('Maturity (hrs)', ascending=False)
    # Add 'Rolls' column for current stock
    filtered_stock_df['Rolls'] = filtered_stock_df['no_of_rolls'] - filtered_stock_df['issue_rolls'].fillna(0)
    show_df = filtered_stock_df.rename(columns={
        'bin_no': 'Bin No',
        'Jute Quality': 'Jute Quality',
        'Rolls': 'Rolls',
        'Maturity (hrs)': 'Maturity (hrs)',
        'Target Maturity (hrs)': 'Target Maturity (hrs)',
    })
    # Conditional formatting
    def highlight_row(row):
        actual = row['Maturity (hrs)']
        target = row['Target Maturity (hrs)']
        style = [''] * len(row)
        # Only highlight the 'Maturity (hrs)' cell
        idx = list(row.index).index('Maturity (hrs)')
        if abs(actual - target) <= 2:
            style[idx] = 'background-color: #d4edda'  # green
        elif actual < target:
            style[idx] = 'background-color: #f8d7da'  # red
        else:
            style[idx] = 'background-color: #fff3cd'  # yellow
        return style
    # Limit rows displayed with slider
    max_rows = len(show_df)
    default_rows = 15
    if max_rows > default_rows:
        num_rows = st.slider("Rows to display", min_value=default_rows, max_value=max_rows, value=default_rows, step=1, key="bins_rows_slider")
    else:
        num_rows = max_rows
    # Slice before styling
    show_df_limited = show_df.head(num_rows)
    styled_df = show_df_limited[['Bin No', 'Jute Quality', 'Rolls', 'Maturity (hrs)', 'Target Maturity (hrs)']].style.apply(highlight_row, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    bins_with_stock = show_df['Bin No'].tolist()
else:
    st.info("No bins with stock.")
    bins_with_stock = []

# --- Issue entry section ---
st.markdown("---")
st.subheader("Bin Issue Entry")

# Prepare bin info for autofill
if not stock_df.empty:
    bin_info = stock_df.set_index('bin_no').to_dict('index')
else:
    bin_info = {}

with st.form("bin_issue_form", clear_on_submit=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        issue_bin_no = st.selectbox("Bin No (to issue)", bins_with_stock, key="issue_bin_no")
        issue_date = st.date_input("Issue Date", datetime.date.today(), key="issue_date")
    with col2:
        issue_spell = st.selectbox("Issue Spell", ["A1", "A2", "B1", "B2", "C"], index=0, key="issue_spell")
        # Default to current hour
        now_hour = int(datetime.datetime.now().replace(minute=30 if datetime.datetime.now().minute >= 30 else 0).hour)
        issue_time = st.number_input("Issue Time (hour, 0-23)", min_value=0, max_value=23, step=1, value=now_hour, key="issue_time")
    with col3:
        # Autofill jute quality from selected bin, not editable
        if issue_bin_no in bin_info:
            jq_id = bin_info[issue_bin_no]['jute_quality_id']
            jq_display = jq_df[jq_df['id'] == jq_id]['jute_quality'].values[0] if not jq_df[jq_df['id'] == jq_id].empty else str(jq_id)
        else:
            jq_display = ""
        st.text_input("Jute Quality (auto)", value=jq_display, disabled=True, key="issue_jute_quality_display")
        issue_rolls = st.number_input("Issue Rolls", min_value=0, step=1, key="issue_rolls")
    with col4:
        st.write("")
        issue_submitted = st.form_submit_button("Save Issue Entry")

    if issue_submitted:
        from batching.spreaderprodentry import update_issue_for_bin
        errors = []
        if issue_bin_no is None or issue_bin_no == "":
            errors.append("Bin No must be selected.")
        if issue_rolls <= 0:
            errors.append("Issue Rolls must be > 0.")
        if errors:
            for e in errors:
                st.error(e)
        else:
            update_issue_for_bin(
                bin_no=int(issue_bin_no),
                issue_date=issue_date,
                issue_time=int(issue_time),
                issue_spell=issue_spell,
                issue_rolls=int(issue_rolls),
            )
            st.success(f"Issue entry saved for Bin {issue_bin_no}")
            st.toast("Issue entry saved", icon="✅")
            st.session_state["_spe_refresh_key"] = st.session_state.get("_spe_refresh_key", 0) + 1
            st.rerun()
