import pandas as pd
import streamlit as st

@st.cache_data(show_spinner="Parsing uploaded file...")
def parse_uploaded_file(uploaded_file):
    """
    Parses CSV or Excel files uploaded by the user.
    Attempts to auto-detect headers and date columns.
    """
    try:
        # 1. Determine File Type
        filename = uploaded_file.name.lower()
        
        if filename.endswith('.csv'):
            # Try reading with default settings
            df = pd.read_csv(uploaded_file)
            
            # Smart Logic: Check if the first few rows are actually metadata (common in IMF/FRED)
            # If the dataset has only 1 column, it's likely a metadata header.
            if len(df.columns) < 2:
                # Try re-reading skipping the first few rows
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, skiprows=4) # Blind guess for "messy" headers
                
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(uploaded_file)
        else:
            return None, None, "❌ Unsupported file format. Please upload CSV or Excel."

        # 2. Standardization (Try to find 'Date' and 'Value')
        # Normalize column names to lowercase for checking
        df.columns = df.columns.str.strip()
        
        # Auto-Rename common Date columns
        date_cols = [c for c in df.columns if 'date' in c.lower() or 'period' in c.lower() or 'time' in c.lower()]
        if date_cols and 'date' not in df.columns:
            df.rename(columns={date_cols[0]: 'date'}, inplace=True)
            df['date'] = pd.to_datetime(df['date'], errors='coerce')

        # Auto-Rename common Value columns
        val_cols = [c for c in df.columns if 'value' in c.lower() or 'obs' in c.lower() or 'rate' in c.lower()]
        if val_cols and 'value' not in df.columns:
            df.rename(columns={val_cols[0]: 'value'}, inplace=True)
            df['value'] = pd.to_numeric(df['value'], errors='coerce')

        return df, {"info": "Loaded from local file"}, None

    except Exception as e:
        return None, None, f"Parsing Error: {str(e)}"