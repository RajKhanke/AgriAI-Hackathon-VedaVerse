from flask import Flask, render_template, request, jsonify
import requests
import pandas as pd
from datetime import datetime

app = Flask(__name__)

# Function to fetch data from the API
def fetch_market_data(state=None, district=None, market=None, commodity=None):
    api_key = "579b464db66ec23bdd000001189bbb99e979428764bdbe8fdd44ebb7"

    base_url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    params = {
        "api-key": api_key,
        "format": "json",
        "limit": 15000,
    }

    if state:
        params["filters[state.keyword]"] = state
    if district:
        params["filters[district.keyword]"] = district
    if market:
        params["filters[market.keyword]"] = market
    if commodity:
        params["filters[commodity.keyword]"] = commodity

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()
        records = data.get("records", [])
        df = pd.DataFrame(records)
        return df
    else:
        return pd.DataFrame()

# Fetch initial state data
@app.route("/")
def index():
    # Fetch distinct states for dropdown
    market_data = fetch_market_data()
    states = market_data['state'].dropna().unique().tolist()
    today = datetime.today().strftime('%Y-%m-%d')
    return render_template('index.html', states=states, today=today)

# Handle AJAX requests to filter market data
@app.route("/filter_data", methods=["POST"])
def filter_data():
    state = request.form.get("state")
    district = request.form.get("district")
    market = request.form.get("market")
    commodity = request.form.get("commodity")

    # Fetch filtered data
    filtered_data = fetch_market_data(state, district, market, commodity)

    # Generate HTML for the filtered table
    table_html = ""
    for _, row in filtered_data.iterrows():
        table_html += f"""
            <tr>
                <td>{row['state']}</td>
                <td>{row['district']}</td>
                <td>{row['market']}</td>
                <td>{row['commodity']}</td>
                <td>{row['variety']}</td>
                <td>{row['grade']}</td>
                <td>{row['arrival_date']}</td>
                <td>{row['min_price']}</td>
                <td>{row['max_price']}</td>
                <td>{row['modal_price']}</td>
            </tr>
        """

    # Get top 5 cheapest crops by modal price
    cheapest_crops = filtered_data.sort_values("modal_price", ascending=True).head(5)
    cheapest_html = ""
    for _, row in cheapest_crops.iterrows():
        cheapest_html += f"""
            <tr>
                <td>{row['commodity']}</td>
                <td>{row['modal_price']}</td>
            </tr>
        """

    # Get top 5 costliest crops by modal price
    costliest_crops = filtered_data.sort_values("modal_price", ascending=False).head(5)
    costliest_html = ""
    for _, row in costliest_crops.iterrows():
        costliest_html += f"""
            <tr>
                <td>{row['commodity']}</td>
                <td>{row['modal_price']}</td>
            </tr>
        """

    return jsonify({
        "market_html": table_html,
        "cheapest_html": cheapest_html,
        "costliest_html": costliest_html
    })

# Handle AJAX requests for dropdown filtering
@app.route("/get_districts", methods=["POST"])
def get_districts():
    state = request.form.get("state")
    market_data = fetch_market_data(state=state)
    districts = market_data["district"].dropna().unique().tolist()
    return jsonify(districts)

@app.route("/get_markets", methods=["POST"])
def get_markets():
    district = request.form.get("district")
    market_data = fetch_market_data(district=district)
    markets = market_data["market"].dropna().unique().tolist()
    return jsonify(markets)

@app.route("/get_commodities", methods=["POST"])
def get_commodities():
    market = request.form.get("market")
    market_data = fetch_market_data(market=market)
    commodities = market_data["commodity"].dropna().unique().tolist()
    return jsonify(commodities)

if __name__ == "__main__":
    app.run(debug=True)
