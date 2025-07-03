import streamlit as st
from doff10.doff10 import doff10
from wvg.wvg import weaving_page
from doff10.doff10new import doff_details
from overall.dailySummary import daily_summary



def about_page():
    st.title("About")
    st.write("This is a multipage Streamlit app for viewing Dofftable data.")




# Sidebar navigation
st.sidebar.title("Navigation")
pages = {
    "Doff10": doff10,
    "About": about_page,
    "Weaving": weaving_page,
    "Doff Details": doff_details,
    "Daily Summary": daily_summary,
    }
selection = st.sidebar.radio("Go to", list(pages.keys()))
pages[selection]()