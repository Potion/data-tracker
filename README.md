# Data Source Validator

A lightweight Streamlit application designed to test the technical viability of external data feeds. This tool allows developers and data stakeholders to quickly validate public APIs against core integration criteria before committing to full-scale engineering. Website link is https://fcat-data-tracker.streamlit.app/

## 🎯 Objective

Validates potential data sources against three core criteria:
1.  **Accessibility:** Can we connect via API? (Checks for status codes, auth headers, and firewalls).
2.  **Completeness:** Does the data contain the necessary dimensions (Time, Geo, Network)?
3.  **Visual Potential:** Is the data volatile or granular enough for compelling visualization?

## 🚀 Features

* **Live API Testing:** Connects directly to endpoints (FRED, CoinGecko, etc.) to verify uptime.
* **Strict Validation Mode:** No simulations. Reports raw HTTP errors (403, 504) to expose integration risks.
* **Schema Inspection:** Automatically parses JSON responses to detect key columns (Dates, Values, Country Codes).
* **Visual Preview:** Generates instant Plotly charts to verify data shape and volatility.
* **Browser Masquerading:** Includes header logic to test APIs that block standard Python user agents.

## 🛠️ Prerequisites

* Python 3.8+
* pip

## 📦 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/jeffpwang/fcat-data-tracker.git
    cd fcat-data-tracker
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## 🔑 Configuration (Secrets)

To access authentication-gated sources (like FRED), you must configure your API keys.

1.  Create a folder named `.streamlit` in the root directory.
2.  Inside it, create a file named `secrets.toml`.
3.  Add your API keys in the following format:

    ```toml
    # .streamlit/secrets.toml
    FRED_API_KEY = "your_actual_api_key_here"
    ```

> **Note:** The `secrets.toml` file is added to `.gitignore` by default to prevent leaking credentials.

## 🏃‍♂️ Running Locally

Execute the following command in your terminal:

```bash
streamlit run app.py
```

The app will open automatically in your default browser at http://localhost:8501.

## ☁️ Deployment
This application is optimized for **Streamlit Community Cloud** or any Dockerized container environment.

**Deploying to Streamlit Cloud**
Push your code to GitHub.

Connect your repository in the Streamlit Cloud dashboard.

**Crucial Step:** Go to the app's **Advanced Settings -> Secrets** and paste the contents of your local `secrets.toml` file there.

## 📂 Project Structure
* `app.py`: Main application logic and UI.

* `requirements.txt`: Python dependencies.

* `.streamlit/secrets.toml`: Local API keys (ignored by Git).

## 🛡️ Troubleshooting
* **403 Forbidden:** The API is likely blocking cloud/script traffic. The app includes logic to attempt browser masquerading, but some sources (like OECD) may require an enterprise API key or IP whitelisting.

* **ReadTimeout:** Institutional APIs (IMF) can be slow. The app handles this by increasing timeout limits, but persistent failures indicate the need for a backend caching server.
