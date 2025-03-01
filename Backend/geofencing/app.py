from flask import Flask, render_template, request, jsonify
import requests
import math
import random
from datetime import datetime, timedelta
import logging
from functools import wraps
import os

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration – ensure your API keys are valid
NEWS_API_KEY = os.getenv('NEWS_API_KEY', '2818e2fcfa204ea7adbbb01059e9b81f')
DISASTER_API_KEY = os.getenv('DISASTER_API_KEY', 'd76ca3581d1482858208f4aca74834132879ae8260157ca56db9545817fab3da')
WEATHER_RETRY_ATTEMPTS = 3

def retry_on_failure(max_attempts=3):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        logging.error(f"Failed after {max_attempts} attempts: {str(e)}")
                        raise
                    logging.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            return None
        return wrapper
    return decorator

def validate_coordinates(lat, lon):
    try:
        lat = float(lat)
        lon = float(lon)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None, None
        return lat, lon
    except (TypeError, ValueError):
        return None, None

def get_destination_point(lat, lon, bearing, distance):
    """Calculate destination point given distance (in km) and bearing."""
    R = 6371.0  # Earth's radius in km
    try:
        bearing_rad = math.radians(bearing)
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        angular_distance = distance / R
        new_lat_rad = math.asin(
            math.sin(lat_rad) * math.cos(angular_distance) +
            math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
        )
        new_lon_rad = lon_rad + math.atan2(
            math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat_rad),
            math.cos(angular_distance) - math.sin(lat_rad) * math.sin(new_lat_rad)
        )
        new_lon_rad = (new_lon_rad + 3 * math.pi) % (2 * math.pi) - math.pi
        return math.degrees(new_lat_rad), math.degrees(new_lon_rad)
    except Exception as e:
        logging.error(f"Error in get_destination_point: {str(e)}")
        return None, None

@app.route('/get_full_weather', methods=['GET'])
@retry_on_failure(WEATHER_RETRY_ATTEMPTS)
def get_full_weather():
    """Get detailed weather for a specific location."""
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    lat, lon = validate_coordinates(lat, lon)
    if lat is None or lon is None:
        return jsonify({"error": "Invalid coordinates provided", "details": "Latitude must be between -90 and 90, longitude between -180 and 180"}), 400
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,relativehumidity_2m,cloudcover,precipitation,uv_index,soil_moisture_0_1cm,windspeed_10m,winddirection_10m,weathercode",
            "daily": "sunrise,sunset,precipitation_sum,temperature_2m_max,temperature_2m_min",
            "current_weather": "true",
            "timezone": "auto"
        }
        response = requests.get("https://api.open-meteo.com/v1/forecast", params=params)
        response.raise_for_status()
        data = response.json()
        current_time_str = datetime.now().strftime("%Y-%m-%dT%H:00")
        if 'hourly' in data and 'time' in data['hourly']:
            try:
                idx = data['hourly']['time'].index(current_time_str)
            except ValueError:
                idx = 0
            data['current_conditions'] = {
                'temperature': data['hourly']['temperature_2m'][idx],
                'humidity': data['hourly']['relativehumidity_2m'][idx] if "relativehumidity_2m" in data['hourly'] else "No data",
                'cloudcover': data['hourly']['cloudcover'][idx] if "cloudcover" in data['hourly'] else "No data",
                'uv_index': data['hourly']['uv_index'][idx] if "uv_index" in data['hourly'] else "No data",
                'soil_moisture': data['hourly'].get('soil_moisture_0_1cm', [None])[idx] or "No data",
                'windspeed': data['hourly']['windspeed_10m'][idx],
                'winddirection': data['hourly']['winddirection_10m'][idx],
                'weathercode': data['hourly']['weathercode'][idx] if "weathercode" in data['hourly'] else None
            }
        else:
            data['current_conditions'] = data.get('current_weather', {})
        return jsonify(data)
    except requests.exceptions.RequestException as e:
        logging.error(f"Weather API error: {str(e)}")
        return jsonify({"error": "Failed to fetch weather data", "details": str(e)}), 503

@app.route('/get_circle_weather', methods=['GET'])
def get_circle_weather():
    """Get weather data for 10 random points around the fixed farm center."""
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    radius = request.args.get('radius', default=200, type=float)
    lat, lon = validate_coordinates(lat, lon)
    if lat is None or lon is None:
        return jsonify({"error": "Invalid coordinates provided"}), 400
    points_weather = []
    num_points = 10
    for _ in range(num_points):
        random_distance = random.uniform(0, radius)
        random_angle = random.uniform(0, 360)
        dest_lat, dest_lon = get_destination_point(lat, lon, random_angle, random_distance)
        if dest_lat is None or dest_lon is None:
            continue
        try:
            params = {
                "latitude": dest_lat,
                "longitude": dest_lon,
                "hourly": "temperature_2m,weathercode,relativehumidity_2m,surface_pressure,soil_moisture_0_1cm,windspeed_10m,uv_index,cloudcover",
                "daily": "temperature_2m_min,temperature_2m_max,sunrise,sunset",
                "current_weather": "true",
                "timezone": "auto"
            }
            response = requests.get("https://api.open-meteo.com/v1/forecast", params=params)
            response.raise_for_status()
            weather_data = response.json()
            if "hourly" in weather_data and "time" in weather_data["hourly"]:
                try:
                    idx = weather_data["hourly"]["time"].index(datetime.now().strftime("%Y-%m-%dT%H:00"))
                except ValueError:
                    idx = 0
                current_data = {
                    "temperature": weather_data["hourly"]["temperature_2m"][idx],
                    "weathercode": weather_data["hourly"]["weathercode"][idx],
                    "relativehumidity": weather_data["hourly"]["relativehumidity_2m"][idx] if "relativehumidity_2m" in weather_data["hourly"] else "No data",
                    "surface_pressure": weather_data["hourly"].get("surface_pressure", [None])[idx] or "No data",
                    "soil_moisture": weather_data["hourly"].get("soil_moisture_0_1cm", [None])[idx] or "No data",
                    "windspeed": weather_data["hourly"]["windspeed_10m"][idx],
                    "uv_index": weather_data["hourly"]["uv_index"][idx] if "uv_index" in weather_data["hourly"] else "No data",
                    "cloudcover": weather_data["hourly"]["cloudcover"][idx] if "cloudcover" in weather_data["hourly"] else "No data"
                }
            else:
                current_data = weather_data.get("current_weather", {})
            processed_data = {
                "location": {
                    "lat": dest_lat,
                    "lon": dest_lon,
                    "random_angle": random_angle,
                    "random_distance": random_distance
                },
                "current_weather": current_data,
                "daily": weather_data.get("daily", {})
            }
            points_weather.append(processed_data)
        except Exception as e:
            logging.error(f"Error fetching circle weather: {str(e)}")
            continue
    if not points_weather:
        return jsonify({"error": "Failed to fetch weather data for points"}), 503
    return jsonify(points_weather)

@app.route('/get_india_disaster_events', methods=['GET'])
def get_india_disaster_events():
    """
    Fetch disaster events in India using the Ambee API.
    Optionally filter by event type using the "disaster_type" query parameter.
    """
    try:
        disaster_filter = request.args.get('disaster_type', '').strip().lower()
        url = "https://api.ambeedata.com/disasters/latest/by-country-code"
        params = {
            "countryCode": "IND",
            "limit": 50,
            "page": 1
        }
        headers = {
            "x-api-key": DISASTER_API_KEY
        }
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        events_data = response.json()  # Contains keys like "message", "hasNextPage", "result", etc.
        if disaster_filter and "result" in events_data:
            filtered = [event for event in events_data["result"]
                        if disaster_filter in (event.get("event_type", "").lower())]
            events_data["result"] = filtered
        return jsonify(events_data)
    except Exception as e:
        logging.error(f"Error fetching disaster events: {str(e)}")
        return jsonify({"error": "Failed to fetch disaster events", "details": str(e)}), 503


@app.route('/get_soil_classification', methods=['GET'])
def get_soil_classification():
    """Fetch soil classification data using SoilGrids API."""
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    lat, lon = validate_coordinates(lat, lon)
    if lat is None or lon is None:
        return jsonify({"error": "Invalid coordinates"}), 400
    try:
        class_url = "https://dev-rest.isric.org/soilgrids/v2.0/classification/query"
        class_params = {
            "lon": str(lon),
            "lat": str(lat),
            "number_classes": "5"
        }
        headers = {"accept": "application/json"}
        response = requests.get(class_url, params=class_params, headers=headers)
        response.raise_for_status()
        class_data = response.json()
        soil_type = class_data.get("wrb_class_name", "Unknown")
        soil_probabilities = class_data.get("wrb_class_probability", [])
        soil_category = classify_soil_category(soil_type)
        return jsonify({
            "soil_type": soil_type,
            "soil_probabilities": soil_probabilities,
            "soil_category": soil_category
        })
    except Exception as e:
        logging.error(f"Soil classification error: {str(e)}")
        return jsonify({"error": "Failed to fetch soil classification", "details": str(e)}), 503

@app.route('/get_soil_properties', methods=['GET'])
def get_soil_properties():
    """Fetch soil properties data using SoilGrids API and map parameters to user-friendly names."""
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    lat, lon = validate_coordinates(lat, lon)
    if lat is None or lon is None:
        return jsonify({"error": "Invalid coordinates"}), 400
    try:
        prop_url = "https://dev-rest.isric.org/soilgrids/v2.0/properties/query"
        prop_params = {
            "lon": str(lon),
            "lat": str(lat),
            "property": [
                "bdod", "cec", "cfvo", "clay", "nitrogen",
                "ocd", "phh2o", "sand", "silt",
                "soc", "wv0010", "wv0033", "wv1500"
            ],
            "depth": "5-15cm",
            "value": "mean"
        }
        headers = {"accept": "application/json"}
        response = requests.get(prop_url, params=prop_params, headers=headers)
        response.raise_for_status()
        prop_data = response.json()
        table_data = []
        PARAMETER_NAMES = {
            "bdod": "Bulk Density",
            "cec": "CEC",
            "cfvo": "Field Capacity",
            "clay": "Clay",
            "nitrogen": "Nitrogen",
            "ocd": "Organic Carbon Density",
            "phh2o": "pH",
            "sand": "Sand",
            "silt": "Silt",
            "soc": "Soil Organic Carbon",
            "wv0010": "Volumetric Water Content (0-10cm)",
            "wv0033": "Volumetric Water Content (10-33cm)",
            "wv1500": "Volumetric Water Content (1500)"
        }
        for layer in prop_data['properties']['layers']:
            parameter = layer['name']
            display_name = PARAMETER_NAMES.get(parameter, parameter)
            value = layer['depths'][0]['values']['mean']
            if parameter in ["wv0010", "wv0033", "wv1500"]:
                final_value = value / 10.0
                unit = layer['unit_measure'].get("target_units", "")
            elif parameter in ["phh2o"]:
                final_value = value / 10.0
                unit = layer['unit_measure'].get("mapped_units", "").replace("*10", "").strip()
            else:
                final_value = value
                unit = layer['unit_measure'].get("mapped_units", "")
            table_data.append([display_name, final_value, unit])
        return jsonify({
            "soil_properties": table_data
        })
    except Exception as e:
        logging.error(f"Soil properties error: {str(e)}")
        return jsonify({"error": "Failed to fetch soil properties", "details": str(e)}), 503

def classify_disaster_type(title, description):
    text = (title + " " + (description or "")).lower()
    disaster_keywords = {
        'tornado': ['tornado'],
        'flood': ['flood', 'flooding'],
        'earthquake': ['earthquake', 'seismic'],
        'wildfire': ['wildfire', 'fire'],
        'cyclone': ['cyclone', 'hurricane', 'typhoon', 'storm']
    }
    for dtype, keywords in disaster_keywords.items():
        if any(keyword in text for keyword in keywords):
            return dtype
    return 'other'

def estimate_severity(title, description):
    text = (title + " " + (description or "")).lower()
    severity_keywords = {
        'high': ['catastrophic', 'devastating', 'emergency', 'evacuate', 'death', 'fatal'],
        'medium': ['severe', 'significant', 'major', 'warning', 'damage'],
        'low': ['minor', 'small', 'limited', 'advisory', 'watch']
    }
    for severity, keywords in severity_keywords.items():
        if any(keyword in text for keyword in keywords):
            return severity
    return 'unknown'

def classify_soil_category(soil_type):
    mapping = {
        "vertisols": "black",
        "cambisols": "red",
        "luvisols": "black",
        "fluvisols": "alluvial",
        "gleysols": "alluvial"
    }
    key = soil_type.lower().strip()
    return mapping.get(key, "unknown")

@app.route('/')
def index():
    return render_template('index.html')

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True)
