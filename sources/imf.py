import pandas as pd
import requests
import urllib3
import streamlit as st

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@st.cache_data(ttl=3600, show_spinner="Fetching data from IMF...")
def get_imf_data(dataset_url, **kwargs):
    """
    Fetches data from IMF. 
    Supports BOTH:
    1. DataMapper API (imf.org/external/datamapper)
    2. Data Services API (dataservices.imf.org / data.imf.org)
    """
    
    # 0. SAFETY CHECK: Ensure it is a Link
    if not dataset_url.startswith("http"):
        return None, None, "❌ Error: Please paste the full API URL (starting with http/https)."

    try:
        # 1. Request
        # IMF requires a User-Agent
        headers = {'User-Agent': 'FCAT_Validator/1.0'}
        r = requests.get(dataset_url, headers=headers, verify=False, timeout=45)
        
        if r.status_code == 200:
            raw_json = r.json()
            
            # --- PARSING LOGIC SWITCHER ---
            
            # CASE A: IMF SDMX-JSON (data.imf.org / dataservices.imf.org)
            if 'CompactData' in raw_json:
                try:
                    series_data = raw_json['CompactData']['DataSet']['Series']
                    
                    # Handle if Series is a single dict or list of dicts
                    if isinstance(series_data, dict):
                        series_data = [series_data]
                        
                    data_list = []
                    for s in series_data:
                        country_code = s.get('@REF_AREA', 'Unknown')
                        obs = s.get('Obs', [])
                        
                        if isinstance(obs, dict): obs = [obs] # Handle single observation
                        
                        for o in obs:
                            data_list.append({
                                'source': country_code,
                                'date': pd.to_datetime(o.get('@TIME_PERIOD')),
                                'value': float(o.get('@OBS_VALUE'))
                            })
                            
                    df = pd.DataFrame(data_list)
                    return df.dropna().sort_values(['source', 'date']), raw_json, None
                    
                except Exception as e:
                    return None, raw_json, f"SDMX Parsing Failed: {str(e)}"

            # CASE B: IMF DataMapper (imf.org/external/datamapper)
            elif 'values' in raw_json:
                try:
                    values = raw_json['values']
                    indicator_key = list(values.keys())[0] # Dynamic Key
                    country_data = values[indicator_key]
                    
                    data_list = []
                    for country_code, year_dict in country_data.items():
                        for year, val in year_dict.items():
                            try:
                                data_list.append({
                                    'source': country_code, 
                                    'date': pd.to_datetime(f"{year}-01-01"),
                                    'value': float(val)
                                })
                            except: continue
                            
                    df = pd.DataFrame(data_list)
                    return df.dropna().sort_values(['source', 'date']), raw_json, None

                except Exception as e:
                    return None, raw_json, f"DataMapper Parsing Failed: {str(e)}"
            
            # CASE C: Unknown Structure
            else:
                return None, raw_json, "Unknown JSON Structure (Not SDMX or DataMapper)."

        elif r.status_code == 429:
             return None, None, "❌ 429 Rate Limit: Too many requests."
             
        return None, None, f"Status {r.status_code}"

    except Exception as e:
        return None, None, str(e)