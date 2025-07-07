import streamlit as st
import plotly.express as px
from doff10.query import get_doff_details, get_dofftable_data

def doff_details():
    st.subheader("Doff Details Summary")
    selected_date4 = st.date_input("Select Doff Date for Details", key="selected_date4")
    if selected_date4:
        details_df, details_json = get_doff_details(selected_date4)
        # st.subheader("JSON Output")
        # st.code(details_json, language="json")
        
        # Add spell dropdown filter
        if not details_df.empty:
            spell_list = ["All Spells"] + sorted(details_df['spell'].unique().tolist())
            selected_spell = st.selectbox("Select Spell", spell_list, key="spell_filter")
            
            # Filter DataFrame by selected spell first
            if selected_spell != "All Spells":
                spell_filtered_df = details_df[details_df['spell'] == selected_spell]
            else:
                spell_filtered_df = details_df
            
            # Add quality dropdown filter - check if spell_filtered_df is not empty
            if not spell_filtered_df.empty:
                quality_values = spell_filtered_df['quality'].dropna().unique().tolist()
                quality_list = ["All Qualities"] + sorted(quality_values)
                selected_quality = st.selectbox("Select Quality", quality_list, key="quality_filter")
                
                # Filter DataFrame by selected quality
                if selected_quality != "All Qualities":
                    filtered_df = spell_filtered_df[spell_filtered_df['quality'] == selected_quality]
                else:
                    filtered_df = spell_filtered_df
            else:
                # If no data for selected spell, show empty dataframe and disable quality filter
                st.warning(f"No data found for Spell {selected_spell}")
                filtered_df = spell_filtered_df
                st.selectbox("Select Quality", ["No qualities available"], key="quality_filter", disabled=True)
        else:
            filtered_df = details_df
        
        st.subheader("Doff Details Table")
        st.dataframe(filtered_df)
        
        # Add summary statistics
        if not filtered_df.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Spells", filtered_df['spell'].nunique())
            with col2:
                st.metric("Total Frames", filtered_df['frameno'].nunique())
            with col3:
                st.metric("Total Netwt", f"{filtered_df['netwt'].sum():,.0f}")
            
            # Add a chart showing netwt by spell
            st.subheader("Netwt by Spell")
            spell_summary = filtered_df.groupby('spell')['netwt'].sum().reset_index()
            
            # Create plotly chart with data labels for spell netwt
            fig_spell = px.bar(spell_summary, x='spell', y='netwt', 
                              title='Network Weight by Spell',
                              text='netwt')
            fig_spell.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
            fig_spell.update_layout(xaxis_title='Spell', yaxis_title='Network Weight (kg)')
            st.plotly_chart(fig_spell, use_container_width=True)
            
            # Add average weight distribution chart
            st.subheader("Frame Distribution by Average Weight Categories")
            
            # Create weight ranges
            def categorize_weight(weight):
                if weight < 26:
                    return "< 26 kg"
                elif weight < 28:
                    return "26-28 kg"
                elif weight < 30:
                    return "28-30 kg"
                elif weight < 32:
                    return "30-32 kg"
                elif weight < 34:
                    return "32-34 kg"
                elif weight < 36:
                    return "34-36 kg"
                elif weight < 38:
                    return "36-38 kg"
                elif weight < 40:
                    return "38-40 kg"
                elif weight < 42:
                    return "40-42 kg"
                elif weight < 44:
                    return "42-44 kg"
                elif weight <= 45:
                    return "44-45 kg"
                else:
                    return "> 45 kg"
            
            # Apply categorization
            weight_analysis = filtered_df.copy()
            weight_analysis['weight_category'] = weight_analysis['averagewt'].apply(categorize_weight)
            
            # Group by weight category and collect frame numbers with spell info
            weight_groups = weight_analysis.groupby('weight_category').agg({
                'frameno': lambda x: ', '.join(map(str, sorted(x))),
                'averagewt': 'count'
            }).rename(columns={'averagewt': 'frame_count'})
            
            # Group by weight category and spell for detailed breakdown
            spell_weight_groups = weight_analysis.groupby(['weight_category', 'spell']).agg({
                'frameno': lambda x: ', '.join(map(str, sorted(x))),
                'averagewt': 'count'
            }).rename(columns={'averagewt': 'frame_count'})
            
            # Define the order of categories
            category_order = ["< 26 kg", "26-28 kg", "28-30 kg", "30-32 kg", "32-34 kg", 
                            "34-36 kg", "36-38 kg", "38-40 kg", "40-42 kg", "42-44 kg", 
                            "44-45 kg", "> 45 kg"]
            
            # Reindex to ensure proper order
            weight_groups = weight_groups.reindex(category_order).fillna({'frameno': '', 'frame_count': 0})
            
            # Create plotly chart with data labels for weight distribution
            weight_chart_data = weight_groups.reset_index()
            weight_chart_data.columns = ['weight_category', 'frameno', 'frame_count']
            
            fig_weight = px.bar(weight_chart_data, x='weight_category', y='frame_count',
                               title='Frame Distribution by Average Weight Categories',
                               text='frame_count')
            fig_weight.update_traces(texttemplate='%{text}', textposition='outside')
            fig_weight.update_layout(xaxis_title='Weight Category', yaxis_title='Number of Frames',
                                   xaxis_tickangle=-45)
            st.plotly_chart(fig_weight, use_container_width=True)
            
            # Display detailed breakdown
            st.subheader("Detailed Frame Distribution by Spell")
            for category in category_order:
                if weight_groups.loc[category, 'frame_count'] > 0:
                    total_count = int(weight_groups.loc[category, 'frame_count'])
                    st.write(f"### {category} - Total: {total_count} frames")
                    
                    # Show spell-wise breakdown for this category
                    category_spells = spell_weight_groups.loc[spell_weight_groups.index.get_level_values('weight_category') == category]
                    
                    if not category_spells.empty:
                        for spell_idx in category_spells.index:
                            spell = spell_idx[1]  # Get spell from multi-index
                            frames = category_spells.loc[spell_idx, 'frameno']
                            count = int(category_spells.loc[spell_idx, 'frame_count'])
                            st.write(f"   **Spell {spell}**: {count} frames - {frames}")
                    st.write("---")  # Add separator between categories
    
    # --- Show raw dofftable data with frame filter at the end ---
    st.markdown("---")
    st.subheader("Raw Doff Table Data (Frame-wise)")
    dofftable_df, _ = get_dofftable_data(selected_date4)
    if not dofftable_df.empty and 'frameno' in dofftable_df.columns:
        frame_list2 = sorted(dofftable_df['frameno'].unique().tolist())
        selected_frameno2 = st.selectbox("Select Frame No (Raw Table)", ["All Frames"] + [str(f) for f in frame_list2], key="frameno_filter_raw")
        if selected_frameno2 != "All Frames":
            filtered_dofftable_df = dofftable_df[dofftable_df['frameno'].astype(str) == selected_frameno2]
        else:
            filtered_dofftable_df = dofftable_df
        st.dataframe(filtered_dofftable_df)
    else:
        st.info("No dofftable data available for the selected date.")




