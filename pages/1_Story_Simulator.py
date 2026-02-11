import streamlit as st
import pandas as pd
import plotly.express as px
from core.catalog import DATA_CATALOG
from sources import fetch_data

st.set_page_config(page_title="Story Composer", layout="wide")

st.title("🧩 Story Composer: Multi-Dataset Analyzer")
st.markdown("Compare the shape of different datasets over a shared timeline.")

# --- 1. SESSION & CONFIG ---
if "composer_data" not in st.session_state:
    st.session_state.composer_data = {}

# Sidebar: Data Loader
with st.sidebar:
    st.header("1. Select Datasets")
    
    # Build selection list from Catalog
    selection_map = {}
    for category, content in DATA_CATALOG.items():
        if "datasets" in content:
            for label, dataset_id in content["datasets"].items():
                if "Custom" not in label and "Paste" not in label:
                    key = f"{category}: {label}"
                    selection_map[key] = {
                        "source": content["type"], 
                        "id": dataset_id,
                        "label": label
                    }
    
    selected_layers = st.multiselect("Choose datasets to fetch:", list(selection_map.keys()))
    
    # API Key Handling
    api_key = None
    if "FRED_API_KEY" in st.secrets:
        api_key = st.secrets["FRED_API_KEY"]
    else:
        api_key = st.text_input("FRED API Key (Optional)", type="password")

    if st.button("Fetch Data", type="primary"):
        st.session_state.composer_data = {} # Reset
        
        progress = st.progress(0)
        for i, layer_name in enumerate(selected_layers):
            meta = selection_map[layer_name]
            with st.spinner(f"Fetching {meta['label']}..."):
                df, _, err = fetch_data(meta['source'], meta['id'], api_key)
                
                if df is not None and not df.empty:
                    df = df.rename(columns={'value': meta['label']})
                    
                    if 'date' in df.columns:
                        df = df.set_index('date')
                        
                        # --- FIX: Prevent Crashes & Gaps ---
                        # 1. Keep only numeric column
                        df = df[[meta['label']]] 
                        # 2. Resample to Monthly & Forward Fill (Connects the dots for Annual data)
                        df = df.resample('ME').mean().ffill()
                        
                        st.session_state.composer_data[meta['label']] = df
                else:
                    st.error(f"Failed to load {meta['label']}: {err}")
            progress.progress((i + 1) / len(selected_layers))

# --- 2. GLOBAL CONTROLS ---
if st.session_state.composer_data:
    st.divider()
    st.subheader("2. Timeline Filter")
    
    # Calculate Global Min/Max Dates across all datasets
    all_dates = []
    for df in st.session_state.composer_data.values():
        all_dates.extend(df.index)
        
    if all_dates:
        min_date = min(all_dates).date()
        max_date = max(all_dates).date()
        
        # Dual-Thumb Slider for Date Range
        start_date, end_date = st.slider(
            "Filter Years:",
            min_value=min_date,
            max_value=max_date,
            value=(min_date, max_date),
            format="YYYY-MM"
        )
    else:
        st.warning("No valid dates found in datasets.")
        st.stop()

    # --- 3. RENDER SEPARATE CHARTS ---
    st.divider()
    
    # Iterate through each loaded dataset
    for label, df in st.session_state.composer_data.items():
        
        # A. Filter by Slider
        mask = (df.index.date >= start_date) & (df.index.date <= end_date)
        plot_df = df[mask]
        
        if plot_df.empty:
            continue
            
        # B. Create Individual Chart
        # Using Area chart for a bit more "volume" feel, but Line works too
        fig = px.area(
            plot_df, 
            x=plot_df.index, 
            y=label,
            title=f"📈 {label}",
            template="plotly_white",
            height=300 # Shorter height since we are stacking them
        )
        
        # Visual cleanup
        fig.update_layout(
            margin=dict(l=20, r=20, t=40, b=20),
            hovermode="x unified",
            xaxis_title=None,
            yaxis_title=None
        )
        
        # C. Display
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Select datasets from the sidebar to begin.")