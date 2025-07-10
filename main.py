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
<a class="icon-btn" href="/Doff_Details" target="_self">📋<span>Doff Details</span></a>
<a class="icon-btn" href="/Daily_Summary" target="_self">📊<span>Daily Summary</span></a>
""", unsafe_allow_html=True)

# --- Sidebar with S4 Reports submenu ---
st.sidebar.title("Navigation")
main_menu = st.sidebar.selectbox("Main Menu", ["General", "S4 Reports"])

if main_menu == "General":
    st.sidebar.markdown("- [Doff10](/Doff10)")
    st.sidebar.markdown("- [Doff Details](/Doff_Details)")
    st.sidebar.markdown("- [Daily Summary](/Daily_Summary)")
elif main_menu == "S4 Reports":
    s4_pages = [
        ("S4reportDay", "S4 Report Daywise"),
        ("S4ReportTodate", "S4 Report To-Date"),
        ("S4FromDayToDay", "S4 From Day To Day"),
    ]
    for page, label in s4_pages:
        st.sidebar.markdown(f"- [{label}](/" + page + ")")

st.info("Use the sidebar or the icon buttons above to navigate between pages.")