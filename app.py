import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# --- PAGE CONFIG ---
st.set_page_config(page_title="Data Source Validator", layout="wide")

st.title("Data Viability Tracker")
st.markdown("""
This tool validates potential data sources against the project's **3 Core Criteria**:
1. **Accessibility:** Can we connect via API?
2. **Completeness:** Does it have the required dimensions (Time, Geo, Nodes)?
3. **Visual Potential:** Is the data volatile and fresh enough for a wall display?
""")

st.divider()

# --- SIDEBAR: CONFIGURATION ---
with st.sidebar:
    st.header("Connection Settings")
    # Check if the key exists in secrets.toml
    if "FRED_API_KEY" in st.secrets:
        api_key = st.secrets["FRED_API_KEY"]
        st.success("API Key loaded automatically")
    else:
        # Fallback: Ask user if key is missing
        api_key = st.text_input("FRED API Key", type="password")
    st.header("Select Test Dataset")

    data_option = st.selectbox(
        "Choose a Series to Test:",
        [
            "GDP (Standard Econ) - GDP", 
            "Coinbase Bitcoin (Crypto Pulse) - CBBTCUSD", 
            "Tech Hardware Output (Growth) - IPB51222S", 
            "Cloud/Hosting Prices (Cost) - PCU518210518210", 
            "US/Euro Exchange Rate (Global) - DEXUSEU"
        ]
    )
    
    # Extract the Series ID from the selection
    series_id = data_option.split(" - ")[-1]
    
    run_test = st.button("Run Viability Test", type="primary")

# --- CORE LOGIC ---
if run_test and api_key:
    # 1. TEST ACCESSIBILITY
    st.subheader("1. Accessibility Test")
    
    # Construct the API URL (The "Handshake")
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            st.success(f"✅ PASS: Connection Successful (Status 200)")
            data = response.json()
            df = pd.DataFrame(data['observations'])
            
            # Clean Data for Visualization
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna()
            
            # Show Raw Data Preview
            with st.expander("Inspect Raw JSON Payload"):
                st.json(data['observations'][0:5])
                
        else:
            st.error(f"❌ FAIL: Connection Refused (Status {response.status_code})")
            st.stop() # Stop the app if we can't connect
            
    except Exception as e:
        st.error(f"❌ FAIL: System Error - {e}")
        st.stop()

    st.divider()

    # 2. TEST COMPLETENESS
    st.subheader("2. Completeness Test (Dimensionality)")
    
    col1, col2, col3 = st.columns(3)
    
    # Check A: Temporal
    has_time = 'date' in df.columns
    col1.metric("Temporal Resolution", "Found" if has_time else "Missing", border=True)
    
    # Check B: Geospatial (Lat/Long)
    # FRED is known to fail this, so we check for it explicitly
    has_geo = any(col in df.columns for col in ['lat', 'long', 'latitude', 'country_code'])
    if has_geo:
        col2.success("Geospatial: FOUND")
    else:
        col2.error("Geospatial: MISSING")
        
    # Check C: Network (Relational)
    # We check if there are "Source" and "Target" columns
    has_network = any(col in df.columns for col in ['to', 'from', 'partner'])
    if has_network:
        col3.success("Network Depth: FOUND")
    else:
        col3.error("Network Depth: MISSING")
        
    st.info(f"📝 **Verdict:** {'Strong Timeline Candidate' if has_time else 'Incomplete'}. " 
            f"{'Fails Map/Network Requirements.' if not has_geo and not has_network else 'Good for Map/Network.'}")

    st.divider()

    # 3. TEST VISUAL POTENTIAL
    st.subheader("3. Visual Potential (Aesthetics & Physics)")
    
    # Metric: Volatility (Standard Deviation)
    volatility = df['value'].std()
    recent_val = df['value'].iloc[-1]
    last_date = df['date'].iloc[-1].strftime('%Y-%m-%d')
    
    # Determine Update Frequency based on date gaps
    df['days_diff'] = df['date'].diff().dt.days
    avg_gap = df['days_diff'].mean()
    
    if avg_gap <= 1:
        freq_label = "Daily (High Velocity)"
        freq_color = "green"
    elif avg_gap <= 31:
        freq_label = "Monthly (Medium Velocity)"
        freq_color = "orange"
    else:
        freq_label = "Annual/Quarterly (Low Velocity)"
        freq_color = "red"

    # Display Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Latest Update", last_date)
    m2.metric("Data Volatility", f"{volatility:.2f}")
    m3.markdown(f"**Update Rate:** :{freq_color}[{freq_label}]")

    # The Visual Proof (Chart)
    st.markdown("##### Visual Simulation")
    fig = px.line(df, x='date', y='value', title=f"Visual Output Simulation: {series_id}")
    st.plotly_chart(fig, use_container_width=True)
    
    if freq_color == "red":
        st.warning("⚠️ **Warning:** This data is too slow for a real-time 'Attractor' mode. Use only for 'Context' mode.")
    elif freq_color == "green":
        st.success("🚀 **Success:** High-frequency data detected. Suitable for 'Live Pulse' visualization.")

elif run_test and not api_key:
    st.warning("⚠️ Please enter a FRED API Key to run the test.")