import pandas as pd
import requests
from datetime import datetime

def get_bls_data(dataset_id, api_key):
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    current_year = datetime.now().year
    
    payload = {
        "seriesid": [dataset_id],
        "startyear": str(current_year - 19),
        "endyear": str(current_year)
    }
    
    if api_key:
        payload["registrationkey"] = api_key

    try:
        r = requests.post(url, json=payload, headers={'Content-type': 'application/json'}, timeout=10)
        if r.status_code == 200:
            raw_json = r.json()
            if raw_json['status'] != 'REQUEST_SUCCEEDED':
                 return None, raw_json, f"BLS Error: {raw_json.get('message', 'Unknown')}"
            
            try:
                series_data = raw_json['Results']['series'][0]['data']
                df = pd.DataFrame(series_data)
                df = df[df['period'].str.contains("M")]
                df['date'] = pd.to_datetime(df['year'] + "-" + df['period'].str.replace("M", "") + "-01")
                df['value'] = pd.to_numeric(df['value'], errors='coerce')
                return df.sort_values('date')[['date', 'value']], raw_json, None
            except (KeyError, IndexError):
                return None, raw_json, "No data found."
        return None, None, f"Status {r.status_code}"
    except Exception as e:
        return None, None, str(e)