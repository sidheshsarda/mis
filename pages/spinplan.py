"""
Streamlit application to create a spin plan for a jute mill.

This app connects to a simple SQLite database that holds information
about fabric qualities (such as fabric width, GSM and the ratio of warp
to weft yarn in the fabric) and different types of machinery used in
spinning. It allows planners at a jute mill to build a production
schedule starting from weaving and automatically calculates the yarn
requirements and machine loads down through the spinning, roving,
drawing and batching processes.

The workflow mirrors the top‑to‑bottom layout used in traditional
textile spin plans: the planner begins by entering weaving production
details (quality, number of looms, planned production length and
efficiency) and the programme progressively derives the yarn weight,
machine requirements and raw jute (batch) needed to fulfil that plan.

Several of the formulas used in this application are grounded in
textile engineering fundamentals. For example, fabric weight per unit
area (GSM) is defined as the ratio of fabric weight to its area【344131627299979†L592-L596】,
and the warp and weft yarn weights can be calculated from the number
of ends or picks, the fabric length and the yarn’s linear density【344131627299979†L599-L601】.  Loom
efficiency—used here to adjust production figures—is determined by
comparing actual production with theoretical output【344131627299979†L618-L619】.

Although the data in the accompanying database is illustrative, the
application has been designed to work with any SQL database containing
similar tables. Replace or extend the sample data to reflect your own
mill’s machines and qualities.
"""

import math
import sqlite3
from typing import List, Dict

import pandas as pd
import streamlit as st


def init_db(db_path: str = "jute_mill.db") -> None:
    """Create and populate the database if it does not already exist.

    This function is idempotent: it only inserts sample records when the
    relevant tables are empty. Feel free to replace the sample data
    with your own machine capacities or fabric qualities as needed.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Table for fabric qualities
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS qualities (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            width_m REAL,
            gsm REAL,
            warp_ratio REAL,
            weft_ratio REAL
        );
        """
    )

    # Table for machine types and capacities (kg/day)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY,
            machine_type TEXT NOT NULL,
            machine_name TEXT NOT NULL,
            capacity_kg_per_day REAL
        );
        """
    )

    # Insert sample qualities if none exist
    cur.execute("SELECT COUNT(*) FROM qualities")
    (qual_count,) = cur.fetchone()
    if qual_count == 0:
        sample_qualities = [
            # name, width_m, gsm, warp_ratio, weft_ratio
            ("Hessian", 1.22, 300.0, 0.55, 0.45),
            ("Sacking", 1.10, 200.0, 0.50, 0.50),
            ("Carpet", 2.00, 250.0, 0.60, 0.40),
        ]
        cur.executemany(
            "INSERT INTO qualities (name, width_m, gsm, warp_ratio, weft_ratio) VALUES (?, ?, ?, ?, ?)",
            sample_qualities,
        )

    # Insert sample machines if none exist
    cur.execute("SELECT COUNT(*) FROM machines")
    (mach_count,) = cur.fetchone()
    if mach_count == 0:
        sample_machines = [
            # machine_type, machine_name, capacity_kg_per_day
            ("spinning", "Spinning Frame", 200.0),
            ("roving", "Roving Frame", 300.0),
            ("drawing", "Drawing Frame", 400.0),
            ("batching", "Batching Machine", 500.0),
        ]
        cur.executemany(
            "INSERT INTO machines (machine_type, machine_name, capacity_kg_per_day) VALUES (?, ?, ?)",
            sample_machines,
        )

    conn.commit()
    conn.close()


def compute_yarn_requirements(
    weaving_df: pd.DataFrame, qualities_df: pd.DataFrame
) -> pd.DataFrame:
    """Compute yarn and fabric weights for each weaving row.

    For each row in the weaving plan the function derives the total
    production length (meters) based on the number of looms, the
    planned production per loom and the efficiency percentage. Using
    the selected quality’s width and GSM, it then calculates the
    total fabric weight, the warp yarn weight and the weft yarn weight.

    Parameters
    ----------
    weaving_df : pd.DataFrame
        DataFrame containing columns: quality_id, quality, looms,
        prod_per_loom (planned production per loom in metres) and
        efficiency.
    qualities_df : pd.DataFrame
        DataFrame of qualities with columns: id, name, width_m, gsm,
        warp_ratio and weft_ratio.

    Returns
    -------
    pd.DataFrame
        New DataFrame containing the original plan along with
        calculated fields: total_length (m), area_m2 (m²), fabric_weight
        (kg), warp_weight (kg), weft_weight (kg) and total_yarn (kg).
    """
    results: List[Dict] = []
    for _, row in weaving_df.iterrows():
        # Look up the quality parameters
        qual = qualities_df.loc[qualities_df["id"] == row["quality_id"]].iloc[0]
        width_m = float(qual["width_m"])
        gsm = float(qual["gsm"])
        warp_ratio = float(qual["warp_ratio"])
        weft_ratio = float(qual["weft_ratio"])

        # Total production length accounting for number of looms and efficiency
        total_length_m = row["looms"] * row["prod_per_loom"] * (row["efficiency"] / 100.0)

        # Fabric area in square metres
        area_m2 = total_length_m * width_m

        # Fabric weight (kg) = area (m²) × GSM (g/m²) / 1000
        fabric_weight = area_m2 * gsm / 1000.0

        # Split into warp and weft based on ratio
        warp_weight = fabric_weight * warp_ratio
        weft_weight = fabric_weight * weft_ratio
        total_yarn = warp_weight + weft_weight

        results.append({
            "quality": row["quality"],
            "looms": row["looms"],
            "prod_per_loom_m": row["prod_per_loom"],
            "efficiency_%": row["efficiency"],
            "total_length_m": total_length_m,
            "fabric_area_m2": area_m2,
            "fabric_weight_kg": fabric_weight,
            "warp_weight_kg": warp_weight,
            "weft_weight_kg": weft_weight,
            "total_yarn_kg": total_yarn,
        })

    return pd.DataFrame(results)


def main() -> None:
    """Run the Streamlit spin plan application."""
    st.set_page_config(page_title="Jute Mill Spin Plan", layout="wide")
    st.title("📜 Jute Mill Spin Plan")
    st.markdown(
        """
        This tool helps plan daily production for a jute mill. Start by entering
        weaving production details—such as the fabric quality, number of looms,
        planned production per loom and estimated efficiency. The app then
        computes fabric weight, yarn requirements and the machine load for
        spinning, roving, drawing and batching. Finally, it estimates the raw
        jute (batch) needed to fulfil the plan.
        """
    )

    # Initialise the database and connect
    init_db()
    conn = sqlite3.connect("jute_mill.db")

    # Load qualities and machines
    qualities_df = pd.read_sql_query(
        "SELECT id, name, width_m, gsm, warp_ratio, weft_ratio FROM qualities", conn
    )
    machines_df = pd.read_sql_query(
        "SELECT machine_type, machine_name, capacity_kg_per_day FROM machines", conn
    )

    # Session state to hold weaving plan rows
    if "weaving_rows" not in st.session_state:
        st.session_state.weaving_rows: List[Dict] = []

    # Section: Weaving Production Plan
    st.header("1️⃣ Weaving Production Details")
    st.write(
        "Provide details for each fabric quality being woven. "
        "Production length is per loom per day."
    )

    with st.form("add_weaving_row"):
        cols = st.columns(4)
        quality_name = cols[0].selectbox(
            "Quality",
            options=qualities_df["name"].tolist(),
            index=0,
        )
        looms = cols[1].number_input(
            "Number of looms",
            min_value=1,
            step=1,
            value=1,
        )
        prod_per_loom = cols[2].number_input(
            "Production per loom (m)",
            min_value=0.0,
            value=100.0,
        )
        efficiency = cols[3].number_input(
            "Efficiency (%)",
            min_value=0.0,
            max_value=100.0,
            value=85.0,
        )
        submitted = st.form_submit_button("Add to plan")
        if submitted:
            # Retrieve the corresponding ID for the chosen quality
            qid = int(qualities_df.loc[qualities_df["name"] == quality_name, "id"].iloc[0])
            st.session_state.weaving_rows.append(
                {
                    "quality_id": qid,
                    "quality": quality_name,
                    "looms": int(looms),
                    "prod_per_loom": float(prod_per_loom),
                    "efficiency": float(efficiency),
                }
            )
            st.success(f"Added plan for {quality_name}.")

    # Display the current weaving plan and allow editing or deletion
    if st.session_state.weaving_rows:
        st.subheader("Current weaving plan")
        weaving_df = pd.DataFrame(st.session_state.weaving_rows)
        edited_df = st.data_editor(
            weaving_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
        )
        # Update session state with any changes made through the editor
        st.session_state.weaving_rows = edited_df.to_dict("records")

        # Provide an option to clear the plan
        if st.button("🗑️ Clear plan"):
            st.session_state.weaving_rows = []
            st.info("Cleared the weaving plan.")

    # Compute yarn requirements once there are rows in the plan
    if st.session_state.weaving_rows:
        yarn_df = compute_yarn_requirements(pd.DataFrame(st.session_state.weaving_rows), qualities_df)
        st.header("2️⃣ Yarn and Fabric Requirements")
        st.dataframe(
            yarn_df[
                [
                    "quality",
                    "looms",
                    "prod_per_loom_m",
                    "efficiency_%",
                    "total_length_m",
                    "fabric_area_m2",
                    "fabric_weight_kg",
                    "warp_weight_kg",
                    "weft_weight_kg",
                    "total_yarn_kg",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        total_warp = yarn_df["warp_weight_kg"].sum()
        total_weft = yarn_df["weft_weight_kg"].sum()
        total_yarn = yarn_df["total_yarn_kg"].sum()
        st.write(
            f"**Total warp yarn:** {total_warp:.2f} kg | "
            f"**Total weft yarn:** {total_weft:.2f} kg | "
            f"**Total yarn:** {total_yarn:.2f} kg"
        )

        # Section: Machine Requirements
        st.header("3️⃣ Machine Requirements")
        machine_results = []
        for _, mach in machines_df.iterrows():
            # Determine the required production for each machine type
            if mach["machine_type"] in ["spinning", "roving", "drawing"]:
                required_kg = total_yarn
            elif mach["machine_type"] == "batching":
                # Batching is upstream of spinning; assume 10% additional for waste
                required_kg = total_yarn * 1.10
            else:
                required_kg = 0.0

            machines_needed = math.ceil(required_kg / mach["capacity_kg_per_day"]) if mach["capacity_kg_per_day"] > 0 else 0
            machine_results.append(
                {
                    "Machine Type": mach["machine_type"].capitalize(),
                    "Machine Name": mach["machine_name"],
                    "Capacity (kg/day)": mach["capacity_kg_per_day"],
                    "Required Production (kg/day)": round(required_kg, 2),
                    "Machines Needed": machines_needed,
                }
            )

        machines_calc_df = pd.DataFrame(machine_results)
        st.dataframe(
            machines_calc_df,
            use_container_width=True,
            hide_index=True,
        )

        # Section: Batch Requirement
        st.header("4️⃣ Batch Requirement (Raw Jute)")
        # Add 10% waste allowance for raw jute consumption
        batch_requirement_kg = total_yarn * 1.10
        st.write(
            f"Estimated raw jute required: **{batch_requirement_kg:.2f} kg** including 10% waste allowance."
        )

    else:
        st.info("Add at least one weaving plan entry above to compute the spin plan.")


if __name__ == "__main__":
    main()