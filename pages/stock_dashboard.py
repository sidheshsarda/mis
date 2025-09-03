import streamlit as st
import pandas as pd
import yfinance as yf

st.title("Stock Market Day Trader Dashboard (NSE/BSE)")

# Company selection
company_dict = {
    'RELIANCE': 'RELIANCE.NS',
    'TCS': 'TCS.NS',
    'INFY': 'INFY.NS',
    'HDFC BANK': 'HDFCBANK.NS',
    'SBIN': 'SBIN.NS',
    'ICICI BANK': 'ICICIBANK.NS',
    'HDFC': 'HDFC.NS',
    'LT': 'LT.NS',
    'AXIS BANK': 'AXISBANK.NS',
    'ITC': 'ITC.NS',
    'BSE': 'BSE.BO',
    'NSE': 'NSE.BO'
}
company = st.selectbox("Select Company", list(company_dict.keys()))
symbol = company_dict[company]

# Date range selection
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", value=pd.Timestamp.today() - pd.Timedelta(days=7))
with col2:
    end_date = st.date_input("End Date", value=pd.Timestamp.today())

if start_date and end_date and start_date <= end_date:
    # Fetch stock data
    data = yf.download(symbol, start=start_date, end=end_date)
    if not data.empty:
        st.subheader(f"{company} ({symbol}) Stock Data")
        # Flatten multi-index columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [' '.join([str(i) for i in col if i]) for col in data.columns.values]
        # Find columns for display
        display_cols = [col for col in data.columns if any(x in col for x in ['Open', 'High', 'Low', 'Close', 'Volume'])]
        st.dataframe(data[display_cols])
        # Use scalar values for metrics, handle empty data
        high_col = next((col for col in data.columns if 'High' in col), None)
        low_col = next((col for col in data.columns if 'Low' in col), None)
        close_col = next((col for col in data.columns if 'Close' in col), None)
        open_col = next((col for col in data.columns if 'Open' in col), None)
        vol_col = next((col for col in data.columns if 'Volume' in col), None)
        high_val = float(data[high_col].max()) if high_col and not data[high_col].empty else 0.0
        low_val = float(data[low_col].min()) if low_col and not data[low_col].empty else 0.0
        close_val = float(data[close_col].iloc[-1]) if close_col and not data[close_col].empty else 0.0
        open_val = float(data[open_col].iloc[0]) if open_col and not data[open_col].empty else 0.0
        total_vol = int(data[vol_col].sum()) if vol_col and not data[vol_col].empty else 0
        st.metric("Day's High", f"₹ {high_val:,.2f}")
        st.metric("Day's Low", f"₹ {low_val:,.2f}")
        st.metric("Day's Close", f"₹ {close_val:,.2f}")
        st.metric("Day's Open", f"₹ {open_val:,.2f}")
        st.metric("Total Volume", f"{total_vol:,}")
        chart_cols = [c for c in display_cols if any(x in c for x in ['Open', 'High', 'Low', 'Close'])]
        st.line_chart(data[chart_cols])
    else:
        st.warning("No data found for selected company and date range.")
