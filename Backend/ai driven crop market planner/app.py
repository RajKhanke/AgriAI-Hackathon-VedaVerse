from flask import Flask, render_template, request
import pandas as pd
from math import radians, sin, cos, sqrt, atan2
from geopy.geocoders import Nominatim

app = Flask(__name__)

# Load CSV file (ensure your CSV is in the same directory, e.g., "df1.csv")
df = pd.read_csv('final_data_ai_market.csv')

# Haversine function to calculate the distance (in km) between two points
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# Geocode function to convert location text to lat, lon using geopy
def geocode_location(location_text):
    geolocator = Nominatim(user_agent="agri_market_planner")
    location = geolocator.geocode(location_text)
    if location:
        return location.latitude, location.longitude
    else:
        return None, None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        location_text = request.form.get('location')
        try:
            radius = float(request.form.get('radius'))
            crop = request.form.get('crop')
            quantity = float(request.form.get('quantity'))
        except Exception as e:
            return render_template('index.html', error="Invalid input provided.", crop_options=df['Commodity'].unique().tolist())

        # Convert the text location to coordinates
        lat, lon = geocode_location(location_text)
        if lat is None or lon is None:
            return render_template('index.html', error="Unable to geocode the provided location.", crop_options=df['Commodity'].unique().tolist())

        # Filter CSV data for the selected crop (case-insensitive)
        df_crop = df[df['Commodity'].str.lower() == crop.lower()].copy()

        # Calculate distance from the given location for each market
        df_crop['distance'] = df_crop.apply(
            lambda row: haversine(lat, lon, row['Latitude'], row['Longitude']),
            axis=1
        )

        # Filter markets within the selected radius
        df_filtered = df_crop[df_crop['distance'] <= radius]
        if df_filtered.empty:
            return render_template('index.html', error="No markets found within the selected radius.", crop_options=df['Commodity'].unique().tolist())

        # Compute the average price from the min and max prices
        df_filtered['avg_price'] = (df_filtered['Min_x0020_Price'] + df_filtered['Max_x0020_Price']) / 2.0

        # Compute profit for each market: (Modal Price * quantity) - (6 * distance)
        df_filtered['profit'] = df_filtered['Modal_x0020_Price'] * quantity - 6 * df_filtered['distance']

        # Sort markets by profit descending and select the top one as optimal
        df_sorted = df_filtered.sort_values(by='profit', ascending=False)
        optimal_market = df_sorted.iloc[0]

        # Get additional markets (exclude optimal) – top 3 if available
        if len(df_sorted) > 1:
            other_markets = df_sorted.iloc[1:4].to_dict('records')
        else:
            other_markets = []

        # Calculate total profit (with cost subtracted)
        total_profit = optimal_market['profit']

        # Prepare the result (excluding Grade and Arrival Date as requested)
        result = {
            'state': optimal_market['State'],
            'district': optimal_market['District'],
            'market': optimal_market['Market'],
            'commodity': optimal_market['Commodity'],
            'variety': optimal_market['Variety'],
            'min_price': optimal_market['Min_x0020_Price'],
            'max_price': optimal_market['Max_x0020_Price'],
            'modal_price': optimal_market['Modal_x0020_Price'],
            'latitude': optimal_market['Latitude'],
            'longitude': optimal_market['Longitude'],
            'distance': round(optimal_market['distance'], 2),
            'avg_price': round(optimal_market['avg_price'], 2),
            'profit': round(total_profit, 2)
        }

        # Capture user location info to show on the map and farmer card
        user_location = {
            'latitude': lat,
            'longitude': lon,
            'location_text': location_text,
            'crop': crop,
            'quantity': quantity
        }

        crop_options = df['Commodity'].unique().tolist()

        return render_template('index.html',
                               result=result,
                               user_location=user_location,
                               radius=radius,
                               crop_options=crop_options,
                               other_markets=other_markets)
    else:
        crop_options = df['Commodity'].unique().tolist()
        return render_template('index.html', crop_options=crop_options)

if __name__ == '__main__':
    app.run(debug=True)
