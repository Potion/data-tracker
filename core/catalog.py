DATA_CATALOG = {
    "Consumer Price Index: New Vehicles" : { 
        "type" : "fred",
        "datasets" : { 
            "Consumer Price Index: New Vehicles" : "https://fred.stlouisfed.org/release/tables?rid=10&eid=34561#snid=34605"
        }
    },

    "House Price Index Per State" : {
        "type" : "fred",
        "datasets" : { 
            "House Price Index for Alaska" : "AKSTHPI",
            "House Price Index for Alabama" : "ALSTHPI",
            "House Price Index for Arkansas" : "ARSTHPI",
            "House Price Index for Arizona" : "AZSTHPI",
            "House Price Index for California" : "CASTHPI",
            "House Price Index for Colorado" : "COSTHPI",
            "House Price Index for Connecticut" : "CTSTHPI",
            "House Price Index for the District of Columbia" : "DCSTHPI",
            "House Price Index for Delaware" : "DESTHPI",
            "House Price Index for Florida" : "FLSTHPI",
            "House Price Index for Georgia" : "GASTHPI",
            "House Price Index for Hawaii" : "HISTHPI",
            "House Price Index for Iowa" : "IASTHPI",
            "House Price Index for Idaho" : "IDSTHPI",
            "House Price Index for Illinois" : "ILSTHPI",
            "House Price Index for Indiana" : "INSTHPI",
            "House Price Index for Kansas" : "KSSTHPI",
            "House Price Index for Kentucky" : "KYSTHPI",
            "House Price Index for Louisiana" : "LASTHPI",
            "House Price Index for Massachusetts" : "MASTHPI",
            "House Price Index for Maryland" : "MDSTHPI",
            "House Price Index for Maine" : "MESTHPI",
            "House Price Index for Michigan" : "MISTHPI",
            "House Price Index for Minnesota" : "MNSTHPI",
            "House Price Index for Missouri" : "MOSTHPI",
            "House Price Index for Mississippi" : "MSSTHPI",
            "House Price Index for Montana" : "MTSTHPI",
            "House Price Index for North Carolina" : "NCSTHPI",
            "House Price Index for North Dakota" : "NDSTHPI",
            "House Price Index for Nebraska" : "NESTHPI",
            "House Price Index for New Hampshire" : "NHSTHPI",
            "House Price Index for New Jersey" : "NJSTHPI",
            "House Price Index for New Mexico" : "NMSTHPI",
            "House Price Index for Nevada" : "NVSTHPI",
            "House Price Index for New York" : "NYSTHPI",
            "House Price Index for Ohio" : "OHSTHPI",
            "House Price Index for Oklahoma" : "OKSTHPI",
            "House Price Index for Oregon" : "ORSTHPI",
            "House Price Index for Pennsylvania" : "PASTHPI",
            "House Price Index for Rhode Island" : "RISTHPI",
            "House Price Index for South Carolina" : "SCSTHPI",
            "House Price Index for South Dakota" : "SDSTHPI",
            "House Price Index for Tennessee" : "TNSTHPI",
            "House Price Index for Texas" : "TXSTHPI",
            "House Price Index for Utah" : "UTSTHPI",
            "House Price Index for Virginia" : "VASTHPI",
            "House Price Index for Vermont" : "VTSTHPI",
            "House Price Index for Washington" : "WASTHPI",
            "House Price Index for Wisconsin" : "WISTHPI",
            "House Price Index for West Virginia" : "WVSTHPI",
            "House Price Index for Wyoming" : "WYSTHPI"
        }
    },

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