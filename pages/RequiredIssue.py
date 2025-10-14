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
        value=date.today() - timedelta(days=1),
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

# Roll stock snapshot runs at next-day 06:00 for current inventory
roll_snapshot_dt = snapshot_dt + timedelta(days=1)
roll_opening_dt_str = roll_snapshot_dt.strftime("%Y-%m-%d %H")
roll_closing_dt_str = roll_opening_dt_str

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

@st.cache_data(ttl=60)
def q6_jute_quality_lookup(_engine) -> pd.DataFrame:
    sql = text("""
        SELECT
            jqpm.id AS jute_quality_id,
            jqpm.jute_quality
        FROM vowsls.jute_quality_price_master jqpm
        WHERE jqpm.company_id = :co_id;
    """)
    with _engine.connect() as cn:
        df = pd.read_sql(sql, cn, params={"co_id": COMPANY_ID})
    return df

# ------------------
# LOAD DATA (A) & (B)
# ------------------
from db import engine

prod_df = q1_production_by_yarn(engine, selected_date)
plan_df = q2_batch_plan_window(engine, range_start, range_end)
composition_df = q3_batch_composition(engine)
maturity_df = q5_maturity_map(engine)
roll_stock_df = q4_roll_stock_snapshot(engine, roll_opening_dt_str, roll_closing_dt_str)

quality_lookup_df = q6_jute_quality_lookup(engine)
if (quality_lookup_df is None or quality_lookup_df.empty) and composition_df is not None and not composition_df.empty:
    quality_lookup_df = (
        composition_df[["jute_quality_id", "jute_quality"]]
        .dropna()
        .drop_duplicates()
    )

# ------------------
# SHOW (A) Production by Yarn Type
# ------------------
st.subheader("A. Production by Yarn Type (selected date)")
if prod_df.empty:
    st.info("No production rows for the selected date.")
else:
    with st.expander("A. Production by Yarn Type (selected date)", expanded=False):
        left, right = st.columns([2, 1])
        with left:
            st.dataframe(prod_df[["yarn_type", "yarn_type_id", "total_netwt", "total_netwt_MT"]], use_container_width=True)
            st.caption(f"Query window: Production date = {selected_date.strftime('%Y-%m-%d')} (snapshot at 06:00)")
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
            for plan_date in plan_dates:
                label = plan_date.strftime("%Y-%m-%d")
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
        st.caption(
            f"Batch plan query window: {range_start.strftime('%Y-%m-%d')} to {range_end.strftime('%Y-%m-%d')}"
        )

        percent_df = edited_df.copy()
        st.session_state[state_key] = percent_df

        # Calculate target production for each date column
        targets_df = percent_df[["Yarn Type", "Reference Production (kg)"]].copy()
        for plan_date in plan_dates:
            label = plan_date.strftime("%Y-%m-%d")
            pct_col = f"{label} %"
            prod_col = f"{label} Target (kg)"
            targets_df[prod_col] = (
                percent_df["Reference Production (kg)"] * percent_df[pct_col] / 100.0
            ).round(2)

        # Build pivot-style yarn ↔ batch summary with day columns
        target_cols = [col for col in targets_df.columns if col.endswith("Target (kg)")]
        target_long = targets_df.melt(
            id_vars=["Yarn Type", "Reference Production (kg)"],
            value_vars=target_cols,
            var_name="_date_label",
            value_name="Target (kg)"
        )
        if not target_long.empty:
            target_long["plan_date"] = pd.to_datetime(
                target_long["_date_label"].str.replace(" Target (kg)", "", regex=False)
            )
            target_long = target_long[target_long["Target (kg)"].notna()]

            plan_lookup = (
                plan_df[["plan_date", "yarn_label", "batch_plan_code"]]
                .drop_duplicates()
                .copy()
            )
            plan_lookup["plan_date"] = pd.to_datetime(plan_lookup["plan_date"])

            summary = target_long.merge(
                plan_lookup,
                left_on=["plan_date", "Yarn Type"],
                right_on=["plan_date", "yarn_label"],
                how="left"
            )
            summary["batch_plan_code"] = summary["batch_plan_code"].fillna("Unassigned")

            pivot_df = (
                summary.pivot_table(
                    index=["batch_plan_code", "Yarn Type"],
                    columns="plan_date",
                    values="Target (kg)",
                    aggfunc="sum",
                    fill_value=0.0
                )
                .reset_index()
            )

            # Flatten date columns and ensure chronological order
            base_cols = ["batch_plan_code", "Yarn Type"]
            date_columns = [
                col.strftime("%Y-%m-%d") if isinstance(col, (dt.date, datetime, pd.Timestamp)) else str(col)
                for col in pivot_df.columns[len(base_cols):]
            ]
            pivot_df.columns = ["Batch Plan Code", "Yarn Type", *date_columns]

            date_columns = [col for col in pivot_df.columns if col not in {"Batch Plan Code", "Yarn Type"}]
            date_columns = sorted(date_columns)
            pivot_df = pivot_df[["Batch Plan Code", "Yarn Type", *date_columns]]
            pivot_df["Row Total (kg)"] = pivot_df[date_columns].sum(axis=1).round(2)

            pivot_display_df = pivot_df.copy()
            date_totals = None
            if date_columns:
                date_totals = pivot_df[date_columns].sum().round(2)
                totals_row = {"Batch Plan Code": "Grand Total", "Yarn Type": "Total"}
                for date_col in date_columns:
                    totals_row[date_col] = date_totals[date_col]
                totals_row["Row Total (kg)"] = pivot_df["Row Total (kg)"].sum().round(2)
                pivot_display_df = pd.concat(
                    [pivot_display_df, pd.DataFrame([totals_row])],
                    ignore_index=True
                )

            st.markdown("##### Batch ↔ Yarn Pivot (Targets in kg)")
            st.dataframe(pivot_display_df, use_container_width=True, hide_index=True)
            st.caption(
                f"Batch plan query window: {range_start.strftime('%Y-%m-%d')} to {range_end.strftime('%Y-%m-%d')}"
            )

            if date_columns:
                if date_totals is None:
                    date_totals = pivot_df[date_columns].sum().round(2)

                batch_totals = (
                    summary.groupby(["batch_plan_code", "plan_date"])["Target (kg)"]
                    .sum()
                    .reset_index()
                )

                batch_totals_pivot = (
                    batch_totals.pivot(
                        index="batch_plan_code",
                        columns="plan_date",
                        values="Target (kg)"
                    )
                    .fillna(0.0)
                )

                batch_totals_pivot = batch_totals_pivot.reindex(columns=[pd.to_datetime(d) for d in date_columns], fill_value=0.0)
                batch_totals_pivot.index.name = "Batch Plan Code"
                batch_totals_pivot = batch_totals_pivot.reset_index()

                batch_totals_pivot.columns = [
                    "Batch Plan Code",
                    *date_columns
                ]
                batch_totals_pivot[date_columns] = batch_totals_pivot[date_columns].round(2)
                batch_totals_pivot["Row Total (kg)"] = batch_totals_pivot[date_columns].sum(axis=1).round(2)

                grand_total = date_totals.sum().round(2)
                totals_row = {"Batch Plan Code": "Grand Total"}
                for date_col in date_columns:
                    totals_row[date_col] = date_totals[date_col]
                totals_row["Row Total (kg)"] = grand_total
                batch_totals_pivot = pd.concat(
                    [batch_totals_pivot, pd.DataFrame([totals_row])],
                    ignore_index=True
                )

                with st.expander("Batch Plan Totals by Date", expanded=False):
                    st.dataframe(batch_totals_pivot, hide_index=True, use_container_width=True)
                    st.caption(
                        f"Batch plan query window: {range_start.strftime('%Y-%m-%d')} to {range_end.strftime('%Y-%m-%d')}"
                    )

                if composition_df is not None and not composition_df.empty:
                    active_plan_codes = [code for code in batch_totals_pivot["Batch Plan Code"].unique() if code != "Grand Total"]
                    comp_subset = composition_df[composition_df["plan_code"].isin(active_plan_codes)].copy()

                    if not comp_subset.empty:
                        comp_subset["percentage"] = comp_subset["percentage"].astype(float)
                        comp_display = comp_subset.rename(columns={
                            "plan_code": "Batch Plan Code",
                            "plan_name": "Plan Name",
                            "jute_quality": "Jute Quality",
                            "percentage": "Percentage (%)"
                        })
                        comp_display["Percentage (%)"] = comp_display["Percentage (%)"].round(2)
                        comp_display = comp_display[[
                            "Batch Plan Code",
                            "Plan Name",
                            "Jute Quality",
                            "Percentage (%)"
                        ]]

                        with st.expander("Batch Plan with Jute", expanded=False):
                            st.dataframe(comp_display, hide_index=True, use_container_width=True)
                            st.caption(
                                f"Composition reference for active plans within {range_start.strftime('%Y-%m-%d')} to {range_end.strftime('%Y-%m-%d')}"
                            )

                        totals_matrix = batch_totals_pivot[batch_totals_pivot["Batch Plan Code"] != "Grand Total"].set_index("Batch Plan Code")
                        contributions = comp_subset.merge(
                            totals_matrix.reset_index(),
                            left_on="plan_code",
                            right_on="Batch Plan Code",
                            how="left"
                        )
                        if "Batch Plan Code" in contributions.columns:
                            contributions = contributions.drop(columns=["Batch Plan Code"])

                        for date_col in date_columns:
                            contributions[date_col] = (
                                contributions[date_col].fillna(0.0) * contributions["percentage"] / 100.0
                            ).round(2)

                        contributions["Row Total (kg)"] = contributions[date_columns].sum(axis=1).round(2)

                        contributions_display = contributions.rename(columns={
                            "plan_code": "Batch Plan Code",
                            "plan_name": "Plan Name",
                            "jute_quality": "Jute Quality",
                            "percentage": "Percentage (%)"
                        })
                        contributions_display["Percentage (%)"] = contributions_display["Percentage (%)"].round(2)
                        contributions_display = contributions_display[[
                            "Batch Plan Code",
                            "Plan Name",
                            "Jute Quality",
                            "Percentage (%)",
                            *date_columns,
                            "Row Total (kg)"
                        ]]

                        with st.expander("Batch Plan with Jute — Contributions (MT)", expanded=False):
                            mt_columns = date_columns + ["Row Total (kg)"]
                            contributions_display[mt_columns] = (contributions_display[mt_columns] / 1000.0).round(3)
                            contributions_display = contributions_display.rename(columns={
                                "Row Total (kg)": "Row Total (MT)"
                            })
                            st.dataframe(contributions_display, hide_index=True, use_container_width=True)
                            st.caption(
                                f"Contributions computed for batch plan dates {range_start.strftime('%Y-%m-%d')} to {range_end.strftime('%Y-%m-%d')}"
                            )

                        jute_totals = contributions_display.groupby("Jute Quality")[date_columns + ["Row Total (MT)"]]
                        jute_totals = jute_totals.sum().round(3).reset_index()

                        jute_totals.columns = [
                            "Jute Quality",
                            *date_columns,
                            "Row Total (MT)"
                        ]

                        plan_issue_date = selected_date + timedelta(days=1)
                        plan_issue_label = plan_issue_date.strftime("%Y-%m-%d")
                        jute_day_totals_map = {}
                        if plan_issue_label in jute_totals.columns:
                            jute_day_totals_map = dict(zip(
                                jute_totals["Jute Quality"],
                                jute_totals[plan_issue_label].fillna(0.0)
                            ))
                        else:
                            jute_day_totals_map = {quality: 0.0 for quality in jute_totals["Jute Quality"]}

                        jute_totals_df = jute_totals.copy()
                        jute_totals_caption = (
                            f"Totals across batch plan dates {range_start.strftime('%Y-%m-%d')} to {range_end.strftime('%Y-%m-%d')}"
                        )

                        with st.expander("Jute Quality Totals (MT)", expanded=False):
                            st.dataframe(jute_totals_df, hide_index=True, use_container_width=True)
                            st.caption(jute_totals_caption)

                        if maturity_df is not None and not maturity_df.empty:
                            quality_map = quality_lookup_df
                            maturity_named = maturity_df.copy()
                            if quality_map is not None and not quality_map.empty:
                                maturity_named = maturity_named.merge(
                                    quality_map,
                                    on="jute_quality_id",
                                    how="left"
                                )
                                maturity_named = (
                                    maturity_named.dropna(subset=["jute_quality"])
                                )
                            else:
                                maturity_named["jute_quality"] = maturity_named["jute_quality_id"].astype(str)

                            maturity_by_quality = (
                                maturity_named.groupby("jute_quality", as_index=False)["maturity_hours"].mean()
                            )
                            maturity_lookup = dict(zip(
                                maturity_by_quality["jute_quality"],
                                maturity_by_quality["maturity_hours"]
                            ))

                            target_stock = jute_totals.merge(
                                maturity_by_quality,
                                left_on="Jute Quality",
                                right_on="jute_quality",
                                how="left"
                            )
                            target_stock = target_stock.drop(columns=["jute_quality"], errors="ignore")
                            target_stock["maturity_hours"] = target_stock["maturity_hours"].fillna(0.0)

                            for date_col in date_columns:
                                target_stock[date_col] = (
                                    target_stock[date_col] * target_stock["maturity_hours"] / 24.0
                                ).round(3)

                            target_stock_display = target_stock[[
                                "Jute Quality",
                                *date_columns
                            ]]

                            with st.expander("Target Roll Stock (MT)", expanded=False):
                                st.dataframe(target_stock_display, hide_index=True, use_container_width=True)
                                st.caption(
                                    f"Target stock projected using maturity hours from snapshot date {selected_date.strftime('%Y-%m-%d')}"
                                )

                            current_stock_map = {}
                            current_stock_df = pd.DataFrame(columns=["label", "closstock_MT"])
                            if roll_stock_df is not None and not roll_stock_df.empty:
                                current_stock = (
                                    roll_stock_df.groupby("jute_quality_id")["closstock_MT"]
                                    .sum()
                                    .reset_index()
                                )
                                if quality_map is not None and not quality_map.empty:
                                    current_stock = current_stock.merge(
                                        quality_map,
                                        on="jute_quality_id",
                                        how="left"
                                    )
                                    current_stock["label"] = current_stock["jute_quality"].fillna(current_stock["jute_quality_id"].astype(str))
                                else:
                                    current_stock["label"] = current_stock["jute_quality_id"].astype(str)
                                current_stock_map = dict(zip(current_stock["label"], current_stock["closstock_MT"].round(3)))
                                current_stock_df = current_stock[["label", "closstock_MT"]].copy()

                            target_stock_snapshot_rows = []
                            planned_qualities = set()
                            for _, row in target_stock.iterrows():
                                maturity_hours = float(row.get("maturity_hours", 0.0) or 0.0)
                                days_offset = int(round(maturity_hours / 24.0, 0)) + 1
                                closing_dt = selected_date + timedelta(days=days_offset)
                                closing_dt_str = closing_dt.strftime("%Y-%m-%d")
                                target_value = float(row.get(closing_dt_str, 0.0) or 0.0)
                                current_value = current_stock_map.get(row["Jute Quality"], 0.0)
                                plan_issue = float(jute_day_totals_map.get(row["Jute Quality"], 0.0) or 0.0)
                                required_issue = target_value - (current_value - plan_issue)
                                planned_qualities.add(row["Jute Quality"])
                                target_stock_snapshot_rows.append({
                                    "Jute Quality": row["Jute Quality"],
                                    "Closing Target Stock Date": closing_dt_str,
                                    "Target Stock (MT)": round(target_value, 3),
                                    "Current Roll Stock (MT)": round(current_value, 3),
                                    "Plan Issue (MT)": round(plan_issue, 3),
                                    "Required Issue": round(required_issue, 3)
                                })

                            if not current_stock_df.empty:
                                for _, stock_row in current_stock_df.iterrows():
                                    label = stock_row["label"]
                                    if label in planned_qualities:
                                        continue
                                    maturity_hours = float(maturity_lookup.get(label, 0.0) or 0.0)
                                    days_offset = int(round(maturity_hours / 24.0, 0))
                                    closing_dt = selected_date + timedelta(days=days_offset)
                                    closing_dt_str = closing_dt.strftime("%Y-%m-%d") if maturity_hours else selected_date.strftime("%Y-%m-%d")
                                    plan_issue = float(jute_day_totals_map.get(label, 0.0) or 0.0)
                                    current_value = float(stock_row["closstock_MT"] or 0.0)
                                    required_issue = 0.0 - (current_value - plan_issue)
                                    target_stock_snapshot_rows.append({
                                        "Jute Quality": label,
                                        "Closing Target Stock Date": closing_dt_str,
                                        "Target Stock (MT)": 0.0,
                                        "Current Roll Stock (MT)": round(current_value, 3),
                                        "Plan Issue (MT)": round(plan_issue, 3),
                                        "Required Issue": round(required_issue, 3)
                                    })

                            if target_stock_snapshot_rows:
                                snapshot_df = pd.DataFrame(target_stock_snapshot_rows)
                                snapshot_df = snapshot_df.sort_values(
                                    by="Current Roll Stock (MT)", ascending=False
                                ).reset_index(drop=True)
                                target_stock_snapshot_caption = (
                                    f"Current roll stock sourced from snapshot query at {roll_snapshot_dt.strftime('%Y-%m-%d %H:%M')} (opening/closing window), with maturity roll-forward to closing dates"
                                )
                                summary_df = snapshot_df[["Jute Quality", "Required Issue"]].copy()
                                summary_df["Required Issue (Bales)"] = (
                                    summary_df["Required Issue"].astype(float) / 0.148
                                ).round(3)

                                with st.expander("Target Roll Stock Snapshot (MT)", expanded=False):
                                    st.dataframe(snapshot_df, hide_index=True, use_container_width=True)
                                    st.caption(target_stock_snapshot_caption)

                                st.markdown("##### Required Issue Snapshot")
                                st.dataframe(summary_df, use_container_width=True, hide_index=True)
    else:
        st.info("Batch plan has no dates available for the selected window.")


