import streamlit as st
import urllib3
from core.catalog import DATA_CATALOG
from core.ui import render_completeness, render_visual_potential, render_data_inspector
from sources import fetch_data
from sources.local import parse_uploaded_file

# Config
st.set_page_config(page_title="FCAT Validator", layout="wide")
urllib3.disable_warnings()

# Configuration for Custom Inputs
CUSTOM_INPUT_CONFIG = {
    "fred": {"label": "Enter FRED Series ID:", "placeholder": "e.g., GDP"},
    "bls": {"label": "Enter BLS Series ID:", "placeholder": "e.g., CUSR0000SA0"},
    "ecb": {"label": "Enter ECB Series Key:", "placeholder": "e.g., ICP.M.U2.N.000000.4.ANR"},
    "coingecko": {"label": "Enter Coin ID (Slug):", "placeholder": "e.g., bitcoin"},
    "imf": {"label": "Paste IMF API Link:", "placeholder": "http://dataservices.imf.org/REST/SDMX_JSON.svc/..."},
    "oecd": {"label": "Paste Developer API URL:", "placeholder": "https://sdmx.oecd.org/..."},
    "census": {"label": "Paste Census API URL:", "placeholder": "https://api.census.gov/data/..."}
}

def main():
    st.title("Data Viability Tracker")
    st.caption("Universal Data Source Validator")

    # --- 0. SESSION STATE SETUP (The Fix) ---
    # We initialize these variables in memory so they persist across re-runs
    if "data_payload" not in st.session_state:
        st.session_state.data_payload = None
    if "data_label" not in st.session_state:
        st.session_state.data_label = None
    if "data_error" not in st.session_state:
        st.session_state.data_error = None
    if "raw_json" not in st.session_state:
        st.session_state.raw_json = None

    # 1. SIDEBAR SELECTION
    with st.sidebar:
        st.header("Configuration")
        source_options = ["📁 Upload Local File"] + list(DATA_CATALOG.keys())
        source_name = st.selectbox("Source", source_options)
        
        # --- MODE A: FILE UPLOAD ---
        if source_name == "📁 Upload Local File":
            uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=['csv', 'xlsx'])
            run = st.button("Analyze File", type="primary")
            
        # --- MODE B: API CONNECTION ---
        else:
            config = DATA_CATALOG[source_name]
            source_type = config["type"]
            dataset_options = ["🛠️ Custom Query"] + list(config["datasets"].keys())
            dataset_label = st.selectbox("Dataset", dataset_options)
            
            if dataset_label == "🛠️ Custom Query":
                rules = CUSTOM_INPUT_CONFIG.get(source_type, {"label": "Enter ID:", "placeholder": ""})
                dataset_id = st.text_input(rules["label"], placeholder=rules["placeholder"])
            else:
                dataset_id = config["datasets"][dataset_label]
            
            # API Key Logic
            api_key = None
            if source_type in ["fred", "bls"]:
                secret_key = f"{source_type.upper()}_API_KEY"
                if secret_key in st.secrets:
                    api_key = st.secrets[secret_key]
                    st.success(f"🔑 {source_name} Key Loaded")
                else:
                    api_key = st.text_input(f"{source_name} Key", type="password")

            run = st.button("Run Validation", type="primary")

    # 2. EXECUTION LOGIC (Save to Session State)
    if run:
        # Clear previous state
        st.session_state.data_payload = None
        st.session_state.data_error = None
        
        df = None
        error = None
        raw_json = None
        label = "Data"

        # Logic for File Upload
        if source_name == "📁 Upload Local File":
            if uploaded_file is not None:
                df, raw_json, error = parse_uploaded_file(uploaded_file)
                label = uploaded_file.name
            else:
                st.warning("⚠️ Please select a file first.")
                st.stop()
        
        # Logic for API
        else:
            if not dataset_id:
                st.warning("⚠️ Please enter a valid ID or URL.")
                st.stop()
            label = dataset_label
            with st.spinner('Connecting to source...'):
                df, raw_json, error = fetch_data(source_type, dataset_id, api_key)

        # SAVE RESULTS TO SESSION STATE
        st.session_state.data_payload = df
        st.session_state.data_label = label
        st.session_state.data_error = error
        st.session_state.raw_json = raw_json

    # 3. RENDERING (Read from Session State)
    # This runs every time, even after you interact with the chart builder
    
    if st.session_state.data_error:
        st.error(f"❌ FAIL: {st.session_state.data_error}")
        if st.session_state.raw_json:
             with st.expander("View Raw Error Response"):
                 st.json(st.session_state.raw_json)

    elif st.session_state.data_payload is not None:
        df = st.session_state.data_payload
        label = st.session_state.data_label
        
        if not df.empty:
            st.success(f"✅ Loaded: {label}")
            
            # 1. Inspector
            selected_df = render_data_inspector(df)
            
            # 2. Completeness
            render_completeness(df)
            
            # 3. Visual Potential (Now safe to interact with)
            render_visual_potential(selected_df, label)
            
    elif st.session_state.raw_json:
        st.info("Raw Data retrieved (Parsing failed or skipped):")
        st.json(st.session_state.raw_json)

if __name__ == "__main__":
    main()