import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

st.set_page_config(page_title="Creative Lab", layout="wide")

st.title("🎨 Creative Lab: The Abstraction Engine")
st.markdown("""
**For Designers:** Don't look at the line chart. Look at the *behavior*. 
Map raw data to abstract visual properties to see how the 'texture' of the story feels.
""")

# --- 1. GET DATA FROM COMPOSER ---
if "composer_data" not in st.session_state or not st.session_state.composer_data:
    st.warning("⚠️ No data found. Please go to 'Story Composer' and fetch some datasets first.")
    st.stop()

# Sidebar Controls
with st.sidebar:
    st.header("🎛️ Design Controls")
    
    # Select Dataset
    dataset_options = list(st.session_state.composer_data.keys())
    selected_dataset = st.selectbox("1. Driver Dataset", dataset_options)
    
    # Select Metaphor
    metaphor = st.radio(
        "2. Visual Metaphor", 
        ["The Orb (Scale)", "The Mood (Color)", "The Swarm (Chaos/Noise)", "The Bar (Progress)"]
    )
    
    # Playback Speed
    speed = st.slider("Playback Speed", 0.01, 0.5, 0.1)
    
    # Loop Toggle
    auto_play = st.toggle("Auto-Play Story", value=False)

# Prepare Data
df = st.session_state.composer_data[selected_dataset]
df = df.dropna()
values = df.iloc[:, 0].values
dates = df.index

# Normalize Data (0 to 1 scale) for generic visual mapping
min_val, max_val = np.min(values), np.max(values)
norm_values = (values - min_val) / (max_val - min_val)

# --- 2. THE VISUAL STAGE ---
st.divider()
col1, col2 = st.columns([3, 1])

with col1:
    chart_spot = st.empty()

with col2:
    stats_spot = st.empty()

# --- 3. ANIMATION LOOP ---
# If Auto-Play is ON, we loop. If OFF, we show a slider for manual scrubbing.

if not auto_play:
    # Manual Scrub
    step = st.slider("Timeline Scrubber", 0, len(dates)-1, 0)
    current_val = values[step]
    current_norm = norm_values[step]
    current_date = dates[step]
    
    # Render Single Frame
    fig = go.Figure()
    
    if metaphor == "The Orb (Scale)":
        # A circle that grows/shrinks
        fig.add_trace(go.Scatter(
            x=[0], y=[0],
            mode='markers',
            marker=dict(
                size=50 + (current_norm * 250), # Maps 0-1 to 50px-300px
                color=current_norm,
                colorscale='Viridis',
                showscale=False
            )
        ))
        fig.update_layout(xaxis_range=[-1,1], yaxis_range=[-1,1], title="Mapping: Value -> Radius")

    elif metaphor == "The Mood (Color)":
        # A block that shifts from Blue (Low) to Red (High)
        fig.add_trace(go.Bar(
            x=["Mood"], y=[1],
            marker=dict(
                color=current_norm,
                colorscale='RdBu_r', # Red is High, Blue is Low
                cmin=0, cmax=1
            )
        ))
        fig.update_layout(yaxis_range=[0,1], title="Mapping: Value -> Heat/Color")

    elif metaphor == "The Swarm (Chaos/Noise)":
        # Random particles that spread out more as value increases
        # We generate 50 random points
        spread = 0.1 + (current_norm * 2.0)
        noise_x = np.random.normal(0, spread, 50)
        noise_y = np.random.normal(0, spread, 50)
        
        fig.add_trace(go.Scatter(
            x=noise_x, y=noise_y,
            mode='markers',
            marker=dict(color='black', size=8, opacity=0.6)
        ))
        fig.update_layout(xaxis_range=[-3,3], yaxis_range=[-3,3], title="Mapping: Value -> Entropy/Spread")
        
    elif metaphor == "The Bar (Progress)":
        # Simple progress bar
        fig.add_trace(go.Bar(
            y=["Value"], x=[current_norm],
            orientation='h',
            marker=dict(color='#00CC96')
        ))
        fig.update_layout(xaxis_range=[0,1], title="Mapping: Value -> Length")

    # Common Cleanup
    fig.update_layout(
        template="plotly_white", 
        height=500, 
        xaxis=dict(visible=False), 
        yaxis=dict(visible=False)
    )
    
    # In manual mode, it only runs once per script execution, so 'key' is optional but good practice
    chart_spot.plotly_chart(fig, use_container_width=True, key="manual_chart")
    
    stats_spot.metric("Date", current_date.strftime('%Y-%b'))
    stats_spot.metric("Raw Value", f"{current_val:,.2f}")
    stats_spot.metric("Normalized Impact", f"{current_norm:.2f}")

else:
    # Auto-Play Logic
    for i in range(0, len(dates), 2): # Skip frames for speed if needed
        current_val = values[i]
        current_norm = norm_values[i]
        current_date = dates[i]
        
        fig = go.Figure()
        
        # (Repeat Logic - Simplified for brevity in loop)
        if metaphor == "The Orb (Scale)":
            fig.add_trace(go.Scatter(x=[0], y=[0], mode='markers', marker=dict(size=50+(current_norm*250), color=current_norm, colorscale='Viridis')))
            fig.update_layout(xaxis_range=[-1,1], yaxis_range=[-1,1])
        
        elif metaphor == "The Mood (Color)":
             fig.add_trace(go.Bar(x=["Mood"], y=[1], marker=dict(color=current_norm, colorscale='RdBu_r', cmin=0, cmax=1)))
             fig.update_layout(yaxis_range=[0,1])

        elif metaphor == "The Swarm (Chaos/Noise)":
            spread = 0.1 + (current_norm * 2.0)
            fig.add_trace(go.Scatter(x=np.random.normal(0, spread, 50), y=np.random.normal(0, spread, 50), mode='markers', marker=dict(color='black', opacity=0.6)))
            fig.update_layout(xaxis_range=[-3,3], yaxis_range=[-3,3])

        elif metaphor == "The Bar (Progress)":
            fig.add_trace(go.Bar(y=["Value"], x=[current_norm], orientation='h', marker=dict(color='#00CC96')))
            fig.update_layout(xaxis_range=[0,1])

        fig.update_layout(template="plotly_white", height=500, xaxis=dict(visible=False), yaxis=dict(visible=False))
        
        # --- FIX IS HERE ---
        # We add a unique 'key' for every iteration of the loop (e.g. "auto_chart_0", "auto_chart_2", etc.)
        chart_spot.plotly_chart(fig, use_container_width=True, key=f"auto_chart_{i}")
        
        stats_spot.metric("Date", current_date.strftime('%Y-%b'))
        stats_spot.metric("Raw Value", f"{current_val:,.2f}")
        
        time.sleep(speed)