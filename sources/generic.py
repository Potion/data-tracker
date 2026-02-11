import requests
import urllib3

urllib3.disable_warnings()

def get_generic_json(dataset_id, **kwargs):
    # dataset_id is the URL
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(dataset_id, headers=headers, verify=False, timeout=15)
        if r.status_code == 200:
            return None, r.json(), None # No DF, just JSON
        elif r.status_code == 403:
            return None, None, "Access Denied (403)"
        return None, None, f"Status {r.status_code}"
    except Exception as e:
        return None, None, str(e)