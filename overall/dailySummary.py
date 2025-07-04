import streamlit as st
from overall.query import get_dofftable_data, get_dofftable_sum_by_date, get_spg_fine_coarse, get_spg_sid_mtd, get_quality_winding_details, weaving_details
import pandas as pd
import datetime 

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
        st.subheader("Spg Production Summary")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_order=column_order,
            column_config=column_config,
            row_height=28  # Compact layout
        )
        
        # Display Spinning Fine/Coarse Data
        st.subheader("Spinning Fine/Coarse Summary")
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
        st.subheader("Quality Winding Details")
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
                                total_row[col] = None
                        
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

            



