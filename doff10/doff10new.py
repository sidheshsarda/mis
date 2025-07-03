


import streamlit as st
from doff10.query import get_doff_details

def doff_details():
    st.subheader("Doff Details Summary")
    selected_date4 = st.date_input("Select Doff Date for Details", key="selected_date4")
    if selected_date4:
        details_df, details_json = get_doff_details(selected_date4)
        # st.subheader("JSON Output")
        # st.code(details_json, language="json")
        st.subheader("Doff Details Table")
        st.dataframe(details_df)
        
        # Add summary statistics
        if not details_df.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Spells", details_df['spell'].nunique())
            with col2:
                st.metric("Total Frames", details_df['frameno'].nunique())
            with col3:
                st.metric("Total Netwt", f"{details_df['netwt'].sum():,.0f}")
            
            # Add a chart showing netwt by spell
            st.subheader("Netwt by Spell")
            spell_summary = details_df.groupby('spell')['netwt'].sum().reset_index()
            st.bar_chart(spell_summary.set_index('spell'))

    
        