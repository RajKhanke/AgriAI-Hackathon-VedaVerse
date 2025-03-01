import requests
import json
from flask import Flask, render_template, request, jsonify, Response
from google import genai
import markdown

app = Flask(__name__)

# Replace with your actual Gemini API key
client = genai.Client(api_key="AIzaSyBtXV2xJbrWVV57B5RWy_meKXOA59HFMeY")
def validate_coordinates(lat, lon):
    """Validate and convert latitude and longitude to float."""
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_weather_data', methods=['GET'])
def get_weather_data():
    """
    Fetch weather data using Open-Meteo's forecast endpoint:
      - daily: temperature_2m_max (max_temp), temperature_2m_min (min_temp), precipitation_sum (rain)
      - hourly: relative_humidity_2m, soil_moisture_3_to_9cm, cloudcover, windspeed_10m
      - current_weather: for current temperature and wind speed
    """
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    lat, lon = validate_coordinates(lat, lon)
    if lat is None or lon is None:
        return jsonify({"error": "Invalid coordinates"}), 400

    try:
        forecast_url = "https://api.open-meteo.com/v1/forecast"
        forecast_params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "hourly": "relative_humidity_2m,soil_moisture_3_to_9cm,cloudcover,windspeed_10m",
            "timezone": "auto"
        }
        resp = requests.get(forecast_url, params=forecast_params)
        resp.raise_for_status()
        data = resp.json()

        daily   = data.get("daily", {})
        hourly  = data.get("hourly", {})
        current = data.get("current_weather", {})

        # Daily data
        max_temp = daily.get("temperature_2m_max", [None])[0]
        min_temp = daily.get("temperature_2m_min", [None])[0]
        rain     = daily.get("precipitation_sum", [None])[0]

        # Hourly data (averages)
        humidity_list     = hourly.get("relative_humidity_2m", [])
        soil_list         = hourly.get("soil_moisture_3_to_9cm", [])
        cloud_list        = hourly.get("cloudcover", [])
        wind_list         = hourly.get("windspeed_10m", [])

        avg_humidity      = sum(humidity_list)/len(humidity_list) if humidity_list else None
        avg_soil_moisture = sum(soil_list)/len(soil_list) if soil_list else None
        avg_cloud_cover   = sum(cloud_list)/len(cloud_list) if cloud_list else None

        # Current weather
        current_temp = current.get("temperature")
        wind_speed   = current.get("windspeed")

        weather = {
            "max_temp": max_temp,
            "min_temp": min_temp,
            "rainfall": rain,
            "humidity": avg_humidity,
            "soil_moisture": avg_soil_moisture,
            "current_temp": current_temp,
            "wind_speed": wind_speed,
            "cloud_cover": avg_cloud_cover
        }
        return jsonify(weather)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_soil_properties', methods=['GET'])
def get_soil_properties():
    """Fetch soil properties using SoilGrids API and map to user-friendly names."""
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    lat, lon = validate_coordinates(lat, lon)
    if lat is None or lon is None:
        return jsonify({"error": "Invalid coordinates"}), 400

    try:
        prop_url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
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
        for layer in prop_data.get('properties', {}).get('layers', []):
            parameter = layer.get('name')
            display_name = PARAMETER_NAMES.get(parameter, parameter)
            value = layer.get('depths', [{}])[0].get('values', {}).get('mean')
            if value is None:
                continue
            if parameter in ["wv0010", "wv0033", "wv1500"]:
                final_value = value / 10.0
                unit = layer.get('unit_measure', {}).get("target_units", "")
            elif parameter in ["phh2o"]:
                final_value = value / 10.0
                unit = layer.get('unit_measure', {}).get("mapped_units", "").replace("*10", "").strip()
            else:
                final_value = value
                unit = layer.get('unit_measure', {}).get("mapped_units", "")
            table_data.append([display_name, final_value, unit])

        return jsonify({"soil_properties": table_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def call_gemini_api(input_data):
    language = input_data.get('language', 'English')
    prompt = f"""
Create a visually appealing, farmer-friendly pest outbreak report in Markdown with the following:
1. A large, centered heading: "Pest Outbreak Dashboard Report".
2. A short paragraph indicating location (latitude: {input_data.get('latitude')}, longitude: {input_data.get('longitude')}) with the location derived from lat,long.
3. Several subheadings (e.g., "Agricultural Inputs", "Pest Outbreak Analysis", "Best Agricultural Practices", "Insights") with short paragraphs.
4. A colorfully styled table (no raw CSS code blocks) with:
   - Pest Name
   - Predicted Outbreak Month(s)
   - Severity
   - Potential Damage by Pests
   - Precautionary Measures against damages
5. Provide bullet points for best practices.
6. Use a friendly color scheme with subtle hovers or highlights for rows, and consistent fonts.
7. Avoid printing any raw code blocks.
8. Incorporate the weather, soil, and agricultural data (like sowing date, irrigation method) into the narrative without listing them as raw parameters.
9. Do not give off-topic instructions—only pest outbreak report instructions.
10. Important details from the user:
   - Crop Type: {input_data.get('crop_type')}
   - Sowing Date: {input_data.get('sowing_date')}
   - Harvest Date: {input_data.get('harvest_date')}
   - Current Growth Stage: {input_data.get('growth_stage')}
   - Irrigation Frequency: {input_data.get('irrigation_freq')}
   - Irrigation Method: {input_data.get('irrigation_method')}
   - Soil Type: {input_data.get('soil_type')}
   - Max Temp: {input_data.get('max_temp')}
   - Min Temp: {input_data.get('min_temp')}
   - Current Temp: {input_data.get('current_temp')}
   - Humidity: {input_data.get('humidity')}
   - Rainfall: {input_data.get('rain')}
   - Soil Moisture: {input_data.get('soil_moisture')}
   - Wind Speed: {input_data.get('wind_speed')}
   - Cloud Cover: {input_data.get('cloud_cover')}
11. Order the content as follows:
    - First, display the title along with the derived location (e.g., Nagpur, India).
    - Next, show the agricultural input parameters analysis.
    - Then, present the pest table.
    - Followed by pest avoidance practices in-depth (5-6 bullet points).
    - Finally, include specific agricultural best practices based on the inputs.
12. Use short, easily understandable sentences suitable for farmers, with large fonts and colorful subheadings.
13. Do not include long paragraphs; keep the language simple and the report well-formatted.
14. Highlight important points (such as key damages, recommendations, pest names, key seasons) with yellow highlighters (only highlight key points, not the text).
Please provide the complete report in {language} language only.
"""
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return response.text


@app.route('/predict', methods=['POST'])
def predict():
    form_data = request.form.to_dict()
    report_md = call_gemini_api(form_data)

    # Convert raw markdown to HTML
    report_html = markdown.markdown(report_md)

    # Inject advanced, colorful styling into the final HTML
    html_output = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Pest Outbreak Dashboard Report</title>
  <!-- Tailwind for utility classes -->
  <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
  <style>
    /* Overall page background with a subtle gradient */
    body {{
      margin: 0;
      padding: 2rem;
      background: linear-gradient(120deg, #f7f7f7 0%, #e3f2fd 100%);
      font-family: 'Segoe UI', Tahoma, sans-serif;
    }}
    .report-container {{
      max-width: 1000px;
      margin: 0 auto;
      background-color: #ffffff;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.1);
      padding: 2rem;
      transition: transform 0.3s ease, box-shadow 0.3s ease;
    }}
    .report-container:hover {{
      transform: translateY(-4px);
      box-shadow: 0 12px 24px rgba(0,0,0,0.15);
    }}
    /* Gradient heading for H1 */
    .report-container h1 {{
      text-align: center;
      font-size: 2rem;
      margin-bottom: 1.5rem;
      color: #ffffff;
      background: linear-gradient(to right, #81c784, #388e3c);
      padding: 1rem;
      border-radius: 6px;
      box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
    }}
    /* Secondary headings (H2, H3) */
    .report-container h2, 
    .report-container h3 {{
      margin-top: 1.5rem;
      margin-bottom: 0.75rem;
      color: #2c3e50;
      text-align: left;
    }}
    /* Paragraphs */
    .report-container p {{
      margin-bottom: 1rem;
      color: #555555;
      text-align: justify;
      line-height: 1.6;
    }}
    /* Lists */
    .report-container ul, 
    .report-container ol {{
      margin-left: 1.5rem;
      margin-bottom: 1rem;
      color: #555555;
    }}
    /* Table styling */
    .report-container table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1.5rem 0;
    }}
    .report-container thead tr {{
      background: linear-gradient(to right, #81c784, #388e3c);
      color: #ffffff;
    }}
    .report-container th, 
    .report-container td {{
      border: 1px solid #ddd;
      padding: 12px 15px;
      text-align: left;
      transition: background-color 0.2s ease;
    }}
    .report-container tbody tr:hover {{
      background-color: #f9f9f9;
    }}
    /* Responsive table for smaller screens */
    @media (max-width: 768px) {{
      .report-container table, 
      .report-container thead, 
      .report-container tbody, 
      .report-container th, 
      .report-container td, 
      .report-container tr {{
        display: block;
        width: 100%;
      }}
      .report-container thead tr {{
        display: none;
      }}
      .report-container td {{
        border: none;
        border-bottom: 1px solid #ddd;
        position: relative;
        padding-left: 50%;
        text-align: left;
      }}
      .report-container td:before {{
        content: attr(data-label);
        position: absolute;
        left: 15px;
        font-weight: bold;
      }}
    }}
  </style>
</head>
<body>
  <div class="report-container">
    {report_html}
  </div>
</body>
</html>"""
    return Response(html_output, mimetype="text/html")


if __name__ == '__main__':
    app.run(debug=True)