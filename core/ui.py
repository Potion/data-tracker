import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import networkx as nx
import re

def normalize_wide_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detects if a dataset is 'Wide' (dates as columns) and melts it into 'Long' format.
    Fixes name collisions if a 'value' column already exists.
    """
    # 1. Identify Date Columns (Matches YYYY, YYYY-QQ, YYYY-MM)
    date_cols = [c for c in df.columns if re.match(r'^\d{4}(?:-[QM]\d{2})?$', str(c))]
    
    # If we found a significant number of date columns (e.g., > 3), assume it's wide
    if len(date_cols) > 3:
        # 2. Identify ID Columns (Everything else)
        id_cols = [c for c in df.columns if c not in date_cols]
        
        # --- COLLISION FIX ---
        # If 'value' is already in id_cols, we need to handle the conflict.
        target_value_name = 'value'
        needs_swap = False
        
        if 'value' in id_cols:
            # Temporary name to avoid error
            target_value_name = 'melted_numeric_value' 
            needs_swap = True
            
        # 3. Melt (Pivot) the Data
        df_melted = df.melt(id_vars=id_cols, value_vars=date_cols, var_name='date', value_name=target_value_name)
        
        # Post-Melt Swap: Rename the old 'value' (metadata) to allow numbers to be 'value'
        if needs_swap:
            df_melted = df_melted.rename(columns={'value': 'value_desc', 'melted_numeric_value': 'value'})
        
        # 4. Clean Date Formats
        df_melted['date'] = df_melted['date'].astype(str)
        df_melted['date'] = df_melted['date'].str.replace(r'-Q1', '-01-01', regex=True)
        df_melted['date'] = df_melted['date'].str.replace(r'-Q2', '-04-01', regex=True)
        df_melted['date'] = df_melted['date'].str.replace(r'-Q3', '-07-01', regex=True)
        df_melted['date'] = df_melted['date'].str.replace(r'-Q4', '-10-01', regex=True)
        df_melted['date'] = df_melted['date'].str.replace(r'-M', '-', regex=True)
        
        # Normalize Annual
        df_melted['date'] = df_melted['date'].apply(lambda x: f"{x}-01-01" if len(x) == 4 else x)
        
        # Convert types
        df_melted['date'] = pd.to_datetime(df_melted['date'], errors='coerce')
        df_melted['value'] = pd.to_numeric(df_melted['value'], errors='coerce')
        
        return df_melted.dropna(subset=['value'])
        
    return df

def render_data_inspector(df: pd.DataFrame) -> pd.DataFrame:
    """
    Shows summary and Interactive Table. Returns filtered subset.
    """
    st.divider()
    st.subheader("🔍 Data Inspector")
    
    # High-Level Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", len(df))
    c2.metric("Columns", len(df.columns))
    
    if 'value' in df.columns and pd.api.types.is_numeric_dtype(df['value']):
        c4.metric("Volatility", f"{df['value'].std():.2f}")
    else:
        c4.metric("Volatility", "N/A")

    st.markdown("👇 **Select rows** to filter the chart:")
    
    # Interactive Table
    # Limit to 1000 for performance
    event = st.dataframe(
        df.head(1000),
        use_container_width=True,
        on_select="rerun",
        selection_mode="multi-row",
        height=300
    )
    
    # Filter Logic
    if event.selection.rows:
        return df.iloc[event.selection.rows]
    return df

def render_completeness(df: pd.DataFrame):
    """
    Scorecard for dimensions.
    """
    st.divider()
    st.subheader("✅ Completeness Scorecard")
    
    dimensions = {
        "Temporal": ["date", "year", "time", "timestamp"],
        "Geospatial": ["iso", "country", "lat", "lon", "source", "state", "county", "fips", "name", "region"],
        "Quantitative": ["value", "price", "count", "gdp", "index", "obs_value", "p1_001n", "estimate"],
        "Relational": ["source", "target", "partner"]
    }
    
    cols = st.columns(4)
    for i, (dim, keywords) in enumerate(dimensions.items()):
        found = [col for col in df.columns if col.lower() in keywords]
        with cols[i]:
            if found:
                st.success(f"**{dim}**")
                st.caption(f"Found: `{found[0]}`")
            else:
                st.error(f"**{dim}**")
                st.caption("Missing")

def render_visual_potential(df: pd.DataFrame, label: str):
    """
    Interactive Chart Builder. 
    Allows user to select X, Y, and Color columns.
    """
    # 1. Normalize Data
    df = normalize_wide_data(df)
    
    st.divider()
    st.subheader("🎨 Chart Builder")

    if df.empty:
        st.warning("⚠️ No data available.")
        return

    # --- INTELLIGENT DEFAULTS ---
    # Guess the best columns so the user doesn't start with blank dropdowns
    all_cols = list(df.columns)
    
    # Guess X Axis (Time -> Text)
    default_x = all_cols[0]
    for c in ['date', 'year', 'time']: 
        if c in df.columns: default_x = c; break
    
    # Guess Y Axis (Numeric)
    default_y = all_cols[-1]
    num_cols = df.select_dtypes(include=['number']).columns.tolist()
    for c in ['value', 'price', 'gdp', 'count', 'obs_value']:
        if c in df.columns: default_y = c; break
    if not num_cols: default_y = default_x # Fallback
    
    # Guess Color (Categorical)
    default_color = "None"
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    for c in ['country', 'iso', 'source', 'type', 'category']:
        if c in df.columns: default_color = c; break
    
    # --- CONTROLS UI ---
    with st.expander("🛠️ **Configure Chart** (Axes & Filters)", expanded=True):
        c1, c2, c3 = st.columns(3)
        
        # Axis Selection
        x_col = c1.selectbox("X Axis (Category/Time)", all_cols, index=all_cols.index(default_x) if default_x in all_cols else 0)
        y_col = c2.selectbox("Y Axis (Value)", num_cols if num_cols else all_cols, index=num_cols.index(default_y) if default_y in num_cols else 0)
        
        # Color Selection
        color_options = ["None"] + all_cols
        # Safe default index
        color_index = color_options.index(default_color) if default_color in all_cols else 0
        color_col = c3.selectbox("Group/Color By", color_options, index=color_index)
        
        # Optional Filter
        st.divider()
        st.caption("Filter specific values:")
        filter_col = st.selectbox("Filter Column", ["None"] + cat_cols)
        
        plot_df = df.copy()
        if filter_col != "None":
            unique_vals = list(df[filter_col].unique())
            selected_vals = st.multiselect(f"Select values in '{filter_col}'", unique_vals, default=unique_vals[:5])
            if selected_vals:
                plot_df = plot_df[plot_df[filter_col].isin(selected_vals)]

    # --- RENDERING ENGINE ---
    
    st.markdown(f"**Visualizing:** `{y_col}` by `{x_col}`")
    
    try:
        # 1. NETWORK (Special Case)
        if 'source' in df.columns and 'target' in df.columns and x_col == 'date': 
            # Only switch to network if explicitly NOT plotting time-series
            pass 
        
        # 2. GENERAL PLOTTER
        if color_col != "None":
            # If too many groups, limit them to avoid crashing browser
            if plot_df[color_col].nunique() > 20:
                top_n = plot_df.groupby(color_col)[y_col].sum().nlargest(20).index
                plot_df = plot_df[plot_df[color_col].isin(top_n)]
                st.caption(f"ℹ️ Showing top 20 '{color_col}' groups only.")
                
            fig = px.line(plot_df, x=x_col, y=y_col, color=color_col, title=f"{label}: {y_col} by {x_col}", markers=True)
            
            # Switch to Bar if X is not date/numeric
            if not pd.api.types.is_datetime64_any_dtype(plot_df[x_col]) and not pd.api.types.is_numeric_dtype(plot_df[x_col]):
                 fig = px.bar(plot_df, x=x_col, y=y_col, color=color_col, title=f"{label}: {y_col} by {x_col}")
                 
        else:
            # Simple Chart
            fig = px.area(plot_df, x=x_col, y=y_col, title=f"{label}: {y_col} by {x_col}")
            
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Could not render chart: {e}")