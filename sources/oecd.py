import pandas as pd
import requests
import urllib3
from io import StringIO

# Disable SSL warnings for the "Nuclear" fix
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_oecd_data(dataset_id, **kwargs):
    """
    Fetches data from OECD Data Explorer API.
    dataset_id: Must be the FULL URL from the Developer API tab.
    NOTE: This uses 'Browser Masquerading' to bypass the 403 Cloud Firewall.
    IN PRODUCTION: This logic must move to a private middleware server.
    """
    
    # 1. BROWSER MASQUERADE HEADERS
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/csv,application/json,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://data-explorer.oecd.org/',
        'Connection': 'keep-alive'
    }

    try:
        session = requests.Session()
        r = session.get(dataset_id, headers=headers, verify=False, timeout=25)

        if r.status_code == 200:
            content_type = r.headers.get("Content-Type", "")
            
            # Case A: CSV (Common for data downloads)
            if "csv" in content_type:
                try:
                    df = pd.read_csv(StringIO(r.text))
                    
                    # --- NORMALIZATION LOGIC ---
                    
                    # 1. Standard Time/Value Mapping
                    if 'TIME_PERIOD' in df.columns:
                        df.rename(columns={'TIME_PERIOD': 'date', 'OBS_VALUE': 'value'}, inplace=True)
                        df['date'] = pd.to_datetime(df['date'], errors='coerce')
                        df['value'] = pd.to_numeric(df['value'], errors='coerce')

                    # 2. NETWORK DATA MAPPING (For Scientific Collaboration)
                    if 'REF_AREA' in df.columns and 'COUNTERPART_AREA' in df.columns:
                        df.rename(columns={
                            'REF_AREA': 'source',             # ID: "FRA"
                            'COUNTERPART_AREA': 'target',     # ID: "USA"
                            'Reference area': 'source_name',  # Label: "France"
                            'Counterpart area': 'target_name' # Label: "United States"
                        }, inplace=True)
                        
                        # Filter for raw counts if multiple measures exist
                        if 'Measure' in df.columns:
                             df = df[df['Measure'].str.contains('whole counts', na=False)]

                    return df, None, None
                except Exception as e:
                    return None, {"raw_text": r.text[:1000]}, f"CSV Parsing Failed: {e}"

            # Case B: JSON
            elif "json" in content_type:
                return None, r.json(), "Connection Successful (JSON Received)"
            
            # Case C: Unknown
            else:
                return None, {"raw_text": r.text[:500]}, f"Unknown Content-Type: {content_type}"

        elif r.status_code == 403:
            return None, None, "❌ 403 Forbidden: Server blocked the request. (Likely Cloud IP Block)"
            
        elif r.status_code == 429:
             return None, None, "❌ 429 Too Many Requests: Rate limit exceeded (60/hour)."

        return None, None, f"Status {r.status_code}"

    except Exception as e:
        return None, None, str(e)