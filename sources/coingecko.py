import pandas as pd
import requests

def get_crypto_data(coin_id, **kwargs):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
    try:
        r = requests.get(url, headers={'User-Agent': 'FCAT_Validator'}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data['prices'], columns=['timestamp', 'value'])
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df, data, None
        return None, None, f"Status {r.status_code}"
    except Exception as e:
        return None, None, str(e)