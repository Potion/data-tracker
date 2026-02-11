import pandas as pd
import requests

def get_fred_data(dataset_id, api_key):
    if not api_key:
        return None, None, "API Key Required"
    
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={dataset_id}&api_key={api_key}&file_type=json"
    
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            df = pd.DataFrame(r.json()['observations'])
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            return df.dropna(), r.json(), None
        return None, None, f"Status {r.status_code}"
    except Exception as e:
        return None, None, str(e)