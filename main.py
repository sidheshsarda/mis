import streamlit as st

st.title("MIS Dashboard")

st.markdown("""
<style>
.icon-btn {
    display: inline-block;
    margin: 0 20px 20px 0;
    text-align: center;
    font-size: 2.2em;
    text-decoration: none;
    color: inherit;
}
.icon-btn span {
    display: block;
    font-size: 0.7em;
    margin-top: 0.2em;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<a class="icon-btn" href="/Doff10" target="_self">🧵<span>Doff10</span></a>
<a class="icon-btn" href="/Weaving" target="_self">🪡<span>Weaving</span></a>
<a class="icon-btn" href="/Doff_Details" target="_self">📋<span>Doff Details</span></a>
<a class="icon-btn" href="/Daily_Summary" target="_self">📊<span>Daily Summary</span></a>
""", unsafe_allow_html=True)

st.info("Use the sidebar or the icon buttons above to navigate between pages.")