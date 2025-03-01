from flask import Flask, render_template, request, jsonify, Response
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# Internal mapping of crops to pests (for the form)
CROP_TO_PESTS = {
    "Sorgum": ["FallArmyWorm"],
    "Maize": ["FallArmyWorm"],
    "Rice": ["Blast", "GallMidge", "YSB", "PlantHopper", "BlueBeetle", "BacterialLeafBlight"],
    "Cotton": ["Thrips", "Whitefly", "PinkBollworm", "Jassid", "BollRot", "AmericanBollworm"],
    "Soybean": ["Girdlebeetle", "H.armigera", "Semilooper", "Spodoptera", "StemFLy"],
    "Tur": ["Wilt", "Webbed_Leaves", "Pod_damage"],
    "Sugarcane": ["FallArmyGrub", "WhiteGrub"],
    "Gram": ["H.armigera", "Wilt"]
}

# Fixed year options for the form
YEARS = ["2024-25", "2023-24", "2022-23", "2021-22"]

# Map our internal crop names to the external page's crop values.
CROP_MAPPING = {
    "Cotton": "1",
    "Gram": "4",
    "Maize": "7",
    "Rice": "3",
    "Sorghum": "6",
    "Soybean": "2",
    "Sugarcane": "8",
    "Tur": "5",
    "Sorgum": "6"  # Adjust if needed
}

# Map our internal pest names to external page values per crop.
PEST_MAPPING = {
    "Cotton": {
        "FallArmyWorm": "71"
    },
    "Gram": {
        "H.armigera": "72",
        "Wilt": "73"
    },
    "Maize": {
        "FallArmyWorm": "74"
    },
    "Rice": {
        "Blast": "75",
        "GallMidge": "76",
        "YSB": "77",
        "PlantHopper": "78",
        "BlueBeetle": "79",
        "BacterialLeafBlight": "80"
    },
    "Soybean": {
        "Girdlebeetle": "81",
        "H.armigera": "82",
        "Semilooper": "83",
        "Spodoptera": "84",
        "StemFLy": "85"
    },
    "Tur": {
        "Wilt": "86",
        "Webbed_Leaves": "87",
        "Pod_damage": "88"
    },
    "Sugarcane": {
        "FallArmyGrub": "89",
        "WhiteGrub": "90"
    },
    "Sorgum": {
        "FallArmyWorm": "91"
    }
}

# Parameter codes and labels for the final image URL
PARAMS = {
    "Mint": "Min Temperature",
    "Maxt": "Max Temperature",
    "RH": "Relative Humidity",
    "RF": "Rainfall",
    "PR": "Pest Report"
}

@app.route('/')
def index():
    # Read query parameters (if provided)
    crop = request.args.get('crop', '')
    pest = request.args.get('pest', '')
    year = request.args.get('year', '')
    week = request.args.get('week', '')
    param = request.args.get('param', '')

    image_url = ""
    if crop and pest and year and week and param:
        # Build the external image URL (using HTTP)
        base_url = f"http://www.icar-crida.res.in:8080/naip/gisimages/{crop}/{year}/{pest}_"
        external_image_url = f"{base_url}{param}{week}.jpg"
        # Instead of using the external HTTP URL directly, we build our proxy URL
        image_url = f"/proxy-image?url={external_image_url}"

    return render_template('index.html',
                           crops=list(CROP_TO_PESTS.keys()),
                           crop_to_pests=CROP_TO_PESTS,
                           years=YEARS,
                           params=PARAMS,
                           selected_crop=crop,
                           selected_pest=pest,
                           selected_year=year,
                           selected_week=week,
                           selected_param=param,
                           image_url=image_url)

@app.route('/fetch_weeks')
def fetch_weeks():
    crop = request.args.get('crop', '')
    pest = request.args.get('pest', '')
    year = request.args.get('year', '')

    ext_crop = CROP_MAPPING.get(crop, '')
    ext_pest = ""
    if crop in PEST_MAPPING and pest in PEST_MAPPING[crop]:
        ext_pest = PEST_MAPPING[crop][pest]

    payload = {
        "country": ext_crop,
        "city": ext_pest,
        "sowing": year
    }

    weeks = []
    try:
        response = requests.get("http://www.icar-crida.res.in:8080/naip/gismaps.jsp", params=payload, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        week_options = soup.select('select[name="week"] option')
        weeks = [opt.get('value') for opt in week_options if opt.get('value') and "Select" not in opt.get('value')]
        if not weeks:
            weeks = [str(i) for i in range(1, 53)]
    except Exception as e:
        weeks = [str(i) for i in range(1, 53)]
    return jsonify({"weeks": weeks})

@app.route('/proxy-image')
def proxy_image():
    # Get the external URL from the query parameter
    external_url = request.args.get('url')
    if not external_url:
        return "Missing URL", 400

    try:
        # Fetch the image from the external server
        resp = requests.get(external_url, timeout=10)
        return Response(resp.content, mimetype=resp.headers.get('Content-Type', 'image/jpeg'))
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(debug=True)
