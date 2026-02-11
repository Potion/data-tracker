from .fred import get_fred_data
from .bls import get_bls_data
from .coingecko import get_crypto_data
from .imf import get_imf_data
from .oecd import get_oecd_data       
from .ecb import get_ecb_data
from .generic import get_generic_json
from .census import get_census_data

STRATEGY_MAP = {
    "fred": get_fred_data,
    "bls": get_bls_data,
    "coingecko": get_crypto_data,
    "imf": get_imf_data,
    "oecd": get_oecd_data,           
    "ecb": get_ecb_data, 
    "generic": get_generic_json,
    "census": get_census_data
}

def fetch_data(source_type, dataset_id, api_key=None):
    strategy = STRATEGY_MAP.get(source_type)
    if not strategy:
        # Fallback for random URLs pasted into Custom Query
        if "http" in str(dataset_id):
             return get_generic_json(dataset_id)
        return None, None, f"No connector found for type: {source_type}"
    
    # Census doesn't strictly need a key for small calls, but we pass it if present
    return strategy(dataset_id, api_key=api_key)