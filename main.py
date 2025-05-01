import streamlit as st
from doff10.doff10 import doff10
from wvg.wvg import weaving_page



def about_page():
    st.title("About")
    st.write("This is a multipage Streamlit app for viewing Dofftable data.")




# Sidebar navigation
st.sidebar.title("Navigation")
pages = {
    "Doff10": doff10,
    "About": about_page,
    "Weaving": weaving_page
    }
selection = st.sidebar.radio("Go to", list(pages.keys()))
pages[selection]()