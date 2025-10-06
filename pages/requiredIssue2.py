# pages/10_Jute_Issue_Planner.py
import datetime as dt
from datetime import date, time, datetime, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import text  # works with your existing engine

# ------------------------------------------------------------------
# Replace this import with your actual engine/provider if different
# from my_project.db import engine
# ------------------------------------------------------------------

st.set_page_config(page_title="Jute Issue Planner (Snapshot)", layout="wide")

st.title("Jute Issue Planner — Point-in-Time Snapshot (06:00)")

# ------------------
# GLOBAL CONSTANTS
# ------------------
COMPANY_ID = 2
SNAPSHOT_HOUR = 6              # 06:00 local
MATURITY_TOLERANCE_HRS = 2     # ±2 hours

# ------------------
# UI — Snapshot Date
# ------------------
col_date, col_info = st.columns([1, 2], gap="large")
with col_date:
    selected_date = st.date_input(
        "Select date (snapshot is fixed at 06:00):",
        value=date.today(),
        help="We compute stock and maturity as of 06:00 on this date."
    )

with col_info:
    st.markdown(
        f"""
        **Snapshot**: {selected_date.isoformat()} at **06:00**  
        **Company**: {COMPANY_ID}  
        **Maturity tolerance**: ±{MATURITY_TOLERANCE_HRS} hours  
        **Mode**: Read-only (no write-backs)
        """
    )

# Build point-in-time timestamps (opening==closing => window sums cancel)
snapshot_dt = datetime.combine(selected_date, time(hour=SNAPSHOT_HOUR))
opening_dt_str = snapshot_dt.strftime("%Y-%m-%d %H")   # e.g. "2025-09-24 06"
closing_dt_str = opening_dt_str                         # point-in-time

# Date range for batch plan = day after selected_date → day + 4
range_start = selected_date + timedelta(days=1)
range_end = range_start + timedelta(days=4)

# ------------------
# CACHING HELPERS
# ------------------
@st.cache_data(ttl=60)  # refreshes if inputs change; tune as needed
def q1_production_by_yarn(_engine, dte: date) -> pd.DataFrame:
    sql = text("""
        SELECT 
            COALESCE(ytm.yarn_type, 'Unmapped') AS yarn_type,
            ytm.yarn_type_id,
            ROUND(SUM(d.netwt), 0) AS total_netwt
        FROM vowsls.dofftable d
        LEFT JOIN vowsls.weaving_quality_master wqm 
            ON wqm.quality_code = d.q_code 
           AND wqm.company_id = d.company_id
        LEFT JOIN vowsls.yarn_type_master ytm 
            ON ytm.company_id = d.company_id 
           AND ytm.yarn_type = wqm.yarn_type
        WHERE d.company_id = :co_id
          AND d.doffdate   = :doff_date
        GROUP BY ytm.yarn_type, ytm.yarn_type_id
        ORDER BY ytm.yarn_type;
    """)
    with _engine.connect() as cn:
        df = pd.read_sql(sql, cn, params={"co_id": COMPANY_ID, "doff_date": dte})
    # Convert to MT if your netwt is kg; adjust if units differ
    if not df.empty:
        df["total_netwt_MT"] = (df["total_netwt"] / 1000.0).round(3)
    return df

@st.cache_data(ttl=60)
def q2_batch_plan_window(_engine, start_d: date, end_d: date) -> pd.DataFrame:
    sql = text("""
        SELECT 
            bpdi.hdr_id, 
            bpdi.plan_date, 
            bpdi.batch_plan_code, 
            bpdi.yarn_type_id, 
            ytm.yarn_type
        FROM vowsls.batch_plan_daily_implement bpdi
        LEFT JOIN vowsls.yarn_type_master ytm 
               ON ytm.yarn_type_id = bpdi.yarn_type_id
        WHERE bpdi.company_id = :co_id
          AND bpdi.plan_date BETWEEN :start_d AND :end_d
          AND bpdi.is_active = 1
        ORDER BY bpdi.hdr_id DESC;
    """)
    with _engine.connect() as cn:
        df = pd.read_sql(sql, cn, params={
            "co_id": COMPANY_ID,
            "start_d": start_d,
            "end_d": end_d
        })
    return df

@st.cache_data(ttl=60)
def q3_batch_composition(_engine) -> pd.DataFrame:
    sql = text("""
        SELECT 
            bph.plan_hdr_id,
            bph.plan_code,
            bph.plan_name,
            bph.percentage,
            bpd.jute_quality_id,
            jqpm.jute_quality
        FROM vowsls.batch_plan_hdr bph
        LEFT JOIN vowsls.batch_plan_dtl bpd 
               ON bpd.batch_plan_hdr_id = bph.plan_hdr_id
              AND bpd.is_active = 1
              AND bpd.company_id = bph.company_id
        LEFT JOIN vowsls.jute_quality_price_master jqpm 
               ON jqpm.id = bpd.jute_quality_id
        WHERE bph.company_id = :co_id
          AND bph.is_active = 1;
    """)
    with _engine.connect() as cn:
        df = pd.read_sql(sql, cn, params={"co_id": COMPANY_ID})
    return df

@st.cache_data(ttl=60)
def q4_roll_stock_snapshot(_engine, opening_dt: str, closing_dt: str) -> pd.DataFrame:
    """
    Uses your existing window query. With opening==closing, window contributions are zero,
    so you effectively get 'closing stock as of snapshot'.
    """
    sql = text("""
        SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
               SUM(openstock) AS openstock,
               SUM(prodroll)  AS prodroll,
               SUM(issueroll) AS issueroll,
               SUM(openstock) + SUM(prodroll) - SUM(issueroll) AS closstock
        FROM (
            -- Opening stock from production before snapshot
            SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
                   SUM(no_of_rolls) AS openstock, 0 AS prodroll, 0 AS issueroll
            FROM (
                SELECT spe.entry_id_grp, spe.entry_date, spe.entry_time, spe.bin_no, spe.wt_per_roll,
                       spe.jute_quality_id, spe.no_of_rolls,
                       CASE WHEN spe.entry_time < 6 THEN DATE_ADD(spe.entry_date, INTERVAL -1 DAY) ELSE spe.entry_date END AS proddate
                FROM EMPMILL12.spreader_prod_entry spe
            ) sprdprod
            WHERE STR_TO_DATE(CONCAT(entry_date, ' ', entry_time), '%Y-%m-%d %H') < STR_TO_DATE(:opening_dt, '%Y-%m-%d %H')
            GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
            UNION ALL
            -- Opening stock negative adjustment from issues before snapshot
            SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
                   -SUM(no_of_rolls) AS openstock, 0 AS prodroll, 0 AS issueroll
            FROM (
                SELECT sri.entry_id_grp, spe.jute_quality_id, spe.bin_no, sri.wt_per_roll,issue_date,
                       CASE WHEN sri.issue_time < 6 THEN DATE_ADD(sri.issue_date, INTERVAL -1 DAY) ELSE sri.issue_date END AS issudate,
                       sri.issue_time, sri.no_of_rolls
                FROM EMPMILL12.spreader_roll_issue sri
                LEFT JOIN (select entry_id_grp,bin_no,jute_quality_id,sum(no_of_rolls) pdrolls
                           from EMPMILL12.spreader_prod_entry
                           group by entry_id_grp,bin_no,jute_quality_id) spe 
                       ON spe.entry_id_grp = sri.entry_id_grp
            ) sprdissu
            WHERE STR_TO_DATE(CONCAT(issue_date, ' ', issue_time), '%Y-%m-%d %H') < STR_TO_DATE(:opening_dt, '%Y-%m-%d %H')
            GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
            UNION ALL
            -- Production within window (zero when opening==closing)
            SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
                   0 AS openstock, SUM(no_of_rolls) AS prodroll, 0 AS issueroll
            FROM (
                SELECT spe.entry_id_grp, spe.entry_date, spe.entry_time, spe.bin_no, spe.wt_per_roll,
                       spe.jute_quality_id, spe.no_of_rolls,
                       CASE WHEN spe.entry_time < 6 THEN DATE_ADD(spe.entry_date, INTERVAL -1 DAY) ELSE spe.entry_date END AS proddate
                FROM EMPMILL12.spreader_prod_entry spe
            ) sprdprod2
            WHERE STR_TO_DATE(CONCAT(entry_date, ' ', entry_time), '%Y-%m-%d %H') >= STR_TO_DATE(:opening_dt, '%Y-%m-%d %H')
              AND STR_TO_DATE(CONCAT(entry_date, ' ', entry_time), '%Y-%m-%d %H') < STR_TO_DATE(:closing_dt, '%Y-%m-%d %H')
            GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
            UNION ALL
            -- Issues within window (zero when opening==closing)
            SELECT bin_no, entry_id_grp, wt_per_roll, jute_quality_id,
                   0 AS openstock, 0 AS prodroll, SUM(no_of_rolls) AS issueroll
            FROM (
                SELECT sri.entry_id_grp, spe.jute_quality_id, spe.bin_no, sri.wt_per_roll,issue_date,
                       CASE WHEN sri.issue_time < 6 THEN DATE_ADD(sri.issue_date, INTERVAL -1 DAY) ELSE sri.issue_date END AS issudate,
                       sri.issue_time, sri.no_of_rolls
                FROM EMPMILL12.spreader_roll_issue sri
                LEFT JOIN (select entry_id_grp,bin_no,jute_quality_id,sum(no_of_rolls) pdrolls
                           from EMPMILL12.spreader_prod_entry
                           group by entry_id_grp,bin_no,jute_quality_id) spe 
                       ON spe.entry_id_grp = sri.entry_id_grp
            ) sprdissu2
            WHERE STR_TO_DATE(CONCAT(issue_date, ' ', issue_time), '%Y-%m-%d %H') >= STR_TO_DATE(:opening_dt, '%Y-%m-%d %H')
              AND STR_TO_DATE(CONCAT(issue_date, ' ', issue_time), '%Y-%m-%d %H') < STR_TO_DATE(:closing_dt, '%Y-%m-%d %H')
            GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
        ) g
        GROUP BY bin_no, entry_id_grp, wt_per_roll, jute_quality_id
        HAVING closstock <> 0 OR openstock <> 0 OR prodroll <> 0 OR issueroll <> 0
        ORDER BY bin_no, entry_id_grp, wt_per_roll;
    """)
    with _engine.connect() as cn:
        df = pd.read_sql(sql, cn, params={"opening_dt": opening_dt, "closing_dt": closing_dt})
    # Derive MT (rolls * wt_per_roll / 1000)
    if not df.empty:
        df["closstock_rolls"] = df["closstock"]
        df["closstock_MT"] = (df["closstock"] * df["wt_per_roll"] / 1000.0).round(3)
    return df

@st.cache_data(ttl=60)
def q5_maturity_map(_engine) -> pd.DataFrame:
    sql = text("""SELECT mtm.jute_quality_id, mtm.maturity_hours FROM EMPMILL12.maturity_time_master mtm;""")
    with _engine.connect() as cn:
        df = pd.read_sql(sql, cn)
    return df

# ------------------
# LOAD DATA (A) & (B)
# ------------------
from db import engine

prod_df = q1_production_by_yarn(engine, selected_date)
plan_df = q2_batch_plan_window(engine, range_start, range_end)

# ------------------
# SHOW (A) Production by Yarn Type
# ------------------
st.subheader("A. Production by Yarn Type (selected date)")
if prod_df.empty:
    st.info("No production rows for the selected date.")
else:
    left, right = st.columns([2, 1])
    with left:
        st.dataframe(prod_df[["yarn_type", "yarn_type_id", "total_netwt", "total_netwt_MT"]], use_container_width=True)
    with right:
        total_kg = float(prod_df["total_netwt"].sum())
        st.metric("Total production (kg)", f"{int(total_kg):,}")
        st.metric("Total production (MT)", f"{total_kg/1000:.3f}")

st.divider()

# ------------------
# SHOW (B) Batch Plan (selected_date → +4 days)
# ------------------
st.subheader("B. Batch Plan (Date → Date + 4 days)")
if plan_df.empty:
    st.info("No active batch plan entries in this 5-day window.")
else:
    # --- Wide-format batch plan table with per-date target inputs ---
    plan_dates = sorted(plan_df['plan_date'].dropna().unique())
    if plan_dates:
        # Normalize yarn labels
        plan_df = plan_df.copy()
        plan_df['yarn_label'] = plan_df['yarn_type'].fillna(plan_df['yarn_type_id'].apply(lambda x: f"Yarn {x}" if pd.notna(x) else "Unmapped"))

        prod_base_map = {}
        if not prod_df.empty:
            prod_base_map = {
                row['yarn_type']: float(row['total_netwt'])
                for _, row in prod_df.iterrows()
            }

        plan_yarns = sorted(set(plan_df['yarn_label'].tolist()))
        table_rows = []
        for yarn in plan_yarns:
            reference_val = prod_base_map.get(yarn, None)
            if reference_val is None or reference_val == 0:
                reference_val = 1000.0  # default 1 MT (1000 kg) when base production missing
            row = {
                "Yarn Type": yarn,
                "Reference Production (kg)": reference_val
            }
            for dt in plan_dates:
                label = dt.strftime("%Y-%m-%d")
                row[f"{label} %"] = 100.0
            table_rows.append(row)

        table_df = pd.DataFrame(table_rows)

        # Manage session state to persist user adjustments
        state_key = "batch_plan_targets_percent_v2"
        schema_signature = (tuple(table_df.columns), tuple(plan_dates), tuple(plan_yarns))
        if state_key not in st.session_state or st.session_state.get("_batch_plan_schema") != schema_signature:
            st.session_state[state_key] = table_df.copy()
            st.session_state["_batch_plan_schema"] = schema_signature

        st.markdown("#### Batch Plan Targets (per date)")
        percent_cols = [col for col in table_df.columns if col.endswith('%')]

        column_config = {
            "Yarn Type": st.column_config.TextColumn("Yarn Type", disabled=True),
            "Reference Production (kg)": st.column_config.NumberColumn("Reference Production (kg)", disabled=True, format="%.0f")
        }
        for col in percent_cols:
            column_config[col] = st.column_config.NumberColumn(col, min_value=0.0, step=0.1, format="%.2f")

        edited_df = st.data_editor(
            st.session_state[state_key],
            column_config=column_config,
            hide_index=True,
            use_container_width=True,
            key="batch_plan_targets_editor"
        )

        percent_df = edited_df.copy()
        st.session_state[state_key] = percent_df

        # Calculate target production for each date column (display separately)
        targets_df = percent_df[["Yarn Type", "Reference Production (kg)"]].copy()
        for dt in plan_dates:
            label = dt.strftime("%Y-%m-%d")
            pct_col = f"{label} %"
            prod_col = f"{label} Target (kg)"
            targets_df[prod_col] = (
                percent_df["Reference Production (kg)"] * percent_df[pct_col] / 100.0
            ).round(2)

        st.markdown("##### Calculated Targets")
        st.dataframe(targets_df, use_container_width=True, hide_index=True)
    else:
        st.info("Batch plan has no dates available for the selected window.")

st.caption(
    "Next steps (in upcoming sections): batch composition lookup, snapshot stock & maturity summary (aggregated), "
    "and the MT-based required-issue calculator."
)
