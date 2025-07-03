import streamlit as st
from doff10.query import get_dofftable_data, get_dofftable_sum_by_date, get_dofftable_withname

# Define each page as a function
def doff10():
    st.title("Dofftable Data Viewer")
    selected_date = st.date_input("Select Doff Date")
    if selected_date:
        df, json_output = get_dofftable_data(selected_date)
        st.subheader("JSON Output")
        st.code(json_output, language="json")

        # Add cards for q_code wise sum of netwt in each spell
        st.subheader("Q_Code Wise Netwt Sum by Spell")
        if not df.empty:
            # Pivot so that spells are rows and q_codes are columns
            pivot = (
            df.pivot_table(
                index="quality_name",
                columns="spell",
                values="netwt",
                aggfunc="sum",
                fill_value=0,
            )
            .sort_index()
            .sort_index(axis=1)
            )

            # Add row‑wise totals
            pivot["Total"] = pivot.sum(axis=1)

            # Add column‑wise totals
            total_row = pivot.sum(axis=0)
            total_row.name = "Total"
            # Add the total row without using the deprecated .append()
            pivot.loc["Total"] = total_row

            st.dataframe(pivot)

        st.subheader("Table Output")

        # --- Frame No. selector -------------------------------------------------
        frameno_list = sorted(df["frameno"].unique().tolist())
        selected_frameno = st.selectbox("Select Frame No", frameno_list, key="frameno")

        # --- Filter DataFrame by the chosen Frame No. ---------------------------
        filtered_df = df[df["frameno"] == selected_frameno]

        # ------------------------------------------------------------------------
        st.dataframe(filtered_df)

    # --- New Section: Doffdate-wise Netwt Sum (Range) ---
    st.subheader("Doffdate-wise Netwt Sum (Range)")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", key="start_date")
    with col2:
        end_date = st.date_input("End Date", key="end_date")
    if start_date and end_date and start_date <= end_date:
        sum_df, sum_json = get_dofftable_sum_by_date(start_date, end_date)
        st.code(sum_json, language="json")
        st.dataframe(sum_df)


    st.subheader("Dofftable with Worker Name")
    selected_date3 = st.date_input("Select Doff Date3", key="selected_date")
    if selected_date3:
        abc, json_output = get_dofftable_withname(selected_date3)
        st.dataframe(abc)

    
        