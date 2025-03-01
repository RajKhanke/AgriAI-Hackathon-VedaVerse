from flask import Flask, render_template, request, redirect, url_for, flash
import folium
from folium.plugins import Draw
from geopy.geocoders import ArcGIS
from shapely.geometry import shape
from shapely.ops import transform
import pyproj
from google import genai
import json

app = Flask(__name__)
app.secret_key = 'a44f0e299a2c3a4b8f1f58c7de34edac'  # Replace with your own secret key

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        place = request.form.get('place')
        if not place:
            flash("Please enter a location.", "error")
            return redirect(url_for('index'))

        geolocator = ArcGIS()
        try:
            location = geolocator.geocode(place, timeout=10)
        except Exception:
            flash("Geocoding service is currently unavailable. Please try again later.", "error")
            return redirect(url_for('index'))

        if not location:
            flash("Location not found. Please try a different search term.", "error")
            return redirect(url_for('index'))

        lat, lon = location.latitude, location.longitude

        # Create a Folium map centered on the location using Esri satellite imagery.
        m = folium.Map(location=[lat, lon], zoom_start=14, tiles='Esri.WorldImagery', name='Satellite')
        # Add an overlay labels layer from CartoDB.
        folium.TileLayer(
            tiles="http://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}.png",
            attr='CartoDB',
            name='Labels',
            overlay=True,
            control=True
        ).add_to(m)
        folium.LayerControl().add_to(m)
        # Add the Draw plugin for polygon drawing.
        draw = Draw(
            export=True,
            draw_options={
                'polyline': False,
                'rectangle': False,
                'circle': False,
                'marker': False,
                'circlemarker': False,
                'polygon': True,
            },
            edit_options={'edit': True}
        )
        draw.add_to(m)
        # Render the map to HTML.
        map_html = m._repr_html_()

        return render_template('index.html', location=location, map_html=map_html)
    return render_template('index.html', location=None)

@app.route('/recommend', methods=['POST'])
def recommend():
    polygon_geojson_str = request.form.get('polygon_geojson')
    address = request.form.get('address')
    lat = request.form.get('lat')
    lon = request.form.get('lon')

    if not (polygon_geojson_str and address and lat and lon):
        flash("Missing data. Ensure you have drawn a polygon on the map.", "error")
        return redirect(url_for('index'))

    try:
        polygon_geojson = json.loads(polygon_geojson_str)
    except Exception:
        flash("Invalid polygon data.", "error")
        return redirect(url_for('index'))

    # Convert the GeoJSON polygon into a shapely shape and calculate the area.
    try:
        polygon_shape = shape(polygon_geojson)
    except Exception:
        flash("Error processing polygon geometry.", "error")
        return redirect(url_for('index'))

    # Reproject from WGS84 to EPSG:3857 for accurate area calculation.
    project = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
    projected_polygon = transform(project, polygon_shape)
    area_sqm = projected_polygon.area
    area_acres = area_sqm / 4046.85642

    # Build the prompt using the farm details.
    prompt = (
        f"Farm location: {address}\n"
        f"Coordinates: ({float(lat):.4f}, {float(lon):.4f})\n"
        f"Farm area: {area_sqm:.2f} square meters ({area_acres:.2f} acres)\n"
        f"Farm polygon data (GeoJSON): {polygon_geojson}\n\n"
        "i wnt the out put formated heading then the recommended crops in table with ratio and then the justification. "
        "Based on the above details, produce a formal analysis report that recommends the top three crops best suited for this farm. "
        "not always top 3 based on the farm sie you can adjust means is farm is small then fewer crops and like that. "
        "i want at the top the recommendations and their ratio. For each crop, include the recommended cultivation ratio (in percentage) and a concise, data-driven reason for selecting it, "
        "taking into account soil quality, local weather conditions, market trends, and pest risk assessments. "
        "dont recommend fruits genrally. The output should be formatted with clear headings and bullet points, and include additional contextual details to simulate a comprehensive analysis. "
        "Do not include any conversational language or references to any language model."
    )

    # Create the Gemini client using your API key.
    client = genai.Client(api_key="AIzaSyDkiYr-eSkqIXpZ1fHlik_YFsFtfQoFi0w")
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    report = response.text

    return render_template('report.html', report=report)

if __name__ == '__main__':
    app.run(debug=True)
