DATA_CATALOG = {
    "35 Years": {
        "type": "fred",
        "datasets": {
            # THE CHARACTERS (Alex & Kate)
            "Median Household Income": "MEHOINUSA646N",   # Income Proxy
            "Personal Saving Rate": "PSAVERT",            # Behavior Proxy
            "Expenses (Age 35-44)": "CXUTOTALEXPLB0404M", # Expenses Proxy
            "Retirement Expenses (Age 65+)": "CXUTOTALEXPLB0407M", # <-- The Finish Line
            # THE ENVIRONMENT (The Economy)
            "US GDP": "GDP",
            "S&P 500 (Daily)": "SP500",
            "Market Volatility (VIX)": "VIXCLS",
            "30-Year Mortgage Rate": "MORTGAGE30US"
        }
    },
    "FRED": {
        "type": "fred",
        "datasets": {
            "US GDP": "GDP",
            "Tech Output": "IPB51222S",
            "Cloud Costs": "PCU518210518210",
            "Bitcoin": "CBBTCUSD"
        }
    },
    "BLS": {
        "type": "bls",
        "datasets": {
            "US CPI (Inflation)": "CUSR0000SA0",
            "US Unemployment": "LNS14000000"
        }
    },
    "CoinGecko": {
        "type": "coingecko",
        "datasets": {
            "Bitcoin History": "bitcoin",
            "Ethereum History": "ethereum"
        }
    },
    "OECD": {
        "type": "oecd",
        "datasets": {
            "Scientific Collaboration (2021)": "https://sdmx.oecd.org/public/rest/data/OECD.STI.STP,DSD_BIBLIO@DF_BIBLIO_COLLAB,1.1/all?startPeriod=2021&endPeriod=2021&dimensionAtObservation=AllDimensions",
            "USA GDP (Quarterly)": "https://sdmx.oecd.org/public/rest/data/OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA,1.1/Q.USA.B1GQ...?startPeriod=2015-Q1&dimensionAtObservation=AllDimensions",
            "Trust in Government (Map)": "https://sdmx.oecd.org/public/rest/data/OECD.GOV.GG,DSD_GOV_TRUST@DF_TRUST_INST,1.0/.......?startPeriod=2020&dimensionAtObservation=AllDimensions"
        }
    },
    "ECB": {
        "type": "ecb",
        "datasets": {
            "Eurozone Inflation (HICP)": "ICP.M.U2.N.000000.4.ANR",
            "USD/EUR Exchange Rate": "EXR.D.USD.EUR.SP00.A"
        }
    },
    "US Census": {
        "type": "census",
        "datasets": {
            "Population by State (2020)": "https://api.census.gov/data/2020/dec/pl?get=NAME,P1_001N&for=state:*",
            "Median Income by County (2021)": "https://api.census.gov/data/2021/acs/acs1/profile?get=NAME,DP03_0062E&for=county:*",
            "Poverty Rate by State": "https://api.census.gov/data/timeseries/poverty/saipe?get=NAME,SAEPOVRTALL_PT&for=state:*&time=2021"
        }
    },
    "IMF": {
        "type": "imf",
        "datasets": {
            "Paste API Link": "" 
        }
    }
}