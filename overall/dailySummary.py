import streamlit as st
from overall.query import get_dofftable_data, get_dofftable_sum_by_date, get_spg_fine_coarse, get_spg_sid_mtd, get_quality_winding_details, weaving_details, get_weaving_shiftwise, get_weaving_total_mtd, get_hands_details, get_hands_mtd_details
import pandas as pd
import datetime 
import numpy as np
import gspread
from google.oauth2.service_account import Credentials

def daily_summary():
    st.title("Executive Summary")
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    no_of_frames = 48 # Assuming 3 frames as per your original code
    day_shift = 3
    mtd_shift = 6
    selected_date = st.date_input("Select Date", value=yesterday, key="daily_summary_date")

    start_date = selected_date.replace(day=1) if selected_date else None
    num_days = (selected_date - start_date).days + 1 if start_date else 0

    if selected_date:
        df, json_data = get_dofftable_data(selected_date)
        if start_date:
            mtd_df, mtd_json = get_dofftable_sum_by_date(start_date, selected_date)
            mtd_df = mtd_df.rename(columns={'value': 'MTD'})
            df = pd.merge(df, mtd_df, on='DoffWtProd', how='left')


        # Rename first column to 'Metric' if needed
        if df.columns[0] != 'DoffWtProd':
            df.rename(columns={df.columns[0]: 'DoffWtProd'}, inplace=True)

        # Convert A/B/C to numeric
        for col in ['A', 'B', 'C']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Add Total and fill MTD
        if all(col in df.columns for col in ['A', 'B', 'C']):
            df['Total'] = df[['A', 'B', 'C']].sum(axis=1, skipna=True)
            df['MTD'] = df['MTD'].fillna(0)

        # Add Average and Utilisation rows
        try:
            prod_row = df[df['DoffWtProd'] == 'PRODUCTION (MT)'].iloc[0]
            frame_row = df[df['DoffWtProd'] == 'NO OF FRAME RUNS'].iloc[0]

            avg_row = {
                'DoffWtProd': 'AVG PER FRAME (Kg)',
                'A': round((prod_row['A'] * 1000) / frame_row['A'], 1) if frame_row['A'] else None,
                'B': round((prod_row['B'] * 1000) / frame_row['B'], 1) if frame_row['B'] else None,
                'C': round((prod_row['C'] * 1000) / frame_row['C'], 1) if frame_row['C'] else None,
                'Total': round((prod_row['Total'] * 1000) / frame_row['Total'], 1) if frame_row['Total'] else None,
                'MTD': round((prod_row['MTD'] * 1000) / frame_row['MTD'], 1) if frame_row['MTD'] else None
            }

            utilisation_row = {
                'DoffWtProd': 'Utilisation (%)',
                'A': round((frame_row['A'] / no_of_frames)*100, 0) if frame_row['A'] else None,
                'B': round((frame_row['B'] / no_of_frames)*100, 0) if frame_row['B'] else None,
                'C': round((frame_row['C'] / no_of_frames)*100, 0) if frame_row['C'] else None,
                'Total': round((frame_row['Total'] / (no_of_frames*3))*100, 0) if frame_row['Total'] else None,
                'MTD': round((frame_row['MTD'] / (no_of_frames*3*num_days))*100, 0) if frame_row['MTD'] else None
            }

            df = pd.concat([df, pd.DataFrame([avg_row, utilisation_row])], ignore_index=True)

        except (IndexError, KeyError) as e:
            st.warning(f"Could not calculate average per frame: {e}")

        # Move 'MTD' to the end
        if 'MTD' in df.columns:
            column_order = [col for col in df.columns if col != 'MTD'] + ['MTD']
        else:
            column_order = df.columns.tolist()

        # Configure column widths and formats
        column_config = {}
        for col in df.columns:
            if col == 'DoffWtProd':
                column_config[col] = st.column_config.TextColumn(width="medium")
            else:
                column_config[col] = st.column_config.NumberColumn(format="%.1f", width="60px")

        # Display final table
        st.markdown("Spg Production Summary")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_order=column_order,
            column_config=column_config,
            row_height=28  # Compact layout
        )
        
        # Display Spinning Fine/Coarse Data
        st.markdown("Spinning Fine/Coarse Summary")
        try:
            spg_df, spg_json = get_spg_fine_coarse(selected_date)
            
            # Get MTD data and combine with fine/coarse data
            if start_date:
                mtd_spg_df, mtd_spg_json = get_spg_sid_mtd(selected_date, start_date)
                # Combine both dataframes
                combined_spg_df = pd.concat([spg_df, mtd_spg_df], ignore_index=True)
            else:
                combined_spg_df = spg_df
            
            if not combined_spg_df.empty:
                # Transpose the data: set 'side' as index, transpose, then reset index
                spg_transposed = combined_spg_df.set_index('side').T.reset_index()
                spg_transposed.rename(columns={'index': 'SpgProd'}, inplace=True)
                
                # Replace column names: 1 with F/S and 3 with C/S
                column_mapping = {'1': 'F/S', '3': 'C/S'}
                spg_transposed.rename(columns=column_mapping, inplace=True)
                
                # Set column order: F/S, C/S, Overall, MTD
                desired_order = ['SpgProd', 'F/S', 'C/S', 'Overall', 'MTD']
                # Only include columns that actually exist in the dataframe
                spg_column_order = [col for col in desired_order if col in spg_transposed.columns]
                
                # Configure column formatting for the transposed table
                spg_column_config = {}
                for col in spg_transposed.columns:
                    if col == 'SpgProd':
                        spg_column_config[col] = st.column_config.TextColumn(width="small")
                    else:
                        spg_column_config[col] = st.column_config.NumberColumn(format="%.1f", width="small")
                
                st.dataframe(
                    spg_transposed,
                    use_container_width=True,
                    hide_index=True,
                    column_order=spg_column_order,
                    column_config=spg_column_config,
                    row_height=28
                )
            else:
                st.info("No spinning fine/coarse data available for the selected date.")
        except Exception as e:
            st.error(f"Error fetching spinning fine/coarse data: {str(e)}")
        
        # Display Quality Winding Details
        st.markdown("Quality Winding Details")
        try:
            if start_date:
                winding_df, winding_json = get_quality_winding_details(selected_date, start_date)
                if not winding_df.empty:
                    # Add total row for WdgProd column
                    if 'WdgProd' in winding_df.columns:
                        # Calculate total for WdgProd column
                        wdg_prod_total = winding_df['WdgProd'].sum()
                        
                        # Create total row
                        total_row = {}
                        for col in winding_df.columns:
                            if col == 'WdgProd':
                                total_row[col] = wdg_prod_total
                            elif 'Quality' in col or col == 'TDQuality':
                                total_row[col] = 'TOTAL'
                            else:
                                total_row[col] = np.nan
                        
                        # Add total row to dataframe
                        winding_df = pd.concat([winding_df, pd.DataFrame([total_row])], ignore_index=True)
                    
                    # Configure column formatting for winding details table
                    winding_column_config = {}
                    for col in winding_df.columns:
                        if 'Quality' in col or col == 'TDQuality':
                            winding_column_config[col] = st.column_config.TextColumn(width="medium")
                        else:
                            winding_column_config[col] = st.column_config.NumberColumn(format="%.0f", width="small")
                    
                    st.dataframe(
                        winding_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config=winding_column_config,
                        row_height=28
                    )
                else:
                    st.info("No quality winding details available for the selected date.")
            else:
                st.info("Start date not available for quality winding details.")
        except Exception as e:
            st.error(f"Error fetching quality winding details: {str(e)}")
        
        # Display Weaving Details
        st.markdown("Weaving Details")
        try:
            weaving_df, weaving_json = weaving_details(selected_date)
            if not weaving_df.empty:
                # Transpose the data, assuming the first column is the metric names
                weaving_transposed = weaving_df.set_index(weaving_df.columns[0]).T.reset_index()
                weaving_transposed.rename(columns={'index': 'Metric'}, inplace=True)

                # Add Utilisation row: Utilisation = McRun / TotalLooms * 100 (as a row after transpose)
                if 'Metric' in weaving_transposed.columns:
                    utilisation_row = {'Metric': 'Utilisation (%)'}
                    for col in weaving_transposed.columns:
                        if col == 'Metric':
                            continue
                        try:
                            mc_run = pd.to_numeric(weaving_transposed.loc[weaving_transposed['Metric'] == 'McRun', col], errors='coerce').values[0]
                            total_looms = pd.to_numeric(weaving_transposed.loc[weaving_transposed['Metric'] == 'TotalLooms', col], errors='coerce').values[0]
                            if pd.notna(mc_run) and pd.notna(total_looms) and total_looms != 0:
                                utilisation_row[col] = round((mc_run / (3*total_looms)) * 100, 1)
                            else:
                                utilisation_row[col] = np.nan
                        except Exception:
                            utilisation_row[col] = np.nan
                    weaving_transposed = pd.concat([weaving_transposed, pd.DataFrame([utilisation_row])], ignore_index=True)

                # Add 'Total' column for Production and McRun rows only
                if 'Metric' in weaving_transposed.columns:
                    total_col = []
                    for idx, row in weaving_transposed.iterrows():
                        if row['Metric'] in ['Production', 'McRun']:
                            # Sum all numeric columns except 'Metric' and 'Total'
                            vals = pd.to_numeric(row.drop(['Metric']), errors='coerce')
                            total_col.append(vals.sum(skipna=True))
                        else:
                            total_col.append("")
                    weaving_transposed['Total'] = total_col

                # Configure column formatting for the weaving table
                weaving_column_config = {}
                for col in weaving_transposed.columns:
                    if col == 'Metric' or weaving_transposed[col].dtype == 'object':
                        weaving_column_config[col] = st.column_config.TextColumn(width="small")
                    else:
                        weaving_column_config[col] = st.column_config.NumberColumn(format="%.1f", width="small")
                
                st.dataframe(
                    weaving_transposed,
                    use_container_width=True,
                    hide_index=True,
                    column_config=weaving_column_config,
                    row_height=28
                )
            else:
                st.info("No weaving details available for the selected date.")
        except Exception as e:
            st.error(f"Error fetching weaving details: {str(e)}")
        
        # Display Weaving Shiftwise Details
        st.markdown("Weaving Shiftwise Details")
        try:
            weaving_shiftwise_df, weaving_shiftwise_json = get_weaving_shiftwise(selected_date)
            mtd_total_df, mtd_total_json = get_weaving_total_mtd(selected_date, start_date) if start_date else (pd.DataFrame(), None)
            if not weaving_shiftwise_df.empty:
                # Merge MTD Total column if available
                if not mtd_total_df.empty and 'Quality' in mtd_total_df.columns and 'Total' in mtd_total_df.columns:
                    weaving_shiftwise_df = weaving_shiftwise_df.merge(
                        mtd_total_df[['Quality', 'Total']].rename(columns={'Total': 'MTD Total'}),
                        on='Quality', how='left')
                # Add Grand Total row
                numeric_cols = [col for col in weaving_shiftwise_df.columns if weaving_shiftwise_df[col].dtype != 'object' and col != 'Quality']
                grand_total = {'Quality': 'Total Weaving Production'}
                for col in weaving_shiftwise_df.columns:
                    if col in numeric_cols:
                        grand_total[col] = weaving_shiftwise_df[col].sum(skipna=True)
                    else:
                        grand_total[col] = ''
                weaving_shiftwise_df = pd.concat([weaving_shiftwise_df, pd.DataFrame([grand_total])], ignore_index=True)
                # Configure column formatting for the shiftwise table
                shiftwise_column_config = {}
                for col in weaving_shiftwise_df.columns:
                    if col == 'Quality' or weaving_shiftwise_df[col].dtype == 'object':
                        shiftwise_column_config[col] = st.column_config.TextColumn(width="small")
                    else:
                        shiftwise_column_config[col] = st.column_config.NumberColumn(format="%.1f", width="small")
                st.dataframe(
                    weaving_shiftwise_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config=shiftwise_column_config,
                    row_height=28
                )
            else:
                st.info("No weaving shiftwise details available for the selected date.")
        except Exception as e:
            st.error(f"Error fetching weaving shiftwise details: {str(e)}")
        
        # Display Hands Details (Daily + MTD)
        st.markdown("Hands Details (Daily + MTD)")
        try:
            hands_df, hands_json = get_hands_details(selected_date)
            hands_mtd_df, hands_mtd_json = get_hands_mtd_details(selected_date, start_date) if start_date else (pd.DataFrame(), None)
            hands_total = None
            if not hands_df.empty:
                # Transpose daily hands data
                hands_transposed = hands_df.set_index(hands_df.columns[0]).T.reset_index()
                hands_transposed.rename(columns={'index': 'Metric'}, inplace=True)
                # Add Total column (sum across all shifts for each metric)
                shift_cols = [col for col in hands_transposed.columns if col != 'Metric']
                hands_transposed['Total'] = hands_transposed[shift_cols].apply(pd.to_numeric, errors='coerce').sum(axis=1)
                # Prepare MTD total (not shift-wise)
                mtd_total = None
                if hands_mtd_df is not None and not hands_mtd_df.empty:
                    mtd_total = hands_mtd_df['hands'].sum()
                # Add MTD column: only fill for 'Total' row
                hands_transposed['MTD'] = ''
                if mtd_total is not None:
                    # Only fill MTD for the 'Total' row (i.e., the last row)
                    hands_transposed.at[hands_transposed.index[-1], 'MTD'] = mtd_total
                # Save hands total (last row, 'Total' column)
                hands_total = hands_transposed['Total'].iloc[-1]
                # Configure column formatting
                hands_column_config = {}
                for col in hands_transposed.columns:
                    if col == 'Metric' or hands_transposed[col].dtype == 'object':
                        hands_column_config[col] = st.column_config.TextColumn(width="small")
                    else:
                        hands_column_config[col] = st.column_config.NumberColumn(format="%.1f", width="small")
                # Set column order: Metric, shifts..., Total, MTD
                col_order = ['Metric'] + [col for col in shift_cols] + ['Total', 'MTD']
                st.dataframe(
                    hands_transposed[col_order],
                    use_container_width=True,
                    hide_index=True,
                    column_config=hands_column_config,
                    row_height=28
                )
            else:
                st.info("No hands details available for the selected date.")
        except Exception as e:
            st.error(f"Error fetching hands details: {str(e)}")

    # --- Google Sheets Section ---
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_file(
        "C:\\code\\mis\\careful-analyst-441615-j6-ac33950f3271.json", scopes=scope
    )
    try:
        # Connect to Google Sheets
        gc = gspread.authorize(credentials)
        # Open the Google Sheet and worksheet
        sheet = gc.open("new R-08-16 Yarn Parameter Entry (Responses)").worksheet("YARN")
        # Read data
        df = pd.DataFrame(sheet.get_all_records())
        # Automatically use the 'Date' column for filtering
        date_col = 'Date' if 'Date' in df.columns else df.columns[0]
        # Use the main selected_date from above for filtering
        if not df.empty:
            all_dates = pd.to_datetime(df[date_col], errors='coerce').dt.date.dropna().unique()
            if len(all_dates) > 0:
                # Filter by selected_date
                mask = pd.to_datetime(df[date_col], errors='coerce').dt.date == selected_date
                filtered = df[mask]
                # Columns to display
                display_cols = [col for col in ["Date", "Quality", "Wt /450 yds in Gms1", "MR"] if col in filtered.columns]
                filtered_display = filtered[display_cols]
                # st.dataframe(filtered_display)
                # Group by Quality and calculate averages
                if not filtered_display.empty:
                    grouped = filtered_display.groupby("Quality").agg({
                        "Wt /450 yds in Gms1": lambda x: pd.to_numeric(x, errors='coerce').mean(),
                        "MR": lambda x: pd.to_numeric(x, errors='coerce').mean()
                    }).reset_index()
                    grouped = grouped.rename(columns={
                        "Wt /450 yds in Gms1": "Avg Wt /450 yds in Gms1",
                        "MR": "Avg MR"
                    })
                    grouped["Avg MR"] = grouped["Avg MR"].apply(lambda x: round(x, 2) if pd.notnull(x) else None)
                    grouped["Observed Count (Lbs)"] = grouped["Avg Wt /450 yds in Gms1"].apply(lambda k: round((k / 450) * 14400 / 454, 2) if pd.notnull(k) else None)
                    # --- Read STD parameters from the STD worksheet ---
                    std_count_df = pd.DataFrame()
                    std_mr_df = pd.DataFrame()
                    try:
                        std_sheet = gc.open("new R-08-16 Yarn Parameter Entry (Responses)").worksheet("STD")
                        std_values = std_sheet.get_all_values()
                        # Table 1: Quality-wise std count (columns A and B)
                        std_count_data = [[row[0], row[1]] for row in std_values[1:] if len(row) > 1 and row[0] and row[1]]
                        std_count_df = pd.DataFrame(std_count_data, columns=["Quality", "Std Count"])
                        # Table 2: Quality-wise std MR% (columns D and E)
                        std_mr_data = [[row[3], row[4]] for row in std_values[1:] if len(row) > 4 and row[3] and row[4]]
                        std_mr_df = pd.DataFrame(std_mr_data, columns=["Quality", "Std MR%"])
                    except Exception as e:
                        st.error(f"Error loading STD parameters: {e}")
                    # Merge STD columns into the grouped table (unique Quality only)
                    if not grouped.empty and not std_count_df.empty and not std_mr_df.empty:
                        # Drop duplicates in std_count_df and std_mr_df to ensure unique Quality
                        std_count_df = std_count_df.drop_duplicates(subset=["Quality"])
                        std_mr_df = std_mr_df.drop_duplicates(subset=["Quality"])
                        merged = grouped.merge(std_count_df, on="Quality", how="left")
                        merged = merged.merge(std_mr_df, on="Quality", how="left")
                        # Remove columns that look like serial numbers or 'Avg Wt /450 yds in Gms1'
                        drop_cols = [col for col in merged.columns if 'sr' in col.lower() or 'serial' in col.lower() or col == 'Avg Wt /450 yds in Gms1']
                        merged = merged.drop(columns=drop_cols, errors='ignore')
                        # Calculate Corr Count column
                        if all(col in merged.columns for col in ["Observed Count (Lbs)", "Avg MR", "Std MR%"]):
                            merged["Corr Count"] = merged.apply(
                                lambda row: round(
                                    float(row["Observed Count (Lbs)"]) * (100 + float(row["Avg MR"])) / (100 + float(row["Std MR%"])), 2
                                ) if pd.notnull(row["Observed Count (Lbs)"]) and pd.notnull(row["Avg MR"]) and pd.notnull(row["Std MR%"])
                                else None,
                                axis=1
                            )
                            # Calculate Hvy/Light % column
                            if "Std Count" in merged.columns:
                                merged["Hvy/Light %"] = merged.apply(
                                    lambda row: f"{round(((float(row['Corr Count']) - float(row['Std Count'])) / float(row['Std Count']) * 100), 2)}%" if pd.notnull(row["Corr Count"]) and pd.notnull(row["Std Count"]) and float(row["Std Count"]) != 0 else None,
                                    axis=1
                                )
                            # Insert Corr Count and Hvy/Light % after Observed Count (Lbs), exclude Std MR%
                            col_order = ["Quality", "Std Count", "Observed Count (Lbs)", "Corr Count", "Hvy/Light %", "Avg MR"]
                            merged = merged[[col for col in col_order if col in merged.columns]]
                        st.markdown("Heavy Light Yarn")
                        st.dataframe(merged, hide_index=True)
                    else:
                        st.info("No data for selected date.")
                else:
                    st.info("No matching dates in sheet.")
            else:
                st.info("Sheet is empty.")
    except Exception as e:
            st.error(f"Error: {e}")









