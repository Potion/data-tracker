import pandas as pd
import requests
import streamlit as st

@st.cache_data(ttl=3600, show_spinner="Fetching ECB data...")
def get_ecb_data(dataset_id, **kwargs):
    """
    Fetches data from ECB Data Portal.
    Base URL: https://data-api.ecb.europa.eu/service/data/
    """
    # 1. Handle Short vs Full IDs
    if "." in dataset_id and "/" not in dataset_id:
        flow_ref, key = dataset_id.split(".", 1)
        resource_path = f"{flow_ref}/{key}"
    else:
        resource_path = dataset_id

    url = f"https://data-api.ecb.europa.eu/service/data/{resource_path}"
    
    # 2. Set Headers (Important for SDMX)
    headers = {
        "Accept": "application/json",
        "User-Agent": "FCAT_Validator"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        
        if r.status_code == 200:
            raw_json = r.json()
            try:
                # 3. Parse ECB SDMX Structure
                if 'dataSets' not in raw_json or not raw_json['dataSets']:
                    return None, raw_json, "Empty dataSets in response"
                
                dataset = raw_json['dataSets'][0]
                if 'series' in dataset:
                    series_dict = dataset['series']
                    # Just grab the first series found
                    key = list(series_dict.keys())[0]
                    observations = series_dict[key]['observations']
                else:
                    return None, raw_json, "Could not locate 'series' in SDMX response"

                # 4. Extract Dates from Structure
                time_dim = raw_json['structure']['dimensions']['observation'][0]['values']
                
                # 5. Build DataFrame
                data_list = []
                for time_idx, obs_data in observations.items():
                    date_str = time_dim[int(time_idx)]['name']
                    val = obs_data[0]
                    data_list.append({'date': date_str, 'value': val})
                
                df = pd.DataFrame(data_list)
                df['date'] = pd.to_datetime(df['date'], errors='coerce') 
                df['value'] = pd.to_numeric(df['value'])
                
                # 6. Basic Cleanup
                df = df.dropna().sort_values('date')
                
                return df, raw_json, None
                
            except Exception as parse_e:
                return None, raw_json, f"SDMX Parsing Failed: {parse_e}"
        
        elif r.status_code == 406:
             return None, None, "406 Error: Server rejected headers."
        else:
            return None, None, f"Status {r.status_code}"
            
    except Exception as e:
        return None, None, str(e)