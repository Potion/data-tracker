import pandas as pd
import requests

def get_census_data(url: str, api_key=None):
    """
    Fetches data from US Census API. 
    Handles the specific 'List of Lists' format (Header row + Data rows).
    """
    try:
        # 1. Handle Missing Protocol
        if not url.startswith("http"):
            url = f"https://{url}"

        # 2. Fetch Data
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # 3. Strategy A: Census Format (List of Lists)
        # Checks if it looks like: [ ["NAME", "POP"], ["Alabama", "50000"] ]
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            headers = data[0]
            rows = data[1:]
            
            df = pd.DataFrame(rows, columns=headers)
            
            # Auto-convert numeric columns
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='ignore')
                
            return df, data, None
        
        # 4. Strategy B: Standard JSON (List of Objects)
        # Fallback if you paste a non-Census URL into this slot
        elif isinstance(data, list):
            df = pd.DataFrame(data)
            return df, data, None
            
        else:
            return None, data, "JSON format not recognized (Expected List of Lists or List of Objects)"

    except Exception as e:
        return None, None, f"Census Connection Error: {str(e)}"