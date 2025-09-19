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
<a class="icon-btn" href="/Doff_Details" target="_self">📋<span>Doff Details</span></a>
<a class="icon-btn" href="/Daily_Summary" target="_self">📊<span>Daily Summary</span></a>
<a class="icon-btn" href="/SpreaderProductionEntry" target="_self">🧵<span>Spreader Production</span></a>
""", unsafe_allow_html=True)



# --- Sidebar with S4 Reports submenu ---
st.sidebar.title("Navigation")
main_menu = st.sidebar.selectbox("Main Menu", ["General", "S4 Reports"])

# --- Expandable menu for Weaving S4 ---
with st.expander("Weaving S4"):
    st.markdown("""
    <a class="icon-btn" href="/S4FromDayToDay" target="_self">📅<span>S4 From Day to Day</span></a>
    <a class="icon-btn" href="/S4LowProducer" target="_self">🟢<span>S4 Low Producer</span></a>
    """, unsafe_allow_html=True)

